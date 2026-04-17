from playwright.sync_api import sync_playwright

from sites.core.browser import create_browser_context
from sites.core.outputs import save_json
from sites.core.utils import iso_now
from sites.chsi.common.config import SCHOOLS_LIST_URL, SCHOOL_STARTS, SCHOOLS_OUTPUT_DIR
from .extractors import extract_school_detail, extract_school_list_rows


def log(message):
    print(message, flush=True)


def write_partial(all_rows):
    save_json(
        SCHOOLS_OUTPUT_DIR / "schools-flat.partial.json",
        {
            "抓取时间": iso_now(),
            "数量": len(all_rows),
            "院校列表": all_rows,
        },
    )
    log(f"[INFO] partial saved: {len(all_rows)} schools")


def run():
    SCHOOLS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []
    seen = set()

    log("[INFO] CHSI schools crawler started")
    log(f"[INFO] total list pages: {len(SCHOOL_STARTS)}")

    with sync_playwright() as p:
        browser, context = create_browser_context(p)
        page = context.new_page()

        try:
            for idx, start in enumerate(SCHOOL_STARTS, start=1):
                url = SCHOOLS_LIST_URL.format(start=start)
                log(f"[INFO] loading list page {idx}/{len(SCHOOL_STARTS)}: start={start}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector("#app-yxk-sch-list .sch-item", timeout=30000)
                page.wait_for_timeout(1200)

                rows = extract_school_list_rows(page, url, idx)
                log(f"[INFO] list page {idx} parsed: {len(rows)} schools")

                page_new_count = 0

                for row_idx, row in enumerate(rows, start=1):
                    key = row["schId"] or row["详情页"]
                    if key in seen:
                        log(
                            f"[INFO] skip duplicate school on page {idx}: "
                            f"{row.get('学校名称', '')} ({row_idx}/{len(rows)})"
                        )
                        continue

                    seen.add(key)
                    page_new_count += 1

                    school_name = row.get("学校名称", "")
                    detail_url = row.get("详情页", "")
                    log(
                        f"[INFO] fetching school detail: "
                        f"page={idx}/{len(SCHOOL_STARTS)}, row={row_idx}/{len(rows)}, "
                        f"name={school_name}, schId={row.get('schId', '')}"
                    )

                    try:
                        row["详情"] = extract_school_detail(context, row)
                        log(
                            f"[INFO] detail done: {school_name}, "
                            f"intro_len={len(row.get('详情', {}).get('intro', {}).get('学校简介正文', ''))}"
                        )
                    except Exception as e:
                        row["详情"] = {
                            "顶部信息": {},
                            "intro": {},
                            "error": repr(e),
                        }
                        log(f"[WARN] detail failed: {school_name} -> {repr(e)}")

                    all_rows.append(row)

                    if len(all_rows) % 10 == 0:
                        log(f"[INFO] progress checkpoint: total_collected={len(all_rows)}")
                        write_partial(all_rows)

                log(
                    f"[INFO] page {idx} finished: "
                    f"new_schools={page_new_count}, total_collected={len(all_rows)}"
                )
                write_partial(all_rows)

        except Exception as e:
            log(f"[ERROR] crawler aborted: {repr(e)}")
            write_partial(all_rows)
            raise
        finally:
            context.close()
            browser.close()
            log("[INFO] browser closed")

    save_json(
        SCHOOLS_OUTPUT_DIR / "schools-flat.json",
        {
            "抓取时间": iso_now(),
            "数量": len(all_rows),
            "院校列表": all_rows,
        },
    )

    log(f"[INFO] finished: total schools={len(all_rows)}")
