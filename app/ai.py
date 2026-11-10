import json
import re
import urllib.request
import urllib.error


class AIError(Exception):
    pass


def _post_json(url, payload, headers=None, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        if v is not None and v != "":
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise AIError(f"HTTP {e.code}: {body[:500]}")
    except Exception as e:
        raise AIError(str(e))


def _get_json(url, headers=None, timeout=60):
    req = urllib.request.Request(url, method="GET")
    for k, v in (headers or {}).items():
        if v is not None and v != "":
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise AIError(f"HTTP {e.code}: {body[:500]}")
    except Exception as e:
        raise AIError(str(e))


def list_models(settings: dict) -> list:
    ai = (settings or {}).get("ai") or {}
    provider = (ai.get("provider") or "openai_compatible").lower()
    base_url = (ai.get("base_url") or "").rstrip("/")
    api_key = ai.get("api_key") or ""
    if not base_url and provider != "anthropic":
        raise AIError("No base URL configured")

    if provider == "anthropic":
        url = (base_url + "/models") if base_url else "https://api.anthropic.com/v1/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        resp = _get_json(url, headers=headers)
        items = resp.get("data") or resp.get("models") or []
        out = []
        for m in items:
            if isinstance(m, dict):
                mid = m.get("id") or m.get("name")
                if mid:
                    out.append(mid)
            elif isinstance(m, str):
                out.append(m)
        return sorted(set(out))

    if provider == "ollama":
        url = base_url + "/api/tags"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = _get_json(url, headers=headers)
        items = resp.get("models") or []
        out = []
        for m in items:
            if isinstance(m, dict):
                mid = m.get("name") or m.get("model") or m.get("id")
                if mid:
                    out.append(mid)
            elif isinstance(m, str):
                out.append(m)
        return sorted(set(out))

    # openai_compatible
    url = base_url + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = _get_json(url, headers=headers)
    items = resp.get("data") or resp.get("models") or []
    out = []
    for m in items:
        if isinstance(m, dict):
            mid = m.get("id") or m.get("name")
            if mid:
                out.append(mid)
        elif isinstance(m, str):
            out.append(m)
    return sorted(set(out))


def _extract_json(text: str):
    if text is None:
        raise AIError("Empty response from model")
    text = text.strip()
    # fenced code block
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1).strip()
    # try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # try to find first JSON object/array
    for open_c, close_c in [("{", "}"), ("[", "]")]:
        start = text.find(open_c)
        end = text.rfind(close_c)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                continue
    raise AIError("Could not parse JSON from model response")


def chat(settings: dict, messages: list, temperature=None) -> str:
    ai = (settings or {}).get("ai") or {}
    provider = (ai.get("provider") or "openai_compatible").lower()
    base_url = (ai.get("base_url") or "").rstrip("/")
    api_key = ai.get("api_key") or ""
    model = ai.get("model") or ""
    temp = ai.get("temperature", 0.7) if temperature is None else temperature

    if not model:
        raise AIError("No model configured. Please set a model in AI Settings.")
    if not base_url and provider != "anthropic":
        raise AIError("No base URL configured. Please set a base URL in AI Settings.")

    if provider == "anthropic":
        url = base_url + "/messages" if base_url else "https://api.anthropic.com/v1/messages"
        system = ""
        conv = []
        for m in messages:
            if m.get("role") == "system":
                system += (m.get("content") or "") + "\n"
            else:
                conv.append({"role": m.get("role"), "content": m.get("content") or ""})
        payload = {"model": model, "max_tokens": 4096, "messages": conv, "temperature": temp}
        if system.strip():
            payload["system"] = system.strip()
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        resp = _post_json(url, payload, headers=headers)
        parts = resp.get("content") or []
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict))

    if provider == "ollama":
        # native Ollama API
        url = base_url + "/api/chat"
        payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": temp}}
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = _post_json(url, payload, headers=headers)
        msg = resp.get("message") or {}
        return msg.get("content") or resp.get("response") or ""

    # openai_compatible (OpenAI, LM Studio, Ollama /v1, Mistral, Groq, etc.)
    url = base_url + "/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": temp}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = _post_json(url, payload, headers=headers)
    choices = resp.get("choices") or []
    if not choices:
        raise AIError(f"Unexpected response: {json.dumps(resp)[:400]}")
    msg = choices[0].get("message") or {}
    return msg.get("content") or ""


DESIGN_SYSTEM = """You are a presentation design assistant. Generate a JSON object for an HTML presentation design/theme.
Return ONLY valid JSON (no markdown fences, no explanation) with this exact structure:
{
  "name": "Design Name",
  "description": "Short description",
  "settings": {
    "background_color": "#hex",
    "text_color": "#hex",
    "heading_color": "#hex",
    "accent_color": "#hex",
    "font_family": "CSS font-family value",
    "heading_font_family": "CSS font-family value",
    "slide_align": "left|center|right",
    "title_align": "left|center|right",
    "show_slide_numbers": true,
    "custom_css": "optional extra CSS rules for .slide, .slide-title, .slide-content, .bullets, .progress etc."
  }
}
Use readable, high-contrast colors and professional styling."""

PRESENTATION_SYSTEM = """You are a presentation authoring assistant. Generate a JSON object for an HTML presentation.
Return ONLY valid JSON (no markdown fences, no explanation) with this exact structure:
{
  "name": "Presentation Title",
  "slides": [
    {
      "title": "Slide title",
      "content": "Markdown text content (can be empty)",
      "bullets": ["bullet 1", "bullet 2"],
      "notes": "speaker notes (optional)",
      "layout": "title|default|section"
    }
  ]
}
Create clear, well-structured slides. Use layout "title" for the first/cover slide, "section" for section breaks, "default" for content slides. Content may use Markdown (bold, italic, etc.)."""


def generate_design(settings: dict, prompt: str) -> dict:
    messages = [
        {"role": "system", "content": DESIGN_SYSTEM},
        {"role": "user", "content": f"Create a presentation design based on this request:\n{prompt}"},
    ]
    text = chat(settings, messages)
    data = _extract_json(text)
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        raise AIError("Model did not return a design object")
    # normalize
    return {
        "name": data.get("name") or "AI Design",
        "description": data.get("description") or "",
        "settings": data.get("settings") or data,
    }


def generate_presentation(settings: dict, prompt: str, slide_count: int | None = None) -> dict:
    extra = f"\nAim for about {int(slide_count)} slides." if slide_count else ""
    messages = [
        {"role": "system", "content": PRESENTATION_SYSTEM},
        {"role": "user", "content": f"Create a presentation based on this request:\n{prompt}{extra}"},
    ]
    text = chat(settings, messages)
    data = _extract_json(text)
    if isinstance(data, list):
        data = {"name": "AI Presentation", "slides": data}
    if not isinstance(data, dict):
        raise AIError("Model did not return a presentation object")
    slides = data.get("slides") or []
    norm = []
    for s in slides:
        if not isinstance(s, dict):
            continue
        bullets = s.get("bullets") or []
        if isinstance(bullets, str):
            bullets = [b.strip("- *") for b in bullets.splitlines() if b.strip()]
        norm.append({
            "title": s.get("title") or "",
            "content": s.get("content") or "",
            "bullets": bullets if isinstance(bullets, list) else [],
            "notes": s.get("notes") or "",
            "layout": s.get("layout") or "default",
        })
    return {
        "name": data.get("name") or "AI Presentation",
        "slides": norm or [{"title": "New Slide", "content": "", "bullets": [], "layout": "title"}],
    }
