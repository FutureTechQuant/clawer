from sites.core.utils import clean_text


def split_department_text(text):
    text = clean_text(text)
    location = ""
    department = ""
    if text:
        parts = [clean_text(x) for x in text.split("|")]
        if parts:
            location = parts[0].replace("", "").strip()
        if len(parts) > 1:
            department = parts[1].replace("主管部门：", "").strip()
    return location, department


def split_level_text(text):
    text = clean_text(text)
    school_level = ""
    school_type = ""
    if text:
        parts = [clean_text(x) for x in text.split("|")]
        if parts:
            school_level = parts[0]
        if len(parts) > 1:
            school_type = parts[1]
    return school_level, school_type