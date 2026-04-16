import re
from urllib.parse import parse_qs, urljoin, urlparse

from .config import LEVEL_NAMES, NAV_BLACKLIST, SATISFACTION_LABELS, SCHOOL_NAME_RE
from .utils import clean_text, unique_keep_order


def find_title_and_level(lines):
    for i, line in enumerate(lines):
        if line in LEVEL_NAMES:
            title = lines[i - 1] if i > 0 else ""
            return title, line
    return "", ""


def parse_field(text, label):
    m = re.search(rf"{re.escape(label)}[:：]\s*([^\n]+)", text)
    return clean_text(m.group(1)) if m else ""


def extract_section(lines, heading, all_headings):
    try:
        start = lines.index(heading)
    except ValueError:
        return {"raw_text": "", "lines": []}

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i] in all_headings:
            end = i
            break

    content_lines = lines[start + 1:end]
    return {
        "raw_text": "\n".join(content_lines).strip(),
        "lines": content_lines,
    }


def parse_data_cutoff(text):
    m = re.search(r"数据统计截止日期[:：]\s*([^\n]+)", text)
    return clean_text(m.group(1)) if m else ""


def parse_graduates_scale(lines):
    for i, line in enumerate(lines):
        if "全国普通高校毕业生规模" in line:
            if i + 1 < len(lines):
                return clean_text(lines[i + 1])
    return ""


def parse_satisfaction_items(text):
    result = {}
    for label in SATISFACTION_LABELS:
        m = re.search(rf"{re.escape(label)}\s*([0-9.]+)\s*([0-9]+人)", text, re.S)
        result[label] = {
            "评分": clean_text(m.group(1)) if m else "",
            "人数": clean_text(m.group(2)) if m else "",
        }
    return result


def build_tag_list(level_name="", discipline="", major_class=""):
    return [x for x in [clean_text(level_name), clean_text(discipline), clean_text(major_class)] if x]


def parse_links_from_page(page):
    anchors = page.locator("a")
    links = {
        "基本信息": "",
        "开设院校": "",
        "开设课程": "",
        "专业解读": "",
        "图解专业": "",
        "选科要求": "",
    }
    other_links = []

    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if not text or not href:
            continue

        full = urljoin(page.url, href)
        if text in links and not links[text]:
            links[text] = full
        elif text not in NAV_BLACKLIST:
            other_links.append({"名称": text, "链接": full})

    return links, unique_keep_order(other_links)


def parse_nearby_majors(page, current_spec_id):
    anchors = page.locator("a")
    items = []
    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if not text or not href:
            continue

        full = urljoin(page.url, href)
        if "/zyk/zybk/detail/" not in full:
            continue

        sid = ""
        m = re.search(r"/detail/(\d+)", full)
        if m:
            sid = m.group(1)

        if sid and sid == current_spec_id:
            continue

        items.append({"名称": text})

    return unique_keep_order(items)


def parse_postgraduate_links(page):
    anchors = page.locator("a")
    items = []
    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if not text or not href:
            continue

        full = urljoin(page.url, href)
        if "yz.chsi.com.cn/zyk/specialityDetail.do" in full:
            items.append({
                "名称": text,
                "链接": full,
            })

    return unique_keep_order(items)


def parse_employment_directions(section_lines):
    raw = "".join(section_lines).strip()
    if not raw:
        return []

    parts = re.split(r"[、，,；;\s]+", raw)
    return [{"名称": x} for x in [clean_text(p) for p in parts] if x]


def parse_metric_cell(text):
    text = clean_text(text)
    score = ""
    count = ""

    m_score = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if m_score:
        score = m_score.group(1)

    m_count = re.search(r"([0-9]+)\s*人", text)
    if m_count:
        count = f"{m_count.group(1)}人"

    return {
        "评分": score,
        "人数": count,
    }


def parse_salary_image_url(page):
    try:
        src = page.evaluate(
            """
            () => {
                const toAbs = (u) => {
                    try { return new URL(u, location.href).href; } catch(e) { return u || ''; }
                };

                const imgs = Array.from(document.querySelectorAll('img'));
                for (const img of imgs) {
                    const src = img.getAttribute('src') || '';
                    const alt = img.getAttribute('alt') || '';
                    const text = `${src} ${alt}`;
                    if (/薪酬|salary/i.test(text)) return toAbs(src);
                }

                const nodes = Array.from(document.querySelectorAll('*'));
                for (const node of nodes) {
                    const txt = (node.innerText || '').trim();
                    if (txt === '薪酬指数') {
                        let cur = node;
                        for (let i = 0; i < 4 && cur; i++) {
                            const img = cur.querySelector && cur.querySelector('img');
                            if (img && img.getAttribute('src')) {
                                return toAbs(img.getAttribute('src'));
                            }
                            cur = cur.parentElement;
                        }
                    }
                }
                return '';
            }
            """
        )
        return clean_text(src)
    except Exception:
        return ""
