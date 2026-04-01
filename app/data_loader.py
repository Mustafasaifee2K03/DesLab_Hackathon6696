import json
from pathlib import Path

from .database import insert_content_items

SOURCE_DIR = Path(__file__).resolve().parent / "data" / "sources"


REQUIRED_FIELDS = {
    "id",
    "domain",
    "title",
    "description",
    "tags",
    "language",
    "duration_minutes",
    "source",
    "url",
    "creator",
    "published_at",
    "popularity",
}


def load_seed_data() -> int:
    items: list[dict] = []
    for file_path in sorted(SOURCE_DIR.glob("*.json")):
        records = json.loads(file_path.read_text(encoding="utf-8"))
        for record in records:
            missing = REQUIRED_FIELDS - set(record.keys())
            if missing:
                raise ValueError(f"Missing fields {missing} in {file_path.name}")
            items.append(record)

    insert_content_items(items)
    return len(items)
