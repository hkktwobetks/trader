from apscheduler.schedulers.background import BackgroundScheduler
from app.db import get_session


scheduler = BackgroundScheduler()


@scheduler.scheduled_job("interval", minutes=5)
def manage_positions():
    # TODO: 価格取得→SL/TP 条件満たせばクローズ
    pass


if __name__ == "__main__":
    scheduler.start()
    import time
    while True:
        time.sleep(10)