import os
import signal
import threading
import webbrowser
from flask import Flask, jsonify, render_template, request, send_file, abort

from app import storage, ai, extractors
from app.renderer import render_presentation_html, export_presentation

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")


def ensure_seed():
    designs = storage.list_designs()
    if not designs:
        common = {
            "font_family": "Segoe UI, Arial, sans-serif",
            "heading_font_family": "Segoe UI, Arial, sans-serif",
            "show_slide_numbers": True,
            "slide_align": "left",
            "title_align": "center",
        }
        storage.save_design({
            "name": "DigitEgal Dark",
            "description": "Dark theme with brand blue and magenta accents (bg #17202c)",
            "settings": {**common, "background_color": "#17202c", "text_color": "#e6edf5", "heading_color": "#ffffff", "accent_color": "#29b6f6", "custom_css": ".slide-title{color:#ffffff;} .slide-content strong,.slide-content a{color:#29b6f6;} .progress{background:linear-gradient(90deg,#29b6f6,#c3317d);} .bullets li::marker{color:#c3317d;}"},
        })
        storage.save_design({
            "name": "DigitEgal Slate",
            "description": "Slate background variant with brand accents (bg #1c2735)",
            "settings": {**common, "background_color": "#1c2735", "text_color": "#e2e8f0", "heading_color": "#f8fafc", "accent_color": "#29b6f6", "custom_css": ".slide.layout-title .slide-title{color:#29b6f6;} .slide-content a{color:#29b6f6;} h2.slide-title{border-bottom:2px solid #c3317d; padding-bottom:0.2em; display:inline-block;} .progress{background:#29b6f6;}"},
        })
        storage.save_design({
            "name": "DigitEgal Highlight",
            "description": "Brand blue focus with magenta highlights on dark background",
            "settings": {**common, "background_color": "#17202c", "text_color": "#dbe7f3", "heading_color": "#29b6f6", "accent_color": "#c3317d", "title_align": "left", "custom_css": ".slide{border-left:8px solid #29b6f6;} .slide.layout-title,.slide.layout-section{border-left-color:#c3317d;} .slide-number{color:#29b6f6;} .bullets li::marker{color:#29b6f6;}"},
        })
        storage.save_design({
            "name": "DigitEgal Clean",
            "description": "Clean dark design with subtle contrast and brand accents",
            "settings": {**common, "background_color": "#1c2735", "text_color": "#eef4fb", "heading_color": "#ffffff", "accent_color": "#29b6f6", "custom_css": ".slide-inner{background:rgba(255,255,255,0.02); padding:32px 40px; border-radius:14px; border:1px solid rgba(41,182,246,0.25);} .slide.layout-title .slide-title{font-weight:700;} .slide-content em{color:#c3317d; font-style:normal;} .progress{background:#c3317d;}"},
        })
    if not storage.list_presentations():
        designs = storage.list_designs()
        dmap = {d.get("name"): d.get("id", "") for d in designs}
        def did(name):
            return dmap.get(name) or (designs[0].get("id", "") if designs else "")

        storage.save_presentation({
            "name": "Dartmouth Conference",
            "design_id": did("DigitEgal Dark"),
            "slides": [
                {"title": "Dartmouth Conference", "content": "**The Birth of Artificial Intelligence (1956)**", "bullets": [], "layout": "title"},
                {"title": "Background", "content": "In summer 1956, a group of researchers gathered at Dartmouth College to explore the idea that aspects of learning and intelligence could be precisely described and simulated by machines.", "bullets": ["Location: Dartmouth College, Hanover, New Hampshire", "Duration: ~6–8 weeks (Summer 1956)", "Organized as a research workshop"], "layout": "default"},
                {"title": "Key Organizers & Participants", "content": "The proposal and workshop brought together pioneers of computing and cognition.", "bullets": ["John McCarthy (coined “Artificial Intelligence”)", "Marvin Minsky", "Nathaniel Rochester", "Claude Shannon", "Other attendees included Allen Newell and Herbert A. Simon"], "layout": "default"},
                {"title": "Core Ideas Proposed", "content": "The proposal suggested that machines could be made to simulate human intelligence.", "bullets": ["Automatic computers and language use", "Neuron nets and abstraction", "Creativity and problem solving", "Self-improvement"], "layout": "default"},
                {"title": "Impact & Legacy", "content": "The Dartmouth workshop helped establish AI as a field and shaped decades of research.", "bullets": ["Popularized the term *Artificial Intelligence*", "Set an ambitious agenda for symbolic AI", "Influenced research directions, optimism, and later AI winters", "Remembered as a foundational moment in computing history"], "layout": "default"},
                {"title": "Key Takeaway", "content": "A small summer workshop launched a field that continues to transform science, business, and society.", "bullets": [], "layout": "section"},
            ],
        })
        storage.save_presentation({
            "name": "Digital Transformation",
            "design_id": did("DigitEgal Slate"),
            "slides": [
                {"title": "Digital Transformation", "content": "**Rethinking processes, culture, and value in a digital world**", "bullets": [], "layout": "title"},
                {"title": "What Is Digital Transformation?", "content": "Digital transformation is the integration of digital technology into all areas of an organization, changing how it operates and delivers value.", "bullets": ["Modernize processes and systems", "Improve customer and employee experiences", "Enable data-driven decisions"], "layout": "default"},
                {"title": "Key Drivers", "content": "Organizations transform in response to internal and external pressures.", "bullets": ["Changing customer expectations", "Competitive pressure and new business models", "Advances in cloud, data, AI, and connectivity", "Need for agility and resilience"], "layout": "default"},
                {"title": "Core Pillars", "content": "Successful transformation balances technology with people and process.", "bullets": ["**Technology:** cloud, automation, platforms", "**Data:** governance, analytics, insights", "**People:** skills, culture, change management", "**Process:** redesign for efficiency and value"], "layout": "default"},
                {"title": "Challenges", "content": "Transformation is as much organizational as it is technical.", "bullets": ["Legacy systems and technical debt", "Siloed data and processes", "Skill gaps and resistance to change", "Security, privacy, and compliance"], "layout": "default"},
                {"title": "Roadmap to Success", "content": "A pragmatic, iterative approach delivers sustainable results.", "bullets": ["Define clear vision and outcomes", "Start with high-value use cases", "Invest in people and governance", "Measure progress and scale what works"], "layout": "default"},
                {"title": "The Goal", "content": "Create an adaptable organization that continuously delivers value through digital capabilities.", "bullets": [], "layout": "section"},
            ],
        })
        storage.save_presentation({
            "name": "AI History",
            "design_id": did("DigitEgal Highlight"),
            "slides": [
                {"title": "AI History", "content": "**From early ideas to modern intelligent systems**", "bullets": [], "layout": "title"},
                {"title": "Early Foundations (1940s–1950s)", "content": "Theoretical and computational foundations set the stage for AI.", "bullets": ["Turing’s work on computation and machine intelligence (1950)", "Dartmouth Conference (1956) coins “Artificial Intelligence”", "Early programs for logic, games, and problem solving"], "layout": "default"},
                {"title": "Symbolic AI & Expert Systems (1960s–1980s)", "content": "Researchers focused on rules, knowledge, and reasoning.", "bullets": ["Growth of symbolic methods and knowledge representation", "Expert systems applied in industry", "Periods of optimism followed by AI winters due to limits and funding cuts"], "layout": "default"},
                {"title": "Machine Learning Rises (1990s–2010s)", "content": "Data and statistical methods became central to progress.", "bullets": ["Advances in probabilistic models and neural networks", "Milestones: Deep Blue (1997), Watson (2011)", "Deep learning breakthroughs in vision and speech (2012+)"], "layout": "default"},
                {"title": "Modern Era (2017–Today)", "content": "Large-scale models expanded capabilities and adoption.", "bullets": ["Transformers and large language models", "Generative AI for text, code, and media", "Wider deployment across products, science, and business", "Growing focus on safety, alignment, and governance"], "layout": "default"},
                {"title": "Looking Ahead", "content": "AI continues to evolve through research, applications, and responsible development.", "bullets": ["More capable and efficient models", "Human–AI collaboration", "Emphasis on trust, ethics, and societal impact"], "layout": "section"},
            ],
        })


@app.route("/")
def index():
    ensure_seed()
    return render_template("index.html")


# ---- Designs API ----

@app.get("/api/designs")
def api_list_designs():
    return jsonify(storage.list_designs())


@app.get("/api/designs/<design_id>")
def api_get_design(design_id):
    d = storage.get_design(design_id)
    if not d:
        abort(404)
    return jsonify(d)


@app.post("/api/designs")
def api_create_design():
    data = request.get_json(force=True) or {}
    data.pop("id", None)
    return jsonify(storage.save_design(data)), 201


@app.put("/api/designs/<design_id>")
def api_update_design(design_id):
    data = request.get_json(force=True) or {}
    data["id"] = design_id
    if not storage.get_design(design_id):
        abort(404)
    return jsonify(storage.save_design(data))


@app.delete("/api/designs/<design_id>")
def api_delete_design(design_id):
    if not storage.delete_design(design_id):
        abort(404)
    return jsonify({"ok": True})


@app.post("/api/designs/import")
def api_import_design():
    # Accept JSON body or uploaded file
    data = None
    if request.is_json:
        data = request.get_json(silent=True)
    if data is None and 'file' in request.files:
        import json as _json
        try:
            data = _json.load(request.files['file'])
        except Exception:
            abort(400, description="Invalid JSON file")
    if not data or not isinstance(data, dict):
        abort(400, description="Invalid design JSON")
    # Import as a new design (ignore provided id to avoid collisions)
    payload = {
        "name": data.get("name") or "Imported Design",
        "description": data.get("description") or "",
        "settings": data.get("settings") or {},
    }
    design = storage.save_design(payload)
    return jsonify(design), 201


# ---- Presentations API ----

@app.get("/api/presentations")
def api_list_presentations():
    return jsonify(storage.list_presentations())


@app.get("/api/presentations/<pres_id>")
def api_get_presentation(pres_id):
    p = storage.get_presentation(pres_id)
    if not p:
        abort(404)
    return jsonify(p)


@app.post("/api/presentations")
def api_create_presentation():
    data = request.get_json(force=True) or {}
    data.pop("id", None)
    return jsonify(storage.save_presentation(data)), 201


@app.put("/api/presentations/<pres_id>")
def api_update_presentation(pres_id):
    data = request.get_json(force=True) or {}
    data["id"] = pres_id
    if not storage.get_presentation(pres_id):
        abort(404)
    return jsonify(storage.save_presentation(data))


@app.delete("/api/presentations/<pres_id>")
def api_delete_presentation(pres_id):
    if not storage.delete_presentation(pres_id):
        abort(404)
    return jsonify({"ok": True})


# ---- Settings & AI ----

@app.get("/api/settings")
def api_get_settings():
    s = storage.get_settings()
    # do not expose api_key in full? keep simple but mask hint; return as-is for local tool usability
    return jsonify(s)


@app.put("/api/settings")
def api_save_settings():
    data = request.get_json(force=True) or {}
    saved = storage.save_settings(data)
    return jsonify(saved)


@app.post("/api/shutdown")
def api_shutdown():
    def _shutdown():
        try:
            os.kill(os.getpid(), signal.SIGINT)
        except Exception:
            os._exit(0)
    threading.Timer(0.5, _shutdown).start()
    return jsonify({"ok": True, "message": "Shutting down"})


@app.post("/api/ai/models")
def api_ai_models():
    data = request.get_json(silent=True) or {}
    # allow passing config directly (from form) or fall back to saved settings
    if data.get("ai") or data.get("provider") or data.get("base_url"):
        if "ai" in data and isinstance(data.get("ai"), dict):
            settings = {"ai": data["ai"]}
        else:
            settings = {"ai": {
                "provider": data.get("provider"),
                "base_url": data.get("base_url"),
                "api_key": data.get("api_key"),
                "model": data.get("model"),
            }}
    else:
        settings = storage.get_settings()
    try:
        models = ai.list_models(settings)
        return jsonify({"models": models})
    except ai.AIError as e:
        return jsonify({"error": str(e), "models": []}), 400
    except Exception as e:
        return jsonify({"error": str(e), "models": []}), 500


@app.post("/api/ai/generate-design")
def api_ai_generate_design():
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    try:
        result = ai.generate_design(storage.get_settings(), prompt)
    except ai.AIError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if data.get("save"):
        saved = storage.save_design(result)
        return jsonify({"result": result, "saved": saved})
    return jsonify({"result": result})


@app.post("/api/ai/generate-presentation")
def api_ai_generate_presentation():
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    slide_count = data.get("slide_count")
    try:
        result = ai.generate_presentation(storage.get_settings(), prompt, slide_count=slide_count)
    except ai.AIError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if data.get("save"):
        payload = {
            "name": result.get("name") or "AI Presentation",
            "design_id": data.get("design_id") or "",
            "slides": result.get("slides") or [],
        }
        saved = storage.save_presentation(payload)
        return jsonify({"result": result, "saved": saved})
    return jsonify({"result": result})


@app.post("/api/ai/generate-design-from-file")
def api_ai_generate_design_from_file():
    if 'file' not in request.files:
        return jsonify({"error": "File is required"}), 400
    try:
        extracted = extractors.extract_file(request.files['file'])
        hints = extractors.summarize_for_design(extracted)
    except Exception as e:
        return jsonify({"error": f"Could not analyze file: {e}"}), 400
    prompt = (request.form.get('prompt') or "").strip()
    full_prompt = "Create a presentation design similar to the style of the uploaded file.\n\n" + hints
    if prompt:
        full_prompt += "\n\nAdditional instructions:\n" + prompt
    ai_error = None
    source = "ai"
    try:
        result = ai.generate_design(storage.get_settings(), full_prompt)
    except Exception as e:
        # Heuristic fallback: build a design directly from extracted colors/fonts
        ai_error = str(e)
        source = "heuristic"
        name = os.path.splitext(getattr(request.files['file'], 'filename', '') or 'Imported Style')[0]
        result = extractors.design_from_hints(extracted, name=f"{name} Style" if name else None)
    if request.form.get('save', 'true').lower() in ('1', 'true', 'yes', 'on'):
        saved = storage.save_design(result)
        resp = {"result": result, "saved": saved, "hints": extracted.get("design_hints"), "source": source}
        if ai_error:
            resp["ai_warning"] = ai_error
        return jsonify(resp)
    resp = {"result": result, "hints": extracted.get("design_hints"), "source": source}
    if ai_error:
        resp["ai_warning"] = ai_error
    return jsonify(resp)


@app.post("/api/presentations/import-file")
def api_import_presentation_file():
    if 'file' not in request.files:
        return jsonify({"error": "File is required"}), 400
    f = request.files['file']
    filename = f.filename or "Imported Presentation"
    try:
        extracted = extractors.extract_file(f)
    except Exception as e:
        return jsonify({"error": f"Could not analyze file: {e}"}), 400
    slides = extracted.get("slides") or []
    text = (extracted.get("text") or "").strip()
    ftype = extracted.get("type") or "file"
    name = (request.form.get('name') or "").strip() or os.path.splitext(filename)[0] or "Imported Presentation"
    design_id = request.form.get('design_id') or ""
    use_ai = request.form.get('use_ai', 'true').lower() in ('1', 'true', 'yes', 'on')
    ai_error = None

    # If no slides extracted, try AI to structure available text/content
    if use_ai and not slides:
        try:
            if text:
                prompt = (
                    f"Create a structured presentation from the following content extracted from a {ftype.upper()} file named '{filename}'.\n"
                    f"Preserve the key topics, facts, and structure. Create clear slide titles, concise content (Markdown allowed), and useful bullets.\n\n"
                    f"EXTRACTED CONTENT:\n{text[:12000]}"
                )
                result = ai.generate_presentation(storage.get_settings(), prompt)
            else:
                # No extractable text (e.g. scanned/image-only PDF or missing PDF extractor): cannot reliably send file to text-only provider
                if ftype == "pdf" and not extracted.get("pdf_text_extractor"):
                    ai_error = "No extractable text found. PDF text extraction library (pypdf) is not available in the running Python environment. Run install.bat and start the app via start.bat (.venv), then try again."
                else:
                    ai_error = "No extractable text found in file. The PDF may be scanned/image-only. AI text models require extracted/selectable text (use OCR or a PDF with selectable text)."
                result = None
            if result:
                ai_slides = result.get("slides") or []
                if ai_slides:
                    slides = ai_slides
                    if result.get("name") and not (request.form.get('name') or "").strip():
                        name = result.get("name")
        except Exception as e:
            ai_error = str(e)

    if not slides:
        if text:
            # last-resort fallback chunking
            paras = [p.strip() for p in text.split("\n\n") if p.strip()]
            for i, ptxt in enumerate(paras[:30], start=1):
                lines = [ln.strip() for ln in ptxt.splitlines() if ln.strip()]
                title = (lines[0][:120] if lines else f"Slide {i}")
                rest = lines[1:]
                bullets = rest if 1 < len(rest) <= 8 else []
                content = "" if bullets else "\n".join(rest[:6])
                slides.append({"title": title, "content": content, "bullets": bullets, "notes": "", "layout": "title" if i == 1 else "default"})

    if not slides:
        msg = "No presentation content/slides could be extracted from the file."
        if ftype == "pdf":
            if not extracted.get("pdf_text_extractor"):
                msg += " pypdf is not installed/available in the running Python environment. Run install.bat and start via start.bat (.venv)."
            elif not extracted.get("has_text"):
                msg += " No selectable text was found (the PDF may be scanned/image-only). Use OCR or a PDF with selectable text."
            else:
                msg += " Could not structure extracted PDF text."
        if ai_error:
            msg += f" AI: {ai_error}"
        return jsonify({"error": msg}), 400

    payload = {
        "name": name,
        "design_id": design_id,
        "slides": slides,
    }
    saved = storage.save_presentation(payload)
    resp = {"saved": saved, "slides_count": len(slides), "type": ftype}
    if ai_error:
        resp["ai_warning"] = ai_error
    return jsonify(resp)


# ---- Preview / Export ----

@app.get("/preview/<pres_id>")
def preview(pres_id):
    p = storage.get_presentation(pres_id)
    if not p:
        abort(404)
    design = storage.get_design(p.get("design_id")) if p.get("design_id") else None
    return render_presentation_html(p, design)


@app.post("/api/presentations/<pres_id>/export")
def api_export(pres_id):
    p = storage.get_presentation(pres_id)
    if not p:
        abort(404)
    design = storage.get_design(p.get("design_id")) if p.get("design_id") else None
    path = export_presentation(p, design)
    return jsonify({"ok": True, "path": path, "filename": os.path.basename(path)})


@app.get("/api/presentations/<pres_id>/download")
def api_download(pres_id):
    p = storage.get_presentation(pres_id)
    if not p:
        abort(404)
    design = storage.get_design(p.get("design_id")) if p.get("design_id") else None
    from io import BytesIO
    html_str = render_presentation_html(p, design)
    buf = BytesIO(html_str.encode("utf-8"))
    buf.seek(0)
    filename = (p.get("name") or "presentation").replace(" ", "_") + ".html"
    return send_file(buf, as_attachment=True, download_name=filename, mimetype="text/html")


if __name__ == "__main__":
    ensure_seed()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    url = f"http://{host}:{port}"

    def _open_browser():
        try:
            webbrowser.open(url)
        except Exception:
            pass

    # Open browser once on startup (avoid opening during reloader child process)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        threading.Timer(1.0, _open_browser).start()
    elif os.environ.get("WERKZEUG_RUN_MAIN") is None:
        # default run (debug off below) -> open
        threading.Timer(1.0, _open_browser).start()

    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
