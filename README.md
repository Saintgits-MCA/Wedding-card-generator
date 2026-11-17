# Kerala Wedding Card Generator

FastAPI + Jinja2 + Gemini wedding and engagement invitation studio.

## Improvements in this edition
- A natural-language **Your invitation idea** field guides both invitation wording and design.
- Backend wording prompts let Gemini write distinctive, custom English and/or Malayalam copy in the requested tone, rather than repeating stock invitation phrases.
- Gemini chooses fonts, colours, palette, borders, ornaments, dividers and patterns from backend-owned catalogues. Customers describe the desired result without needing to know technical design settings.
- The editor's Ask Gemini panel supports design-only, wording-only, combined updates and surprise redesign.
- Model design output is validated against renderer-supported choices; arbitrary HTML/CSS is never injected.
- Existing event data, bilingual options, editor controls and PNG/PDF workflows are retained.

## Install (Windows)
1. Extract the ZIP and open PowerShell in the project folder.
2. Run `py -m venv .venv` then `.venv\Scripts\Activate.ps1`.
3. Run `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and add your Gemini API key.
5. Run `python -m uvicorn main:app --reload`.
6. Open `http://127.0.0.1:8000`.

## Layout
- `main.py`
- `templates/form.html`
- `templates/card.html`
- `js/editor.js`

Keep `.env` private. The application expects it beside `main.py`.
