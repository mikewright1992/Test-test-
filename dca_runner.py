"""
DCA runner — buys $7.50 of each configured symbol on days it's trading below
its prior close. Currently configured for VOO, MU, WDC (see
trading_model.config.DCA_PARAMS["symbols"]) — each symbol is evaluated and
bought independently, so a day where all three are down means three
separate $7.50 buys (one per symbol), for a max of $22.50/day.

This MUST be scheduled by something outside of Claude Code — a Claude Code
chat session cannot run unattended for weeks at a time; its in-chat cron
mechanism is session-only and is reclaimed with the container, so it cannot
be trusted for daily real-money trades. Use your OS's own scheduler:

  cron (Linux/macOS), Task Scheduler (Windows), or launchd (macOS).

Setup
-----
1. pip install -r dashboard/requirements.txt   (reuses robin_stocks + dotenv)
2. Create a .env file (repo root, or dashboard/.env — both are checked):
     ROBINHOOD_USER=your@email.com
     ROBINHOOD_PASS=yourpassword
3. First run interactively once to clear the Robinhood MFA challenge:
     python3 dca_runner.py --dry-run
   (enter the SMS/app code when prompted; the session is then pickled to
   ~/.tokens/rh_dca.pickle and reused, same as the dashboard backend.)
4. Schedule it. Easiest: run setup_cron.sh, which installs the crontab line
   below for you. Or add it yourself — server/local time must be US/Eastern,
   or adjust the hour for your machine's timezone:
     30 10 * * 1-5  cd /path/to/repo && python3 dca_runner.py --live >> data/dca_cron.log 2>&1

Safety
------
- Defaults to --dry-run: prints each symbol's decision, places no orders.
  You must pass --live to actually submit trades.
- Hardcoded to the agentic-allowed account only (trading_model.config.AGENTIC_ACCOUNT).
  Any other account number is rejected by DCAConfig.
- Refuses to buy a given symbol twice in the same calendar day (checked
  against data/dca_log.jsonl), even if invoked multiple times.
- One symbol's failure (bad quote, API error, order rejection) is logged and
  skipped — it does not stop the remaining symbols from being evaluated.
"""

import argparse
import json
import os
import sys
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
load_dotenv(ROOT / 'dashboard' / '.env')

from trading_model.config import AGENTIC_ACCOUNT, DCA_PARAMS
from trading_model.dca import DCAConfig, plan_dca_purchase, already_ran_today

LOG_PATH = ROOT / 'data' / 'dca_log.jsonl'


def _log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('a') as f:
        f.write(json.dumps(entry) + '\n')


def _run_symbol(rh, symbol: str, amount: float, threshold: float, live: bool, today: date) -> None:
    config = DCAConfig(
        symbol=symbol,
        dollar_amount=amount,
        account_number=AGENTIC_ACCOUNT,
        down_day_threshold_pct=threshold,
    )

    if already_ran_today(LOG_PATH, config.symbol, today):
        print(f"[{today}] Already bought {config.symbol} today — skipping.")
        return

    quote = rh.get_quotes([config.symbol])[0]
    current_price = float(quote['last_trade_price'])
    previous_close = float(quote['adjusted_previous_close'])

    decision = plan_dca_purchase(config, current_price, previous_close)
    print(f"[{datetime.now(timezone.utc).isoformat()}] {decision.reason}")

    log_entry = {
        'date': today.isoformat(),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'symbol': decision.symbol,
        'current_price': decision.current_price,
        'previous_close': decision.previous_close,
        'change_pct': decision.change_pct,
        'should_buy': decision.should_buy,
        'dollar_amount': decision.dollar_amount,
        'account_number': decision.account_number,
        'mode': 'live' if live else 'dry_run',
    }

    if not decision.should_buy:
        log_entry['status'] = 'skipped'
        _log(log_entry)
        return

    if not live:
        print(f"DRY RUN — would buy ${decision.dollar_amount:.2f} of {decision.symbol} "
              f"in account {decision.account_number}. Re-run with --live to submit.")
        log_entry['status'] = 'dry_run_only'
        _log(log_entry)
        return

    order = rh.orders.order_buy_fractional_by_price(
        decision.symbol,
        decision.dollar_amount,
        account_number=decision.account_number,
        timeInForce='gfd',
    )
    print(f"Order submitted for {decision.symbol}: {order}")
    log_entry['status'] = 'filled_or_submitted'
    log_entry['order_response'] = order
    _log(log_entry)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true',
                         help='Actually submit orders. Without this flag, runs as a dry run.')
    parser.add_argument('--symbols', default=','.join(DCA_PARAMS["symbols"]),
                         help='Comma-separated list of symbols to evaluate independently.')
    parser.add_argument('--amount', type=float, default=DCA_PARAMS["dollar_amount"])
    args = parser.parse_args(argv)

    symbols = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
    today = date.today()

    import robin_stocks.robinhood as rh
    rh.login(
        username=os.getenv('ROBINHOOD_USER', ''),
        password=os.getenv('ROBINHOOD_PASS', ''),
        store_session=True,
        pickle_name='rh_dca',
    )

    _thresholds = DCA_PARAMS.get("thresholds", {})
    _default_threshold = DCA_PARAMS["down_day_threshold_pct"]

    failures = []
    for symbol in symbols:
        threshold = _thresholds.get(symbol, _default_threshold)
        try:
            _run_symbol(rh, symbol, args.amount, threshold, args.live, today)
        except Exception as e:
            print(f"ERROR evaluating {symbol}: {e}", file=sys.stderr)
            traceback.print_exc()
            failures.append(symbol)
            _log({
                'date': today.isoformat(),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'symbol': symbol,
                'status': 'error',
                'mode': 'live' if args.live else 'dry_run',
                'error': str(e),
            })

    if failures:
        print(f"Completed with errors on: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
