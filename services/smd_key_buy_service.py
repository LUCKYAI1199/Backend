from datetime import datetime, timedelta
from typing import Dict, Optional

from services.kite_api_service import kite_api_service
from database import get_session, engine, Base
from models import SmdKeyBuy


class SmdKeyBuyService:
    def __init__(self):
        # Ensure tables
        Base.metadata.create_all(bind=engine)

    def _round_to_atm(self, spot: float, symbol: str) -> float:
        # Basic step rules; can be refined per symbol
        step = 50 if symbol in ['NIFTY', 'FINNIFTY', 'MIDCPNIFTY'] else 100
        if symbol == 'BANKNIFTY':
            step = 100
        return round(spot / step) * step

    def _otm_strikes(self, atm: float, step: int = 100) -> tuple[float, float]:
        return atm + step, atm - step

    def _derive_interval(self, strikes: list[float]) -> int:
        try:
            diffs = sorted({ round(abs(b - a)) for a, b in zip(strikes[:-1], strikes[1:]) if b > a })
            iv = int(diffs[0]) if diffs else 50
            return iv if iv > 0 else 50
        except Exception:
            return 50

    def _nearest_strike(self, strikes: list[float], target: float) -> float:
        if not strikes:
            return target
        return min(strikes, key=lambda s: abs(s - target))

    def _prev_close_for(self, row: dict, side: str) -> float:
        if not isinstance(row, dict):
            return 0.0
        if side == 'CE':
            val = row.get('ce_prev_close')
            return float(val or 0.0)
        else:
            val = row.get('pe_prev_close')
            return float(val or 0.0)

    def _get_option_close(self, symbol: str, expiry: Optional[str], strike: float, opt_type: str) -> float:
        oc = kite_api_service.get_option_chain(symbol, expiry)
        for row in oc.get('option_chain', []):
            if float(row.get('strike_price')) == float(strike):
                if opt_type == 'CE':
                    return row.get('ce_close') or row.get('ce_c') or row.get('ce_ltp') or row.get('ce_last_price') or 0.0
                else:
                    return row.get('pe_close') or row.get('pe_c') or row.get('pe_ltp') or row.get('pe_last_price') or 0.0
        return 0.0

    def calculate_current(self, symbol: str, expiry: Optional[str] = None, market: str = 'NSE') -> Dict:
        # Spot
        spot_info = kite_api_service.get_spot_price(symbol)
        spot = float(spot_info.get('spot_price') or 0)
        atm = self._round_to_atm(spot, symbol)
        # Strikes
        call_strike, put_strike = self._otm_strikes(atm, 100)
        # Close prices
        ce_close = float(self._get_option_close(symbol, expiry, call_strike, 'CE') or 0)
        pe_close = float(self._get_option_close(symbol, expiry, put_strike, 'PE') or 0)
        smd_val = (ce_close + pe_close) / 2 if (ce_close or pe_close) else 0.0
        return {
            'symbol': symbol,
            'market': market,
            'spot_price': spot,
            'atm_strike': atm,
            'otm_call_strike': call_strike,
            'otm_put_strike': put_strike,
            'otm_call_close': ce_close,
            'otm_put_close': pe_close,
            'smd_key_buy': smd_val,
            'timestamp': datetime.utcnow().isoformat()
        }

    def calculate_prevday(self, symbol: str, expiry: Optional[str] = None, market: str = 'NSE') -> Dict:
        # Previous-day underlying close
        hist = kite_api_service.get_recent_daily_history(symbol, 2)
        prev_close = 0.0
        try:
            if hist and len(hist) >= 2:
                prev_close = float(hist[-2].get('close') or 0.0)
        except Exception:
            prev_close = 0.0

        # Option chain (all strikes) to determine available strikes and interval
        chain = kite_api_service.get_option_chain(symbol, expiry, include_all_strikes=True)
        option_rows = chain.get('option_chain', []) if isinstance(chain, dict) else []
        strike_to_row = {
            float(r.get('strike_price')): r
            for r in option_rows
            if r.get('strike_price') is not None
        }
        strikes = sorted(strike_to_row.keys())
        interval = self._derive_interval(strikes)

        # Determine ATM from previous-day close using nearest available strike
        fallback_atm = strikes[len(strikes) // 2] if strikes else 0.0
        atm = self._nearest_strike(strikes, prev_close if prev_close > 0 else fallback_atm)

        # OTM strikes: previous-day basis at ±100 from ATM (snap to nearest available if gaps)
        step = 100
        call_target = atm + step
        put_target = atm - step
        otm_call_strike = self._nearest_strike(strikes, call_target)
        otm_put_strike = self._nearest_strike(strikes, put_target)

        ce_row = strike_to_row.get(otm_call_strike, {})
        pe_row = strike_to_row.get(otm_put_strike, {})
        ce_close = self._prev_close_for(ce_row, 'CE')
        pe_close = self._prev_close_for(pe_row, 'PE')
        smd_val = (ce_close + pe_close) / 2 if (ce_close or pe_close) else 0.0

        return {
            'symbol': symbol,
            'market': market,
            'spot_price': prev_close,  # previous-day spot close
            'atm_strike': atm,
            'strike_interval': interval,
            'otm_call_strike': otm_call_strike,
            'otm_put_strike': otm_put_strike,
            'otm_call_close': ce_close,
            'otm_put_close': pe_close,
            'smd_key_buy': smd_val,
            'timestamp': datetime.utcnow().isoformat()
        }

    def persist_snapshot(self, data: Dict) -> int:
        session = get_session()
        try:
            rec = SmdKeyBuy(
                symbol=data['symbol'],
                market=data.get('market', 'NSE'),
                spot_price=data['spot_price'],
                atm_strike=data['atm_strike'],
                otm_call_strike=data['otm_call_strike'],
                otm_put_strike=data['otm_put_strike'],
                otm_call_close=data['otm_call_close'],
                otm_put_close=data['otm_put_close'],
                smd_key_buy=data['smd_key_buy'],
            )
            session.add(rec)
            session.commit()
            return rec.id
        finally:
            session.close()

    def fetch_recent(self, within_hours: int = 24) -> Dict[str, list]:
        cutoff = datetime.utcnow() - timedelta(hours=within_hours)
        session = get_session()
        try:
            rows = session.query(SmdKeyBuy).filter(SmdKeyBuy.created_at >= cutoff).order_by(SmdKeyBuy.created_at.desc()).all()
            return {
                'count': len(rows),
                'items': [
                    {
                        'id': r.id,
                        'symbol': r.symbol,
                        'market': r.market,
                        'spot_price': r.spot_price,
                        'atm_strike': r.atm_strike,
                        'otm_call_strike': r.otm_call_strike,
                        'otm_put_strike': r.otm_put_strike,
                        'otm_call_close': r.otm_call_close,
                        'otm_put_close': r.otm_put_close,
                        'smd_key_buy': r.smd_key_buy,
                        'created_at': r.created_at.isoformat(),
                    } for r in rows
                ]
            }
        finally:
            session.close()

    def delete_older_than(self, hours: int = 24):
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        session = get_session()
        try:
            session.query(SmdKeyBuy).filter(SmdKeyBuy.created_at < cutoff).delete()
            session.commit()
        finally:
            session.close()
