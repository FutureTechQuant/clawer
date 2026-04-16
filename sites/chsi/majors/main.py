from playwright.sync_api import sync_playwright

from sites.core.browser import create_browser_context
from sites.core.outputs import save_json
from sites.core.utils import iso_now
from sites.chsi.common.config import MAJORS_OUTPUT_DIR


def run():
    MAJORS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    result = {
        "抓取时间": iso_now(),
        "来源": "https://gaokao.chsi.com.cn/zyk/zybk/",
        "专业列表": [],
    }

    with sync_playwright() as p:
        browser, context = create_browser_context(p)
        try:
            save_json(MAJORS_OUTPUT_DIR / "majors-flat.json", result)
        finally:
            context.close()
            browser.close()