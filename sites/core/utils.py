import json
import re
from datetime import datetime, timezone


def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()


def clean_text(text):
    if text is None:
        return ""
    return " ".join(str(text).split()).strip()


def normalize_lines(text):
    return [clean_text(x) for x in (text or "").splitlines() if clean_text(x)]


def unique_keep_order(items):
    seen = set()
    out = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def extract_spec_id(url: str):
    if not url:
        return ""
    m = re.search(r"specId=(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/detail/(\d+)", url)
    return m.group(1) if m else ""


def extract_sch_id(url: str):
    if not url:
        return ""
    m = re.search(r"schId-(\d+)", url)
    return m.group(1) if m else ""