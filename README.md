# Presentation Toolbox

**Create, edit, and export beautiful HTML presentations — with reusable designs and AI assistance.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-22c55e)

Presentation Toolbox is a local, browser-based Python application for building HTML presentations. It combines a visual design editor, a slide editor, Markdown content, AI-assisted generation, and import/analysis of existing PowerPoint, PDF, and HTML files.

> Runs locally. Your presentations, designs, and API keys stay on your machine.

---

## Table of contents

- [Features](#features)
- [Quick start (Windows)](#quick-start-windows)
- [Manual installation](#manual-installation)
- [Usage](#usage)
- [AI providers](#ai-providers)
- [Import & design extraction](#import--design-extraction)
- [Project structure](#project-structure)
- [Data & configuration](#data--configuration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Presentations
- Create, edit, duplicate, and delete presentations.
- Slides with title, Markdown content, bullet points, speaker notes, and layouts (`title`, `default`, `section`).
- Reorder and remove slides.
- Live browser preview with keyboard navigation, progress bar, and fullscreen mode.
- Export/download as a standalone, self-contained HTML file.

### Designs
- Create and edit reusable themes: background, text, heading and accent colors, fonts, alignment, slide numbers, and custom CSS.
- Assign a design to any presentation and switch designs at any time.
- Import designs from JSON.
- Ships with **DigitEgal** standard designs: *Dark*, *Slate*, *Highlight*, *Clean*.

### AI assistance
- Generate presentations from a prompt (topic, audience, slide count).
- Generate designs from a style description.
- Use local models (LM Studio, Ollama) or cloud models (OpenAI, Anthropic Claude, Mistral, and other OpenAI-compatible APIs).
- Load available models directly from the provider and select them with one click.

### Import & analysis
- Import **PPTX**, **PDF**, and **HTML** files and transfer their content to any design.
- Extract colors, fonts, background, and accent colors from uploaded files to generate a similar design.
- AI-assisted structuring when text is available; heuristic fallback without AI.

### Usability
- **Tool beenden** button stops the local server from the UI.
- `start.bat` starts the app without a visible console window.
- `Presentation Toolbox.vbs` starts it completely hidden (ideal for a desktop shortcut).
- Automatic browser launch after startup.

---

## Quick start (Windows)

1. Download or clone this folder.
2. Double-click **`install.bat`** once. It creates `.venv` and installs all dependencies.
3. Double-click **`Presentation Toolbox.vbs`** (hidden start) or **`start.bat`**.
4. The browser opens automatically at **http://127.0.0.1:5000**.

To stop the app, click **Tool beenden** in the top-right corner of the UI.

> Requires Python 3.10+ with `python`/`pythonw` available in `PATH`.
> Download Python: <https://www.python.org/downloads/>

---

## Manual installation

```bash
python -m venv .venv
```

Activate the environment:

**CMD**
```bat
.venv\Scripts\activate.bat
```

**PowerShell**
```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the app:

```bash
python app.py
```

If `requirements.txt` fails, install the core packages directly:

```bash
python -m pip install Flask markdown pypdf pymupdf python-pptx
```

---

## Usage

### Create a presentation
1. Open the **Presentations** tab.
2. Click **+ New Presentation**.
3. Choose a design and edit the slides.
4. Save, preview, or download as HTML.

### Create or edit a design
1. Open the **Designs** tab.
2. Select an existing design or click **+ New Design**.
3. Adjust colors, fonts, alignment, slide numbers, and custom CSS.
4. Save. The design is immediately available for all presentations.

### Generate with AI
1. Open **AI Settings** and configure provider, base URL, model, and API key.
2. Click **Modelle laden** to list available models, then select one.
3. In **Presentations** or **Designs**, click **✨ AI Generate** and enter a prompt.

### Import an existing file
- **Content:** Presentations → **Import Datei** → choose `.pptx`, `.pdf`, or `.html` → select a target design → **Importieren & Speichern**.
- **Design:** Designs → **✨ AI Generate** → choose a file under *Ähnliches Design aus Datei* → generate and save.

---

## AI providers

| Provider | Provider setting | Base URL example | Model example | API key |
|---|---|---|---|---|
| LM Studio (local) | OpenAI-compatible | `http://localhost:1234/v1` | model shown in LM Studio | optional |
| Ollama (local) | Ollama | `http://localhost:11434` | `llama3.1` | optional |
| Ollama (OpenAI-compatible) | OpenAI-compatible | `http://localhost:11434/v1` | `llama3.1` | optional |
| OpenAI / ChatGPT | OpenAI-compatible | `https://api.openai.com/v1` | `gpt-4o-mini` | required |
| Anthropic Claude | Anthropic | `https://api.anthropic.com/v1` | `claude-3-5-sonnet-latest` | required |
| Mistral | OpenAI-compatible | `https://api.mistral.ai/v1` | `mistral-large-latest` | required |
| Other OpenAI-compatible APIs | OpenAI-compatible | provider `/v1` URL | provider-specific | usually required |

The app supports:
- **OpenAI-compatible** chat completions (`/chat/completions`) and model listing (`/models`).
- **Anthropic** messages API (`/messages`) and model listing.
- **Ollama** native chat (`/api/chat`) and model listing (`/api/tags`).

---

## Import & design extraction

| Format | Content extraction | Design extraction |
|---|---|---|
| **PPTX** | Slide titles, body text, bullets, notes via `python-pptx` | Theme/slide colors, background, fonts, palette |
| **PDF** | Page text, titles, bullets via `PyMuPDF`; fallback `pypdf` | Background color, text/heading colors, accent color, fonts (PyMuPDF) |
| **HTML** | Sections/slides, headings, text | CSS colors, variables, background, fonts, accent |

**Notes**
- PDFs need **selectable text**. Scanned/image-only PDFs require OCR first.
- Design extraction produces a heuristic design even if no AI provider is configured.
- With AI configured, extracted style hints and content are passed to the model for a more polished result.

---

## Project structure

```text
PresentationToolbox/
├─ app.py                     # Flask app and API routes
├─ app/
│  ├─ ai.py                   # AI provider integration
│  ├─ extractors.py           # PPTX / PDF / HTML extraction
│  ├─ renderer.py             # Standalone HTML renderer
│  ├─ storage.py              # JSON storage
│  ├─ templates/index.html    # Toolbox UI
│  └─ static/                 # CSS and JavaScript
├─ data/
│  ├─ designs/                # Design JSON files
│  └─ presentations/          # Presentation JSON files
├─ exports/                   # Exported HTML files
├─ logs/                      # Server log (hidden start)
├─ install.bat                # One-click installer
├─ start.bat                  # Start without visible console
├─ uninstall.bat              # Remove local environment
├─ Presentation Toolbox.vbs   # Fully hidden launcher
├─ requirements.txt
└─ README.md
```

---

## Data & configuration

- Designs: `data/designs/*.json`
- Presentations: `data/presentations/*.json`
- AI settings: `data/settings.json` (contains your API key — do not commit it)
- Exports: `exports/*.html`
- Server log: `logs/app.log`

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `5000` | HTTP port |
| `FLASK_DEBUG` | `0` | Set to `1` for debug mode |

---

## Troubleshooting

### The `.bat` files close immediately
- Ensure Python 3.10+ is installed and available in `PATH`.
- Run `install.bat` from the project folder.
- Start via `Presentation Toolbox.vbs` or `start.bat`.

### PDF import says no text was found
- The PDF may be a scan/image-only file. Use OCR or a PDF with selectable text.
- Ensure `pymupdf` (recommended) and `pypdf` are installed in `.venv`:
  ```bat
  .venv\Scripts\python.exe -m pip install pymupdf pypdf
  ```

### AI model cannot be reached
- Verify the provider is running (LM Studio/Ollama) and the base URL is correct.
- For cloud providers, check the API key and model name.
- Use **Modelle laden** in **AI Settings** to test the connection.

### Port 5000 is already in use
- Close the other instance or start with a different port:
  ```bat
  set PORT=5050
  .venv\Scripts\python.exe app.py
  ```

---

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Open a pull request.

Please keep changes focused and consistent with the existing code style.

---

## License

MIT License. See [LICENSE](LICENSE).
