from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .browser import (
    click_group_item_by_text,
    click_level_by_text,
    get_group,
    get_group_items_texts,
    get_level_texts,
    wait_ready,
    wait_table,
)
from .config import BASE_URL, LEVEL_NAMES, OUTPUT_DIR, SCRAPE_DETAILS
from .extractors import extract_detail, extract_table_rows
from .outputs import build_hierarchy, ensure_output, save_debug, save_json, write_partial
from .utils import iso_now


def run():
    ensure_output()

    flat_majors = []
    levels_found = []
    seen_major = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            wait_ready(page)
            save_debug(page, "01_ready")

            all_level_texts = get_level_texts(page)
            for level_name in LEVEL_NAMES:
                if level_name in all_level_texts:
                    levels_found.append(level_name)

            for level_name in levels_found:
                print(f"[INFO] 进入培养层次: {level_name}")
                click_level_by_text(page, level_name)

                discipline_group = get_group(page, 0)
                discipline_texts = get_group_items_texts(discipline_group)

                for discipline in discipline_texts:
                    print(f"[INFO] 进入门类: {level_name} / {discipline}")
                    discipline_group = get_group(page, 0)
                    click_group_item_by_text(discipline_group, discipline)
                    page.wait_for_timeout(800)

                    class_group = get_group(page, 1)
                    class_texts = get_group_items_texts(class_group)

                    for major_class in class_texts:
                        try:
                            print(f"[INFO] 进入专业类: {level_name} / {discipline} / {major_class}")
                            class_group = get_group(page, 1)
                            click_group_item_by_text(class_group, major_class)
                            wait_table(page)

                            rows = extract_table_rows(page, level_name, discipline, major_class)
                            print(f"[INFO] 表格行数: {len(rows)}")

                            for row in rows:
                                key = row["specId"] or (
                                    row["培养层次"],
                                    row["门类"],
                                    row["专业类"],
                                    row["专业名称"],
                                    row["专业代码"],
                                )
                                if key in seen_major:
                                    continue
                                seen_major.add(key)

                                row["详情"] = extract_detail(context, row) if SCRAPE_DETAILS else {}
                                flat_majors.append(row)

                            write_partial(flat_majors)

                        except Exception as e:
                            print(f"[WARN] 跳过专业类: {level_name} / {discipline} / {major_class} -> {repr(e)}")
                            write_partial(flat_majors)
                            continue

            save_debug(page, "02_done")

        except PlaywrightTimeoutError as e:
            save_debug(page, "timeout")
            write_partial(flat_majors)
            raise e
        except Exception as e:
            save_debug(page, "error")
            write_partial(flat_majors)
            raise e
        finally:
            context.close()
            browser.close()

    all_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL,
        "培养层次列表": build_hierarchy(levels_found, flat_majors),
    }

    flat_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL,
        "数量": len(flat_majors),
        "专业列表": flat_majors,
    }

    meta_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL,
        "培养层次": levels_found,
        "专业总数": len(flat_majors),
        "是否抓详情": SCRAPE_DETAILS,
    }

    save_json(OUTPUT_DIR / "all.json", all_json)
    save_json(OUTPUT_DIR / "majors-flat.json", flat_json)
    save_json(OUTPUT_DIR / "meta.json", meta_json)

    print(f"levels: {len(levels_found)}")
    print(f"majors: {len(flat_majors)}")
    print(f"detail: {SCRAPE_DETAILS}")


if __name__ == "__main__":
    run()
