import re
from urllib.parse import urljoin

from sites.core.utils import clean_text, iso_now
from .parsers import (
    abs_url,
    parse_count_text,
    parse_data_cutoff,
    parse_metric_cell_text,
    parse_spec_id,
    unique_links,
    unique_text_items,
)


TAB_INDEX_MAP = {
    "基本信息": 0,
    "开设院校": 1,
    "开设课程": 2,
    "毕业发展": 3,
}


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


def switch_detail_tab(page, tab_name):
    tab_index = TAB_INDEX_MAP.get(tab_name)
    if tab_index is None:
        return False

    selectors = [
        ".catalog-bar-container .bar-item",
        ".zydc-detail-catalog .bar-item",
        ".bar-item",
    ]

    for selector in selectors:
        tabs = page.locator(selector)
        if tabs.count() <= tab_index:
            continue

        try:
            target = tabs.nth(tab_index)
            target.scroll_into_view_if_needed()
            try:
                target.click(timeout=5000)
            except Exception:
                target.dispatch_event("click")

            page.wait_for_timeout(1200)
            return True
        except Exception:
            continue

    return False


def extract_courses_from_current_page(page, source_url):
    result = {
        "课程页 URL": source_url or "",
        "课程列表": [],
    }

    try:
        candidate_selectors = [
            ".zydc-kskc-table tbody tr",
            "table.zydc-kskc-table tbody tr",
            ".xz-zydc-list table tbody tr",
            "table tbody tr",
        ]

        course_rows = []

        for selector in candidate_selectors:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue

            rows = locator.evaluate_all(
                """
                rows => rows.map(tr => {
                    const tds = Array.from(tr.querySelectorAll('td'));
                    return {
                        course_name: (tds[0]?.innerText || '').trim(),
                        likes_text: (tds[1]?.innerText || '').trim(),
                        difficulty_text: (tds[2]?.innerText || '').trim(),
                        practical_text: (tds[3]?.innerText || '').trim(),
                    };
                })
                """
            )

            for row in rows:
                course_name = clean_text(row.get("course_name", ""))
                if not course_name or "课程名称" in course_name:
                    continue

                likes = re.sub(r"[^\d]", "", clean_text(row.get("likes_text", "")))
                difficulty = parse_metric_cell_text(row.get("difficulty_text", ""))
                practical = parse_metric_cell_text(row.get("practical_text", ""))

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


def extract_graduated_development_from_current_page(page, source_url):
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
        "来源页": source_url or "",
    }

    try:
        part_data = page.locator(".zydc-detail-part").evaluate_all(
            """
            parts => parts.map(part => {
                const title = part.querySelector('.part-head .head-title')?.innerText?.trim() || '';
                const text = part.innerText || '';
                const images = Array.from(part.querySelectorAll('img')).map(img => ({
                    src: img.getAttribute('src') || '',
                    alt: img.getAttribute('alt') || ''
                }));
                const links = Array.from(part.querySelectorAll('a')).map(a => ({
                    text: a.innerText?.trim() || '',
                    href: a.getAttribute('href') || ''
                }));
                return { title, text, images, links };
            })
            """
        )

        postgraduate = []
        occupations_expect = []
        occupations_graduated = []
        startups = []
        related_images = []

        for part in part_data:
            title = clean_text(part.get("title", ""))
            text = clean_text(part.get("text", ""))
            images = part.get("images", []) or []
            links = part.get("links", []) or []

            combined = f"{title}\n{text}"

            for link in links:
                link_text = clean_text(link.get("text", ""))
                href = abs_url(page.url, link.get("href", ""))

                if not href:
                    continue

                if "yz.chsi.com.cn" in href:
                    postgraduate.append({
                        "专业": link_text,
                        "专业链接": href,
                    })

                if (
                    "careeroccudetail.action" in href
                    or "careerspecrecocc.action" in href
                    or "occu" in href
                    or "career" in href
                ):
                    item = {
                        "职业": link_text,
                        "职业链接": href,
                    }

                    if "在校" in combined or "期望" in combined:
                        occupations_expect.append(item)
                    elif "已毕业" in combined or "毕业后" in combined:
                        occupations_graduated.append(item)
                    else:
                        occupations_expect.append(item)
                        occupations_graduated.append(item)

            image_urls = []
            for img in images:
                src = img.get("src", "")
                if src:
                    image_urls.append(abs_url(page.url, src))

            if image_urls:
                if (not result["升学指数图片链接"]) and ("升学" in combined or "考研" in combined):
                    result["升学指数图片链接"] = image_urls[0]

                if (not result["薪酬指数图片链接"]) and ("薪酬" in combined or "薪资" in combined):
                    result["薪酬指数图片链接"] = image_urls[0]

                if (not result["已毕业学生主要就业省份图片链接"]) and ("省份" in combined or "就业省份" in combined):
                    result["已毕业学生主要就业省份图片链接"] = image_urls[0]

                if "相关专业" in combined:
                    related_images.extend(image_urls)

            startup_matches = re.findall(r"创业方向[:：]?\s*([^\n]+)", combined)
            for item in startup_matches:
                parts = re.split(r"[、，,；; /]+", item)
                for p in parts:
                    p = clean_text(p)
                    if p:
                        startups.append({"行业名称": p})

        if not result["升学指数图片链接"]:
            imgs = parse_image_urls_by_keywords(page, ["升学", "sx", "study"])
            if imgs:
                result["升学指数图片链接"] = imgs[0]

        if not result["薪酬指数图片链接"]:
            imgs = parse_image_urls_by_keywords(page, ["薪酬", "薪资", "xc"])
            if imgs:
                result["薪酬指数图片链接"] = imgs[0]

        if not result["已毕业学生主要就业省份图片链接"]:
            imgs = parse_image_urls_by_keywords(page, ["省份", "就业省份"])
            if imgs:
                result["已毕业学生主要就业省份图片链接"] = imgs[0]

        if not related_images:
            related_images = parse_image_urls_by_keywords(page, ["相关专业", "xgzy"])

        result["考研方向"] = unique_links(postgraduate)
        result["相关专业图片链接列表"] = list(dict.fromkeys([x for x in related_images if x]))
        result["从业情况"]["在校生期望从业方向"] = unique_links(occupations_expect)
        result["从业情况"]["已毕业人员从业方向"] = unique_links(occupations_graduated)
        result["从业情况"]["已毕业学生创业方向"] = unique_text_items(startups, key="行业名称")

        return result

    except Exception as e:
        result["error"] = repr(e)
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
        return extract_all_courses_from_current_page(page, course_url)

    except Exception as e:
        result["error"] = repr(e)
        return result
    finally:
        page.close()

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
        return extract_graduated_development_from_current_page(page, dev_url)

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
        page.wait_for_timeout(1200)

        detail["顶部信息"] = parse_top_info(page, major_row)
        detail["basic_info"] = parse_basic_info(page)

        course_done = False
        dev_done = False

        if switch_detail_tab(page, "开设课程"):
            detail["courses"] = extract_all_courses_from_current_page(page, f"{detail_url}#courses")
            course_done = bool(detail["courses"].get("课程列表"))

        if switch_detail_tab(page, "毕业发展"):
            detail["graduated_development"] = extract_graduated_development_from_current_page(
                page, f"{detail_url}#graduated-development"
            )
            gd = detail["graduated_development"]
            dev_done = any([
                gd.get("考研方向"),
                gd.get("相关专业图片链接列表"),
                gd.get("从业情况", {}).get("在校生期望从业方向"),
                gd.get("从业情况", {}).get("已毕业人员从业方向"),
                gd.get("从业情况", {}).get("已毕业学生创业方向"),
                gd.get("升学指数图片链接"),
                gd.get("薪酬指数图片链接"),
                gd.get("已毕业学生主要就业省份图片链接"),
            ])

        if (not course_done) or (not dev_done):
            tab_links = parse_tab_links(page)

            if not course_done:
                course_url = tab_links.get("开设课程", "")
                if course_url:
                    detail["courses"] = extract_courses(context, course_url)

            if not dev_done:
                dev_url = tab_links.get("毕业发展", "")
                if dev_url:
                    detail["graduated_development"] = extract_graduated_development(context, dev_url)

        if not detail["courses"].get("课程页 URL"):
            detail["courses"]["课程页 URL"] = f"{detail_url}#courses"

        if not detail["graduated_development"].get("来源页"):
            detail["graduated_development"]["来源页"] = f"{detail_url}#graduated-development"

        return detail

    except Exception as e:
        detail["error"] = repr(e)
        return detail
    finally:
        page.close()

def click_inner_next_page(page, root_selector=None):
    next_selectors = []

    if root_selector:
        next_selectors.extend([
            f"{root_selector} .ivu-page-next",
            f"{root_selector} .ivu-page-next:not(.ivu-page-disabled)",
        ])

    next_selectors.extend([
        ".zydc-detail-part:visible .ivu-page-next",
        ".part-body:visible .ivu-page-next",
        ".xz-zydc-list:visible .ivu-page-next",
        ".ivu-page-next",
    ])

    next_btn = None
    for selector in next_selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            for i in range(locator.count()):
                try:
                    btn = locator.nth(i)
                    cls = btn.get_attribute("class") or ""
                    if "ivu-page-disabled" not in cls:
                        next_btn = btn
                        break
                except Exception:
                    continue
        if next_btn:
            break

    if not next_btn:
        return False

    before_text = ""
    first_row = page.locator(".zydc-kskc-table tbody tr").first
    if first_row.count():
        before_text = clean_text(first_row.inner_text())

    try:
        next_btn.scroll_into_view_if_needed()
    except Exception:
        pass

    try:
        next_btn.click(timeout=5000)
    except Exception:
        try:
            next_btn.dispatch_event("click")
        except Exception:
            return False

    page.wait_for_timeout(1200)

    try:
        page.wait_for_function(
            """
            (prevText) => {
                const first = document.querySelector('.zydc-kskc-table tbody tr');
                const txt = first ? (first.innerText || '').trim() : '';
                return txt && txt !== prevText;
            }
            """,
            arg=before_text,
            timeout=15000,
        )
    except Exception:
        page.wait_for_timeout(1200)

    return True


def extract_courses_from_current_page(page, source_url):
    result = {
        "课程页 URL": source_url or "",
        "课程列表": [],
    }

    try:
        candidate_selectors = [
            ".zydc-kskc-table tbody tr",
            "table.zydc-kskc-table tbody tr",
            ".xz-zydc-list table tbody tr",
            "table tbody tr",
        ]

        course_rows = []

        for selector in candidate_selectors:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue

            rows = locator.evaluate_all(
                """
                rows => rows.map(tr => {
                    const tds = Array.from(tr.querySelectorAll('td'));
                    return {
                        course_name: (tds[0]?.innerText || '').trim(),
                        likes_text: (tds[1]?.innerText || '').trim(),
                        difficulty_text: (tds[2]?.innerText || '').trim(),
                        practical_text: (tds[3]?.innerText || '').trim(),
                    };
                })
                """
            )

            for row in rows:
                course_name = clean_text(row.get("course_name", ""))
                if not course_name or "课程名称" in course_name:
                    continue

                likes = re.sub(r"[^\d]", "", clean_text(row.get("likes_text", "")))
                difficulty = parse_metric_cell_text(row.get("difficulty_text", ""))
                practical = parse_metric_cell_text(row.get("practical_text", ""))

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


def extract_all_courses_from_current_page(page, source_url):
    result = {
        "课程页 URL": source_url or "",
        "课程列表": [],
    }

    all_rows = []
    seen_page_signatures = set()
    max_pages = 200

    for _ in range(max_pages):
        current = extract_courses_from_current_page(page, source_url)
        rows = current.get("课程列表", [])

        if rows:
            signature = tuple(x.get("课程名称", "") for x in rows[:5])
            if signature in seen_page_signatures:
                break
            seen_page_signatures.add(signature)
            all_rows.extend(rows)

        moved = click_inner_next_page(page)
        if not moved:
            break

    result["课程列表"] = unique_text_items(all_rows, key="课程名称")
    return result