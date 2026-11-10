import html
import os
import re
import markdown
from .storage import get_design, default_design_settings, EXPORTS_DIR


def _md(text: str) -> str:
    return markdown.markdown(text or "", extensions=["extra", "nl2br", "sane_lists"])


def _md_inline(text: str) -> str:
    """Render Markdown for inline contexts (e.g. <li>) without wrapping <p> tags."""
    rendered = _md(text)
    match = re.fullmatch(r"<p>(.*?)</p>", rendered.strip(), re.DOTALL)
    return match.group(1) if match else rendered


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
            items = "".join(f"<li>{_md_inline(b)}</li>" for b in bullets)
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
html {{ scroll-behavior: smooth; }}
html, body {{ margin: 0; height: 100%; background: var(--bg); color: var(--text); font-family: var(--font); }}
body {{ overflow: hidden; }}
.deck {{ position: relative; width: 100vw; height: 100vh; overflow: hidden; }}
.slide {{ position: absolute; inset: 0; padding: 64px 80px; display: none; background: var(--bg); }}
.slide.active {{ display: flex; flex-direction: column; justify-content: center; }}
.slide.active .slide-inner {{ animation: slide-in 0.45s cubic-bezier(0.2, 0.7, 0.3, 1) both; }}
@keyframes slide-in {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.slide-inner {{ position: relative; max-width: 1120px; width: 100%; margin: 0 auto; text-align: var(--align); }}
.slide.layout-title .slide-inner {{ text-align: var(--title-align); }}
.slide.layout-title .slide-title {{ font-size: clamp(2.4rem, 5.2vw, 4.4rem); line-height: 1.05; letter-spacing: -0.03em; margin-bottom: 0.35em; }}
.slide.layout-section .slide-inner {{ text-align: center; }}
.slide.layout-section .slide-title {{ font-size: clamp(2rem, 3.8vw, 3.2rem); letter-spacing: -0.02em; }}
h1, h2, h3, h4 {{ color: var(--heading); font-family: var(--heading-font); margin: 0 0 0.6em; }}
h1.slide-title {{ font-size: 3rem; }}
h2.slide-title {{ font-size: clamp(1.8rem, 2.8vw, 2.5rem); }}
.slide-content {{ font-size: clamp(1.05rem, 1.5vw, 1.55rem); line-height: 1.6; }}
.slide-content > *:first-child {{ margin-top: 0; }}
.slide-content > *:last-child {{ margin-bottom: 0; }}
.slide-content p {{ margin: 0.55em 0; }}
.slide-content h1, .slide-content h2, .slide-content h3, .slide-content h4 {{ margin: 0.9em 0 0.35em; line-height: 1.2; }}
.slide-content h1 {{ font-size: 1.6em; }}
.slide-content h2 {{ font-size: 1.35em; }}
.slide-content h3 {{ font-size: 1.18em; }}
.slide-content h4 {{ font-size: 1.05em; }}
.slide-content ul, .slide-content ol {{ margin: 0.6em 0 0.6em 1.25em; padding-left: 0.35em; }}
.slide-content li {{ margin: 0.3em 0; }}
.slide-content li > ul, .slide-content li > ol {{ margin: 0.25em 0 0.25em 1em; }}
.slide-content strong {{ color: var(--heading); font-weight: 700; }}
.slide-content em {{ color: var(--accent); }}
.slide-content a {{ color: var(--accent); text-decoration: none; border-bottom: 1px solid rgba(127, 127, 127, 0.4); }}
.slide-content a:hover {{ border-bottom-color: var(--accent); }}
.slide-content blockquote {{ margin: 1em 0; padding: 0.7em 1.1em; border-left: 4px solid var(--accent); background: rgba(127, 127, 127, 0.10); border-radius: 0 12px 12px 0; font-style: italic; }}
.slide-content blockquote p {{ margin: 0.2em 0; }}
.slide-content table {{ width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 0.84em; }}
.slide-content th, .slide-content td {{ padding: 0.55em 0.75em; border-bottom: 1px solid rgba(127, 127, 127, 0.25); text-align: left; vertical-align: top; }}
.slide-content th {{ color: var(--heading); background: rgba(127, 127, 127, 0.12); font-weight: 600; }}
.slide-content tbody tr:hover td {{ background: rgba(127, 127, 127, 0.06); }}
.slide-content code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.86em; padding: 0.12em 0.38em; border-radius: 6px; background: rgba(127, 127, 127, 0.14); }}
.slide-content pre {{ margin: 1em 0; padding: 1em 1.2em; border-radius: 12px; background: rgba(0, 0, 0, 0.28); overflow: auto; }}
.slide-content pre code {{ padding: 0; background: none; }}
.slide-content img {{ max-width: 100%; max-height: 55vh; border-radius: 14px; box-shadow: 0 18px 45px rgba(0, 0, 0, 0.28); }}
.slide-content hr {{ border: none; height: 1px; margin: 1.2em 0; background: linear-gradient(90deg, transparent, rgba(127, 127, 127, 0.35), transparent); }}
.slide-content mark {{ background: var(--accent); color: #08111f; padding: 0 0.25em; border-radius: 4px; }}
.slide-number {{ position: absolute; right: 28px; bottom: 20px; font-size: 0.9rem; opacity: 0.72; display: {show_numbers}; }}
.controls {{ position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); display: flex; gap: 8px; z-index: 10; }}
.controls button {{ background: rgba(127, 127, 127, 0.16); color: var(--text); border: 1px solid rgba(127, 127, 127, 0.28); padding: 8px 14px; border-radius: 999px; cursor: pointer; font-size: 14px; backdrop-filter: blur(8px); }}
.controls button:hover {{ background: rgba(127, 127, 127, 0.28); }}
.progress {{ position: fixed; left: 0; bottom: 0; height: 4px; background: var(--accent); width: 0; transition: width 0.2s ease; z-index: 20; }}
.help {{ position: fixed; top: 14px; right: 18px; font-size: 12px; opacity: 0.55; }}
@media (max-width: 800px) {{
  .slide {{ padding: 32px 28px 60px; }}
  .slide-content {{ font-size: 1.1rem; }}
  h1.slide-title {{ font-size: 2.1rem; }}
  h2.slide-title {{ font-size: 1.7rem; }}
  .slide.layout-title .slide-title {{ font-size: 2.4rem; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .slide.active .slide-inner {{ animation: none; }}
  .progress {{ transition: none; }}
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
