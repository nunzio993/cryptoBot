import os
import sys
import logging
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from src.core_and_scheduler import auto_execute_pending, check_and_execute_stop_loss, sync_orders, check_tp_fills, check_cancelled_tp_orders, record_daily_balance

# Root logger
root = logging.getLogger()
for h in list(root.handlers):
    root.removeHandler(h)
root.setLevel(logging.INFO)

def scheduled_job():
    auto_execute_pending()
    check_and_execute_stop_loss()
    check_tp_fills()
    sync_orders()

# StreamHandler → stdout
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
root.addHandler(sh)

# FileHandler → logs/scheduler.log with rotation (keep 3 days)
from logging.handlers import TimedRotatingFileHandler
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
import pathlib; pathlib.Path(LOG_DIR).mkdir(exist_ok=True)
# Rotate at UTC midnight (aligned with Binance daily candle close), keep 3 backups
fh = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, 'scheduler.log'),
    when='midnight',
    interval=1,
    backupCount=3,
    utc=True  # Use UTC time for rotation (Binance daily close = 00:00 UTC)
)
fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
root.addHandler(fh)

sched = BlockingScheduler()
if __name__ == "__main__":
    # Start WebSocket streams for real-time order updates
    try:
        from src.stream_manager import stream_manager
        stream_manager.start()
        root.info("WebSocket streams started for real-time updates")
    except Exception as e:
        root.warning(f"Could not start WebSocket streams: {e}")
        root.info("Falling back to polling-only mode")
    
    sched.configure(timezone=pytz.timezone("Europe/Rome"))
    sched.add_job(scheduled_job, 'interval', minutes=1, id='exec_pending')
    sched.add_job(check_and_execute_stop_loss, 'interval', seconds=30, id='check_sl_fast')
    sched.add_job(check_cancelled_tp_orders, 'interval', seconds=10, id='check_tp_cancelled')
    # Record daily balance at midnight UTC
    sched.add_job(record_daily_balance, 'cron', hour=0, minute=0, timezone=pytz.UTC, id='record_balance')
    root.info("Scheduler started: orders every 1 min, SL every 30 sec, TP check every 10 sec, balance at 00:00 UTC")
    
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        try:
            stream_manager.stop()
        except:
            pass
        root.info("Scheduler stopped")
