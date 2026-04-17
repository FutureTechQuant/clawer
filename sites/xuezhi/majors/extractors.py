import re
from urllib.parse import urljoin

from sites.core.utils import clean_text, iso_now
from .parsers import (
    abs_url,
    parse_count_text,
    parse_data_cutoff,
    parse_metric_cell_text,
    parse_qs_value,
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

    title_blocks = detail_page.locator(".zydc-detail-part .part-head")
    body_blocks = detail_page.locator(".zydc-detail-part")
    for i in range(body_blocks.count()):
        part = body_blocks.nth(i)
        title = clean_text(part.locator(".part-head .head-title").first.inner_text()) if part.locator(".part-head .head-title").count() else ""
        if "统计信息" in title:
            cutoff = parse_data_cutoff(title)
            if part.locator(".tjxx .zydc-grey-box").count():
                graduate_scale = clean_text(part.locator(".tjxx .zydc-grey-box").first.inner_text())
            break

    return {
        "专业介绍": intro,
        "统计信息": {
            "数据统计截止日期": cutoff,
            "全国普通高校毕业生规模": graduate_scale,
        },
    }


def parse_tab_links(detail_page):
    result = {
        "基本信息": "",
        "开设院校": "",
        "开设课程": "",
        "毕业发展": "",
    }

    anchors = detail_page.locator("a")
    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if not href:
            continue

        full = urljoin(detail_page.url, href)

        if text in result and not result[text]:
            result[text] = full

    return result


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

        course_rows = []

        candidate_selectors = [
            ".course-table tbody tr",
            ".ivu-table-body tbody tr",
            "table tbody tr",
            ".course-list .course-item",
        ]

        for selector in candidate_selectors:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue

            if "tr" in selector:
                rows = locator.evaluate_all(
                    """
                    rows => rows.map(tr => {
                        const tds = Array.from(tr.querySelectorAll('td'));
                        return {
                            texts: tds.map(td => (td.innerText || '').trim())
                        };
                    })
                    """
                )
                if rows:
                    for row in rows:
                        texts = row.get("texts", [])
                        if not texts:
                            continue

                        course_name = clean_text(texts[0]) if len(texts) > 0 else ""
                        likes = ""
                        difficulty = {"评分": "", "人数": ""}
                        practical = {"评分": "", "人数": ""}

                        if len(texts) > 1:
                            likes = re.sub(r"[^\d]", "", texts[1])
                        if len(texts) > 2:
                            difficulty = parse_metric_cell_text(texts[2])
                        if len(texts) > 3:
                            practical = parse_metric_cell_text(texts[3])

                        if course_name and "课程名称" not in course_name:
                            course_rows.append({
                                "课程名称": course_name,
                                "点赞数": likes,
                                "难易度评分": difficulty["评分"],
                                "难易度人数": difficulty["人数"],
                                "实用性评分": practical["评分"],
                                "实用性人数": practical["人数"],
                            })
                if course_rows:
                    break

        result["课程列表"] = unique_text_items(course_rows, key="课程名称")
        return result

    except Exception as e:
        result["error"] = repr(e)
        return result
    finally:
        page.close()


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

        anchors = page.locator("a")
        postgraduate = []
        occupations_expect = []
        occupations_graduated = []

        for i in range(anchors.count()):
            a = anchors.nth(i)
            text = clean_text(a.inner_text())
            href = a.get_attribute("href") or ""
            if not text or not href:
                continue

            full = urljoin(page.url, href)

            if "yz.chsi.com.cn" in full and ("specialityDetail" in full or "zy" in full):
                postgraduate.append({
                    "专业": text,
                    "专业链接": full,
                })

            if "/career/" in full or "/occupation/" in full or "job" in full:
                item = {
                    "职业": text,
                    "职业链接": full,
                }
                occupations_expect.append(item)
                occupations_graduated.append(item)

        result["考研方向"] = unique_links(postgraduate)

        imgs = page.locator("img")
        for i in range(imgs.count()):
            img = imgs.nth(i)
            src = img.get_attribute("src") or ""
            alt = clean_text(img.get_attribute("alt") or "")
            full = urljoin(page.url, src)

            combined = f"{src} {alt}"

            if not result["升学指数图片链接"] and ("升学" in combined or "sxzs" in combined):
                result["升学指数图片链接"] = full

            if not result["薪酬指数图片链接"] and ("薪酬" in combined or "xczs" in combined):
                result["薪酬指数图片链接"] = full

            if not result["已毕业学生主要就业省份图片链接"] and ("省份" in combined or "就业省份" in combined):
                result["已毕业学生主要就业省份图片链接"] = full

            if "相关专业" in combined or "xgzy" in combined:
                result["相关专业图片链接列表"].append(full)

        result["相关专业图片链接列表"] = list(dict.fromkeys(result["相关专业图片链接列表"]))

        result["从业情况"]["在校生期望从业方向"] = unique_links(occupations_expect)
        result["从业情况"]["已毕业人员从业方向"] = unique_links(occupations_graduated)

        page_text = clean_text(page.locator("body").inner_text())
        startup_matches = re.findall(r"创业方向[:：]?\s*([^\n]+)", page_text)
        startups = []
        for item in startup_matches:
            parts = re.split(r"[、，,；; ]+", item)
            for p in parts:
                p = clean_text(p)
                if p:
                    startups.append({"行业名称": p})
        result["从业情况"]["已毕业学生创业方向"] = unique_text_items(startups, key="行业名称")

        return result

    except Exception as e:
        result["error"] = repr(e)
        return result
    finally:
        page.close()


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
        },
    }

    if not detail_url:
        detail["error"] = "missing_detail_url"
        return detail

    page = context.new_page()
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".zy-title h1", timeout=30000)
        page.wait_for_timeout(1200)

        detail["顶部信息"] = parse_top_info(page, major_row)
        detail["basic_info"] = parse_basic_info(page)

        tab_links = parse_tab_links(page)
        course_url = tab_links.get("开设课程", "")
        dev_url = tab_links.get("毕业发展", "")

        detail["courses"] = extract_courses(context, course_url)
        detail["graduated_development"] = extract_graduated_development(context, dev_url)

        return detail

    except Exception as e:
        detail["error"] = repr(e)
        return detail
    finally:
        page.close()