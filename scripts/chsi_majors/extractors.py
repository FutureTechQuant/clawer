from urllib.parse import urljoin

from .config import BASE_URL, NAV_BLACKLIST, SECTION_ORDER, SCHOOL_NAME_RE
from .parsers import (
    extract_section,
    find_title_and_level,
    parse_data_cutoff,
    parse_employment_directions,
    parse_field,
    parse_graduates_scale,
    parse_links_from_page,
    parse_nearby_majors,
    parse_postgraduate_links,
    parse_recommended_schools,
    parse_satisfaction_items,
)
from .utils import clean_text, extract_spec_id, iso_now, normalize_lines


def extract_table_rows(page, level_name, discipline, major_class):
    row_data = page.locator(".zyk-table-con .ivu-table-body tbody tr").evaluate_all(
        """
        rows => rows.map(tr => {
            const tds = Array.from(tr.querySelectorAll('td'));
            const majorA = tds[0]?.querySelector('a');
            const schoolA = tds[2]?.querySelector('a');

            return {
                cell_count: tds.length,
                major_name: (tds[0]?.innerText || '').trim(),
                major_code: (tds[1]?.innerText || '').trim(),
                school_text: (tds[2]?.innerText || '').trim(),
                satisfaction: (tds[3]?.innerText || '').trim(),
                detail_href: majorA?.getAttribute('href') || '',
                school_href: schoolA?.getAttribute('href') || '',
            };
        })
        """
    )

    rows = []
    for item in row_data:
        if item.get("cell_count", 0) < 4:
            continue

        major_name = clean_text(item.get("major_name", ""))
        major_code = clean_text(item.get("major_code", ""))
        school_text = clean_text(item.get("school_text", ""))
        satisfaction = clean_text(item.get("satisfaction", ""))

        if not major_name or "暂无" in major_name:
            continue

        detail_href = urljoin(BASE_URL, item.get("detail_href", "")) if item.get("detail_href") else ""
        school_href = urljoin(BASE_URL, item.get("school_href", "")) if item.get("school_href") else ""

        spec_id = extract_spec_id(detail_href, school_href)
        if not school_href and spec_id:
            school_href = f"https://gaokao.chsi.com.cn/zyk/zybk/ksyxPage?specId={spec_id}"

        rows.append({
            "培养层次": level_name,
            "门类": discipline,
            "专业类": major_class,
            "专业名称": major_name,
            "专业代码": major_code,
            "专业满意度": satisfaction,
            "开设院校文本": school_text,
            "详情页": detail_href,
            "开设院校页": school_href,
            "specId": spec_id,
        })

    return rows


def extract_detail(context, major_row):
    if not major_row["详情页"]:
        return {
            "error": "missing_detail_url",
            "抓取时间": iso_now(),
        }

    current_spec_id = major_row.get("specId", "")
    detail_page = context.new_page()
    try:
        detail_page.goto(major_row["详情页"], wait_until="domcontentloaded", timeout=60000)
        detail_page.wait_for_timeout(1500)
        text = detail_page.locator("body").inner_text(timeout=30000)
        lines = normalize_lines(text)

        title_guess, level_guess = find_title_and_level(lines)
        code = parse_field(text, "专业代码")
        discipline = parse_field(text, "门类")
        major_class = parse_field(text, "专业类")

        link_map, other_links = parse_links_from_page(detail_page)

        section_map = {}
        for heading in SECTION_ORDER:
            section_map[heading] = extract_section(lines, heading, SECTION_ORDER)

        stats_lines = section_map["统计信息"]["lines"]
        salary_lines = section_map["薪酬指数"]["lines"]

        detail = {
            "标题": title_guess or major_row.get("专业名称", ""),
            "培养层次": level_guess or major_row.get("培养层次", ""),
            "专业代码": code or major_row.get("专业代码", ""),
            "门类": discipline or major_row.get("门类", ""),
            "专业类": major_class or major_row.get("专业类", ""),
            "链接": {
                "详情页": major_row["详情页"],
                "基本信息": link_map.get("基本信息", major_row["详情页"]),
                "开设院校": link_map.get("开设院校", major_row.get("开设院校页", "")),
                "开设课程": link_map.get("开设课程", ""),
                "专业解读": link_map.get("专业解读", ""),
                "图解专业": link_map.get("图解专业", ""),
                "选科要求": link_map.get("选科要求", ""),
            },
            "专业介绍": section_map["专业介绍"]["raw_text"],
            "统计信息": {
                "数据统计截止日期": parse_data_cutoff(section_map["统计信息"]["raw_text"]),
                "全国普通高校毕业生规模": parse_graduates_scale(stats_lines),
                "专业满意度": parse_satisfaction_items(section_map["统计信息"]["raw_text"] + "\n" + text),
                "原始文本": section_map["统计信息"]["raw_text"],
            },
            "相近专业": parse_nearby_majors(detail_page, current_spec_id),
            "本专业推荐人数较多的高校": {
                "原始文本": section_map["本专业推荐人数较多的高校"]["raw_text"],
                "学校列表": parse_recommended_schools(section_map["本专业推荐人数较多的高校"]["lines"]),
            },
            "考研方向": parse_postgraduate_links(detail_page),
            "已毕业人员从业方向": {
                "原始文本": section_map["已毕业人员从业方向"]["raw_text"],
                "列表": parse_employment_directions(section_map["已毕业人员从业方向"]["lines"]),
            },
            "薪酬指数": {
                "原始文本": section_map["薪酬指数"]["raw_text"],
                "列表": salary_lines,
            },
            "其他链接": other_links,
            "抓取时间": iso_now(),
        }
        return detail
    except Exception as e:
        return {
            "error": repr(e),
            "详情页": major_row["详情页"],
            "抓取时间": iso_now(),
        }
    finally:
        detail_page.close()


def extract_school_rows(context, major_row):
    if not major_row["开设院校页"]:
        return {
            "来源页": "",
            "学校数量": 0,
            "学校列表": [],
            "error": "missing_school_url",
        }

    page = context.new_page()
    school_rows = []
    seen = set()

    try:
        page.goto(major_row["开设院校页"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1800)

        page_no = 1
        while True:
            anchors = page.locator("a")
            for i in range(anchors.count()):
                a = anchors.nth(i)
                text = clean_text(a.inner_text())
                href = a.get_attribute("href") or ""

                if not text or text in NAV_BLACKLIST:
                    continue
                if not SCHOOL_NAME_RE.search(text):
                    continue

                key = text
                if key in seen:
                    continue
                seen.add(key)

                school_rows.append({
                    "学校名称": text,
                    "学校链接": urljoin(page.url, href) if href else "",
                    "页码": page_no,
                })

            next_btn = page.locator(".ivu-page-next:not(.ivu-page-disabled)")
            if next_btn.count() == 0:
                break

            next_btn.first.click()
            page.wait_for_timeout(1000)
            page_no += 1

        return {
            "来源页": major_row["开设院校页"],
            "学校数量": len(school_rows),
            "学校列表": school_rows,
        }
    except Exception as e:
        return {
            "来源页": major_row["开设院校页"],
            "学校数量": len(school_rows),
            "学校列表": school_rows,
            "error": repr(e),
        }
    finally:
        page.close()
