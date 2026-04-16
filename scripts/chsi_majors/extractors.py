from urllib.parse import urljoin

from .config import BASE_URL, SECTION_ORDER
from .parsers import (
    build_tag_list,
    extract_section,
    find_title_and_level,
    parse_data_cutoff,
    parse_employment_directions,
    parse_field,
    parse_graduates_scale,
    parse_links_from_page,
    parse_metric_cell,
    parse_nearby_majors,
    parse_postgraduate_links,
    parse_salary_image_url,
)
from .utils import clean_text, extract_spec_id, iso_now, normalize_lines


def extract_table_rows(page, level_name, discipline, major_class):
    row_data = page.locator(".zyk-table-con .ivu-table-body tbody tr").evaluate_all(
        """
        rows => rows.map(tr => {
            const tds = Array.from(tr.querySelectorAll('td'));
            const majorA = tds[0]?.querySelector('a');

            return {
                cell_count: tds.length,
                major_name: (tds[0]?.innerText || '').trim(),
                major_code: (tds[1]?.innerText || '').trim(),
                satisfaction: (tds[3]?.innerText || '').trim(),
                detail_href: majorA?.getAttribute('href') || '',
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
        satisfaction = clean_text(item.get("satisfaction", ""))

        if not major_name or "暂无" in major_name:
            continue

        detail_href = urljoin(BASE_URL, item.get("detail_href", "")) if item.get("detail_href") else ""
        spec_id = extract_spec_id(detail_href, "")

        rows.append({
            "培养层次": level_name,
            "门类": discipline,
            "专业类": major_class,
            "专业名称": major_name,
            "专业代码": major_code,
            "专业满意度": satisfaction,
            "specId": spec_id,
            "详情页": detail_href,
        })

    return rows


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
        page.wait_for_timeout(1500)

        rows = []
        for selector in [
            ".zyk-table-con .ivu-table-body tbody tr",
            "table tbody tr",
            ".ivu-table-body tbody tr",
        ]:
            locator = page.locator(selector)
            if locator.count() > 0:
                rows = locator.evaluate_all(
                    """
                    rows => rows.map(tr =>
                        Array.from(tr.querySelectorAll('td')).map(td => (td.innerText || '').trim())
                    )
                    """
                )
                if rows:
                    break

        course_list = []
        for cells in rows:
            if not cells or len(cells) < 3:
                continue

            course_name = clean_text(cells[0])
            difficulty = parse_metric_cell(cells[1] if len(cells) > 1 else "")
            practical = parse_metric_cell(cells[2] if len(cells) > 2 else "")

            if not course_name or "课程名称" in course_name:
                continue

            course_list.append({
                "课程名称": course_name,
                "难易度评分": difficulty["评分"],
                "难易度人数": difficulty["人数"],
                "实用性评分": practical["评分"],
                "实用性人数": practical["人数"],
            })

        result["课程列表"] = course_list
        return result

    except Exception as e:
        result["error"] = repr(e)
        return result
    finally:
        page.close()


def extract_detail(context, major_row):
    if not major_row["详情页"]:
        return {
            "顶部信息": {
                "标题": major_row.get("专业名称", ""),
                "专业代码标签": major_row.get("专业代码", ""),
                "标签列表": build_tag_list(
                    major_row.get("培养层次", ""),
                    major_row.get("门类", ""),
                    major_row.get("专业类", ""),
                ),
                "来源 URL": "",
                "抓取时间": iso_now(),
            },
            "basic_info": {
                "专业介绍": "",
                "统计信息": {
                    "数据截止日期": "",
                    "毕业生规模": "",
                },
                "相近专业": [],
                "考研方向": [],
                "就业方向": [],
                "薪酬指数图片链接": "",
            },
            "courses": {
                "课程页 URL": "",
                "课程列表": [],
            },
            "error": "missing_detail_url",
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

        link_map, _ = parse_links_from_page(detail_page)

        section_map = {}
        for heading in SECTION_ORDER:
            section_map[heading] = extract_section(lines, heading, SECTION_ORDER)

        stats_lines = section_map["统计信息"]["lines"]
        course_url = link_map.get("开设课程", "")
        courses = extract_courses(context, course_url)

        detail = {
            "顶部信息": {
                "标题": title_guess or major_row.get("专业名称", ""),
                "专业代码标签": code or major_row.get("专业代码", ""),
                "标签列表": build_tag_list(
                    level_guess or major_row.get("培养层次", ""),
                    discipline or major_row.get("门类", ""),
                    major_class or major_row.get("专业类", ""),
                ),
                "来源 URL": major_row["详情页"],
                "抓取时间": iso_now(),
            },
            "basic_info": {
                "专业介绍": section_map["专业介绍"]["raw_text"],
                "统计信息": {
                    "数据截止日期": parse_data_cutoff(section_map["统计信息"]["raw_text"]),
                    "毕业生规模": parse_graduates_scale(stats_lines),
                },
                "相近专业": parse_nearby_majors(detail_page, current_spec_id),
                "考研方向": parse_postgraduate_links(detail_page),
                "就业方向": parse_employment_directions(section_map["已毕业人员从业方向"]["lines"]),
                "薪酬指数图片链接": parse_salary_image_url(detail_page),
            },
            "courses": courses,
        }
        return detail

    except Exception as e:
        return {
            "顶部信息": {
                "标题": major_row.get("专业名称", ""),
                "专业代码标签": major_row.get("专业代码", ""),
                "标签列表": build_tag_list(
                    major_row.get("培养层次", ""),
                    major_row.get("门类", ""),
                    major_row.get("专业类", ""),
                ),
                "来源 URL": major_row["详情页"],
                "抓取时间": iso_now(),
            },
            "basic_info": {
                "专业介绍": "",
                "统计信息": {
                    "数据截止日期": "",
                    "毕业生规模": "",
                },
                "相近专业": [],
                "考研方向": [],
                "就业方向": [],
                "薪酬指数图片链接": "",
            },
            "courses": {
                "课程页 URL": "",
                "课程列表": [],
            },
            "error": repr(e),
        }
    finally:
        detail_page.close()
