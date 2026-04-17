import math
import os

from playwright.sync_api import sync_playwright

from sites.core.browser import create_browser_context
from sites.core.outputs import save_json
from sites.core.utils import iso_now
from sites.xuezhi.common.config import MAJORS_BASE_URL, MAJORS_OUTPUT_DIR
from .extractors import extract_major_detail, extract_major_list_rows


SCRAPE_DETAILS = os.getenv("SCRAPE_DETAILS", "1") == "1"


def log(message):
    print(message, flush=True)


def write_partial(rows):
    save_json(
        MAJORS_OUTPUT_DIR / "majors-flat.partial.json",
        {
            "抓取时间": iso_now(),
            "来源": MAJORS_BASE_URL,
            "数量": len(rows),
            "专业列表": rows,
        },
    )


def get_total_pages(page):
    pager = page.locator(".xz-zyrw-page .ivu-page")
    if pager.count() == 0:
        return 1

    numbers = pager.locator(".ivu-page-item")
    vals = []
    for i in range(numbers.count()):
        txt = numbers.nth(i).inner_text().strip()
        if txt.isdigit():
            vals.append(int(txt))

    return max(vals) if vals else 1


def wait_list_ready(page):
    page.goto(MAJORS_BASE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(".xz-zydc-list .zydc-list-table-item", timeout=30000)
    page.wait_for_timeout(1500)


def click_next_page(page):
    next_btn = page.locator(".xz-zyrw-page .ivu-page-next")
    if next_btn.count() == 0:
        return False

    cls = next_btn.first.get_attribute("class") or ""
    if "ivu-page-disabled" in cls:
        return False

    before_first = ""
    first_item = page.locator(".xz-zydc-list .zydc-list-table-item .zy").first
    if first_item.count():
        before_first = first_item.inner_text().strip()

    next_btn.first.click()
    page.wait_for_timeout(1200)
    page.wait_for_selector(".xz-zydc-list .zydc-list-table-item", timeout=30000)

    try:
        page.wait_for_function(
            """
            prev => {
                const el = document.querySelector('.xz-zydc-list .zydc-list-table-item .zy');
                if (!el) return false;
                return (el.innerText || '').trim() !== prev;
            }
            """,
            arg=before_first,
            timeout=30000,
        )
    except Exception:
        page.wait_for_timeout(1200)

    return True


def run():
    MAJORS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []
    seen = set()

    with sync_playwright() as p:
        browser, context = create_browser_context(p)
        page = context.new_page()

        try:
            log("[INFO] Xuezhi majors crawler started")
            wait_list_ready(page)
            total_pages = get_total_pages(page)
            log(f"[INFO] total pages: {total_pages}")

            current_page = 1
            while True:
                current_url = page.url
                log(f"[INFO] parsing list page {current_page}/{total_pages}")

                rows = extract_major_list_rows(page, current_url, current_page)
                log(f"[INFO] page {current_page} rows: {len(rows)}")

                for idx, row in enumerate(rows, start=1):
                    key = row["specId"] or row["详情页"]
                    if key in seen:
                        continue
                    seen.add(key)

                    if SCRAPE_DETAILS:
                        log(f"[INFO] detail {current_page}-{idx}: {row['专业名称']}")
                        row["详情"] = extract_major_detail(context, row)
                    else:
                        row["详情"] = {}

                    all_rows.append(row)

                    if len(all_rows) % 20 == 0:
                        write_partial(all_rows)
                        log(f"[INFO] partial saved: {len(all_rows)}")

                if current_page >= total_pages:
                    break

                moved = click_next_page(page)
                if not moved:
                    break
                current_page += 1

            save_json(
                MAJORS_OUTPUT_DIR / "majors-flat.json",
                {
                    "抓取时间": iso_now(),
                    "来源": MAJORS_BASE_URL,
                    "数量": len(all_rows),
                    "是否抓详情": SCRAPE_DETAILS,
                    "专业列表": all_rows,
                },
            )
            write_partial(all_rows)
            log(f"[INFO] finished, total majors: {len(all_rows)}")

        finally:
            context.close()
            browser.close()