import json
import os
import re
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DESIGNS_DIR = os.path.join(DATA_DIR, "designs")
PRESENTATIONS_DIR = os.path.join(DATA_DIR, "presentations")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

for _d in (DESIGNS_DIR, PRESENTATIONS_DIR, EXPORTS_DIR):
    os.makedirs(_d, exist_ok=True)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return s or "item"


def _path(folder: str, item_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", item_id)
    return os.path.join(folder, f"{safe}.json")


def _read(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _list(folder: str):
    items = []
    if not os.path.isdir(folder):
        return items
    for name in os.listdir(folder):
        if name.endswith(".json"):
            try:
                items.append(_read(os.path.join(folder, name)))
            except Exception:
                continue
    items.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "")
    return items


# ----- Designs -----

def default_design_settings():
    return {
        "font_family": "Segoe UI, Arial, sans-serif",
        "heading_font_family": "Segoe UI, Arial, sans-serif",
        "background_color": "#0f172a",
        "text_color": "#e2e8f0",
        "accent_color": "#38bdf8",
        "heading_color": "#f8fafc",
        "slide_align": "left",
        "title_align": "center",
        "show_slide_numbers": True,
        "custom_css": "",
    }


def list_designs():
    return _list(DESIGNS_DIR)


def get_design(design_id: str):
    path = _path(DESIGNS_DIR, design_id)
    if not os.path.exists(path):
        return None
    return _read(path)


def save_design(data: dict):
    design_id = data.get("id") or uuid.uuid4().hex[:10]
    existing = get_design(design_id)
    created = existing.get("created_at") if existing else _now()
    settings = default_design_settings()
    settings.update(data.get("settings") or {})
    design = {
        "id": design_id,
        "name": data.get("name") or "Untitled Design",
        "description": data.get("description") or "",
        "settings": settings,
        "created_at": created,
        "updated_at": _now(),
    }
    _write(_path(DESIGNS_DIR, design_id), design)
    return design


def delete_design(design_id: str):
    path = _path(DESIGNS_DIR, design_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# ----- Presentations -----

def list_presentations():
    return _list(PRESENTATIONS_DIR)


def get_presentation(pres_id: str):
    path = _path(PRESENTATIONS_DIR, pres_id)
    if not os.path.exists(path):
        return None
    return _read(path)


def normalize_slides(slides):
    out = []
    for s in slides or []:
        out.append(
            {
                "id": s.get("id") or uuid.uuid4().hex[:8],
                "title": s.get("title") or "",
                "content": s.get("content") or "",
                "bullets": [b for b in (s.get("bullets") or []) if str(b).strip()],
                "notes": s.get("notes") or "",
                "layout": s.get("layout") or "default",
            }
        )
    if not out:
        out.append({"id": uuid.uuid4().hex[:8], "title": "New Slide", "content": "", "bullets": [], "notes": "", "layout": "title"})
    return out


def save_presentation(data: dict):
    pres_id = data.get("id") or uuid.uuid4().hex[:10]
    existing = get_presentation(pres_id)
    created = existing.get("created_at") if existing else _now()
    pres = {
        "id": pres_id,
        "name": data.get("name") or "Untitled Presentation",
        "design_id": data.get("design_id") or "",
        "slides": normalize_slides(data.get("slides")),
        "created_at": created,
        "updated_at": _now(),
    }
    _write(_path(PRESENTATIONS_DIR, pres_id), pres)
    return pres


def delete_presentation(pres_id: str):
    path = _path(PRESENTATIONS_DIR, pres_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# ----- Settings -----

def default_settings():
    return {
        "ai": {
            "provider": "openai_compatible",  # openai_compatible | anthropic | ollama
            "base_url": "http://localhost:1234/v1",
            "api_key": "",
            "model": "",
            "temperature": 0.7,
        }
    }


def get_settings():
    settings = default_settings()
    if os.path.exists(SETTINGS_PATH):
        try:
            stored = _read(SETTINGS_PATH)
            if isinstance(stored, dict):
                # shallow merge ai
                ai = settings.get("ai", {}).copy()
                if isinstance(stored.get("ai"), dict):
                    ai.update(stored["ai"])
                settings.update({k: v for k, v in stored.items() if k != "ai"})
                settings["ai"] = ai
        except Exception:
            pass
    return settings


def save_settings(data: dict):
    current = get_settings()
    if isinstance(data, dict):
        if isinstance(data.get("ai"), dict):
            current["ai"].update(data["ai"])
        for k, v in data.items():
            if k != "ai":
                current[k] = v
    _write(SETTINGS_PATH, current)
    return current
