"""Flexible Kerala Wedding Card Generator — FastAPI + Gemini."""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

load_dotenv()

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Wedding Card Generator")

app.mount("/js", StaticFiles(directory=BASE / "js"), name="js")
templates = Jinja2Templates(directory=str(BASE / "templates"))


def nl2br(value):
    return Markup(str(escape(value or "")).replace("\n", "<br>"))


templates.env.filters["nl2br"] = nl2br


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

def clean(value):
    return (value or "").strip().strip("\"'").strip()


GEMINI_KEY = clean(os.getenv("GEMINI_API_KEY", ""))



def model_name(raw, default):
    raw = clean(raw)
    raw = raw.split("/models/")[-1].replace("models/", "").split(":")[0]
    raw = "".join(raw.split())
    return raw if re.fullmatch(r"[A-Za-z0-9._-]+", raw or "") else default


MODELS = list(dict.fromkeys([
    model_name(os.getenv("GEMINI_MODEL", ""), "gemini-2.5-flash"),
    "gemini-2.5-flash-lite","gemini-3.5-flash"
]))

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


def proxy_url():
    value = clean(os.getenv("GEMINI_PROXY", ""))
    if not value:
        return None

    try:
        parsed = urlparse(value)
        _ = parsed.port
        if parsed.scheme in ("http", "https", "socks5") and parsed.hostname:
            return value
    except ValueError:
        pass

    print("[warn] Invalid GEMINI_PROXY; ignoring it.")
    return None


def make_client():
    options = {"timeout": 90, "trust_env": False}
    proxy = proxy_url()
    if proxy:
        options["proxy"] = proxy
    return httpx.AsyncClient(**options)


def parse_json(text):
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    decoder = json.JSONDecoder()
    index = 0
    found = []

    while index < len(text):
        positions = [
            pos for pos in (text.find("{", index), text.find("[", index))
            if pos != -1
        ]
        if not positions:
            break

        start = min(positions)
        try:
            obj, end = decoder.raw_decode(text, start)
            found.append(obj)
            index = end
        except json.JSONDecodeError:
            index = start + 1

    if not found:
        raise ValueError("Gemini did not return valid JSON.")

    if len(found) == 1:
        return found[0]

    merged = {}
    for item in found:
        if isinstance(item, dict):
            merged.update(item)

    return merged or found[0]


async def call_gemini(system, payload, temperature=0.7):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{
            "role": "user",
            "parts": [{
                "text": json.dumps(payload, ensure_ascii=False)
            }]
        }],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }

    headers = {
        "x-goog-api-key": GEMINI_KEY,
        "Content-Type": "application/json",
    }

    last_error = RuntimeError("Gemini request failed.")

    async with make_client() as client:
        for model in MODELS:
            for attempt in range(2):
                try:
                    response = await client.post(
                        f"{API_ROOT}/{model}:generateContent",
                        headers=headers,
                        json=body,
                    )
                except httpx.HTTPError as exc:
                    last_error = RuntimeError(f"Network error: {exc}")
                    await asyncio.sleep(1)
                    continue

                if response.status_code == 200:
                    try:
                        parts = response.json()["candidates"][0]["content"]["parts"]
                        text = "".join(
                            part.get("text", "") for part in parts
                        )
                        return parse_json(text)
                    except Exception as exc:
                        last_error = RuntimeError(
                            f"Could not read Gemini response: {exc}"
                        )
                        break

                message = response.text[:700].replace("\n", " ")
                lower_message = message.lower()
                
                if response.status_code == 429 or "resource_exhausted" in lower_message or "quota" in lower_message or "limit" in lower_message:
                    friendly_msg = "Gemini API rate limit or quota exceeded. Using robust fallback styling and fine-tuning controls."
                else:
                    friendly_msg = f"Gemini request encountered an issue (HTTP {response.status_code})."
                    
                last_error = RuntimeError(friendly_msg)

                # A quota/billing limit is not fixed by retrying another model.
                quota_error = any(term in lower_message for term in (
                    "exceeded your current quota",
                    "quota exceeded",
                    "billing",
                    "limit: 0",
                    "free_tier",
                    "resource_exhausted",
                ))

                if response.status_code in (400, 401, 403) or quota_error:
                    raise last_error

                if response.status_code in (429, 500, 503):
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue

                break

    raise last_error


# ============================================================
# WORDING GENERATION
# ============================================================

WORDING_PROMPT = """
You are the lead invitation copywriter for a premium Kerala wedding stationery studio.
Create beautiful, natural, memorable invitation copy rather than filling a rigid template.
The customer's own creative brief is a first-class instruction: follow its requested voice,
length, cultural register, emotional mood, formality, poetic style, wording structure and
special phrases as closely as possible.

The customer may request traditional, contemporary, poetic, devotional, warm, intimate,
formal, joyful, minimalist, literary, family-centred, or an original voice. Do not force
all invitations into stock phrases. Vary sentence construction and vocabulary to suit
this couple. The result should feel intentionally written for them.

The structured input contains verified event facts and requested languages. Preserve names
exactly. Never invent or alter dates, times, venues, family relationships, phone numbers,
addresses or hosts. Creatively rewrite invitation sentences, blessings, introductions and
closings. If a factual value is absent, leave its corresponding output empty. Never
translate or transliterate personal names unless explicitly requested.

For Malayalam, write fluent idiomatic Malayalam in Malayalam script, not awkward literal
translation. For English, use polished natural English. For bilingual output, make both
versions read naturally in their own language. Respect community and customer preferences
without assuming religious wording that was not requested.

Return ONLY valid JSON, with exactly the requested language keys ("en" and/or "ml").
Each language object must contain: opening, hosted_by, bride_name, groom_name,
bride_parents, groom_parents, bride_address, groom_address.
For each requested event ("wedding" and/or "engagement"), include: invite_line,
date_text, time_text, venue_text, closing, compliments_from.

Use supplied facts as the source of truth. Keep copy elegant and readable; concise by
default, but honour explicit requests for longer, more poetic or traditional wording.
No markdown, commentary or extra JSON keys.
"""


# ============================================================
# DESIGN SYSTEM
# ============================================================

EN_FONTS = ['Cormorant Garamond', 'Playfair Display', 'Great Vibes', 'Cinzel', 'Lora', 'Marcellus', 'EB Garamond', 'Libre Baskerville', 'Bodoni Moda', 'DM Serif Display', 'Crimson Pro', 'Prata', 'Forum', 'Cormorant Infant', 'Montserrat', 'Raleway', 'Poppins', 'Allura', 'Alex Brush', 'Parisienne', 'Tangerine', 'Sacramento', 'Italianno']

ML_FONTS = ['Noto Serif Malayalam', 'Manjari', 'Anek Malayalam', 'Noto Sans Malayalam', 'Gayathri', 'Rachana', 'Meera', 'Chilanka', 'Karumbi']

BORDERS = ["double", "temple", "corners", "single", "dots", "none"]
DIVIDERS = ["line", "diamond", "dots", "none"]
PATTERNS = ["none", "dots", "lines", "vignette"]
NAME_SIZES = ["md", "lg", "xl"]

ORNAMENTS = {
    "floral": "❀",
    "star": "✦",
    "cross": "✝",
    "crescent": "☪",
    "diamond": "❖",
    "lotus": "❀",
    "leaf": "❧",
    "heart": "♥",
    "arch": "⌂",
    "om": "ॐ",
    "none": "",
}

DEFAULT_DESIGNS = {
    "Hindu": {
        "paper": "#FFF8E8", "ink": "#6E1E1E", "accent": "#B8860B",
        "display_font": "Cinzel", "body_font": "Cormorant Garamond",
        "ml_font": "Noto Serif Malayalam", "border": "temple",
        "ornament": "om", "divider": "diamond", "pattern": "none",
        "name_size": "lg",
    },
    "Christian": {
        "paper": "#FDFCF8", "ink": "#1F3A5F", "accent": "#B8860B",
        "display_font": "Great Vibes", "body_font": "Cormorant Garamond",
        "ml_font": "Noto Serif Malayalam", "border": "double",
        "ornament": "cross", "divider": "line", "pattern": "none",
        "name_size": "xl",
    },
    "Muslim": {
        "paper": "#F7FBF8", "ink": "#14532D", "accent": "#B8860B",
        "display_font": "Playfair Display", "body_font": "Lora",
        "ml_font": "Manjari", "border": "dots", "ornament": "crescent",
        "divider": "dots", "pattern": "dots", "name_size": "lg",
    },
    "Other": {
        "paper": "#FFFDF8", "ink": "#7A1F2B", "accent": "#B8860B",
        "display_font": "Playfair Display", "body_font": "Cormorant Garamond",
        "ml_font": "Noto Serif Malayalam", "border": "corners",
        "ornament": "floral", "divider": "diamond", "pattern": "vignette",
        "name_size": "lg",
    },
}


DESIGN_PROMPT = f"""
You are the creative director of a premium Kerala wedding invitation design studio.
Interpret the customer's free-form brief as the primary art direction. It may describe
colours, mood, visual references, materials, cultural details, motifs, typography,
composition, ornament density, minimalism, luxury, or an original concept.

You choose the exact palette, font combination, border, ornament, divider, pattern and
name scale from the backend catalogue below. Do not make the customer choose technical
values. Make a coherent, distinctive choice that expresses the brief. If the brief is
short or empty, invent a fresh, polished concept suited to the event and community.
Avoid repeating the previous design when asked to surprise or redesign.

BACKEND CATALOGUE — choose exact values only:
English fonts: {', '.join(EN_FONTS)}
Malayalam fonts: {', '.join(ML_FONTS)} 


Choose harmonious six-digit HEX colours for paper, ink and accent. The backend validates
colours and enforces readable contrast. Choose solid or gradient backgrounds and valid
HEX gradient endpoints. Use catalogue font/effect names only. Choose a Malayalam-capable
font when Malayalam is present. Prioritize legibility and print suitability.



Do not return HTML, CSS, scripts, arbitrary class names or markdown. Do not invent
invitation wording or event facts. Prioritize the customer's brief.
"""


# ============================================================
# DESIGN VALIDATION AND CSS SAFETY
# ============================================================

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def valid_hex(value, fallback):
    if isinstance(value, str) and HEX.fullmatch(value.strip()):
        return value.strip().upper()
    return fallback


def luminance(hex_colour):
    channels = [
        int(hex_colour[i:i + 2], 16) / 255
        for i in (1, 3, 5)
    ]
    channels = [
        c / 12.92 if c <= 0.03928
        else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return (
        0.2126 * channels[0]
        + 0.7152 * channels[1]
        + 0.0722 * channels[2]
    )


def contrast_ratio(a, b):
    high, low = sorted(
        (luminance(a), luminance(b)),
        reverse=True,
    )
    return (high + 0.05) / (low + 0.05)


def safe_gradient_angle(value):
    try:
        number = int(float(value))
        return max(0, min(360, number))
    except (TypeError, ValueError):
        return 135


def sanitize_design(raw, community="Other", user_ink=None):
    base = dict(DEFAULT_DESIGNS.get(
        community, DEFAULT_DESIGNS["Other"]
    ))

    raw = raw if isinstance(raw, dict) else {}
    design = dict(base)

    # Unlimited user/Gemini HEX colours, validated before use.
    design["paper"] = valid_hex(raw.get("paper"), base["paper"])
    design["ink"] = valid_hex(raw.get("ink"), base["ink"])
    design["accent"] = valid_hex(raw.get("accent"), base["accent"])

    for key, allowed in (
        ("display_font", EN_FONTS),
        ("body_font", EN_FONTS),
        ("ml_font", ML_FONTS),
        ("border", BORDERS),
        ("divider", DIVIDERS),
        ("pattern", PATTERNS),
        ("name_size", NAME_SIZES),
    ):
        if raw.get(key) in allowed:
            design[key] = raw[key]

    if raw.get("ornament") in ORNAMENTS:
        design["ornament"] = raw["ornament"]

    # Background configuration.
    background_type = raw.get("background_type", "solid")
    if background_type not in ("solid", "gradient"):
        background_type = "solid"

    background_color = valid_hex(
        raw.get("background_color"),
        design["paper"],
    )
    gradient_start = valid_hex(
        raw.get("gradient_start"),
        design["paper"],
    )
    gradient_end = valid_hex(
        raw.get("gradient_end"),
        background_color,
    )
    angle = safe_gradient_angle(raw.get("gradient_angle", 135))

    design["background_type"] = background_type
    design["background_color"] = background_color
    design["gradient_start"] = gradient_start
    design["gradient_end"] = gradient_end
    design["gradient_angle"] = angle

    if background_type == "gradient":
        design["background_css"] = (
            f"linear-gradient({angle}deg, "
            f"{gradient_start} 0%, {gradient_end} 100%)"
        )
    else:
        design["background_css"] = background_color

    # Keep the text readable.
    if contrast_ratio(design["ink"], design["paper"]) < 4.5:
        design["ink"] = base["ink"]

    if user_ink:
        # Legacy form compatibility: allow a custom HEX ink value.
        if HEX.fullmatch(str(user_ink).strip()):
            design["ink"] = user_ink.strip().upper()

    design["mood"] = str(raw.get("mood") or "Custom design")[:120]
    design["background_description"] = str(
        raw.get("background_description") or ""
    )[:300]
    design["decoration_description"] = str(
        raw.get("decoration_description") or ""
    )[:300]

    design["ornament_char"] = ORNAMENTS[design["ornament"]]

    return design


# ============================================================
# DATE AND FORM DATA
# ============================================================

def pretty_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime(
            "%A, %d %B %Y"
        )
    except (ValueError, TypeError):
        return value or ""


def pretty_time(value):
    try:
        return datetime.strptime(value, "%H:%M").strftime(
            "%I:%M %p"
        ).lstrip("0")
    except (ValueError, TypeError):
        return value or ""


def build_data(form):
    cards_for = form.get("cards_for", "Wedding")
    want_wedding = cards_for in ("Wedding", "Both")
    want_engagement = cards_for in ("Engagement", "Both")

    language = form.get("language", "Both")
    languages = {
        "English": ["en"],
        "Malayalam": ["ml"],
    }.get(language, ["en", "ml"])

    data = {
        "community": form.get("community", "Other"),
        "style_notes": form.get("style_notes", ""),
        "design_prompt": form.get("design_prompt", ""),
        "creative_brief": form.get("creative_brief", ""),
        "on_behalf_of": form.get("on_behalf_of", "bride"),
        "cards_for": cards_for,
        "wedding_requested": want_wedding,
        "engagement_requested": want_engagement,
        "languages": languages,
        "layout": form.get("layout", "separate"),
    }

    for key in (
        "bride_name", "bride_father", "bride_mother", "bride_address",
        "groom_name", "groom_father", "groom_mother", "groom_address",
    ):
        data[key] = form.get(key, "")

    if want_wedding:
        for key in (
            "wedding_date", "wedding_time", "wedding_time_to",
            "wedding_place", "wedding_phone", "wedding_compliments",
        ):
            data[key] = form.get(key, "")

        data["wedding_date_text"] = pretty_date(data["wedding_date"])
        start = pretty_time(data["wedding_time"])
        end = pretty_time(data["wedding_time_to"])
        data["wedding_time_text"] = (
            f"{start} to {end}" if start and end else start
        )

    if want_engagement:
        for key in (
            "eng_date", "eng_time", "eng_time_to", "eng_place",
            "eng_phone", "eng_compliments",
        ):
            data[key] = form.get(key, "")

        data["eng_date_text"] = pretty_date(data["eng_date"])
        start = pretty_time(data["eng_time"])
        end = pretty_time(data["eng_time_to"])
        data["eng_time_text"] = (
            f"{start} to {end}" if start and end else start
        )

    return data


def validate(form):
    errors = []
    cards_for = form.get("cards_for", "Wedding")

    if not form.get("bride_name"):
        errors.append("Bride's name is required.")

    if not form.get("groom_name"):
        errors.append("Bridegroom's name is required.")

    if cards_for in ("Wedding", "Both") and not form.get("wedding_date"):
        errors.append("Date of marriage is required for wedding cards.")

    if cards_for in ("Engagement", "Both") and not form.get("eng_date"):
        errors.append("Engagement date is required for engagement cards.")

    return errors


# ============================================================
# FALLBACK WORDING
# ============================================================

ML_EVENT = {
    "wedding": (
        "വിവാഹത്തിന് സ്നേഹപൂർവ്വം ക്ഷണിക്കുന്നു",
        "മുഹൂർത്തം: ",
    ),
    "engagement": (
        "ഒത്തുകല്യാണത്തിന് സ്നേഹപൂർവ്വം ക്ഷണിക്കുന്നു",
        "സമയം: ",
    ),
}


def fallback_wording(data):
    side_en = (
        "bride's" if data["on_behalf_of"] == "bride"
        else "bridegroom's"
    )
    side_ml = (
        "വധുവിന്റെ" if data["on_behalf_of"] == "bride"
        else "വരന്റെ"
    )

    output = {}

    for language in data["languages"]:
        english = language == "en"

        def parents(role):
            father = data.get(f"{role}_father", "")
            mother = data.get(f"{role}_mother", "")
            names = " & ".join(x for x in (father, mother) if x)

            if not names:
                return ""

            if english:
                prefix = "D/o" if role == "bride" else "S/o"
                return f"{prefix} {names}"

            suffix = "മകൾ" if role == "bride" else "മകൻ"
            return f"{names} എന്നിവരുടെ {suffix}"

        item = {
            "opening": (
                "With the blessings of the Almighty"
                if english else "ദൈവാനുഗ്രഹത്താൽ"
            ),
            "hosted_by": (
                f"The {side_en} family cordially invite you"
                if english else f"{side_ml} വീട്ടുകാർ"
            ),
            "bride_name": data["bride_name"],
            "groom_name": data["groom_name"],
            "bride_parents": parents("bride"),
            "groom_parents": parents("groom"),
            "bride_address": data["bride_address"],
            "groom_address": data["groom_address"],
        }

        if data["wedding_requested"]:
            time_text = data.get("wedding_time_text", "")
            item["wedding"] = {
                "invite_line": (
                    "to the marriage of"
                    if english else ML_EVENT["wedding"][0]
                ),
                "date_text": data["wedding_date_text"],
                "time_text": (
                    f"Muhurtham: {time_text}" if english
                    else ML_EVENT["wedding"][1] + time_text
                ) if time_text else "",
                "venue_text": data.get("wedding_place", ""),
                "closing": (
                    "With best compliments" if english
                    else "ഉപചാരപൂർവ്വം"
                ),
                "compliments_from": data.get("wedding_compliments", ""),
            }

        if data["engagement_requested"]:
            time_text = data.get("eng_time_text", "")
            item["engagement"] = {
                "invite_line": (
                    "to the engagement of"
                    if english else ML_EVENT["engagement"][0]
                ),
                "date_text": data["eng_date_text"],
                "time_text": (
                    f"Time: {time_text}" if english
                    else ML_EVENT["engagement"][1] + time_text
                ) if time_text else "",
                "venue_text": data.get("eng_place", ""),
                "closing": (
                    "With best compliments" if english
                    else "ഉപചാരപൂർവ്വം"
                ),
                "compliments_from": data.get("eng_compliments", ""),
            }

        output[language] = item

    return output


def normalise_wording(raw, data):
    fallback = fallback_wording(data)
    output = {}

    for language in data["languages"]:
        generated = raw.get(language) if isinstance(raw, dict) else None
        generated = generated if isinstance(generated, dict) else {}

        item = {}

        for key, default in fallback[language].items():
            if isinstance(default, dict):
                generated_event = generated.get(key)
                generated_event = (
                    generated_event
                    if isinstance(generated_event, dict) else {}
                )
                item[key] = {
                    field: str(
                        generated_event.get(field)
                        if generated_event.get(field) is not None
                        else value
                    )
                    for field, value in default.items()
                }
            else:
                item[key] = str(
                    generated.get(key)
                    if generated.get(key) is not None else default
                )

        output[language] = item

    return output


# ============================================================
# PAGE CREATION AND RENDERING
# ============================================================

def build_pages(data):
    events = []

    if data["wedding_requested"]:
        events.append("wedding")

    if data["engagement_requested"]:
        events.append("engagement")

    pages = []

    for event in events:
        if data["layout"] == "same" or len(data["languages"]) == 1:
            pages.append({
                "event": event,
                "langs": data["languages"],
            })
        else:
            for language in data["languages"]:
                pages.append({
                    "event": event,
                    "langs": [language],
                })

    return pages


def render_preview(request, form, wording, design, notes):
    data = build_data(form)

    state = json.dumps({
        "f": form,
        "wording": wording,
        "design": design,
    }, ensure_ascii=False)

    order = (
        ["bride", "groom"]
        if data["on_behalf_of"] == "bride"
        else ["groom", "bride"]
    )

    return templates.TemplateResponse(
        request,
        "card.html",
        {
            "w": wording,
            "d": data,
            "f": form,
            "design": design,
            "pages": build_pages(data),
            "order": order,
            "notes": notes,
            "state": state,
        },
    )


def render_form(request, prefill=None, errors=None):
    return templates.TemplateResponse(
        request,
        "form.html",
        {
            "inks": [],
            "has_key": bool(GEMINI_KEY),
            "prefill": prefill or {},
            "errors": errors or [],
        },
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return render_form(request)


async def form_dict(request):
    values = await request.form()
    return {
        key: value.strip()
        for key, value in values.items()
        if isinstance(value, str)
    }


# ============================================================
# GENERATE CARD
# ============================================================

@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request):
    form = await form_dict(request)
    errors = validate(form)

    if errors:
        return render_form(request, form, errors)

    data = build_data(form)
    notes = []
    wording_raw = None
    design_raw = None

    if GEMINI_KEY:
        design_payload = {
            "community": data["community"],
            "style_notes": data["style_notes"],
            "design_prompt": data["design_prompt"],
            "creative_brief": data["creative_brief"],
            "cards_for": data["cards_for"],
            "languages": data["languages"],
        }

        results = await asyncio.gather(
            call_gemini(WORDING_PROMPT, {**data, "customer_creative_brief": data.get("creative_brief", ""), "customer_style_notes": data.get("style_notes", "")}, 0.75),
            call_gemini(DESIGN_PROMPT, design_payload, 0.95),
            return_exceptions=True,
        )

        if isinstance(results[0], Exception):
            notes.append(
                f"Gemini wording unavailable. Fallback wording used: {results[0]}"
            )
        else:
            wording_raw = results[0]

        if isinstance(results[1], Exception):
            notes.append(
                f"Gemini design unavailable. Default design used: {results[1]}"
            )
        else:
            design_raw = results[1]
    else:
        notes.append(
            "Gemini API key is not configured. Fallback wording and design used."
        )

    wording = normalise_wording(wording_raw, data)
    design = sanitize_design(
        design_raw,
        data["community"],
        form.get("ink_color"),
    )

    return render_preview(request, form, wording, design, notes)


# ============================================================
# GEMINI REVISION
# ============================================================

@app.post("/revise", response_class=HTMLResponse)
async def revise(request: Request):
    form_data = await request.form()

    try:
        state = json.loads(form_data.get("state", "{}"))
        form = state["f"]
        wording = state["wording"]
        design = state["design"]
    except Exception:
        return render_form(
            request,
            {},
            ["Your editing session expired. Please fill the form again."],
        )

    instruction = str(form_data.get("instruction") or "").strip()
    target = str(form_data.get("target") or "design").strip().lower()

    if target not in ("design", "wording", "both", "redesign"):
        target = "design"

    data = build_data(form)
    notes = []

    if not GEMINI_KEY:
        notes.append(
            "Gemini API key is not configured. Your existing design was retained."
        )
        return render_preview(request, form, wording, design, notes)

    jobs = {}

    if target in ("wording", "both"):
        jobs["wording"] = call_gemini(
            WORDING_PROMPT,
            {
                **data,
                "instruction": instruction,
                "previous_wording": wording,
                "customer_creative_brief": data.get("creative_brief", ""),
            },
            0.75,
        )

    if target in ("design", "both", "redesign"):
        design_payload = {
            "community": data["community"],
            "style_notes": data["style_notes"],
            "design_prompt": data["design_prompt"],
            "creative_brief": data["creative_brief"],
            "cards_for": data["cards_for"],
            "customer_instruction": instruction,
            "previous_design": design,
            "languages": data["languages"],
        }

        if target == "redesign":
            design_payload["instruction"] = (
                instruction
                or "Create a completely different, original design. "
                   "Avoid repeating the previous palette and visual style."
            )
            design_payload["avoid_previous_design"] = True
        else:
            design_payload["instruction"] = (
                instruction
                or "Improve the current design while keeping the invitation elegant."
            )

        jobs["design"] = call_gemini(
            DESIGN_PROMPT,
            design_payload,
            1.0 if target == "redesign" else 0.85,
        )

    results = await asyncio.gather(
        *jobs.values(),
        return_exceptions=True,
    )

    for name, result in zip(jobs.keys(), results):
        if isinstance(result, Exception):
            notes.append(f"Gemini {name} update failed: {result}")
            continue

        if name == "wording":
            wording = normalise_wording(result, data)
        elif name == "design":
            design = sanitize_design(
                result,
                data["community"],
                form.get("ink_color"),
            )

    return render_preview(request, form, wording, design, notes)


# ============================================================
# RETURN TO FORM
# ============================================================

@app.post("/edit", response_class=HTMLResponse)
async def edit(request: Request):
    form_data = await request.form()

    try:
        state = json.loads(form_data.get("state", "{}"))
        form = state.get("f", {})
    except Exception:
        form = {}

    return render_form(request, form)


# ============================================================
# API TEST
# ============================================================

@app.get("/api/test")
async def test_gemini():
    info = { 
        "key_set": bool(GEMINI_KEY),
        "models": MODELS,
        "proxy_enabled": bool(proxy_url()),
    }

    try:
        reply = await call_gemini(
            'Return JSON only: {"ok": true}',
            {"test": "connection"},
            0,
        )
        return {**info, "ok": True, "reply": reply}
    except Exception as exc:
        return JSONResponse(
            {**info, "ok": False, "error": str(exc)},
            status_code=502,
        )