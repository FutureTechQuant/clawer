import os
from pathlib import Path

ROOT_DIR = Path(".")
DATA_DIR = ROOT_DIR / "data"
DEBUG_DIR = ROOT_DIR / "output"

SAVE_DEBUG = os.getenv("SAVE_DEBUG", "0") == "1"
HEADLESS = os.getenv("HEADLESS", "1") == "1"
TIMEOUT = int(os.getenv("CRAWL_TIMEOUT", "60000"))
LOCALE = "zh-CN"
TIMEZONE_ID = "Asia/Shanghai"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)