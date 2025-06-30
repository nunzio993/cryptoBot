import os
import sys
import logging
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from src.core_and_scheduler import auto_execute_pending, check_and_execute_stop_loss, sync_orders_with_binance

# Root logger
root = logging.getLogger()
for h in list(root.handlers):
    root.removeHandler(h)
root.setLevel(logging.INFO)

def scheduled_job():
    auto_execute_pending()
    check_and_execute_stop_loss()
    sync_orders_with_binance()

# StreamHandler → stdout
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
root.addHandler(sh)

# FileHandler → logs/scheduler.log
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
import pathlib; pathlib.Path(LOG_DIR).mkdir(exist_ok=True)
fh = logging.FileHandler(os.path.join(LOG_DIR, 'scheduler.log'))
fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
root.addHandler(fh)

sched = BlockingScheduler()
if __name__ == "__main__":
    sched.configure(timezone=pytz.timezone("Europe/Rome"))
    sched.add_job(scheduled_job, 'interval', minutes=1, id='exec_pending')
    root.info("Scheduler avviato (Testnet): controllo ordini ogni minuto")
    sched.start()
