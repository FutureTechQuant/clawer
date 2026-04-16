import json
from pathlib import Path


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_partial(path, rows, source=""):
    save_json(
        path,
        {
            "来源": source,
            "数量": len(rows),
            "列表": rows,
        },
    )