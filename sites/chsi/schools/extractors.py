from urllib.parse import urljoin

from sites.core.utils import clean_text, extract_sch_id, iso_now
from sites.chsi.common.config import BASE_URL
from sites.chsi.common.selectors import (
    CHSI_SCHOOL_ADDRESS,
    CHSI_SCHOOL_ADMISSION,
    CHSI_SCHOOL_DEPARTMENT,
    CHSI_SCHOOL_FOLLOW,
    CHSI_SCHOOL_HEADER_NAME,
    CHSI_SCHOOL_IMAGE,
    CHSI_SCHOOL_LOCATION,
    CHSI_SCHOOL_PHONE,
    CHSI_SCHOOL_SITE,
    CHSI_SCHOOL_TYPE,
)
from .parsers import split_department_text, split_level_text


def parse_school_nav_links(page):
    links = {"学校首页": "", "学校简介": ""}
    anchors = page.locator(".yxxx-nav-box a")
    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if text in links and href and not links[text]:
            links[text] = urljoin(page.url, href)
    return links


def extract_school_list_rows(page, list_url, page_no):
    row_data = page.locator("#app-yxk-sch-list .sch-item").evaluate_all(
        """
        items => items.map(item => {
            const nameA = item.querySelector('.sch-title a.name');
            const img = item.querySelector('img');
            const deptA = item.querySelector('a.sch-department');
            const levelA = item.querySelector('a.sch-level');
            const scoreA = item.querySelector('.manyidu-star-box a.num');

            return {
                name: (nameA?.innerText || '').trim(),
                href: nameA?.getAttribute('href') || '',
                img: img?.getAttribute('src') || '',
                department_text: (deptA?.innerText || '').trim(),
                level_text: (levelA?.innerText || '').trim(),
                satisfaction: (scoreA?.innerText || '').trim(),
            };
        })
        """
    )

    schools = []
    for item in row_data:
        detail_url = urljoin(BASE_URL, item.get("href", ""))
        sch_id = extract_sch_id(detail_url)
        location, department = split_department_text(item.get("department_text", ""))
        school_level, school_type = split_level_text(item.get("level_text", ""))

        if not clean_text(item.get("name", "")):
            continue

        schools.append({
            "学校名称": clean_text(item.get("name", "")),
            "schId": sch_id,
            "详情页": detail_url,
            "学校图片": clean_text(item.get("img", "")),
            "主管部门": department,
            "院校所在地": location,
            "办学层次": school_level,
            "学校类型": school_type,
            "院校满意度": clean_text(item.get("satisfaction", "")),
            "列表来源页": list_url,
            "页码": page_no,
        })
    return schools


def extract_school_intro(context, intro_url):
    result = {
        "学校简介正文": "",
        "周边环境": "",
        "来源页": intro_url or "",
    }
    if not intro_url:
        return result

    page = context.new_page()
    try:
        page.goto(intro_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)

        body_text = clean_text(page.locator("body").inner_text(timeout=30000))
        result["学校简介正文"] = body_text
        return result
    except Exception as e:
        result["error"] = repr(e)
        return result
    finally:
        page.close()


def extract_school_detail(context, school_row):
    detail_url = school_row.get("详情页", "")
    if not detail_url:
        return {
            "顶部信息": {},
            "intro": {},
            "error": "missing_detail_url",
        }

    page = context.new_page()
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)

        nav_links = parse_school_nav_links(page)

        title = clean_text(page.locator(CHSI_SCHOOL_HEADER_NAME).first.inner_text()) if page.locator(CHSI_SCHOOL_HEADER_NAME).count() else school_row.get("学校名称", "")
        main_href = page.locator(CHSI_SCHOOL_HEADER_NAME).first.get_attribute("href") if page.locator(CHSI_SCHOOL_HEADER_NAME).count() else ""
        school_main_url = urljoin(page.url, main_href) if main_href else detail_url

        follow_count = clean_text(page.locator(CHSI_SCHOOL_FOLLOW).first.inner_text()) if page.locator(CHSI_SCHOOL_FOLLOW).count() else ""
        department = clean_text(page.locator(CHSI_SCHOOL_DEPARTMENT).first.inner_text()) if page.locator(CHSI_SCHOOL_DEPARTMENT).count() else school_row.get("主管部门", "")
        school_type_text = clean_text(page.locator(CHSI_SCHOOL_TYPE).first.inner_text()) if page.locator(CHSI_SCHOOL_TYPE).count() else school_row.get("学校类型", "")
        location = clean_text(page.locator(CHSI_SCHOOL_LOCATION).first.inner_text()) if page.locator(CHSI_SCHOOL_LOCATION).count() else school_row.get("院校所在地", "")
        address = clean_text(page.locator(CHSI_SCHOOL_ADDRESS).first.inner_text()) if page.locator(CHSI_SCHOOL_ADDRESS).count() else ""
        official_site = clean_text(page.locator(CHSI_SCHOOL_SITE).first.get_attribute("href") or "") if page.locator(CHSI_SCHOOL_SITE).count() else ""
        admission_site = clean_text(page.locator(CHSI_SCHOOL_ADMISSION).first.get_attribute("href") or "") if page.locator(CHSI_SCHOOL_ADMISSION).count() else ""
        official_phone = clean_text(page.locator(CHSI_SCHOOL_PHONE).first.inner_text()) if page.locator(CHSI_SCHOOL_PHONE).count() else ""
        school_img = clean_text(page.locator(CHSI_SCHOOL_IMAGE).first.get_attribute("src") or "") if page.locator(CHSI_SCHOOL_IMAGE).count() else school_row.get("学校图片", "")

        intro = extract_school_intro(context, nav_links.get("学校简介", ""))

        return {
            "顶部信息": {
                "标题": title,
                "学校主链接": school_main_url,
                "followCount": follow_count,
                "主管部门 / 主办单位": department,
                "院校类型文本": school_type_text,
                "所在地": location,
                "详细地址": address,
                "官方网站": official_site,
                "招生网址": admission_site,
                "官方电话": official_phone,
                "学校图片": school_img,
                "抓取时间": iso_now(),
            },
            "intro": {
                "学校简介正文": intro.get("学校简介正文", ""),
                "周边环境": intro.get("周边环境", ""),
            },
            "链接": nav_links,
        }
    except Exception as e:
        return {
            "顶部信息": {
                "标题": school_row.get("学校名称", ""),
                "学校主链接": detail_url,
                "followCount": "",
                "主管部门 / 主办单位": school_row.get("主管部门", ""),
                "院校类型文本": school_row.get("学校类型", ""),
                "所在地": school_row.get("院校所在地", ""),
                "详细地址": "",
                "官方网站": "",
                "招生网址": "",
                "官方电话": "",
                "学校图片": school_row.get("学校图片", ""),
                "抓取时间": iso_now(),
            },
            "intro": {
                "学校简介正文": "",
                "周边环境": "",
            },
            "error": repr(e),
        }
    finally:
        page.close()