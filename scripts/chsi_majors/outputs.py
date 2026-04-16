import json
from copy import deepcopy
from pathlib import Path

from .config import BASE_URL, OUTPUT_DIR, SAVE_DEBUG
from .utils import iso_now


def ensure_output():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_debug(page, name: str):
    if not SAVE_DEBUG:
        return
    try:
        page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=True)
    except Exception:
        pass
    try:
        (OUTPUT_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass


def write_partial(flat_majors):
    save_json(
        OUTPUT_DIR / "majors-flat.partial.json",
        {
            "抓取时间": iso_now(),
            "来源": BASE_URL,
            "数量": len(flat_majors),
            "专业列表": flat_majors,
        },
    )


def build_hierarchy(levels_data, flat_rows):
    level_map = {}

    for row in flat_rows:
        level_name = row["培养层次"]
        discipline_name = row["门类"]
        class_name = row["专业类"]

        if level_name not in level_map:
            level_map[level_name] = {
                "名称": level_name,
                "门类列表": {}
            }

        level_obj = level_map[level_name]
        if discipline_name not in level_obj["门类列表"]:
            level_obj["门类列表"][discipline_name] = {
                "门类": discipline_name,
                "专业类列表": {}
            }

        discipline_obj = level_obj["门类列表"][discipline_name]
        if class_name not in discipline_obj["专业类列表"]:
            discipline_obj["专业类列表"][class_name] = {
                "专业类": class_name,
                "专业列表": []
            }

        major_obj = deepcopy(row)
        discipline_obj["专业类列表"][class_name]["专业列表"].append(major_obj)

    final_levels = []
    for level_name in levels_data:
        if level_name not in level_map:
            final_levels.append({"名称": level_name, "门类列表": []})
            continue

        level_obj = level_map[level_name]
        disciplines = []
        for discipline_name, discipline_obj in level_obj["门类列表"].items():
            class_list = []
            for class_name, class_obj in discipline_obj["专业类列表"].items():
                class_list.append({
                    "专业类": class_name,
                    "专业列表": class_obj["专业列表"]
                })
            disciplines.append({
                "门类": discipline_name,
                "专业类列表": class_list
            })

        final_levels.append({
            "名称": level_name,
            "门类列表": disciplines
        })

    return final_levels
