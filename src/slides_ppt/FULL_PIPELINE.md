# Slides PPT Module

This module generates PowerPoint slides from JSON specifications using a two-agent architecture.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        slides_ppt Module                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Input: Slide descriptions (id, title, content, layout_hint)        │
│                          │                                           │
│                          ▼                                           │
│   ┌─────────────────────────────────────────┐                        │
│   │           orchestrator.py               │                        │
│   │  Coordinates the Designer → Render flow │                        │
│   └───────────────────┬─────────────────────┘                        │
│                       │                                              │
│         ┌─────────────┴─────────────┐                                │
│         ▼                           ▼                                │
│   ┌───────────────┐          ┌───────────────┐                       │
│   │ designer_agent│          │  render_agent │                       │
│   │    (Gemini)   │          │               │                       │
│   └───────┬───────┘          └───────┬───────┘                       │
│           │                          │                               │
│           │ Layout JSON              │ Uses:                         │
│           │                          │  • slide_generator.py         │
│           │                          │  • math_renderer.py           │
│           │                          │  • text_utils.py              │
│           │                          │  • Gemini Imagen (images)     │
│           │                          │                               │
│           └──────────┬───────────────┘                               │
│                      ▼                                               │
│              Output Files:                                           │
│              • {slide_id}_layout.json                                │
│              • {slide_id}.pptx                                       │
│              • {slide_id}.jpg (optional)                             │
│              • presentation.pptx (merged)                            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## File Descriptions

### Core Pipeline Files

| File | Description |
|------|-------------|
| `slides_ppt.py` | Main entry point. Exposes `SlidesModule_PPT` class with `load()` and `run()` methods. |
| `orchestrator.py` | Coordinates the Designer → Render pipeline. Saves layout JSON and merges final PPTX. |
| `designer_agent.py` | Uses Gemini API to convert abstract slide descriptions into concrete Layout JSON. |
| `render_agent.py` | Converts Layout JSON to PPTX files. Handles image generation via Gemini Imagen. |

### Utility Files

| File | Description |
|------|-------------|
| `slide_generator.py` | Core PPTX generation logic. Creates slides from Layout JSON using python-pptx. |
| `math_renderer.py` | Renders LaTeX equations to PNG images using matplotlib. Includes caching. |
| `text_utils.py` | Text fitting utilities. Auto-sizes fonts to prevent overflow. |
| `prompts.py` | Contains the Designer Agent's system prompt with element schema and examples. |
| `__init__.py` | Module exports: `SlidesModule_PPT`, `SlideOrchestrator`, `DesignerAgent`, `RenderAgent`. |

---

## How Files Interact

### 1. Entry Point (`slides_ppt.py`)
```python
module = SlidesModule_PPT(gemini_client, output_root='./output')
module.load()  # Initialize orchestrator
result = module.run(slides_data)  # Returns output directory path
```

### 2. Orchestrator Flow (`orchestrator.py`)
For each slide:
1. Calls `designer.design_layout(slide_data)` → returns Layout JSON
2. Saves Layout JSON to `{slide_id}_layout.json`
3. Calls `render.render(layout_json)` → returns PPTX path
4. After all slides: merges into `presentation.pptx`

### 3. Designer Agent (`designer_agent.py`)
- Sends slide data + system prompt to Gemini API
- Extracts JSON from response (handles markdown code blocks)
- Returns Layout JSON with elements, positions, styles

### 4. Render Agent (`render_agent.py`)
1. **Prepare Assets**: Scans for `image` elements with `prompt` field
   - Generates images via Gemini Imagen API
   - Caches generated images by prompt hash
2. **Generate PPTX**: Calls `slide_generator.generate_single_slide()`
3. **Convert to Image** (optional): Uses LibreOffice → PDF → JPG

### 5. Slide Generator (`slide_generator.py`)
- Handles layouts: `TITLE`, `CONTENT`, `SECTION`, `TWO_CONTENT`, `COMPARISON`, `CUSTOM`
- For `CUSTOM` layout, iterates through `content.elements[]` and renders:
  - `textbox`: Text with font styling
  - `math`: LaTeX via `math_renderer.py`
  - `image`: Image file embedding
  - `shape`: Rectangles, ovals with optional text
  - `table`: Data tables
  - `chart`: Column, bar, line, pie charts

---

## Layout JSON Schema

### Standard Layouts
```json
{
  "layout": "TITLE",
  "content": {"title": "...", "subtitle": "..."},
  "style": {"background": "#FFFFFF"}
}
```

### CUSTOM Layout (Full Control)
```json
{
  "layout": "CUSTOM",
  "style": {"background": "#FFFFFF"},
  "content": {
    "elements": [
      {"type": "textbox", "text": "...", "x": 1.0, "y": 0.5, "w": 10, "h": 1, "style": {...}},
      {"type": "math", "latex": "E=mc^2", "x": 1.0, "y": 2.0, "w": 4, "h": 1, "style": {...}},
      {"type": "image", "prompt": "...", "x": 6.0, "y": 2.0, "w": 5, "h": 3}
    ]
  }
}
```

**Canvas**: 13.33" × 7.5" (standard 16:9). Units are inches. Origin (0,0) is top-left.

---

## Testing

### Direct Layout JSON Test (No LLM Required)
Test the render pipeline directly with pre-defined Layout JSON:

```bash
# Set API key (only needed for image generation)
export GEMINI_API_KEY="YOUR-GEMINI-API-KEY"

# Run from project root
python -c "
import json
from src.slides_ppt.render_agent import RenderAgent

# Pre-defined layout (no designer needed)
layout = {
    'id': 'test_math',
    'layout': 'CUSTOM',
    'style': {'background': '#FFFFFF'},
    'content': {
        'elements': [
            {'type': 'textbox', 'text': 'Math Test', 'x': 0.5, 'y': 0.5, 'w': 12, 'h': 1,
             'style': {'font_size': 44, 'bold': True, 'alignment': 'CENTER'}},
            {'type': 'math', 'latex': 'E = mc^2', 'x': 4, 'y': 3, 'w': 5, 'h': 1.5,
             'style': {'font_size': 48}}
        ]
    }
}

agent = RenderAgent('./test_output')
result = agent.render(layout)
print(f'PPTX: {result.get(\"pptx_path\")}')
"
```

### Full Pipeline Test (With Designer)
```bash
python -c "
from src import SlidesModule_PPT, GeminiClient, AppConfig
import yaml

with open('config/default.yaml') as f:
    config = AppConfig(**yaml.safe_load(f))

client = GeminiClient(config.llm)
module = SlidesModule_PPT(client, output_root='./test_output')
module.load()

slides = [{'id': 'slide1', 'title': 'Hello World', 'content': 'Test content.'}]
result = module.run(slides)
print(f'Output: {result}')
"
```

### Run Example JSON Files
```bash
python -c "
import json
from src.slides_ppt.render_agent import RenderAgent

with open('tests/slides_ppt_examples/math_test.json') as f:
    slides = json.load(f)

agent = RenderAgent('./test_output')
for slide in slides:
    result = agent.render(slide)
    print(f'{slide[\"id\"]}: {result.get(\"pptx_path\")}')
"
```

---

## Image Generation

Images are generated via **Gemini Imagen API** when an `image` element has a `prompt` field but no valid `path`.

```json
{
  "type": "image",
  "prompt": "A neural network diagram with interconnected nodes",
  "x": 2.0, "y": 2.0, "w": 9, "h": 4
}
```

- Images are cached by prompt MD5 hash in `{output_dir}/assets/`
- Uses `imagen-4.0-generate-001` model with 16:9 aspect ratio
- Requires `GEMINI_API_KEY` environment variable

---

## Dependencies

```
python-pptx    # PPTX generation
matplotlib     # Math rendering
google-genai   # Gemini API (LLM + Imagen)
pdf2image      # Optional: PPTX → image conversion
```

System dependencies (optional, for image export):
```bash
sudo apt install libreoffice poppler-utils
```
