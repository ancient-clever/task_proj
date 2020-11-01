from pathlib import Path
from threading import Thread
from datetime import datetime


def simple_logger(level: str, message: str) -> None:
    """Write args to file in log directory"""
    dt = datetime.now()

    log_dir = Path.cwd() / "log"
    if not log_dir.exists():
        log_dir.mkdir()

    # set current date for log file
    log_file = log_dir / dt.strftime('%y%m%d.log')
    with open(str(log_file), 'a') as log:
        content = '{}, {}: {}'.format(dt.strftime('%Y-%m-%d %H:%M:%S'), level, message) + '\n'
        log.write(content)


def logger(level: str, message: str) -> None:
    """Run simple logger in thread"""
    th = Thread(
        target=simple_logger,
        args=(level, message)
    )
    th.start()
