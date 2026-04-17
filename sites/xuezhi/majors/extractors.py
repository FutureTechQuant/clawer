import re
from typing import List, Tuple
from urllib.parse import urljoin

from sites.core.utils import clean_text, iso_now
from .parsers import (
    abs_url,
    parse_count_text,
    parse_data_cutoff,
    parse_spec_id,
    unique_links,
    unique_text_items,
)


def extract_major_list_rows(page, list_url, page_no):
    row_data = page.locator(".xz-zydc-list .zydc-list-table-item").evaluate_all(
        """
        items => items.map(item => {
            const a = item.querySelector('a');
            const zymc = item.querySelector('.zy')?.innerText?.trim() || '';
            const rateInput = item.querySelector('.rate input[type="hidden"]');
            const evlNum = item.querySelector('.rate .num')?.innerText?.trim() || '';
            const cc = item.querySelector('.cc')?.innerText?.trim() || '';
            const mlmc = item.querySelector('.mlmc')?.innerText?.trim() || '';
            const xk = item.querySelector('.xk')?.innerText?.trim() || '';
            return {
                zymc,
                score: rateInput ? (rateInput.value || '').trim() : '',
                evlNum,
                cc,
                mlmc,
                xk,
                href: a?.getAttribute('href') || ''
            };
        })
        """
    )

    rows = []
    for item in row_data:
        detail_url = abs_url(page.url, item.get("href", ""))
        rows.append({
            "专业名称": clean_text(item.get("zymc", "")),
            "综合满意度": clean_text(item.get("score", "")),
            "综合满意度评价人数": parse_count_text(item.get("evlNum", "")),
            "学历层次": clean_text(item.get("cc", "")),
            "门类": clean_text(item.get("mlmc", "")),
            "专业类": clean_text(item.get("xk", "")),
            "specId": parse_spec_id(detail_url),
            "详情页": detail_url,
            "列表来源页": list_url,
            "页码": page_no,
        })

    return [x for x in rows if x["专业名称"] and x["详情页"]]


def parse_top_info(detail_page, major_row):
    title = ""
    title_locator = detail_page.locator(".zy-title h1")
    if title_locator.count():
        title = clean_text(title_locator.first.inner_text())

    if not title:
        title = major_row.get("专业名称", "")

    return {
        "标题": title,
        "来源 URL": major_row.get("详情页", ""),
        "抓取时间": iso_now(),
    }


def parse_basic_info(detail_page):
    intro = ""
    intro_locator = detail_page.locator(".zydc-detail-part .zyjs-desc-text")
    if intro_locator.count():
        intro = clean_text(intro_locator.first.inner_text())

    cutoff = ""
    graduate_scale = ""

    body_blocks = detail_page.locator(".zydc-detail-part")
    for i in range(body_blocks.count()):
        part = body_blocks.nth(i)
        title = ""
        title_locator = part.locator(".part-head .head-title")
        if title_locator.count():
            title = clean_text(title_locator.first.inner_text())

        if "统计信息" in title:
            cutoff = parse_data_cutoff(title)
            grey_box = part.locator(".tjxx .zydc-grey-box")
            if grey_box.count():
                graduate_scale = clean_text(grey_box.first.inner_text())
            break

    return {
        "专业介绍": intro,
        "统计信息": {
            "数据统计截止日期": cutoff,
            "全国普通高校毕业生规模": graduate_scale,
        },
    }


def click_tab(page, tab_text):
    candidates = [
        page.locator(".catalog-bar-container .bar-item", has_text=tab_text),
        page.locator(".bar-item", has_text=tab_text),
        page.locator(f"text={tab_text}"),
    ]

    for locator in candidates:
        if locator.count() == 0:
            continue
        try:
            locator.first.click(timeout=5000)
            page.wait_for_timeout(1500)
            return True
        except Exception:
            continue
    return False


def extract_links_in_section(section) -> List[Tuple[str, str]]:
    items = []
    anchors = section.locator("a")
    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if text and href:
            items.append((text, href))
    return items


def extract_courses(context, course_url):
    result = {
        "课程页 URL": course_url or "",
        "课程列表": [],
    }

    if not course_url:
        return result

    page = context.new_page()
    try:
        page.goto(course_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1800)
        return extract_courses_from_current_page(page)
    except Exception as e:
        result["error"] = repr(e)
        return result
    finally:
        page.close()


def extract_courses_from_current_page(page):
    result = {
        "课程页 URL": page.url,
        "课程列表": [],
    }

    try:
        page.wait_for_selector(".zydc-kskc-table tbody tr", timeout=10000)

        rows = page.locator(".zydc-kskc-table tbody tr").evaluate_all(
            """
            rows => rows.map(tr => {
                const courseName =
                    tr.querySelector('td:nth-child(1) .zy')?.innerText?.trim() ||
                    tr.querySelector('td:nth-child(1) span')?.innerText?.trim() ||
                    tr.querySelector('td:nth-child(1)')?.innerText?.trim() || '';

                const likes =
                    tr.querySelector('td:nth-child(2) .dz-content span:last-child')?.innerText?.trim() ||
                    tr.querySelector('td:nth-child(2) span:last-child')?.innerText?.trim() ||
                    tr.querySelector('td:nth-child(2)')?.innerText?.trim() || '';

                const diffScore =
                    tr.querySelector('td:nth-child(3) input[type="hidden"]')?.value?.trim() || '';
                const diffCount =
                    tr.querySelector('td:nth-child(3) span:last-child')?.innerText?.trim() || '';

                const practicalScore =
                    tr.querySelector('td:nth-child(4) input[type="hidden"]')?.value?.trim() || '';
                const practicalCount =
                    tr.querySelector('td:nth-child(4) span:last-child')?.innerText?.trim() || '';

                return {
                    courseName,
                    likes,
                    diffScore,
                    diffCount,
                    practicalScore,
                    practicalCount
                };
            })
            """
        )

        for row in rows:
            course_name = clean_text(row.get("courseName", ""))
            if not course_name or "课程名称" in course_name:
                continue

            result["课程列表"].append({
                "课程名称": course_name,
                "点赞数": re.sub(r"[^\d]", "", clean_text(row.get("likes", ""))),
                "难易度评分": clean_text(row.get("diffScore", "")),
                "难易度人数": re.sub(r"[^\d]", "", clean_text(row.get("diffCount", ""))),
                "实用性评分": clean_text(row.get("practicalScore", "")),
                "实用性人数": re.sub(r"[^\d]", "", clean_text(row.get("practicalCount", ""))),
            })

        result["课程列表"] = unique_text_items(result["课程列表"], key="课程名称")
        return result

    except Exception as e:
        result["error"] = repr(e)
        return result


def parse_image_urls_by_keywords(page, keywords):
    result = []
    imgs = page.locator("img")
    for i in range(imgs.count()):
        img = imgs.nth(i)
        src = img.get_attribute("src") or ""
        alt = img.get_attribute("alt") or ""
        all_text = f"{src} {alt}"
        if any(k in all_text for k in keywords):
            result.append(urljoin(page.url, src))
    dedup = []
    seen = set()
    for x in result:
        if x and x not in seen:
            seen.add(x)
            dedup.append(x)
    return dedup


def extract_graduated_development(context, dev_url):
    result = {
        "考研方向": [],
        "升学指数图片链接": "",
        "相关专业图片链接列表": [],
        "从业情况": {
            "在校生期望从业方向": [],
            "已毕业人员从业方向": [],
            "已毕业学生创业方向": [],
        },
        "薪酬指数图片链接": "",
        "已毕业学生主要就业省份图片链接": "",
        "来源页": dev_url or "",
    }

    if not dev_url:
        return result

    page = context.new_page()
    try:
        page.goto(dev_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1800)
        return extract_graduated_development_from_current_page(page)
    except Exception as e:
        result["error"] = repr(e)
        return result
    finally:
        page.close()


def extract_graduated_development_from_current_page(page):
    result = {
        "考研方向": [],
        "升学指数图片链接": "",
        "相关专业图片链接列表": [],
        "从业情况": {
            "在校生期望从业方向": [],
            "已毕业人员从业方向": [],
            "已毕业学生创业方向": [],
        },
        "薪酬指数图片链接": "",
        "已毕业学生主要就业省份图片链接": "",
        "来源页": page.url,
    }

    try:
        page.wait_for_timeout(1200)
        parts = page.locator(".zydc-detail-part")

        for i in range(parts.count()):
            part = parts.nth(i)

            title = ""
            title_locator = part.locator(".part-head .head-title")
            if title_locator.count():
                title = clean_text(title_locator.first.inner_text())

            if "考研方向" in title:
                for text, href in extract_links_in_section(part):
                    full = urljoin(page.url, href)
                    if "yz.chsi.com.cn" in full:
                        result["考研方向"].append({
                            "专业": text,
                            "专业链接": full,
                        })

            elif "升学指数" in title:
                imgs = part.locator("img")
                if imgs.count():
                    src = imgs.first.get_attribute("src") or ""
                    result["升学指数图片链接"] = urljoin(page.url, src)

            elif "从业情况" in title:
                sub_titles = part.locator("h5")
                zhiy_lists = part.locator(".zhiy-list")

                for j in range(min(sub_titles.count(), zhiy_lists.count())):
                    sub_title = clean_text(sub_titles.nth(j).inner_text())
                    block = zhiy_lists.nth(j)
                    items = []

                    anchors = block.locator("a")
                    for k in range(anchors.count()):
                        a = anchors.nth(k)
                        text = clean_text(a.inner_text())
                        href = a.get_attribute("href") or ""
                        if not text or not href:
                            continue
                        items.append({
                            "职业": text,
                            "职业链接": urljoin(page.url, href),
                        })

                    if "在校生期望从业方向" in sub_title:
                        result["从业情况"]["在校生期望从业方向"] = unique_links(items)
                    elif "已毕业人员从业方向" in sub_title:
                        result["从业情况"]["已毕业人员从业方向"] = unique_links(items)

                page_text = clean_text(part.inner_text())
                startup_matches = re.findall(r"创业方向[:：]?\s*([^\n]+)", page_text)
                startups = []
                for item in startup_matches:
                    parts2 = re.split(r"[、，,；; ]+", item)
                    for p in parts2:
                        p = clean_text(p)
                        if p:
                            startups.append({"行业名称": p})
                result["从业情况"]["已毕业学生创业方向"] = unique_text_items(
                    startups, key="行业名称"
                )

            elif "薪酬指数" in title:
                imgs = part.locator("img")
                if imgs.count():
                    src = imgs.first.get_attribute("src") or ""
                    result["薪酬指数图片链接"] = urljoin(page.url, src)

            elif "已毕业学生主要就业省份" in title:
                imgs = part.locator("img")
                if imgs.count():
                    src = imgs.first.get_attribute("src") or ""
                    result["已毕业学生主要就业省份图片链接"] = urljoin(page.url, src)

            elif "相关专业" in title:
                imgs = part.locator("img")
                for j in range(imgs.count()):
                    src = imgs.nth(j).get_attribute("src") or ""
                    full = urljoin(page.url, src)
                    if full:
                        result["相关专业图片链接列表"].append(full)

        result["相关专业图片链接列表"] = list(
            dict.fromkeys(result["相关专业图片链接列表"])
        )
        result["考研方向"] = unique_links(result["考研方向"])
        return result

    except Exception as e:
        result["error"] = repr(e)
        return result


def extract_major_detail(context, major_row):
    detail_url = major_row.get("详情页", "")
    detail = {
        "顶部信息": {
            "标题": major_row.get("专业名称", ""),
            "来源 URL": detail_url,
            "抓取时间": iso_now(),
        },
        "basic_info": {
            "专业介绍": "",
            "统计信息": {
                "数据统计截止日期": "",
                "全国普通高校毕业生规模": "",
            },
        },
        "courses": {
            "课程页 URL": "",
            "课程列表": [],
        },
        "graduated_development": {
            "考研方向": [],
            "升学指数图片链接": "",
            "相关专业图片链接列表": [],
            "从业情况": {
                "在校生期望从业方向": [],
                "已毕业人员从业方向": [],
                "已毕业学生创业方向": [],
            },
            "薪酬指数图片链接": "",
            "已毕业学生主要就业省份图片链接": "",
            "来源页": "",
        },
    }

    if not detail_url:
        detail["error"] = "missing_detail_url"
        return detail

    page = context.new_page()
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".zy-title h1", timeout=30000)
        page.wait_for_timeout(1500)

        detail["顶部信息"] = parse_top_info(page, major_row)
        detail["basic_info"] = parse_basic_info(page)

        if click_tab(page, "开设课程"):
            detail["courses"] = extract_courses_from_current_page(page)

        if click_tab(page, "毕业发展"):
            detail["graduated_development"] = extract_graduated_development_from_current_page(page)

        return detail

    except Exception as e:
        detail["error"] = repr(e)
        return detail
    finally:
        page.close()