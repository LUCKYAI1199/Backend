import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

_state = {
    'running': False,
    'hits_by_date': {},  # date -> { id -> hit }
}


def _date_key(dt: datetime = None) -> str:
    dt = dt or datetime.utcnow() + timedelta(hours=5, minutes=30)
    return dt.strftime('%Y-%m-%d')


def _ensure_date_bucket(date_key: str):
    if date_key not in _state['hits_by_date']:
        _state['hits_by_date'][date_key] = {}


def _record_hit(hit: Dict[str, Any]):
    date_key = _date_key()
    _ensure_date_bucket(date_key)
    bucket = _state['hits_by_date'][date_key]
    if hit['id'] not in bucket:
        bucket[hit['id']] = hit
    return bucket[hit['id']]


def _cleanup_old_days(retain_days: int = 2):
    # Keep last N days only
    keys = list(_state['hits_by_date'].keys())
    keys.sort()
    while len(keys) > retain_days:
        k = keys.pop(0)
        _state['hits_by_date'].pop(k, None)


def get_today_hits() -> List[Dict[str, Any]]:
    date_key = _date_key()
    bucket = _state['hits_by_date'].get(date_key, {})
    return list(bucket.values())


def start_signal_broadcaster(app):
    if _state['running']:
        return
    _state['running'] = True

    logger = app.logger
    socketio = app.socketio
    option_service = app.option_service

    TICK_SECS = 10
    REFRESH_THRESH_SECS = 15 * 60

    def _calc_thresholds_for_symbol(sym: str):
        """Compute Additional Sharp Pro thresholds (previous-day based) inline.
        Returns dict with atm_pair, itm_steps[3], otm_steps[3]."""
        try:
            from services.kite_api_service import kite_api_service
            # 1) prev day close of underlying
            hist = kite_api_service.get_recent_daily_history(sym, 2)
            if not hist or len(hist) < 2:
                return None
            prev_close = float(hist[-2].get('close') or 0)
            if prev_close <= 0:
                return None
            # 2) option chain with all strikes
            chain = kite_api_service.get_option_chain(sym, None, include_all_strikes=True)
            rows = (chain or {}).get('option_chain') or []
            if not rows:
                return None
            strike_to_row = { float(r.get('strike_price')): r for r in rows if r.get('strike_price') is not None }
            strikes = sorted(strike_to_row.keys())
            if not strikes:
                return None
            diffs = sorted({ round(abs(b - a)) for a,b in zip(strikes[:-1], strikes[1:]) if b > a })
            interval = int(diffs[0]) if diffs else 50
            if interval <= 0:
                interval = 50
            # nearest strike helper
            def nearest(x: float) -> float:
                return min(strikes, key=lambda s: abs(s - x))
            atm = nearest(prev_close)
            # helper: prev close for CE/PE
            def prev_close_for(row: dict, side: str) -> float:
                if not isinstance(row, dict):
                    return 0.0
                if side == 'CE':
                    val = row.get('ce_prev_close')
                    if val is None:
                        val = row.get('ce_close') or row.get('ce_ltp')
                    return float(val or 0)
                else:
                    val = row.get('pe_prev_close')
                    if val is None:
                        val = row.get('pe_close') or row.get('pe_ltp')
                    return float(val or 0)
            # ATM pair smd
            atm_row = strike_to_row.get(float(atm))
            atm_ce = prev_close_for(atm_row, 'CE')
            atm_pe = prev_close_for(atm_row, 'PE')
            atm_smd = round(((atm_ce or 0) + (atm_pe or 0)) / 2.0, 2)

            def build_steps(kind: str, count: int = 12):
                steps = []
                for n in range(1, count+1):
                    if kind == 'ITM':
                        ce_strike = atm - n * interval
                        pe_strike = atm + n * interval
                    else:  # OTM
                        ce_strike = atm + n * interval
                        pe_strike = atm - n * interval
                    ce_s = nearest(ce_strike)
                    pe_s = nearest(pe_strike)
                    ce_row = strike_to_row.get(float(ce_s))
                    pe_row = strike_to_row.get(float(pe_s))
                    ce_pc = prev_close_for(ce_row, 'CE')
                    pe_pc = prev_close_for(pe_row, 'PE')
                    smd_val = round(((ce_pc or 0) + (pe_pc or 0)) / 2.0, 2)
                    steps.append({
                        'step': n,
                        'ce_strike': ce_s,
                        'pe_strike': pe_s,
                        'ce_prev_close': ce_pc,
                        'pe_prev_close': pe_pc,
                        'smd': smd_val,
                    })
                return steps

            # Build more ITM steps (use larger count but unique pairs only)
            raw_itm = build_steps('ITM')
            itm = []
            seen_pairs = set()
            for s in raw_itm:
                key = (s['ce_strike'], s['pe_strike'])
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                itm.append(s)
            # OTM not used in TP mapping per requirement but kept for completeness
            otm = build_steps('OTM')
            return {
                'atm_pair': { 'strike': atm, 'smd': atm_smd, 'ce_prev_close': atm_ce, 'pe_prev_close': atm_pe },
                'itm_steps': itm,
                'otm_steps': otm,
                'strike_interval': interval,
            }
        except Exception:
            return None

    def _pick_price(row: dict, side: str) -> float:
        if not row:
            return 0.0
        if side == 'CE':
            return row.get('ce_ltp') or row.get('ce_last_price') or row.get('ce_close') or 0.0
        return row.get('pe_ltp') or row.get('pe_last_price') or row.get('pe_close') or 0.0

    def _run():
        last_fetch: Dict[str, float] = {}
        thresholds: Dict[str, Dict[str, Any]] = {}
        while True:
            try:
                # Select symbols from Kite discovery (limited set for load control)
                try:
                    from services.kite_api_service import kite_api_service
                    data = kite_api_service.get_all_symbols()
                    indices = data.get('indices', [])
                    stocks = data.get('stocks_with_options', [])[:50]
                    commodities = data.get('commodities', [])
                    symbols = list(dict.fromkeys(indices + stocks + commodities))
                except Exception:
                    time.sleep(TICK_SECS)
                    continue

                now = time.time()
                for sym in symbols:
                    # throttle per symbol
                    if last_fetch.get(sym, 0) + TICK_SECS > now:
                        continue
                    last_fetch[sym] = now

                    # refresh thresholds periodically
                    th = thresholds.get(sym)
                    if (not th) or (now - th.get('last_fetch', 0) > REFRESH_THRESH_SECS):
                        calc = _calc_thresholds_for_symbol(sym)
                        if not calc:
                            continue
                        thresholds[sym] = { 'data': calc, 'last_fetch': now }
                        th = thresholds[sym]

                    data_obj = th.get('data') or {}
                    # current SMDs from live chain
                    try:
                        chain = option_service.get_option_chain(sym)
                    except Exception:
                        continue
                    rows = (chain or {}).get('option_chain') or []
                    if not rows:
                        continue

                    def find_row(strike):
                        for r in rows:
                            if r.get('strike_price') == strike:
                                return r
                        return None

                    # Current prices per side by step: 0 = ATM, +n = ITM step n, -n = OTM step n
                    cur_ce_by_step: Dict[int, float] = {}
                    cur_pe_by_step: Dict[int, float] = {}
                    atm_strike = (data_obj.get('atm_pair') or {}).get('strike')
                    if isinstance(atm_strike, (int, float)):
                        r = find_row(atm_strike)
                        cur_ce_by_step[0] = float(_pick_price(r, 'CE'))
                        cur_pe_by_step[0] = float(_pick_price(r, 'PE'))
                    # Compute for ITM steps (all available)
                    itm_arr = data_obj.get('itm_steps') or []
                    for i in range(len(itm_arr)):
                        ce_r = find_row(itm_arr[i].get('ce_strike'))
                        pe_r = find_row(itm_arr[i].get('pe_strike'))
                        cur_ce_by_step[i+1] = float(_pick_price(ce_r, 'CE'))
                        cur_pe_by_step[i+1] = float(_pick_price(pe_r, 'PE'))
                    # Compute for OTM steps (all available) as negative keys
                    otm_arr = data_obj.get('otm_steps') or []
                    for i in range(len(otm_arr)):
                        ce_r = find_row(otm_arr[i].get('ce_strike'))
                        pe_r = find_row(otm_arr[i].get('pe_strike'))
                        cur_ce_by_step[-(i+1)] = float(_pick_price(ce_r, 'CE'))
                        cur_pe_by_step[-(i+1)] = float(_pick_price(pe_r, 'PE'))

                    # Breakout levels: ATM, ALL ITM steps (+1..), and ALL OTM steps (-1..)
                    breakout_levels = []
                    breakout_levels.append({'step': 0, 'level': (data_obj.get('atm_pair') or {}).get('smd') or 0})
                    for s in range(1, len(itm_arr)+1):
                        breakout_levels.append({'step': s, 'level': itm_arr[s-1].get('smd') or 0})
                    for s in range(1, len(otm_arr)+1):
                        breakout_levels.append({'step': -s, 'level': otm_arr[s-1].get('smd') or 0})

                    def ensure(step: int, side: str, kind: str, level: float, ce_strike=None, pe_strike=None):
                        if not level:
                            return
                        cur = cur_ce_by_step.get(step, 0.0) if side=='CE' else cur_pe_by_step.get(step, 0.0)
                        if cur < float(level):
                            return
                        # If not provided, derive base-step strikes (ATM or ITM step)
                        if ce_strike is None or pe_strike is None:
                            if step == 0:
                                ce_strike = atm_strike
                                pe_strike = atm_strike
                            else:
                                if step > 0 and len(itm_arr) >= step:
                                    ce_strike = itm_arr[step-1].get('ce_strike')
                                    pe_strike = itm_arr[step-1].get('pe_strike')
                                elif step < 0 and len(otm_arr) >= abs(step):
                                    ce_strike = otm_arr[abs(step)-1].get('ce_strike')
                                    pe_strike = otm_arr[abs(step)-1].get('pe_strike')

                        # ID: one per symbol+step+kind per day
                        hit_id = f"ASP_{sym}_{_date_key()}_step{step}_{side}_{kind}"
                        hit = {
                            'id': hit_id,
                            'symbol': sym,
                            'step': step,
                            'kind': kind,
                            'side': side,
                            'ce_strike': ce_strike,
                            'pe_strike': pe_strike,
                            'level': float(level),
                            'cur': float(cur),
                            'hitTime': datetime.utcnow().isoformat() + 'Z'
                        }
                        _record_hit(hit)
                        try:
                            socketio.emit('sharp_pro_signal', hit)
                        except Exception:
                            pass

                    # Breakouts per side (ATM, all ITM, all OTM)
                    for b in breakout_levels:
                        step_i = int(b['step'])
                        # CE breakout level
                        if step_i == 0:
                            ce_level = (data_obj.get('atm_pair') or {}).get('ce_prev_close') or 0
                            pe_level = (data_obj.get('atm_pair') or {}).get('pe_prev_close') or 0
                        elif step_i > 0:
                            ce_level = (itm_arr[step_i-1] or {}).get('ce_prev_close') or 0
                            pe_level = (itm_arr[step_i-1] or {}).get('pe_prev_close') or 0
                        else:
                            ce_level = (otm_arr[abs(step_i)-1] or {}).get('ce_prev_close') or 0
                            pe_level = (otm_arr[abs(step_i)-1] or {}).get('pe_prev_close') or 0
                        ensure(step_i, 'CE', 'breakout', float(ce_level or 0))
                        ensure(step_i, 'PE', 'breakout', float(pe_level or 0))

                    # TPs for base steps: for each base step s, TP1..TP3 are next ITM steps' prev_close per side
                    total_itm = len(itm_arr)
                    # ATM and ITM bases (0..+N)
                    for base in range(0, total_itm+1):  # include ATM (0)
                        base_ce = atm_strike if base == 0 else (itm_arr[base-1].get('ce_strike') if total_itm >= base else None)
                        base_pe = atm_strike if base == 0 else (itm_arr[base-1].get('pe_strike') if total_itm >= base else None)
                        if base > total_itm:
                            continue
                        # need next three ITM steps to exist
                        tp_indices = [base + i for i in range(1,4)]  # 0->1,2,3 ; 1->2,3,4 ; etc.
                        labels = ['tp1','tp2','tp3']
                        for lbl, idx in zip(labels, tp_indices):
                            if 1 <= idx <= total_itm:
                                ce_level = itm_arr[idx-1].get('ce_prev_close') or 0
                                pe_level = itm_arr[idx-1].get('pe_prev_close') or 0
                                ensure(base, 'CE', lbl, float(ce_level or 0), base_ce, base_pe)
                                ensure(base, 'PE', lbl, float(pe_level or 0), base_ce, base_pe)

                    # OTM bases (-1..-M): map to ITM indices m, m+1, m+2 where m=abs(base)
                    total_otm = len(otm_arr)
                    for m in range(1, total_otm+1):
                        base = -m
                        base_ce = otm_arr[m-1].get('ce_strike')
                        base_pe = otm_arr[m-1].get('pe_strike')
                        tp_indices = [m, m+1, m+2]
                        labels = ['tp1','tp2','tp3']
                        for lbl, idx in zip(labels, tp_indices):
                            if 1 <= idx <= total_itm:
                                ce_level = itm_arr[idx-1].get('ce_prev_close') or 0
                                pe_level = itm_arr[idx-1].get('pe_prev_close') or 0
                                ensure(base, 'CE', lbl, float(ce_level or 0), base_ce, base_pe)
                                ensure(base, 'PE', lbl, float(pe_level or 0), base_ce, base_pe)

                _cleanup_old_days(2)
                time.sleep(TICK_SECS)
            except Exception:
                time.sleep(TICK_SECS)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
