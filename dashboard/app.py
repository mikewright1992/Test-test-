"""
Portfolio Dashboard — Flask API server.

Setup:
  1. pip install -r requirements.txt
  2. Create .env in this folder:
       ROBINHOOD_USER=your@email.com
       ROBINHOOD_PASS=yourpassword
  3. python app.py
  4. Open http://localhost:5000

Robinhood MFA: The first login will ask for your 2FA code via the browser.
The session is then pickled (~/.tokens/rh_dashboard.pickle) and reused,
so you only need MFA once unless the session expires (~30 days).
"""

import os, sys, json, threading
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

from flask import Flask, jsonify, send_from_directory, request

app = Flask(__name__, static_folder='static')

# ── Session state ─────────────────────────────────────────────────────────────
_rh = None
_mfa_state = {}       # holds username/password while waiting for MFA code
_cache = {}           # in-process cache to avoid hammering Robinhood
_cache_lock = threading.Lock()
CACHE_TTL = 60        # seconds

# ── Helpers ───────────────────────────────────────────────────────────────────

def _cached(key, fn, ttl=CACHE_TTL):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (datetime.now().timestamp() - entry['ts']) < ttl:
            return entry['data']
    data = fn()
    with _cache_lock:
        _cache[key] = {'data': data, 'ts': datetime.now().timestamp()}
    return data


def _try_restore():
    global _rh
    try:
        import robin_stocks.robinhood as rh
        rh.login(
            username=os.getenv('ROBINHOOD_USER', ''),
            password=os.getenv('ROBINHOOD_PASS', ''),
            store_session=True,
            pickle_name='rh_dashboard',
        )
        _rh = rh
    except Exception:
        pass


def _build_holdings():
    """Fetch all positions + quotes and compute P&L."""
    holdings_raw = _rh.build_holdings()
    symbols = list(holdings_raw.keys())
    if not symbols:
        return [], {}

    quotes_raw = _rh.get_quotes(symbols) or []
    quote_map = {}
    for q in quotes_raw:
        if q and q.get('symbol'):
            quote_map[q['symbol']] = q

    holdings = []
    for sym, h in holdings_raw.items():
        shares     = float(h.get('quantity', 0) or 0)
        avg_cost   = float(h.get('average_buy_price', 0) or 0)
        price      = float(h.get('price', 0) or 0)
        mkt_val    = float(h.get('equity', 0) or 0)
        total_pnl  = float(h.get('equity_change', 0) or 0)
        total_pct  = float(h.get('percent_change', 0) or 0)
        name       = h.get('name', sym)

        q = quote_map.get(sym, {})
        prev       = float(q.get('adjusted_previous_close', price) or price)
        day_pct    = round((price - prev) / prev * 100, 2) if prev else 0
        day_dollar = round(shares * (price - prev), 2)

        holdings.append({
            'symbol':     sym,
            'name':       name,
            'shares':     round(shares, 4),
            'avg_cost':   round(avg_cost, 2),
            'price':      round(price, 2),
            'prev_close': round(prev, 2),
            'day_pct':    day_pct,
            'day_dollar': day_dollar,
            'total_pnl':  round(total_pnl, 2),
            'total_pct':  round(total_pct, 2),
            'mkt_val':    round(mkt_val, 2),
        })

    holdings.sort(key=lambda r: r['mkt_val'], reverse=True)

    total_equity  = sum(r['mkt_val']    for r in holdings)
    day_gain      = sum(r['day_dollar'] for r in holdings)
    total_pnl_sum = sum(r['total_pnl']  for r in holdings)
    cost_basis    = total_equity - total_pnl_sum

    # Try to get cash balance
    cash = 0.0
    try:
        profile = _rh.load_portfolio_profile()
        cash = float(profile.get('withdrawable_amount', 0) or 0)
    except Exception:
        pass

    summary = {
        'total_value':    round(total_equity + cash, 2),
        'equity':         round(total_equity, 2),
        'cash':           round(cash, 2),
        'day_gain':       round(day_gain, 2),
        'day_gain_pct':   round(day_gain / (total_equity - day_gain) * 100, 3)
                          if total_equity > day_gain else 0,
        'total_pnl':      round(total_pnl_sum, 2),
        'total_pnl_pct':  round(total_pnl_sum / cost_basis * 100, 2)
                          if cost_basis else 0,
        'positions':      len(holdings),
        'updated':        datetime.now(timezone.utc).strftime('%b %d %Y, %I:%M %p UTC'),
    }

    return holdings, summary


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/status')
def status():
    return jsonify({'authenticated': _rh is not None})


@app.route('/api/login', methods=['POST'])
def login():
    global _rh, _mfa_state
    body = request.json or {}

    try:
        import robin_stocks.robinhood as rh

        username = body.get('username') or os.getenv('ROBINHOOD_USER', '')
        password = body.get('password') or os.getenv('ROBINHOOD_PASS', '')
        mfa_code = body.get('mfa_code', '')

        kwargs = dict(
            username=username,
            password=password,
            store_session=True,
            pickle_name='rh_dashboard',
        )
        if mfa_code:
            kwargs['mfa_code'] = mfa_code

        rh.login(**kwargs)
        _rh = rh
        _mfa_state = {}
        with _cache_lock:
            _cache.clear()
        return jsonify({'status': 'ok'})

    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ('mfa', '2fa', 'challenge', 'otp', 'verification')):
            _mfa_state = {'username': body.get('username'), 'password': body.get('password')}
            return jsonify({'status': 'mfa_required'})
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/holdings')
def holdings():
    if _rh is None:
        # Fallback: serve cached JSON generated by Claude Code
        cached = ROOT / 'data' / 'holdings.json'
        if cached.exists():
            return jsonify(json.loads(cached.read_text()))
        return jsonify({'error': 'not_authenticated', 'holdings': [], 'summary': {}}), 401

    try:
        result = _cached('holdings', _build_holdings, ttl=CACHE_TTL)
        holdings_list, summary = result
        return jsonify({'holdings': holdings_list, 'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e), 'holdings': [], 'summary': {}}), 500


@app.route('/api/analyze/<symbol>')
def analyze(symbol):
    symbol = symbol.upper().strip()

    if _rh is None:
        return jsonify({'error': 'not_authenticated'}), 401

    def _do_analyze():
        raw = _rh.get_stock_historicals(
            symbol, interval='day', span='3month', bounds='regular',
        ) or []
        bars = [
            {
                'close_price': h.get('close_price', '0'),
                'high_price':  h.get('high_price',  '0'),
                'low_price':   h.get('low_price',   '0'),
                'volume':      h.get('volume',      '0'),
            }
            for h in raw
            if h and h.get('close_price')
        ]
        quotes = _rh.get_quotes([symbol]) or []
        price  = float(quotes[0].get('last_trade_price', 0)) if quotes else 0.0

        from trading_model.signals import analyze as _analyze
        sig = _analyze(symbol, bars)
        if price:
            sig.current_price = price

        return {
            'symbol':     sig.symbol,
            'action':     sig.action,
            'score':      sig.score,
            'trend':      sig.trend,
            'rsi':        round(sig.rsi_value, 1) if sig.rsi_value else None,
            'price':      round(sig.current_price, 2),
            'reasons':    sig.reasons,
            'indicators': {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in sig.indicators.items()
            },
        }

    try:
        result = _cached(f'analyze_{symbol}', _do_analyze, ttl=300)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    _try_restore()
    port = int(os.getenv('PORT', 5000))
    print(f'Dashboard running → http://localhost:{port}')
    app.run(host='0.0.0.0', port=port, debug=False)
