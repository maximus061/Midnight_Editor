# Midnight Editor

A dark-themed, AI-assisted code editor built with **Python** and **PyQt6**.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![PyQt6](https://img.shields.io/badge/PyQt6-6.x-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

| Feature | Details |
|
| **Multi-tab editing** | Open and switch between multiple files simultaneously |
| **Line numbers** | Auto-sizing gutter on every editor tab |
| **File explorer** | Sidebar tree view — double-click any file to open it |
| **Integrated terminal** | Persistent `bash` / `cmd.exe` shell embedded in the window |
| **Syntax highlighting** | Dynamic Python highlighter with a fully customisable lexicon |
| **AI chat panel** | Right-side chat backed by any OpenAI-compatible local model via [LM Studio](https://lmstudio.ai) |
| **Code context toggle** | One-click "Include current file" injects your open file into the AI conversation |
| **Bearer auth** | Optional API key support for tunnelled / remote LM Studio instances |
| **Standalone binary** | Ships as a single executable (no Python install required on target machine) |


## Requirements

- Python 3.11+
- PyQt6

```
pip install PyQt6
```

---

## Running from source

```bash
git clone https://github.com/maximus061/Midnight_Editor.git
cd midnight-editor
pip install -r requirements.txt
python main.py
```

---

## Configuration

At the top of `main.py`, three constants control the AI backend:

```python
LM_STUDIO_URL   = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL = "model-identifier"   				# your model's ID in LM Studio
LM_STUDIO_KEY   = ""                   				# Bearer token — leave blank if auth is off
```

These can also be changed **at runtime** without restarting via **AI → Configure Endpoint…**

### LM Studio server-side auth

To require authentication on the LM Studio server, set `requireAuth` in  
`~/.lmstudio/.internal/http-server-config.json`:

```json
{
  "requireAuth": true
}
```

Then generate a token in LM Studio → Developer → Server Settings → Manage Tokens.

---

## Building a standalone executable

The repo includes a ready-made PyInstaller spec file.

```bash
pip install pyinstaller
pyinstaller Midnight_Editor.spec
```

The finished binary lands in `dist/Midnight_Editor` (Linux/macOS) or  
`dist\Midnight_Editor.exe` (Windows).

To rebuild from scratch:

```bash
pyinstaller --onefile --windowed --name "Midnight_Editor" main.py
```

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New tab |
| `Ctrl+O` | Open file |
| `Ctrl+Shift+O` | Open folder as project root |
| `Ctrl+S` | Save current file |
| `Ctrl+E` | Toggle file explorer |
| `Ctrl+T` | Toggle terminal |
| `Ctrl+I` | Toggle AI panel |
| `F11` | Toggle fullscreen |
| `Ctrl+Enter` | Send message in AI chat |

---

## Customising syntax highlighting

Use the **Lexicon** menu to:

- **Add Custom Word** — highlight any identifier across all open tabs instantly
- **Edit Category Color** — change the colour for `keywords`, `types`, or `custom` words

The lexicon is live: changes apply to all open tabs immediately without a restart.

---

## Project structure

```
midnight-editor/
├── main.py
├── requirements.txt
└── README.md
```

---
