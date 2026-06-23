"""
DCA runner — buys $7.50 of each configured symbol on days it's trading below
its prior close. Currently configured for VOO, MU, WDC (see
trading_model.config.DCA_PARAMS["symbols"]) — each symbol is evaluated and
bought independently, so a day where all three are down means three
separate $7.50 buys (one per symbol), for a max of $22.50/day.

This is meant to run unattended once per weekday, around 10:30am ET, via
your own scheduler (cron / Task Scheduler / launchd) — Claude Code does not
keep a process running in the background, so something on your machine has
to invoke this on a timer.

Setup
-----
1. pip install -r dashboard/requirements.txt   (reuses robin_stocks + dotenv)
2. Create a .env file (repo root, or dashboard/.env — both are checked):
     ROBINHOOD_USER=your@email.com
     ROBINHOOD_PASS=yourpassword
3. First run interactively once to clear the Robinhood MFA challenge:
     python3 dca_runner.py --dry-run
   (enter the SMS/app code when prompted; the session is then pickled and
   reused, same as the dashboard backend.)
4. Schedule it, e.g. crontab (server/local time must be US/Eastern, or
   adjust the hour accordingly):
     30 10 * * 1-5  cd /path/to/repo && python3 dca_runner.py --live >> data/dca_cron.log 2>&1

Safety
------
- Defaults to --dry-run: prints each symbol's decision, places no orders.
  You must pass --live to actually submit trades.
- Hardcoded to the agentic-allowed account only (trading_model.config.AGENTIC_ACCOUNT).
  Any other account number is rejected by DCAConfig.
- Refuses to buy a given symbol twice in the same calendar day (checked
  against data/dca_log.jsonl), even if invoked multiple times.
"""

import argparse
import json
import os
import sys
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


def _run_symbol(rh, symbol: str, amount: float, live: bool, today: date) -> None:
    config = DCAConfig(
        symbol=symbol,
        dollar_amount=amount,
        account_number=AGENTIC_ACCOUNT,
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

    for symbol in symbols:
        _run_symbol(rh, symbol, args.amount, args.live, today)

    return 0


if __name__ == '__main__':
    sys.exit(main())
