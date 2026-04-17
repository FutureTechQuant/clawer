import os

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from sites.core.browser import create_browser_context
from sites.core.outputs import save_json
from sites.core.utils import clean_text, iso_now
from sites.chsi.common.config import MAJORS_BASE_URL, MAJORS_OUTPUT_DIR
from .extractors import extract_major_detail, extract_major_list_rows

LEVEL_NAMES = [
    "本科（普通教育）",
    "本科（职业教育）",
    "高职（专科）",
]

SCRAPE_DETAILS = os.getenv("SCRAPE_DETAILS", "1") == "1"


def write_partial(flat_rows):
    save_json(
        MAJORS_OUTPUT_DIR / "majors-flat.partial.json",
        {
            "抓取时间": iso_now(),
            "来源": MAJORS_BASE_URL,
            "数量": len(flat_rows),
            "专业列表": flat_rows,
        },
    )


def wait_ready(page):
    page.goto(MAJORS_BASE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#app", timeout=30000)
    page.wait_for_function(
        """() => {
            const t = document.body ? document.body.innerText : '';
            return t.includes('专业知识库')
                && t.includes('本科（普通教育）专业目录')
                && t.includes('本科（职业教育）专业目录')
                && t.includes('高职（专科）专业目录');
        }""",
        timeout=60000,
    )
    page.wait_for_selector(".index-cc-list", timeout=30000)
    page.wait_for_timeout(1200)


def wait_table(page):
    page.wait_for_selector(".zyk-table-con .ivu-table-body tbody tr", timeout=30000)
    page.wait_for_function(
        """
        () => {
            const rows = document.querySelectorAll('.zyk-table-con .ivu-table-body tbody tr');
            if (!rows.length) return false;

            const loading =
                document.querySelector('.ivu-spin-spinning') ||
                document.querySelector('.ivu-spin-show-text');

            return !loading;
        }
        """,
        timeout=30000,
    )
    page.wait_for_timeout(600)


def get_level_texts(page):
    items = page.locator(".index-cc-list li")
    out = []
    for i in range(items.count()):
        txt = clean_text(items.nth(i).inner_text())
        if txt:
            out.append(txt)
    return out


def click_level_by_text(page, level_name: str):
    items = page.locator(".index-cc-list li")
    for i in range(items.count()):
        item = items.nth(i)
        txt = clean_text(item.inner_text())
        if txt == level_name:
            item.click()
            page.wait_for_timeout(1000)
            return
    raise RuntimeError(f"未找到培养层次：{level_name}")


def get_group(page, idx: int):
    return page.locator(".spec-list .zyk-lb-ul-con").nth(idx)


def get_group_items_texts(group):
    items = group.locator("ul.zyk-lb-ul > li")
    out = []
    for i in range(items.count()):
        txt = clean_text(items.nth(i).inner_text())
        if txt:
            out.append(txt)
    return out


def click_group_item_by_text(group, text: str):
    items = group.locator("ul.zyk-lb-ul > li")
    for i in range(items.count()):
        item = items.nth(i)
        txt = clean_text(item.inner_text())
        if txt == text:
            item.click()
            return
    raise RuntimeError(f"未找到分组项：{text}")


def run():
    MAJORS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    flat_rows = []
    levels_found = []
    seen = set()

    with sync_playwright() as p:
        browser, context = create_browser_context(p)
        page = context.new_page()

        try:
            wait_ready(page)

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

                            rows = extract_major_list_rows(
                                page,
                                level_name=level_name,
                                discipline=discipline,
                                major_class=major_class,
                            )
                            print(f"[INFO] 表格行数: {len(rows)}")

                            for row in rows:
                                key = row["specId"] or (
                                    row["培养层次"],
                                    row["门类"],
                                    row["专业类"],
                                    row["专业名称"],
                                    row["专业代码"],
                                )
                                if key in seen:
                                    continue

                                seen.add(key)

                                if SCRAPE_DETAILS:
                                    row["详情"] = extract_major_detail(context, row)
                                else:
                                    row["详情"] = {}

                                flat_rows.append(row)

                            write_partial(flat_rows)

                        except Exception as e:
                            print(f"[WARN] 跳过专业类: {level_name} / {discipline} / {major_class} -> {repr(e)}")
                            write_partial(flat_rows)
                            continue

        except PlaywrightTimeoutError:
            write_partial(flat_rows)
            raise
        except Exception:
            write_partial(flat_rows)
            raise
        finally:
            context.close()
            browser.close()

    flat_json = {
        "抓取时间": iso_now(),
        "来源": MAJORS_BASE_URL,
        "数量": len(flat_rows),
        "培养层次": levels_found,
        "是否抓详情": SCRAPE_DETAILS,
        "专业列表": flat_rows,
    }

    save_json(MAJORS_OUTPUT_DIR / "majors-flat.json", flat_json)
    print(f"levels: {len(levels_found)}")
    print(f"majors: {len(flat_rows)}")
    print(f"detail: {SCRAPE_DETAILS}")


if __name__ == "__main__":
    run()