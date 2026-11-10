import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_upload(file_storage):
    name = (getattr(file_storage, "filename", None) or "upload").lower()
    data = file_storage.read()
    return name, data


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _hex(r, g, b) -> str:
    return "#%02x%02x%02x" % (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))


def _norm_hex(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if re.fullmatch(r"[0-9a-fA-F]{6}", s):
        return "#" + s.lower()
    return None


def _rgb_from_int(value) -> str | None:
    try:
        v = int(value)
    except Exception:
        return None
    if v < 0:
        return None
    return _hex((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


def _luminance(hex_color: str) -> float:
    h = _norm_hex(hex_color)
    if not h:
        return 0.5
    r, g, b = int(h[1:3], 16) / 255, int(h[3:5], 16) / 255, int(h[5:7], 16) / 255
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _saturation(hex_color: str) -> float:
    h = _norm_hex(hex_color)
    if not h:
        return 0.0
    r, g, b = int(h[1:3], 16) / 255, int(h[3:5], 16) / 255, int(h[5:7], 16) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    return 0.0 if mx == 0 else (mx - mn) / mx


def _contrast_text(bg: str) -> str:
    return "#0f172a" if _luminance(bg) > 0.55 else "#ffffff"


def _pick_palette(counter: Counter, limit=12):
    """Return most frequent colors, skipping near-identical duplicates."""
    out = []
    for color, _count in counter.most_common(80):
        h = _norm_hex(color)
        if not h:
            continue
        # skip near duplicates
        if any(abs(int(h[1:3], 16) - int(x[1:3], 16)) < 8 and
               abs(int(h[3:5], 16) - int(x[3:5], 16)) < 8 and
               abs(int(h[5:7], 16) - int(x[5:7], 16)) < 8 for x in out):
            continue
        out.append(h)
        if len(out) >= limit:
            break
    return out


def _guess_background(counter: Counter, fallback="#17202c") -> str:
    if not counter:
        return fallback
    # most common color that is not pure black/white noise
    for color, _ in counter.most_common(20):
        h = _norm_hex(color)
        if h and h not in ("#000000", "#ffffff"):
            return h
    return _norm_hex(counter.most_common(1)[0][0]) or fallback


def _guess_text_color(counter: Counter, bg: str) -> str:
    best = None
    best_score = -1
    for color, count in counter.most_common(40):
        h = _norm_hex(color)
        if not h or h == bg:
            continue
        contrast = abs(_luminance(h) - _luminance(bg))
        score = contrast * (1 + min(count, 20) / 20)
        if score > best_score:
            best_score = score
            best = h
    return best or _contrast_text(bg)


def _guess_accent(counter: Counter, bg: str, text: str, fallback="#29b6f6") -> str:
    best = None
    best_score = -1
    for color, count in counter.most_common(60):
        h = _norm_hex(color)
        if not h or h in (bg, text):
            continue
        sat = _saturation(h)
        if sat < 0.18:
            continue
        score = sat * (1 + min(count, 15) / 15)
        if score > best_score:
            best_score = score
            best = h
    return best or fallback


def _rgb(value: str | None) -> tuple[int, int, int]:
    h = _norm_hex(value) or "#000000"
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _mix(a: str, b: str, ratio: float) -> str:
    """Blend two hex colors. ratio 0 -> a, 1 -> b."""
    ratio = max(0.0, min(1.0, ratio))
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return _hex(ra + (rb - ra) * ratio, ga + (gb - ga) * ratio, ba + (bb - ba) * ratio)


def _lighten(color: str, amount: float = 0.12) -> str:
    return _mix(color, "#ffffff", amount)


def _darken(color: str, amount: float = 0.12) -> str:
    return _mix(color, "#000000", amount)


def _rgba(color: str, alpha: float) -> str:
    r, g, b = _rgb(color)
    return f"rgba({r}, {g}, {b}, {max(0.0, min(1.0, alpha)):.2f})"


def _safe_font(font: str | None) -> str:
    if not font:
        return "Segoe UI, Arial, sans-serif"
    cleaned = re.sub(r"[^a-zA-Z0-9 ,\-'\"]", "", str(font)).strip()
    return cleaned or "Segoe UI, Arial, sans-serif"


# ---------------------------------------------------------------------------
# Markdown helpers (shared by all extractors)
# ---------------------------------------------------------------------------

_BULLET_RE = re.compile(r"^\s*(?:[•·▪◦‣∙●○■□❖➢➤]|[-–—*+])\s+")
_ORDERED_RE = re.compile(r"^\s*(\d+)[.)]\s+")


def _strip_bullet(text: str) -> tuple[str, bool]:
    """Remove a leading bullet/number marker. Returns (text, ordered)."""
    t = (text or "").strip()
    m = _ORDERED_RE.match(t)
    if m:
        return t[m.end():].strip(), True
    m = _BULLET_RE.match(t)
    if m:
        return t[m.end():].strip(), False
    return t, False


def _md_run(text: str, bold: bool = False, italic: bool = False) -> str:
    """Wrap a text run in Markdown emphasis while preserving surrounding spaces."""
    if not text:
        return ""
    core = text
    lead = core[: len(core) - len(core.lstrip())]
    trail = core[len(core.rstrip()):]
    core = core.strip()
    if not core:
        return text
    if bold and italic:
        core = f"***{core}***"
    elif bold:
        core = f"**{core}**"
    elif italic:
        core = f"*{core}*"
    return lead + core + trail


def _md_bullet_text(text: str) -> str:
    """Turn 'Label: value' into '**Label:** value' for a modern look."""
    t = _clean_text(text)
    if "**" in t or "](" in t:
        return t
    m = re.match(r"^([^:]{2,42}):\s+(.+)$", t)
    if m:
        label = m.group(1).strip()
        rest = m.group(2).strip()
        if 1 <= len(label.split()) <= 6 and not label.lower().startswith(("http", "www", "mailto")):
            return f"**{label}:** {rest}"
    return t


def _md_list(items) -> str:
    """items: iterable of (level, markdown_text, ordered)."""
    lines = []
    counters = {}
    for level, text, ordered in items:
        try:
            level = max(0, min(int(level or 0), 6))
        except Exception:
            level = 0
        text = (text or "").strip()
        if not text:
            continue
        indent = "    " * level
        if ordered:
            counters[level] = counters.get(level, 0) + 1
            for key in [k for k in counters if k > level]:
                counters.pop(key, None)
            lines.append(f"{indent}{counters[level]}. {text}")
        else:
            counters.pop(level, None)
            lines.append(f"{indent}- {text}")
    return "\n".join(lines)


def _md_table(rows) -> str:
    """Convert a list of row/cell lists into a GitHub-style Markdown table."""
    clean = []
    for row in rows or []:
        cells = [_clean_text(str(c)) for c in (row or [])]
        if any(cells):
            clean.append(cells)
    if len(clean) < 2:
        return ""
    width = max(len(r) for r in clean)
    clean = [r + [""] * (width - len(r)) for r in clean]

    def cell(value: str) -> str:
        return value.replace("|", "\\|")

    header = "| " + " | ".join(cell(c) for c in clean[0]) + " |"
    separator = "| " + " | ".join("---" for _ in range(width)) + " |"
    body = "\n".join("| " + " | ".join(cell(c) for c in r) + " |" for r in clean[1:])
    return "\n".join([header, separator, body])


def _build_content(paragraphs=None, bullets=None, table_rows=None, quote=None) -> str:
    """Assemble rich Markdown content for a slide."""
    parts = []
    for para in paragraphs or []:
        para = (para or "").strip()
        if para:
            parts.append(para)
    if quote:
        q = "\n".join("> " + line for line in str(quote).splitlines() if line.strip())
        if q:
            parts.append(q)
    if bullets:
        lst = _md_list(bullets)
        if lst:
            parts.append(lst)
    if table_rows:
        table = _md_table(table_rows)
        if table:
            parts.append(table)
    return "\n\n".join(parts)


def _plain_md(text: str) -> str:
    """Strip common Markdown markers to get a plain title/label."""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text or "")
    t = re.sub(r"[*_`#>]+", "", t)
    return _clean_text(t)


def _line_markdown(spans) -> str:
    """Build a Markdown line from PDF span dicts, preserving bold/italic."""
    parts = []
    for sp in sorted(spans, key=lambda s: s.get("bbox", (0, 0, 0, 0))[0]):
        parts.append(_md_run(sp.get("text", ""), sp.get("bold", False), sp.get("italic", False)))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _split_title_content(md_text: str) -> tuple[str, str]:
    """Split Markdown into a plain title (first non-empty line) and rich content."""
    raw = (md_text or "").splitlines()
    idx = next((i for i, line in enumerate(raw) if line.strip()), None)
    if idx is None:
        return "", ""
    title = _plain_md(re.sub(r"^#+\s*", "", raw[idx].strip()))
    content = "\n".join(raw[idx + 1:]).strip()
    return title, content


def _make_slide(title, paragraphs=None, bullets=None, table_rows=None, quote=None, notes="", layout="default"):
    title = _plain_md(title)[:180]
    content = _build_content(paragraphs, bullets, table_rows, quote)
    if not layout or layout == "default":
        layout = "default"
    return {
        "title": title,
        "content": content,
        "bullets": [],
        "notes": notes or "",
        "layout": layout,
    }


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True
        if tag in ("br", "p", "div", "li", "h1", "h2", "h3", "h4", "section", "article", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "section", "article", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip and data:
            self.parts.append(data)

    def get_text(self):
        text = "".join(self.parts)
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
        return "\n".join(ln for ln in lines if ln)


def _html_design_hints(text: str):
    color_counter = Counter()
    for c in re.findall(r"#[0-9a-fA-F]{6}\b", text):
        color_counter[_norm_hex(c)] += 1
    for c in re.findall(r"rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+", text):
        m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", c)
        if m:
            color_counter[_hex(int(m.group(1)), int(m.group(2)), int(m.group(3)))] += 1

    css_vars = {}
    for name, value in re.findall(r"--([a-zA-Z0-9_-]+)\s*:\s*([^;}\n]+)", text):
        css_vars[name.strip().lower()] = value.strip()

    def var_color(*names):
        for n in names:
            v = css_vars.get(n)
            if v:
                m = re.search(r"#[0-9a-fA-F]{3,8}", v)
                if m:
                    return _norm_hex(m.group(0))
        return None

    bg = var_color("bg", "background", "background-color", "background_color")
    if not bg:
        m = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,8})", text, re.IGNORECASE)
        bg = _norm_hex(m.group(1)) if m else None
    fg = var_color("text", "color", "text-color", "text_color")
    if not fg:
        m = re.search(r"(?<!-)color\s*:\s*(#[0-9a-fA-F]{3,8})", text, re.IGNORECASE)
        fg = _norm_hex(m.group(1)) if m else None
    heading = var_color("heading", "heading-color", "heading_color")
    accent = var_color("accent", "accent-color", "accent_color")

    m = re.search(r"font-family\s*:\s*([^;\n}]+)", text, re.IGNORECASE)
    font = m.group(1).strip() if m else None

    if not bg:
        bg = _guess_background(color_counter)
    if not fg:
        fg = _guess_text_color(color_counter, bg)
    if not heading:
        heading = fg
    if not accent:
        accent = _guess_accent(color_counter, bg, fg)

    return {
        "colors": _pick_palette(color_counter),
        "background_color": bg,
        "text_color": fg,
        "heading_color": heading,
        "accent_color": accent,
        "font_family": font,
        "css_variables": css_vars,
    }


class _HTMLToMarkdown(HTMLParser):
    """Small HTML -> Markdown converter that preserves structure and emphasis."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._skip = 0
        self._lists = []
        self._hrefs = []
        self._in_pre = False
        self._quote = 0
        self._table = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style", "noscript"):
            self._skip += 1
            return
        if self._skip:
            return
        attrs = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "div", "section", "article", "header", "footer", "main"):
            self.out.append("\n\n")
        elif tag == "br":
            self.out.append("\n")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag in ("del", "s", "strike"):
            self.out.append("~~")
        elif tag == "code" and not self._in_pre:
            self.out.append("`")
        elif tag == "pre":
            self._in_pre = True
            self.out.append("\n\n```\n")
        elif tag == "blockquote":
            self._quote += 1
            self.out.append("\n\n> ")
        elif tag in ("ul", "ol"):
            self._lists.append({"ordered": tag == "ol", "n": 0})
        elif tag == "li":
            indent = "    " * max(0, len(self._lists) - 1)
            if self._lists and self._lists[-1]["ordered"]:
                self._lists[-1]["n"] += 1
                self.out.append(f"\n{indent}{self._lists[-1]['n']}. ")
            else:
                self.out.append(f"\n{indent}- ")
        elif tag == "a":
            self._hrefs.append(attrs.get("href") or "")
            self.out.append("[")
        elif tag == "img":
            src = attrs.get("src") or ""
            alt = attrs.get("alt") or ""
            if src:
                self.out.append(f"![{alt}]({src})")
        elif tag == "hr":
            self.out.append("\n\n---\n\n")
        elif tag == "table":
            self._table = []
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []
        elif tag == "mark":
            self.out.append("**")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self.out.append("\n\n")
        elif tag in ("div", "section", "article", "header", "footer", "main"):
            self.out.append("\n\n")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag in ("del", "s", "strike"):
            self.out.append("~~")
        elif tag == "code" and not self._in_pre:
            self.out.append("`")
        elif tag == "pre":
            self._in_pre = False
            self.out.append("\n```\n\n")
        elif tag == "blockquote":
            self._quote = max(0, self._quote - 1)
            self.out.append("\n\n")
        elif tag in ("ul", "ol"):
            if self._lists:
                self._lists.pop()
        elif tag == "a":
            href = self._hrefs.pop() if self._hrefs else ""
            self.out.append(f"]({href})" if href else "]")
        elif tag in ("td", "th"):
            if self._row is not None and self._cell is not None:
                text = _clean_text("".join(self._cell)).replace("|", "\\|")
                self._row.append(text)
            self._cell = None
        elif tag == "tr":
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table":
            if self._table:
                table = _md_table(self._table)
                if table:
                    self.out.append("\n\n" + table + "\n\n")
            self._table = []
        elif tag == "mark":
            self.out.append("**")

    def handle_data(self, data):
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
            return
        if self._in_pre:
            self.out.append(data)
            return
        text = re.sub(r"\s+", " ", data)
        if self._quote > 0:
            text = text.replace("\n", "\n> ")
        self.out.append(text)

    def get_markdown(self):
        text = "".join(self.out).replace("\xa0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        return text.strip()


def _html_to_markdown(html_text: str) -> str:
    parser = _HTMLToMarkdown()
    try:
        parser.feed(html_text)
        return parser.get_markdown()
    except Exception:
        return _clean_text(re.sub(r"<[^>]+>", " ", html_text))


def _markdown_to_slides(md_text: str, max_slides: int = 40):
    """Split Markdown into slide-sized chunks without breaking lists/tables."""
    md_text = (md_text or "").strip()
    if not md_text:
        return []
    if re.search(r"(?m)^#{1,2}\s+", md_text):
        chunks = re.split(r"(?m)(?=^#{1,2}\s+)", md_text)
    else:
        chunks = re.split(r"\n\s*\n", md_text)

    merged = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        first = chunk.splitlines()[0].strip()
        is_continuation = bool(re.match(r"^([-*+]|\d+[.)]|>|\|)\s*", first))
        if merged and is_continuation:
            merged[-1] += "\n\n" + chunk
        else:
            merged.append(chunk)

    slides = []
    for i, chunk in enumerate(merged[:max_slides], start=1):
        title, content = _split_title_content(chunk)
        if not title and not content:
            continue
        slides.append(
            _make_slide(
                title or f"Slide {i}",
                [content] if content else [],
                layout="title" if i == 1 else ("section" if not content else "default"),
            )
        )
    return slides


def extract_html(data: bytes):
    text = data.decode("utf-8", errors="replace")
    parser = _HTMLText()
    try:
        parser.feed(text)
        plain = parser.get_text()
    except Exception:
        plain = _clean_text(re.sub(r"<[^>]+>", " ", text))

    slides = []
    section_blocks = re.findall(r"<section\b[^>]*>(.*?)</section>", text, re.DOTALL | re.IGNORECASE)
    if not section_blocks:
        section_blocks = re.findall(
            r"<div\b[^>]*class=\"[^\"]*(?:slide|reveal)[^\"]*\"[^>]*>(.*?)</div>",
            text, re.DOTALL | re.IGNORECASE,
        )
    for i, block in enumerate(section_blocks[:60], start=1):
        md = _html_to_markdown(block)
        title, content = _split_title_content(md)
        if not title and not content:
            continue
        slides.append(
            _make_slide(
                title or f"Slide {i}",
                [content] if content else [],
                layout="title" if i == 1 else ("section" if not content else "default"),
            )
        )

    if not slides and plain:
        slides = _markdown_to_slides(_html_to_markdown(text), max_slides=30)

    return {
        "slides": slides,
        "text": plain[:20000],
        "design_hints": _html_design_hints(text),
        "extractor": "html",
        "has_text": bool(plain.strip()),
    }


# ---------------------------------------------------------------------------
# PPTX
# ---------------------------------------------------------------------------

def _pptx_xml_hints(zf):
    """Extract theme/slide colors and fonts directly from the OOXML package."""
    ns = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }
    color_counter = Counter()
    fonts = Counter()
    bg_candidates = Counter()

    for name in zf.namelist():
        if not name.endswith(".xml"):
            continue
        if not (name.startswith("ppt/theme/") or name.startswith("ppt/slides/") or name.startswith("ppt/slideMasters/") or name.startswith("ppt/slideLayouts/")):
            continue
        try:
            root = ET.fromstring(zf.read(name))
        except Exception:
            continue
        for el in root.findall(".//a:srgbClr", ns):
            h = _norm_hex(el.attrib.get("val"))
            if h:
                color_counter[h] += 1
        for el in root.findall(".//a:latin", ns):
            tf = el.attrib.get("typeface")
            if tf and tf not in ("+mn-lt", "+mj-lt"):
                fonts[tf] += 1
        # background elements
        for bg in root.findall(".//p:bg", ns):
            for el in bg.findall(".//a:srgbClr", ns):
                h = _norm_hex(el.attrib.get("val"))
                if h:
                    bg_candidates[h] += 1

    bg = _guess_background(bg_candidates) if bg_candidates else None
    if not bg:
        # Most PPTX decks inherit the default white slide background when no
        # explicit background is defined in slide/master/layout XML.
        bg = "#ffffff"
    text = _guess_text_color(color_counter, bg)
    heading = text
    accent = _guess_accent(color_counter, bg, text)
    font = fonts.most_common(1)[0][0] if fonts else None
    return {
        "colors": _pick_palette(color_counter),
        "background_color": bg,
        "text_color": text,
        "heading_color": heading,
        "accent_color": accent,
        "font_family": font,
        "font_counter": dict(fonts),
    }


def _pptx_para_markdown(para) -> str:
    """Convert a python-pptx paragraph (runs, bold/italic, links) to Markdown."""
    parts = []
    for run in para.runs:
        text = run.text or ""
        if not text:
            continue
        bold = False
        italic = False
        try:
            bold = bool(run.font.bold)
        except Exception:
            pass
        try:
            italic = bool(run.font.italic)
        except Exception:
            pass
        md = _md_run(text, bold, italic)
        try:
            link = run.hyperlink.address
        except Exception:
            link = None
        if link and not str(link).startswith("#"):
            md = f"[{md}]({link})"
        parts.append(md)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _pptx_table_rows(shape):
    rows = []
    try:
        for row in shape.table.rows:
            rows.append([_clean_text(cell.text) for cell in row.cells])
    except Exception:
        return []
    return rows


def _pptx_with_python_pptx(data: bytes):
    from pptx import Presentation  # type: ignore
    from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER  # type: ignore

    prs = Presentation(io.BytesIO(data))
    slides = []
    color_counter = Counter()
    font_counter = Counter()
    bg_counter = Counter()
    text_all = []

    subtitle_type = getattr(PP_PLACEHOLDER, "SUBTITLE", None)
    body_types = {
        t for t in (getattr(PP_PLACEHOLDER, "BODY", None), getattr(PP_PLACEHOLDER, "OBJECT", None)) if t is not None
    }

    def add_color(value):
        h = _norm_hex(value)
        if h:
            color_counter[h] += 1
            return h
        return None

    def fill_color(shape):
        try:
            fill = shape.fill
            if fill.type is not None and fill.fore_color.type is not None:
                return add_color(fill.fore_color.rgb)
        except Exception:
            return None
        return None

    for idx, slide in enumerate(list(prs.slides)[:80], start=1):
        # slide background
        try:
            bg = slide.background.fill
            if bg.type is not None and bg.fore_color.type is not None:
                bg_counter[_norm_hex(bg.fore_color.rgb)] += 1
        except Exception:
            pass

        title = ""
        subtitle = ""
        paragraphs = []
        bullet_items = []
        table_rows = []

        try:
            shapes = sorted(
                slide.shapes,
                key=lambda sh: (sh.top if sh.top is not None else 0, sh.left if sh.left is not None else 0),
            )
        except Exception:
            shapes = list(slide.shapes)

        for shape in shapes:
            try:
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    continue
            except Exception:
                pass
            fill_color(shape)

            if getattr(shape, "has_table", False):
                table_rows.extend(_pptx_table_rows(shape))
                continue

            if not getattr(shape, "has_text_frame", False):
                continue

            is_title = False
            try:
                is_title = slide.shapes.title is not None and shape == slide.shapes.title
            except Exception:
                pass

            ph_type = None
            try:
                ph_type = shape.placeholder_format.type
            except Exception:
                pass
            is_subtitle = subtitle_type is not None and ph_type == subtitle_type
            is_body = ph_type in body_types

            nonempty = []
            for para in shape.text_frame.paragraphs:
                md = _pptx_para_markdown(para)
                if md:
                    nonempty.append((para, md))
            if not nonempty:
                continue

            short_paras = all(len(_strip_bullet(md)[0]) <= 120 for _p, md in nonempty)
            treat_short_as_bullets = (
                not is_title and not is_subtitle and not is_body and len(nonempty) >= 2 and short_paras
            )

            for para, md in nonempty:
                plain = _clean_text("".join(run.text for run in para.runs))
                for run in para.runs:
                    try:
                        if run.font.name:
                            font_counter[run.font.name] += 1
                    except Exception:
                        pass
                    try:
                        if run.font.color and run.font.color.type is not None:
                            add_color(run.font.color.rgb)
                    except Exception:
                        pass

                if is_title and not title:
                    title = plain
                    continue
                if is_subtitle:
                    subtitle = md
                    continue

                stripped, ordered = _strip_bullet(plain)
                explicit_bullet = ordered or stripped != plain or bool(
                    re.match(r"^\s*[•·▪◦‣∙●○■□❖➢➤]", plain)
                )
                level = para.level or 0
                if is_body or explicit_bullet or level > 0 or treat_short_as_bullets:
                    bullet_items.append((level, _md_bullet_text(md), ordered))
                else:
                    paragraphs.append(md)

        if subtitle:
            if "**" not in subtitle and "*" not in subtitle:
                paragraphs.insert(0, f"*{subtitle}*")
            else:
                paragraphs.insert(0, subtitle)

        if not title:
            if paragraphs:
                title = _plain_md(paragraphs.pop(0))
            elif bullet_items:
                title = _plain_md(bullet_items[0][1])
                bullet_items = bullet_items[1:]

        notes = ""
        try:
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            pass

        content = _build_content(paragraphs, bullet_items, table_rows)
        if not (title or content):
            continue

        layout = "title" if idx == 1 else ("section" if not content else "default")
        slides.append(_make_slide(title, [content] if content else [], notes=notes, layout=layout))
        text_all.append(title)
        if content:
            text_all.append(content)

    # theme XML for richer palette
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        xml_hints = _pptx_xml_hints(zf)
    for c in xml_hints.get("colors", []):
        color_counter[c] += 1
    for f, n in (xml_hints.get("font_counter") or {}).items():
        font_counter[f] += n

    bg = _guess_background(bg_counter) if bg_counter else xml_hints.get("background_color")
    if not bg:
        bg = _guess_background(color_counter)
    text = _guess_text_color(color_counter, bg)
    heading = text
    accent = _guess_accent(color_counter, bg, text)
    font = font_counter.most_common(1)[0][0] if font_counter else xml_hints.get("font_family")

    hints = {
        "colors": _pick_palette(color_counter),
        "background_color": bg,
        "text_color": text,
        "heading_color": heading,
        "accent_color": accent,
        "font_family": font,
        "slide_size": {
            "width_in": round(prs.slide_width / 914400, 2),
            "height_in": round(prs.slide_height / 914400, 2),
        },
    }
    return {
        "slides": slides,
        "text": "\n".join(text_all)[:20000],
        "design_hints": hints,
        "extractor": "python-pptx",
        "has_text": bool(text_all),
    }


def extract_pptx(data: bytes):
    try:
        return _pptx_with_python_pptx(data)
    except Exception:
        pass

    # Fallback: OOXML parsing without python-pptx
    ns = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }
    slides = []
    text_all = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            hints = _pptx_xml_hints(zf)
            slide_names = sorted(
                [n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
                key=lambda x: int(re.search(r"(\d+)", x).group(1)),
            )
            for idx, sname in enumerate(slide_names[:80], start=1):
                try:
                    root = ET.fromstring(zf.read(sname))
                except Exception:
                    continue
                paras = []
                for p in root.findall(".//a:p", ns):
                    runs = []
                    for r in p.findall(".//a:r", ns):
                        texts = [t.text for t in r.findall(".//a:t", ns) if t.text]
                        if not texts:
                            continue
                        rpr = r.find("a:rPr", ns)
                        bold = rpr is not None and rpr.attrib.get("b") in ("1", "true")
                        italic = rpr is not None and rpr.attrib.get("i") in ("1", "true")
                        runs.append(_md_run("".join(texts), bold, italic))
                    if runs:
                        paras.append(re.sub(r"\s+", " ", "".join(runs)).strip())
                paras = [p for p in paras if p]
                if not paras:
                    continue
                title = _plain_md(paras[0])
                body = paras[1:]
                plain_body = [_strip_bullet(t)[0] for t in body]
                if len(body) == 1 and len(plain_body[0]) > 120:
                    content = _build_content([body[0]])
                else:
                    content = _build_content([], [(0, _md_bullet_text(t), False) for t in body])
                layout = "title" if idx == 1 else ("section" if not content else "default")
                slides.append(_make_slide(title, [content] if content else [], layout=layout))
                text_all.append(title)
                if content:
                    text_all.append(content)
    except Exception as e:
        raise ValueError(f"Could not read PPTX: {e}")

    return {
        "slides": slides,
        "text": "\n".join(text_all)[:20000],
        "design_hints": hints,
        "extractor": "ooxml",
        "has_text": bool(text_all),
    }


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _pdf_with_pymupdf(data: bytes):
    try:
        import pymupdf as fitz  # type: ignore
    except Exception:
        import fitz  # type: ignore

    doc = fitz.open(stream=data, filetype="pdf")
    slides = []
    text_all = []
    color_counter = Counter()
    font_counter = Counter()
    bg_counter = Counter()
    size_by_color = {}
    heading_color = None
    largest_size = 0

    for page_index in range(min(80, doc.page_count)):
        page = doc.load_page(page_index)
        slide_no = page_index + 1
        # background: render a small pixmap and take dominant color
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), alpha=False)
            samples = pix.samples
            step = max(3, (pix.n or 3) * 37)
            for i in range(0, len(samples) - (pix.n or 3), step):
                if pix.n == 3:
                    c = _hex(samples[i], samples[i + 1], samples[i + 2])
                elif pix.n == 4:
                    c = _hex(samples[i], samples[i + 1], samples[i + 2])
                else:
                    c = _hex(samples[i], samples[i + 1], samples[i + 2])
                bg_counter[c] += 1
        except Exception:
            pass

        spans = []
        try:
            blocks = page.get_text("dict").get("blocks", [])
        except Exception:
            blocks = []
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = (span.get("text") or "").strip()
                    if not txt:
                        continue
                    size = float(span.get("size") or 0)
                    font = (span.get("font") or "").split("+")[-1]
                    font_l = (font or "").lower()
                    flags = int(span.get("flags") or 0)
                    bold = bool(flags & 16) or "bold" in font_l or "black" in font_l
                    italic = bool(flags & 2) or "italic" in font_l or "oblique" in font_l
                    color = _rgb_from_int(span.get("color"))
                    bbox = span.get("bbox") or (0, 0, 0, 0)
                    spans.append({
                        "text": txt,
                        "size": size,
                        "font": font,
                        "color": color,
                        "bbox": bbox,
                        "bold": bold,
                        "italic": italic,
                    })
                    if color:
                        color_counter[color] += 1
                        if size >= size_by_color.get(color, 0):
                            size_by_color[color] = size
                    if font:
                        font_counter[font] += 1
                    if size > largest_size:
                        largest_size = size
                        heading_color = color

        if not spans:
            continue
        spans.sort(key=lambda s: (round(s["bbox"][1], 1), s["bbox"][0]))
        lines = []
        current_y = None
        current = []
        for sp in spans:
            y = round(sp["bbox"][1], 1)
            tolerance = max(3.0, (sp.get("size") or 10) * 0.35)
            if current_y is None or abs(y - current_y) <= tolerance:
                current.append(sp)
                if current_y is None:
                    current_y = y
            else:
                lines.append(current)
                current = [sp]
                current_y = y
        if current:
            lines.append(current)

        line_infos = []
        for ln in lines:
            md = _line_markdown(ln)
            plain = _clean_text(" ".join(s["text"] for s in ln))
            if not md or not plain:
                continue
            sizes = [s.get("size") or 0 for s in ln]
            xs = [s["bbox"][0] for s in ln]
            line_infos.append({
                "text": md,
                "plain": plain,
                "size": max(sizes) if sizes else 0,
                "x0": min(xs) if xs else 0,
            })
        if not line_infos:
            continue

        title_raw, _ordered = _strip_bullet(line_infos[0]["text"])
        title = _plain_md(title_raw)
        rest = line_infos[1:]
        content = ""
        if rest:
            body_sizes = sorted(info["size"] for info in rest if info["size"] > 0)
            body_size = body_sizes[len(body_sizes) // 2] if body_sizes else 12
            min_x0 = min(info["x0"] for info in rest)
            explicit_bullets = any(
                _strip_bullet(info["plain"])[1] or _strip_bullet(info["plain"])[0] != info["plain"]
                for info in rest
            )
            short_lines = all(len(_strip_bullet(info["plain"])[0]) <= 110 for info in rest)
            use_bullets = explicit_bullets or (short_lines and len(rest) >= 2)

            if use_bullets:
                items = []
                for info in rest:
                    text = _strip_bullet(info["text"])[0]
                    _plain, ordered = _strip_bullet(info["plain"])
                    level = 0 if info["x0"] <= min_x0 + max(12, body_size * 1.2) else 1
                    items.append((level, _md_bullet_text(text), ordered))
                content = _build_content([], items)
            else:
                paragraphs = []
                for info in rest:
                    text = info["text"]
                    if info["size"] >= body_size * 1.3 and len(info["plain"]) <= 120:
                        text = f"### {text}"
                    elif info["size"] <= body_size * 0.82 and len(info["plain"]) <= 120:
                        text = f"*{text}*"
                    paragraphs.append(text)
                content = _build_content(paragraphs)

        layout = "title" if slide_no == 1 else ("section" if not content else "default")
        slides.append(_make_slide(title, [content] if content else [], layout=layout))
        text_all.extend(info["plain"] for info in line_infos)

    bg = _guess_background(bg_counter) if bg_counter else _guess_background(color_counter)
    text_color = _guess_text_color(color_counter, bg)
    accent = _guess_accent(color_counter, bg, text_color)
    font = font_counter.most_common(1)[0][0] if font_counter else None

    hints = {
        "colors": _pick_palette(color_counter),
        "background_color": bg,
        "text_color": text_color,
        "heading_color": heading_color or text_color,
        "accent_color": accent,
        "font_family": font,
        "page_count": doc.page_count,
    }
    return {
        "slides": slides,
        "text": "\n".join(text_all)[:20000],
        "design_hints": hints,
        "extractor": "pymupdf",
        "has_text": bool(text_all),
    }


def _pdf_with_pypdf(data: bytes):
    text = ""
    pdf_lib = None
    try:
        import pypdf  # type: ignore
        pdf_lib = "pypdf"
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = []
        for pg in reader.pages[:80]:
            try:
                pages.append(pg.extract_text() or "")
            except Exception:
                pages.append("")
        text = "\n".join(pages)
    except Exception:
        try:
            import PyPDF2  # type: ignore
            pdf_lib = "PyPDF2"
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            pages = []
            for pg in reader.pages[:80]:
                try:
                    pages.append(pg.extract_text() or "")
                except Exception:
                    pages.append("")
            text = "\n".join(pages)
        except Exception:
            text = ""
            pdf_lib = None

    text = (text or "").strip()
    slides = []
    if text:
        # Prefer page separators if present
        chunks = [c.strip() for c in re.split(r"\f+", text) if c.strip()]
        if len(chunks) < 2:
            chunks = [c.strip() for c in re.split(r"\n\s*\n\s*\n+", text) if c.strip()]
        if len(chunks) < 2:
            chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
        for i, ch in enumerate(chunks[:60], start=1):
            lines = [ln.strip() for ln in ch.splitlines() if ln.strip()]
            if not lines:
                continue
            title = _plain_md(_strip_bullet(lines[0])[0])
            rest = lines[1:]
            if len(rest) == 1 and len(_strip_bullet(rest[0])[0]) > 120:
                content = _build_content([rest[0]])
            else:
                items = []
                for line in rest:
                    text, ordered = _strip_bullet(line)
                    items.append((0, _md_bullet_text(text), ordered))
                content = _build_content([], items)
            layout = "title" if i == 1 else ("section" if not content else "default")
            slides.append(_make_slide(title, [content] if content else [], layout=layout))

    return {
        "slides": slides,
        "text": text[:20000],
        "design_hints": {
            "colors": [],
            "background_color": "#17202c",
            "text_color": "#e6edf5",
            "heading_color": "#ffffff",
            "accent_color": "#29b6f6",
            "font_family": "Segoe UI, Arial, sans-serif",
            "note": "Install pymupdf for richer PDF text and design extraction.",
        },
        "extractor": pdf_lib or "none",
        "has_text": bool(text),
    }


def extract_pdf(data: bytes):
    try:
        return _pdf_with_pymupdf(data)
    except Exception:
        return _pdf_with_pypdf(data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_file(file_storage):
    name, data = _read_upload(file_storage)
    ext = os.path.splitext(name)[1].lower()
    if ext in (".html", ".htm"):
        return {**extract_html(data), "type": "html"}
    if ext == ".pptx":
        return {**extract_pptx(data), "type": "pptx"}
    if ext == ".pdf":
        return {**extract_pdf(data), "type": "pdf"}
    raise ValueError("Unsupported file type. Please upload .pptx, .pdf, or .html/.htm")


def design_from_hints(extracted: dict, name: str | None = None) -> dict:
    """Create a modern, Markdown-ready design from extracted style hints (no AI required)."""
    hints = extracted.get("design_hints") or {}
    bg = _norm_hex(hints.get("background_color")) or "#17202c"
    text = _norm_hex(hints.get("text_color")) or _contrast_text(bg)
    heading = _norm_hex(hints.get("heading_color")) or text
    accent = _norm_hex(hints.get("accent_color")) or "#29b6f6"
    font = _safe_font(hints.get("font_family"))
    source = (extracted.get("type") or "file").upper()
    design_name = name or f"Imported {source} Style"

    palette = [c for c in (hints.get("colors") or []) if _norm_hex(c)]
    accent2 = "#c3317d"
    for candidate in palette:
        candidate = _norm_hex(candidate)
        if not candidate or candidate == accent or _saturation(candidate) < 0.25:
            continue
        if _luminance(candidate) < 0.18:
            continue
        if sum(abs(a - b) for a, b in zip(_rgb(candidate), _rgb(bg))) < 70:
            continue
        if sum(abs(a - b) for a, b in zip(_rgb(candidate), _rgb(text))) < 50:
            continue
        distance = sum(abs(a - b) for a, b in zip(_rgb(candidate), _rgb(accent)))
        if distance > 60:
            accent2 = candidate
            break

    is_dark = _luminance(bg) < 0.5
    surface = _lighten(bg, 0.07) if is_dark else _darken(bg, 0.035)
    surface2 = _lighten(bg, 0.13) if is_dark else _darken(bg, 0.07)
    border = _rgba(accent, 0.30 if is_dark else 0.22)
    muted = _mix(text, bg, 0.38)
    grid = "rgba(255,255,255,0.04)" if is_dark else "rgba(0,0,0,0.05)"
    hover = "rgba(255,255,255,0.035)" if is_dark else "rgba(0,0,0,0.03)"
    pre_bg = "rgba(0,0,0,0.35)" if is_dark else "rgba(0,0,0,0.06)"
    quote_bg = _rgba(accent, 0.16 if is_dark else 0.10)
    quote_bg_end = _rgba(accent, 0.03 if is_dark else 0.02)
    title_weight = "800" if is_dark else "750"

    custom_css = f"""
:root {{
  --accent-2: {accent2};
  --surface: {surface};
  --surface-2: {surface2};
  --border: {border};
  --muted: {muted};
}}
.slide {{
  background:
    radial-gradient(circle at 14% 10%, {_rgba(accent, 0.22)}, transparent 44%),
    radial-gradient(circle at 86% 90%, {_rgba(accent2, 0.17)}, transparent 48%),
    linear-gradient(135deg, {bg} 0%, {surface} 100%);
}}
.slide::before {{
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient({grid} 1px, transparent 1px),
    linear-gradient(90deg, {grid} 1px, transparent 1px);
  background-size: 48px 48px;
  -webkit-mask-image: radial-gradient(circle at 50% 50%, #000 0%, transparent 78%);
  mask-image: radial-gradient(circle at 50% 50%, #000 0%, transparent 78%);
  pointer-events: none;
}}
.slide-inner {{ position: relative; z-index: 1; }}
.slide-title {{
  letter-spacing: -0.025em;
  line-height: 1.08;
  text-wrap: balance;
}}
h1.slide-title {{ font-weight: {title_weight}; }}
h2.slide-title {{ font-weight: 750; }}
h2.slide-title::after {{
  content: "";
  display: block;
  width: 72px;
  height: 4px;
  margin-top: 0.5em;
  border-radius: 999px;
  background: linear-gradient(90deg, {accent}, {accent2});
  box-shadow: 0 0 18px {_rgba(accent, 0.45)};
}}
.slide.layout-title .slide-title::after,
.slide.layout-section .slide-title::after {{
  margin-left: auto;
  margin-right: auto;
}}
.slide-content {{
  font-size: clamp(1.05rem, 1.45vw, 1.5rem);
  line-height: 1.65;
}}
.slide-content p {{ margin: 0.55em 0; }}
.slide-content strong {{ color: {accent}; font-weight: 700; }}
.slide-content em {{ color: {accent2}; font-style: normal; font-weight: 600; }}
.slide-content a {{
  color: {accent};
  text-decoration: none;
  border-bottom: 1px solid {_rgba(accent, 0.5)};
}}
.slide-content a:hover {{ border-bottom-color: {accent}; }}
.slide-content h3 {{
  font-size: 1.25em;
  color: {accent};
  margin: 1em 0 0.35em;
  letter-spacing: 0.01em;
}}
.slide-content h4 {{
  font-size: 1.08em;
  color: {accent2};
  margin: 0.8em 0 0.3em;
}}
.slide-content ul,
.slide-content ol,
.bullets {{
  margin: 0.65em 0 0.65em 1.15em;
  padding-left: 0.35em;
}}
.slide-content li,
.bullets li {{
  margin: 0.38em 0;
  padding-left: 0.25em;
}}
.slide-content li::marker,
.bullets li::marker {{
  color: {accent};
  font-weight: 700;
}}
.slide-content li > ul,
.slide-content li > ol {{ margin: 0.25em 0 0.25em 0.9em; }}
.slide-content blockquote {{
  margin: 1em 0;
  padding: 0.75em 1.1em;
  border-left: 4px solid {accent};
  background: linear-gradient(90deg, {quote_bg}, {quote_bg_end});
  border-radius: 0 14px 14px 0;
  font-style: italic;
  color: {_lighten(text, 0.08) if is_dark else _darken(text, 0.08)};
}}
.slide-content blockquote p {{ margin: 0.2em 0; }}
.slide-content table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 1em 0;
  font-size: 0.82em;
  border: 1px solid {border};
  border-radius: 14px;
  overflow: hidden;
}}
.slide-content th,
.slide-content td {{
  padding: 0.65em 0.85em;
  border-bottom: 1px solid {border};
  text-align: left;
  vertical-align: top;
}}
.slide-content th {{
  background: linear-gradient(135deg, {_rgba(accent, 0.22)}, {_rgba(accent2, 0.16)});
  color: {heading};
  font-weight: 700;
  letter-spacing: 0.02em;
}}
.slide-content tr:last-child td {{ border-bottom: none; }}
.slide-content tbody tr:hover td {{ background: {hover}; }}
.slide-content code {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.86em;
  padding: 0.12em 0.38em;
  border-radius: 6px;
  background: {hover};
  color: {heading};
}}
.slide-content pre {{
  margin: 1em 0;
  padding: 1em 1.2em;
  border-radius: 14px;
  border: 1px solid {border};
  background: {pre_bg};
  overflow: auto;
}}
.slide-content pre code {{ background: none; padding: 0; font-size: 0.82em; }}
.slide-content img {{
  max-width: 100%;
  max-height: 52vh;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 22px 55px rgba(0, 0, 0, 0.35);
}}
.slide-content hr {{
  border: none;
  height: 1px;
  margin: 1.2em 0;
  background: linear-gradient(90deg, transparent, {border}, transparent);
}}
.slide-number {{
  padding: 0.18em 0.55em;
  border-radius: 999px;
  background: {hover};
  border: 1px solid {border};
  color: {muted};
}}
.progress {{
  background: linear-gradient(90deg, {accent}, {accent2});
  box-shadow: 0 0 18px {_rgba(accent, 0.6)};
}}
.controls button {{
  background: {hover};
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  padding: 0.5em 1em;
  backdrop-filter: blur(10px);
}}
.controls button:hover {{
  background: {_rgba(accent, 0.18)};
  border-color: {_rgba(accent, 0.5)};
}}
""".strip()

    return {
        "name": design_name,
        "description": (
            f"Modern Markdown-ready theme extracted from uploaded {source} file — "
            "gradient background, accent details, styled lists, tables, quotes and images."
        ),
        "settings": {
            "font_family": font,
            "heading_font_family": font,
            "background_color": bg,
            "text_color": text,
            "heading_color": heading,
            "accent_color": accent,
            "slide_align": "left",
            "title_align": "center",
            "show_slide_numbers": True,
            "custom_css": custom_css,
        },
    }


def summarize_for_design(extracted: dict) -> str:
    hints = extracted.get("design_hints") or {}
    colors = hints.get("colors") or []
    parts = [f"Source type: {extracted.get('type')}", f"Extractor: {extracted.get('extractor')}"]
    if hints.get("background_color"):
        parts.append(f"Background: {hints.get('background_color')}")
    if hints.get("text_color"):
        parts.append(f"Text color: {hints.get('text_color')}")
    if hints.get("heading_color"):
        parts.append(f"Heading color: {hints.get('heading_color')}")
    if hints.get("accent_color"):
        parts.append(f"Accent color: {hints.get('accent_color')}")
    if hints.get("font_family"):
        parts.append(f"Font: {hints.get('font_family')}")
    slide_size = hints.get("slide_size")
    if slide_size:
        parts.append(f"Slide size: {slide_size.get('width_in')} x {slide_size.get('height_in')} inches")
    if colors:
        parts.append("Detected color palette: " + ", ".join(colors[:12]))
    sample = (extracted.get("text") or "")[:1600]
    if sample:
        parts.append("Content sample:\n" + sample)
    return "\n".join(parts)
