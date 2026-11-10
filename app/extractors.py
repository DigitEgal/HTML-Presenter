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
        p = _HTMLText()
        try:
            p.feed(block)
            btext = p.get_text()
        except Exception:
            btext = _clean_text(re.sub(r"<[^>]+>", " ", block))
        if not btext:
            continue
        lines = [ln for ln in btext.splitlines() if ln.strip()]
        title = lines[0][:160] if lines else f"Slide {i}"
        rest = lines[1:]
        bullets = rest[:10] if len(rest) > 1 else []
        content = "" if bullets else "\n".join(rest[:4])
        slides.append({
            "title": title,
            "content": content,
            "bullets": bullets,
            "notes": "",
            "layout": "title" if i == 1 else "default",
        })

    if not slides and plain:
        paras = [p.strip() for p in re.split(r"\n{2,}", plain) if p.strip()]
        for i, ptxt in enumerate(paras[:30], start=1):
            lines = [ln.strip() for ln in ptxt.splitlines() if ln.strip()]
            title = lines[0][:160] if lines else f"Slide {i}"
            rest = lines[1:]
            bullets = rest[:10] if len(rest) > 2 else []
            content = "" if bullets else "\n".join(rest)
            slides.append({
                "title": title,
                "content": content,
                "bullets": bullets,
                "notes": "",
                "layout": "title" if i == 1 else "default",
            })

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


def _pptx_with_python_pptx(data: bytes):
    from pptx import Presentation  # type: ignore
    from pptx.enum.shapes import MSO_SHAPE_TYPE  # type: ignore

    prs = Presentation(io.BytesIO(data))
    slides = []
    color_counter = Counter()
    font_counter = Counter()
    bg_counter = Counter()
    text_all = []

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
        paragraphs = []
        for shape in slide.shapes:
            try:
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    continue
            except Exception:
                pass
            fill_color(shape)
            if not getattr(shape, "has_text_frame", False):
                continue
            tf = shape.text_frame
            is_title = False
            try:
                is_title = slide.shapes.title is not None and shape == slide.shapes.title
            except Exception:
                pass
            for para in tf.paragraphs:
                txt = "".join(run.text for run in para.runs).strip()
                if not txt:
                    continue
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
                    title = _clean_text(txt)
                else:
                    paragraphs.append((para.level, _clean_text(txt)))

        if not title and paragraphs:
            title = paragraphs[0][1]
            paragraphs = paragraphs[1:]

        bullets = [txt for _lvl, txt in paragraphs]
        if len(bullets) == 1 and len(bullets[0]) > 90:
            content = bullets[0]
            bullets = []
        elif len(bullets) > 10:
            content = "\n".join(bullets)
            bullets = []
        else:
            content = ""

        notes = ""
        try:
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            pass

        if not (title or content or bullets):
            continue
        slides.append({
            "title": title[:180],
            "content": content,
            "bullets": bullets,
            "notes": notes,
            "layout": "title" if idx == 1 else "default",
        })
        text_all.extend([title] + bullets)

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
                    runs = [t.text for t in p.findall(".//a:t", ns) if t.text]
                    if runs:
                        paras.append(_clean_text("".join(runs)))
                paras = [p for p in paras if p]
                if not paras:
                    continue
                title = paras[0][:180]
                body = paras[1:]
                bullets = body[:10] if len(body) > 1 else []
                content = "" if bullets else "\n".join(body)
                slides.append({
                    "title": title,
                    "content": content,
                    "bullets": bullets,
                    "notes": "",
                    "layout": "title" if idx == 1 else "default",
                })
                text_all.extend([title] + body)
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
                    color = _rgb_from_int(span.get("color"))
                    bbox = span.get("bbox") or (0, 0, 0, 0)
                    spans.append({"text": txt, "size": size, "font": font, "color": color, "bbox": bbox})
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
            if current_y is None or abs(y - current_y) <= 3:
                current.append(sp)
                current_y = y if current_y is None else current_y
            else:
                lines.append(current)
                current = [sp]
                current_y = y
        if current:
            lines.append(current)

        line_texts = []
        for ln in lines:
            txt = _clean_text(" ".join(s["text"] for s in ln))
            if txt:
                line_texts.append(txt)
        if not line_texts:
            continue

        title = line_texts[0]
        body = line_texts[1:]
        if len(body) == 1 and len(body[0]) > 90:
            content = body[0]
            bullets = []
        else:
            bullets = body[:10] if len(body) > 1 else []
            content = "" if bullets else "\n".join(body)
        slides.append({
            "title": title[:180],
            "content": content,
            "bullets": bullets,
            "notes": "",
            "layout": "title" if slide_no == 1 else "default",
        })
        text_all.extend(line_texts)

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
            title = lines[0][:180]
            rest = lines[1:]
            bullets = rest[:10] if len(rest) > 1 else []
            content = "" if bullets else "\n".join(rest[:8])
            slides.append({
                "title": title,
                "content": content,
                "bullets": bullets,
                "notes": "",
                "layout": "title" if i == 1 else "default",
            })

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
    """Create a usable design directly from extracted style hints (no AI required)."""
    hints = extracted.get("design_hints") or {}
    bg = _norm_hex(hints.get("background_color")) or "#17202c"
    text = _norm_hex(hints.get("text_color")) or _contrast_text(bg)
    heading = _norm_hex(hints.get("heading_color")) or text
    accent = _norm_hex(hints.get("accent_color")) or "#29b6f6"
    font = hints.get("font_family") or "Segoe UI, Arial, sans-serif"
    source = (extracted.get("type") or "file").upper()
    design_name = name or f"Imported {source} Style"
    return {
        "name": design_name,
        "description": f"Design extracted from uploaded {source} file",
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
            "custom_css": (
                f".slide-title{{color:{heading};}} "
                f".slide-content strong,.slide-content a{{color:{accent};}} "
                f".progress{{background:{accent};}} "
                f".bullets li::marker{{color:{accent};}}"
            ),
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
