from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from services.kite_api_service import kite_api_service


def _nearest_multiple(val: float, base: int) -> int:
    try:
        return int(round(float(val) / base) * base)
    except Exception:
        return 0


def _ceil_to_multiple(val: float, base: int) -> int:
    try:
        v = float(val)
        m = int(base)
        q = int(v // m)
        return (q if v % m == 0 else q + 1) * m
    except Exception:
        return 0


def _floor_to_multiple(val: float, base: int) -> int:
    try:
        v = float(val)
        m = int(base)
        return int(v // m) * m
    except Exception:
        return 0


class AdditionalSharpProService:
    """Compute Additional Sharp Pro data for any symbol.

    Uses previous-day spot (close) and the option chain enriched with previous-day
    per-option OHLC to compute SMD KEY BUY values for ATM/ITM/OTM bases and steps.
    """

    def _prev_day_spot(self, symbol: str) -> float:
        history = kite_api_service.get_recent_daily_history(symbol, 2) or []
        if len(history) >= 2:
            try:
                return float(history[-2].get('close') or 0)
            except Exception:
                return 0.0
        # Fall back to reference price from quote if no history
        q = kite_api_service.get_spot_price(symbol) or {}
        try:
            return float(q.get('previous_close') or q.get('spot_price') or 0)
        except Exception:
            return 0.0

    def _pick_nearest_expiry(self, symbol: str) -> Optional[str]:
        try:
            expiries = kite_api_service.get_expiry_dates(symbol) or []
            return expiries[0] if expiries else None
        except Exception:
            return None

    def _get_prev_close_for(self, chain_rows: List[Dict[str, Any]], strike: float) -> Tuple[Optional[float], Optional[float]]:
        """Return (ce_prev_close, pe_prev_close) for a given strike if present."""
        for r in chain_rows:
            try:
                if float(r.get('strike_price')) == float(strike):
                    return (
                        r.get('ce_prev_close') if r.get('ce_prev_close') is not None else r.get('ce_close'),
                        r.get('pe_prev_close') if r.get('pe_prev_close') is not None else r.get('pe_close'),
                    )
            except Exception:
                continue
        return (None, None)

    def compute(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        spot_prev = self._prev_day_spot(symbol)
        # Baselines
        atm50 = _nearest_multiple(spot_prev, 50)
        atm100 = _nearest_multiple(spot_prev, 100)
        # ITM bases: CE uses lower strikes (<= spot), PE uses higher strikes (>= spot)
        itm_call_base = _floor_to_multiple(spot_prev, 50)
        itm_put_base = _ceil_to_multiple(spot_prev, 50)
        # OTM bases: opposite sides
        otm_call_base = _ceil_to_multiple(spot_prev, 50)
        otm_put_base = _floor_to_multiple(spot_prev, 50)

        ex = expiry or self._pick_nearest_expiry(symbol)
        chain = kite_api_service.get_option_chain(symbol, ex)
        rows = chain.get('option_chain', []) if isinstance(chain, dict) else []

        def smd_for_strike(s: float) -> Dict[str, Any]:
            ce_c, pe_c = self._get_prev_close_for(rows, s)
            smd = None
            try:
                if ce_c is not None and pe_c is not None:
                    smd = (float(ce_c) + float(pe_c)) / 2.0
            except Exception:
                smd = None
            return {
                'strike': s,
                'ce_prev_close': ce_c,
                'pe_prev_close': pe_c,
                'smd_key_buy': smd,
            }

        payload = {
            'symbol': symbol,
            'expiry': ex,
            'previous_day_spot': spot_prev,
            'atm': {
                'step50': smd_for_strike(atm50),
                'step100': smd_for_strike(atm100),
            },
            'itm': {
                'call': {
                    'base': smd_for_strike(itm_call_base),
                    'step1': smd_for_strike(itm_call_base + 50),
                    'step2': smd_for_strike(itm_call_base + 100),
                    'five_strikes': [smd_for_strike(itm_call_base - 50 * i) for i in reversed(range(0, 5))],
                },
                'put': {
                    'base': smd_for_strike(itm_put_base),
                    'step1': smd_for_strike(itm_put_base - 50),
                    'step2': smd_for_strike(itm_put_base - 100),
                    'five_strikes': [smd_for_strike(itm_put_base + 50 * i) for i in range(0, 5)],
                },
            },
            'otm': {
                'call': {
                    'base': smd_for_strike(otm_call_base),
                    'step1': smd_for_strike(otm_call_base + 50),
                    'step2': smd_for_strike(otm_call_base + 100),
                    'five_strikes': [smd_for_strike(otm_call_base + 50 * i) for i in range(0, 5)],
                },
                'put': {
                    'base': smd_for_strike(otm_put_base),
                    'step1': smd_for_strike(otm_put_base - 50),
                    'step2': smd_for_strike(otm_put_base - 100),
                    'five_strikes': [smd_for_strike(otm_put_base - 50 * i) for i in range(0, 5)],
                },
            },
            'timestamp': datetime.utcnow().isoformat(),
        }

        return payload


additional_sharp_pro_service = AdditionalSharpProService()
