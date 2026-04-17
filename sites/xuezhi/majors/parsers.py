# sites/xuezhi/majors/parsers.py
import re
from urllib.parse import parse_qs, urljoin, urlparse

from sites.core.utils import clean_text, unique_keep_order


LEVEL_NAMES = [
    "本科（普通教育）",
    "本科（职业教育）",
    "高职（专科）",
]


def parse_spec_id(url: str):
    if not url:
        return ""
    m = re.search(r"specId=([^&#]+)", url)
    return m.group(1) if m else ""


def parse_count_text(text: str):
    text = clean_text(text)
    m = re.search(r"([\d,]+)\s*人?", text)
    return m.group(1).replace(",", "") if m else ""


def parse_data_cutoff(text: str):
    text = clean_text(text)
    m = re.search(r"数据统计截止日期[:：]\s*([^\n]+)", text)
    return clean_text(m.group(1)) if m else ""


def parse_metric_cell_text(text: str):
    text = clean_text(text)
    score = ""
    count = ""

    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if nums:
        score = nums[0]

    m_count = re.search(r"([\d,]+)\s*人", text)
    if m_count:
        count = m_count.group(1).replace(",", "")
    elif len(nums) >= 2:
        count = nums[1].replace(",", "")

    return {
        "评分": score,
        "人数": count,
    }


def normalize_major_row(row: dict):
    return {
        "专业名称": clean_text(row.get("专业名称", "")),
        "综合满意度": clean_text(row.get("综合满意度", "")),
        "综合满意度评价人数": clean_text(row.get("综合满意度评价人数", "")),
        "学历层次": clean_text(row.get("学历层次", "")),
        "门类": clean_text(row.get("门类", "")),
        "专业类": clean_text(row.get("专业类", "")),
        "specId": clean_text(row.get("specId", "")),
        "详情页": clean_text(row.get("详情页", "")),
        "列表来源页": clean_text(row.get("列表来源页", "")),
        "页码": row.get("页码", 1),
    }


def abs_url(base_url: str, maybe_url: str):
    return urljoin(base_url, maybe_url or "")


def parse_qs_value(url: str, key: str):
    if not url:
        return ""
    try:
        return parse_qs(urlparse(url).query).get(key, [""])[0]
    except Exception:
        return ""


def unique_links(items):
    seen = set()
    out = []

    for item in items:
        name = clean_text(
            item.get("名称")
            or item.get("专业")
            or item.get("职业")
            or item.get("行业名称")
            or ""
        )
        link = clean_text(
            item.get("链接")
            or item.get("专业链接")
            or item.get("职业链接")
            or ""
        )

        if not name and not link:
            continue

        key = (name, link)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out

def unique_text_items(items, key="名称"):
    seen = set()
    out = []
    for item in items:
        value = clean_text(item.get(key, ""))
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(item)
    return out