import html
import os
import markdown
from .storage import get_design, default_design_settings, EXPORTS_DIR


def _md(text: str) -> str:
    return markdown.markdown(text or "", extensions=["extra", "nl2br", "sane_lists"])


def render_presentation_html(presentation: dict, design: dict | None = None) -> str:
    if design is None and presentation.get("design_id"):
        design = get_design(presentation["design_id"])
    settings = default_design_settings()
    if design:
        settings.update(design.get("settings") or {})

    slides = presentation.get("slides") or []
    title = presentation.get("name") or "Presentation"

    slide_blocks = []
    for i, slide in enumerate(slides, start=1):
        layout = slide.get("layout") or "default"
        stitle = html.escape(slide.get("title") or "")
        content_html = _md(slide.get("content") or "")
        bullets = slide.get("bullets") or []
        bullets_html = ""
        if bullets:
            items = "".join(f"<li>{_md(b)}</li>" for b in bullets)
            bullets_html = f"<ul class=\"bullets\">{items}</ul>"
        notes = html.escape(slide.get("notes") or "")
        notes_attr = f' data-notes="{notes}"' if notes else ""
        slide_blocks.append(
            f'''<section class="slide layout-{html.escape(layout)}" data-index="{i}"{notes_attr}>
  <div class="slide-inner">
    {f'<h1 class="slide-title">{stitle}</h1>' if layout == 'title' else (f'<h2 class="slide-title">{stitle}</h2>' if stitle else '')}
    <div class="slide-content">{content_html}{bullets_html}</div>
  </div>
  <div class="slide-number">{i} / {len(slides)}</div>
</section>'''
        )

    slides_html = "\n".join(slide_blocks)
    show_numbers = "block" if settings.get("show_slide_numbers", True) else "none"
    custom_css = settings.get("custom_css") or ""

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(title)}</title>
<style>
:root {{
  --bg: {settings.get("background_color", "#0f172a")};
  --text: {settings.get("text_color", "#e2e8f0")};
  --accent: {settings.get("accent_color", "#38bdf8")};
  --heading: {settings.get("heading_color", "#f8fafc")};
  --font: {settings.get("font_family", "Segoe UI, Arial, sans-serif")};
  --heading-font: {settings.get("heading_font_family", "Segoe UI, Arial, sans-serif")};
  --align: {settings.get("slide_align", "left")};
  --title-align: {settings.get("title_align", "center")};
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; height: 100%; background: var(--bg); color: var(--text); font-family: var(--font); }}
.deck {{ position: relative; width: 100vw; height: 100vh; overflow: hidden; }}
.slide {{ position: absolute; inset: 0; padding: 64px 80px; display: none; }}
.slide.active {{ display: flex; flex-direction: column; justify-content: center; }}
.slide-inner {{ max-width: 1100px; width: 100%; margin: 0 auto; text-align: var(--align); }}
.slide.layout-title .slide-inner {{ text-align: var(--title-align); }}
.slide.layout-title .slide-title {{ font-size: 3.5rem; margin-bottom: 0.5em; }}
.slide.layout-section .slide-inner {{ text-align: center; }}
h1, h2, h3 {{ color: var(--heading); font-family: var(--heading-font); margin: 0 0 0.6em; }}
h1.slide-title {{ font-size: 3rem; }}
h2.slide-title {{ font-size: 2.2rem; }}
.slide-content {{ font-size: 1.6rem; line-height: 1.5; }}
.slide-content p {{ margin: 0.4em 0; }}
.slide-content ul, .slide-content ol {{ margin: 0.5em 0 0.5em 1.2em; }}
.slide-content li {{ margin: 0.25em 0; }}
a {{ color: var(--accent); }}
.slide-number {{ position: absolute; right: 28px; bottom: 20px; font-size: 0.95rem; opacity: 0.7; display: {show_numbers}; }}
.controls {{ position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); display: flex; gap: 8px; z-index: 10; }}
.controls button {{ background: rgba(255,255,255,0.08); color: var(--text); border: 1px solid rgba(255,255,255,0.2); padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 14px; }}
.controls button:hover {{ background: rgba(255,255,255,0.16); }}
.progress {{ position: fixed; left: 0; bottom: 0; height: 4px; background: var(--accent); width: 0; transition: width 0.2s ease; }}
.help {{ position: fixed; top: 14px; right: 18px; font-size: 12px; opacity: 0.55; }}
@media (max-width: 800px) {{
  .slide {{ padding: 32px 28px 60px; }}
  .slide-content {{ font-size: 1.2rem; }}
  h1.slide-title {{ font-size: 2rem; }}
  h2.slide-title {{ font-size: 1.6rem; }}
}}
{custom_css}
</style>
</head>
<body>
<div class="deck" id="deck">
{slides_html}
</div>
<div class="progress" id="progress"></div>
<div class="controls">
  <button id="prev" type="button">&#9664; Prev</button>
  <button id="next" type="button">Next &#9654;</button>
  <button id="fs" type="button">Fullscreen</button>
</div>
<div class="help">← → / Space to navigate</div>
<script>
(function() {{
  const slides = Array.from(document.querySelectorAll('.slide'));
  const progress = document.getElementById('progress');
  let idx = 0;
  function show(i) {{
    if (!slides.length) return;
    idx = Math.max(0, Math.min(i, slides.length - 1));
    slides.forEach((s, k) => s.classList.toggle('active', k === idx));
    progress.style.width = ((idx + 1) / slides.length * 100) + '%';
    history.replaceState(null, '', '#'+(idx+1));
  }}
  function next() {{ show(idx + 1); }}
  function prev() {{ show(idx - 1); }}
  document.getElementById('next').addEventListener('click', next);
  document.getElementById('prev').addEventListener('click', prev);
  document.getElementById('fs').addEventListener('click', () => {{
    if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(()=>{{}});
    else document.exitFullscreen();
  }});
  document.addEventListener('keydown', (e) => {{
    if (['ArrowRight','PageDown',' '].includes(e.key)) {{ e.preventDefault(); next(); }}
    if (['ArrowLeft','PageUp'].includes(e.key)) {{ e.preventDefault(); prev(); }}
    if (e.key === 'Home') {{ e.preventDefault(); show(0); }}
    if (e.key === 'End') {{ e.preventDefault(); show(slides.length-1); }}
  }});
  const start = parseInt(location.hash.replace('#',''), 10);
  show(isNaN(start) ? 0 : start - 1);
}})();
</script>
</body>
</html>'''


def export_presentation(presentation: dict, design: dict | None = None) -> str:
    html_str = render_presentation_html(presentation, design)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in (presentation.get("name") or "presentation"))
    filename = f"{safe or 'presentation'}-{presentation.get('id','export')}.html"
    path = os.path.join(EXPORTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_str)
    return path
