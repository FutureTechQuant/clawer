from playwright.sync_api import sync_playwright

from sites.core.browser import create_browser_context
from sites.core.outputs import save_json
from sites.core.utils import iso_now
from sites.chsi.common.config import SCHOOLS_LIST_URL, SCHOOL_STARTS, SCHOOLS_OUTPUT_DIR
from .extractors import extract_school_detail, extract_school_list_rows


def run():
    SCHOOLS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []
    seen = set()

    with sync_playwright() as p:
        browser, context = create_browser_context(p)
        page = context.new_page()

        try:
            for idx, start in enumerate(SCHOOL_STARTS, start=1):
                url = SCHOOLS_LIST_URL.format(start=start)
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector("#app-yxk-sch-list .sch-item", timeout=30000)
                page.wait_for_timeout(1200)

                rows = extract_school_list_rows(page, url, idx)

                for row in rows:
                    key = row["schId"] or row["详情页"]
                    if key in seen:
                        continue
                    seen.add(key)
                    row["详情"] = extract_school_detail(context, row)
                    all_rows.append(row)

                save_json(
                    SCHOOLS_OUTPUT_DIR / "schools-flat.partial.json",
                    {
                        "抓取时间": iso_now(),
                        "数量": len(all_rows),
                        "院校列表": all_rows,
                    },
                )
        finally:
            context.close()
            browser.close()

    save_json(
        SCHOOLS_OUTPUT_DIR / "schools-flat.json",
        {
            "抓取时间": iso_now(),
            "数量": len(all_rows),
            "院校列表": all_rows,
        },
    )