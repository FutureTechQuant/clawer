from urllib.parse import urljoin

from sites.core.utils import clean_text, extract_spec_id
from sites.chsi.common.config import BASE_URL


def extract_major_list_rows(page, level_name="", discipline="", major_class=""):
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

        detail_url = urljoin(BASE_URL, item.get("detail_href", "")) if item.get("detail_href") else ""
        rows.append({
            "培养层次": level_name,
            "门类": discipline,
            "专业类": major_class,
            "专业名称": clean_text(item.get("major_name", "")),
            "专业代码": clean_text(item.get("major_code", "")),
            "专业满意度": clean_text(item.get("satisfaction", "")),
            "specId": extract_spec_id(detail_url),
            "详情页": detail_url,
        })
    return rows


def extract_major_detail(context, row):
    return {
        "顶部信息": {
            "标题": row.get("专业名称", ""),
            "专业代码标签": row.get("专业代码", ""),
            "标签列表": [x for x in [row.get("培养层次", ""), row.get("门类", ""), row.get("专业类", "")] if x],
            "来源 URL": row.get("详情页", ""),
        },
        "basic_info": {},
        "courses": {},
    }