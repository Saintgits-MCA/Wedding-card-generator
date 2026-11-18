# """Flexible Kerala Wedding Card Generator — FastAPI + Gemini."""

# import asyncio
# import json
# import os
# import re
# from datetime import datetime
# from pathlib import Path
# from urllib.parse import urlparse

# import httpx
# from dotenv import load_dotenv
# from fastapi import FastAPI, Request
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates
# from markupsafe import Markup, escape

# load_dotenv()

# BASE = Path(__file__).resolve().parent
# app = FastAPI(title="Wedding Card Generator")

# app.mount("/js", StaticFiles(directory=BASE / "js"), name="js")
# templates = Jinja2Templates(directory=str(BASE / "templates"))


# def nl2br(value):
#     return Markup(str(escape(value or "")).replace("\n", "<br>"))


# templates.env.filters["nl2br"] = nl2br


# # ============================================================
# # GEMINI CONFIGURATION
# # ============================================================

# def clean(value):
#     return (value or "").strip().strip("\"'").strip()


# GEMINI_KEY = clean(os.getenv("GEMINI_API_KEY", ""))



# def model_name(raw, default):
#     raw = clean(raw)
#     raw = raw.split("/models/")[-1].replace("models/", "").split(":")[0]
#     raw = "".join(raw.split())
#     return raw if re.fullmatch(r"[A-Za-z0-9._-]+", raw or "") else default


# MODELS = list(dict.fromkeys([
#     model_name(os.getenv("GEMINI_MODEL", ""), "gemini-2.5-flash"),
#     "gemini-2.5-flash-lite","gemini-3.5-flash"
# ]))

# API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


# def proxy_url():
#     value = clean(os.getenv("GEMINI_PROXY", ""))
#     if not value:
#         return None

#     try:
#         parsed = urlparse(value)
#         _ = parsed.port
#         if parsed.scheme in ("http", "https", "socks5") and parsed.hostname:
#             return value
#     except ValueError:
#         pass

#     print("[warn] Invalid GEMINI_PROXY; ignoring it.")
#     return None


# def make_client():
#     options = {"timeout": 90, "trust_env": False}
#     proxy = proxy_url()
#     if proxy:
#         options["proxy"] = proxy
#     return httpx.AsyncClient(**options)


# def parse_json(text):
#     text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
#     decoder = json.JSONDecoder()
#     index = 0
#     found = []

#     while index < len(text):
#         positions = [
#             pos for pos in (text.find("{", index), text.find("[", index))
#             if pos != -1
#         ]
#         if not positions:
#             break

#         start = min(positions)
#         try:
#             obj, end = decoder.raw_decode(text, start)
#             found.append(obj)
#             index = end
#         except json.JSONDecodeError:
#             index = start + 1

#     if not found:
#         raise ValueError("Gemini did not return valid JSON.")

#     if len(found) == 1:
#         return found[0]

#     merged = {}
#     for item in found:
#         if isinstance(item, dict):
#             merged.update(item)

#     return merged or found[0]


# async def call_gemini(system, payload, temperature=0.7):
#     if not GEMINI_KEY:
#         raise RuntimeError("GEMINI_API_KEY is not configured.")

#     body = {
#         "systemInstruction": {"parts": [{"text": system}]},
#         "contents": [{
#             "role": "user",
#             "parts": [{
#                 "text": json.dumps(payload, ensure_ascii=False)
#             }]
#         }],
#         "generationConfig": {
#             "temperature": temperature,
#             "responseMimeType": "application/json",
#         },
#     }

#     headers = {
#         "x-goog-api-key": GEMINI_KEY,
#         "Content-Type": "application/json",
#     }

#     last_error = RuntimeError("Gemini request failed.")

#     async with make_client() as client:
#         for model in MODELS:
#             for attempt in range(2):
#                 try:
#                     response = await client.post(
#                         f"{API_ROOT}/{model}:generateContent",
#                         headers=headers,
#                         json=body,
#                     )
#                 except httpx.HTTPError as exc:
#                     last_error = RuntimeError(f"Network error: {exc}")
#                     await asyncio.sleep(1)
#                     continue

#                 if response.status_code == 200:
#                     try:
#                         parts = response.json()["candidates"][0]["content"]["parts"]
#                         text = "".join(
#                             part.get("text", "") for part in parts
#                         )
#                         return parse_json(text)
#                     except Exception as exc:
#                         last_error = RuntimeError(
#                             f"Could not read Gemini response: {exc}"
#                         )
#                         break

#                 message = response.text[:700].replace("\n", " ")
#                 lower_message = message.lower()
                
#                 if response.status_code == 429 or "resource_exhausted" in lower_message or "quota" in lower_message or "limit" in lower_message:
#                     friendly_msg = "Gemini API rate limit or quota exceeded. Using robust fallback styling and fine-tuning controls."
#                 else:
#                     friendly_msg = f"Gemini request encountered an issue (HTTP {response.status_code})."
                    
#                 last_error = RuntimeError(friendly_msg)

#                 # A quota/billing limit is not fixed by retrying another model.
#                 quota_error = any(term in lower_message for term in (
#                     "exceeded your current quota",
#                     "quota exceeded",
#                     "billing",
#                     "limit: 0",
#                     "free_tier",
#                     "resource_exhausted",
#                 ))

#                 if response.status_code in (400, 401, 403) or quota_error:
#                     raise last_error

#                 if response.status_code in (429, 500, 503):
#                     await asyncio.sleep(1.5 * (attempt + 1))
#                     continue

#                 break

#     raise last_error


# # ============================================================
# # WORDING GENERATION
# # ============================================================

# WORDING_PROMPT = """
# You are the lead invitation copywriter for a premium Kerala wedding stationery studio.
# Create beautiful, natural, memorable invitation copy rather than filling a rigid template.
# The customer's own creative brief is a first-class instruction: follow its requested voice,
# length, cultural register, emotional mood, formality, poetic style, wording structure and
# special phrases as closely as possible.

# The customer may request traditional, contemporary, poetic, devotional, warm, intimate,
# formal, joyful, minimalist, literary, family-centred, or an original voice. Do not force
# all invitations into stock phrases. Vary sentence construction and vocabulary to suit
# this couple. The result should feel intentionally written for them.

# The structured input contains verified event facts and requested languages. Preserve names
# exactly. Never invent or alter dates, times, venues, family relationships, phone numbers,
# addresses or hosts. Creatively rewrite invitation sentences, blessings, introductions and
# closings. If a factual value is absent, leave its corresponding output empty. Never
# translate or transliterate personal names unless explicitly requested.

# For Malayalam, write fluent idiomatic Malayalam in Malayalam script, not awkward literal
# translation. For English, use polished natural English. For bilingual output, make both
# versions read naturally in their own language. Respect community and customer preferences
# without assuming religious wording that was not requested.

# Return ONLY valid JSON, with exactly the requested language keys ("en" and/or "ml").
# Each language object must contain: opening, hosted_by, bride_name, groom_name,
# bride_parents, groom_parents, bride_address, groom_address.
# For each requested event ("wedding" and/or "engagement"), include: invite_line,
# date_text, time_text, venue_text, closing, compliments_from.

# Use supplied facts as the source of truth. Keep copy elegant and readable; concise by
# default, but honour explicit requests for longer, more poetic or traditional wording.
# No markdown, commentary or extra JSON keys.
# """


# # ============================================================
# # DESIGN SYSTEM
# # ============================================================

# EN_FONTS = ['Cormorant Garamond', 'Playfair Display', 'Great Vibes', 'Cinzel', 'Lora', 'Marcellus', 'EB Garamond', 'Libre Baskerville', 'Bodoni Moda', 'DM Serif Display', 'Crimson Pro', 'Prata', 'Forum', 'Cormorant Infant', 'Montserrat', 'Raleway', 'Poppins', 'Allura', 'Alex Brush', 'Parisienne', 'Tangerine', 'Sacramento', 'Italianno']

# ML_FONTS = ['Noto Serif Malayalam', 'Manjari', 'Anek Malayalam', 'Noto Sans Malayalam', 'Gayathri', 'Rachana', 'Meera', 'Chilanka', 'Karumbi']

# BORDERS = ["double", "temple", "corners", "single", "dots", "none"]
# DIVIDERS = ["line", "diamond", "dots", "none"]
# PATTERNS = ["none", "dots", "lines", "vignette"]
# NAME_SIZES = ["md", "lg", "xl"]

# ORNAMENTS = {
#     "floral": "❀",
#     "star": "✦",
#     "cross": "✝",
#     "crescent": "☪",
#     "diamond": "❖",
#     "lotus": "❀",
#     "leaf": "❧",
#     "heart": "♥",
#     "arch": "⌂",
#     "om": "ॐ",
#     "none": "",
# }

# DEFAULT_DESIGNS = {
#     "Hindu": {
#         "paper": "#FFF8E8", "ink": "#6E1E1E", "accent": "#B8860B",
#         "display_font": "Cinzel", "body_font": "Cormorant Garamond",
#         "ml_font": "Noto Serif Malayalam", "border": "temple",
#         "ornament": "om", "divider": "diamond", "pattern": "none",
#         "name_size": "lg",
#     },
#     "Christian": {
#         "paper": "#FDFCF8", "ink": "#1F3A5F", "accent": "#B8860B",
#         "display_font": "Great Vibes", "body_font": "Cormorant Garamond",
#         "ml_font": "Noto Serif Malayalam", "border": "double",
#         "ornament": "cross", "divider": "line", "pattern": "none",
#         "name_size": "xl",
#     },
#     "Muslim": {
#         "paper": "#F7FBF8", "ink": "#14532D", "accent": "#B8860B",
#         "display_font": "Playfair Display", "body_font": "Lora",
#         "ml_font": "Manjari", "border": "dots", "ornament": "crescent",
#         "divider": "dots", "pattern": "dots", "name_size": "lg",
#     },
#     "Other": {
#         "paper": "#FFFDF8", "ink": "#7A1F2B", "accent": "#B8860B",
#         "display_font": "Playfair Display", "body_font": "Cormorant Garamond",
#         "ml_font": "Noto Serif Malayalam", "border": "corners",
#         "ornament": "floral", "divider": "diamond", "pattern": "vignette",
#         "name_size": "lg",
#     },
# }


# DESIGN_PROMPT = f"""
# You are the creative director of a premium Kerala wedding invitation design studio.
# Interpret the customer's free-form brief as the primary art direction. It may describe
# colours, mood, visual references, materials, cultural details, motifs, typography,
# composition, ornament density, minimalism, luxury, or an original concept.

# You choose the exact palette, font combination, border, ornament, divider, pattern and
# name scale from the backend catalogue below. Do not make the customer choose technical
# values. Make a coherent, distinctive choice that expresses the brief. If the brief is
# short or empty, invent a fresh, polished concept suited to the event and community.
# Avoid repeating the previous design when asked to surprise or redesign.

# BACKEND CATALOGUE — choose exact values only:
# English fonts: {', '.join(EN_FONTS)}
# Malayalam fonts: {', '.join(ML_FONTS)} 
# Borders: {', '.join(BORDERS)}
# Ornaments: {', '.join(ORNAMENTS.keys())}
# Dividers: {', '.join(DIVIDERS)}
# Patterns: {', '.join(PATTERNS)}
# Name sizes: {', '.join(NAME_SIZES)}

# Choose harmonious six-digit HEX colours for paper, ink and accent. The backend validates
# colours and enforces readable contrast. Choose solid or gradient backgrounds and valid
# HEX gradient endpoints. Use catalogue font/effect names only. Choose a Malayalam-capable
# font when Malayalam is present. Prioritize legibility and print suitability.

# Ensure readability when color background or theme changes and ensure attractiveness and you are free to apply beyong these listed ornaments and limited decorations apply more images and themes from online according to what you feel appropriate

# Do not return HTML, CSS, scripts, arbitrary class names or markdown. Do not invent
# invitation wording or event facts. Prioritize the customer's brief.
# """


# # ============================================================
# # DESIGN VALIDATION AND CSS SAFETY
# # ============================================================

# HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


# def valid_hex(value, fallback):
#     if isinstance(value, str) and HEX.fullmatch(value.strip()):
#         return value.strip().upper()
#     return fallback


# def luminance(hex_colour):
#     channels = [
#         int(hex_colour[i:i + 2], 16) / 255
#         for i in (1, 3, 5)
#     ]
#     channels = [
#         c / 12.92 if c <= 0.03928
#         else ((c + 0.055) / 1.055) ** 2.4
#         for c in channels
#     ]
#     return (
#         0.2126 * channels[0]
#         + 0.7152 * channels[1]
#         + 0.0722 * channels[2]
#     )


# def contrast_ratio(a, b):
#     high, low = sorted(
#         (luminance(a), luminance(b)),
#         reverse=True,
#     )
#     return (high + 0.05) / (low + 0.05)


# def safe_gradient_angle(value):
#     try:
#         number = int(float(value))
#         return max(0, min(360, number))
#     except (TypeError, ValueError):
#         return 135


# def sanitize_design(raw, community="Other", user_ink=None):
#     base = dict(DEFAULT_DESIGNS.get(
#         community, DEFAULT_DESIGNS["Other"]
#     ))

#     raw = raw if isinstance(raw, dict) else {}
#     design = dict(base)

#     # Unlimited user/Gemini HEX colours, validated before use.
#     design["paper"] = valid_hex(raw.get("paper"), base["paper"])
#     design["ink"] = valid_hex(raw.get("ink"), base["ink"])
#     design["accent"] = valid_hex(raw.get("accent"), base["accent"])

#     for key, allowed in (
#         ("display_font", EN_FONTS),
#         ("body_font", EN_FONTS),
#         ("ml_font", ML_FONTS),
#         ("border", BORDERS),
#         ("divider", DIVIDERS),
#         ("pattern", PATTERNS),
#         ("name_size", NAME_SIZES),
#     ):
#         if raw.get(key) in allowed:
#             design[key] = raw[key]

#     if raw.get("ornament") in ORNAMENTS:
#         design["ornament"] = raw["ornament"]

#     # Background configuration.
#     background_type = raw.get("background_type", "solid")
#     if background_type not in ("solid", "gradient"):
#         background_type = "solid"

#     background_color = valid_hex(
#         raw.get("background_color"),
#         design["paper"],
#     )
#     gradient_start = valid_hex(
#         raw.get("gradient_start"),
#         design["paper"],
#     )
#     gradient_end = valid_hex(
#         raw.get("gradient_end"),
#         background_color,
#     )
#     angle = safe_gradient_angle(raw.get("gradient_angle", 135))

#     design["background_type"] = background_type
#     design["background_color"] = background_color
#     design["gradient_start"] = gradient_start
#     design["gradient_end"] = gradient_end
#     design["gradient_angle"] = angle

#     if background_type == "gradient":
#         design["background_css"] = (
#             f"linear-gradient({angle}deg, "
#             f"{gradient_start} 0%, {gradient_end} 100%)"
#         )
#     else:
#         design["background_css"] = background_color

#     # Keep the text readable.
#     if contrast_ratio(design["ink"], design["paper"]) < 4.5:
#         design["ink"] = base["ink"]

#     if user_ink:
#         # Legacy form compatibility: allow a custom HEX ink value.
#         if HEX.fullmatch(str(user_ink).strip()):
#             design["ink"] = user_ink.strip().upper()

#     design["mood"] = str(raw.get("mood") or "Custom design")[:120]
#     design["background_description"] = str(
#         raw.get("background_description") or ""
#     )[:300]
#     design["decoration_description"] = str(
#         raw.get("decoration_description") or ""
#     )[:300]

#     design["ornament_char"] = ORNAMENTS[design["ornament"]]

#     return design


# # ============================================================
# # DATE AND FORM DATA
# # ============================================================

# def pretty_date(value):
#     try:
#         return datetime.strptime(value, "%Y-%m-%d").strftime(
#             "%A, %d %B %Y"
#         )
#     except (ValueError, TypeError):
#         return value or ""


# def pretty_time(value):
#     try:
#         return datetime.strptime(value, "%H:%M").strftime(
#             "%I:%M %p"
#         ).lstrip("0")
#     except (ValueError, TypeError):
#         return value or ""


# def build_data(form):
#     cards_for = form.get("cards_for", "Wedding")
#     want_wedding = cards_for in ("Wedding", "Both")
#     want_engagement = cards_for in ("Engagement", "Both")

#     language = form.get("language", "Both")
#     languages = {
#         "English": ["en"],
#         "Malayalam": ["ml"],
#     }.get(language, ["en", "ml"])

#     data = {
#         "community": form.get("community", "Other"),
#         "style_notes": form.get("style_notes", ""),
#         "design_prompt": form.get("design_prompt", ""),
#         "creative_brief": form.get("creative_brief", ""),
#         "on_behalf_of": form.get("on_behalf_of", "bride"),
#         "cards_for": cards_for,
#         "wedding_requested": want_wedding,
#         "engagement_requested": want_engagement,
#         "languages": languages,
#         "layout": form.get("layout", "separate"),
#     }

#     for key in (
#         "bride_name", "bride_father", "bride_mother", "bride_address",
#         "groom_name", "groom_father", "groom_mother", "groom_address",
#     ):
#         data[key] = form.get(key, "")

#     if want_wedding:
#         for key in (
#             "wedding_date", "wedding_time", "wedding_time_to",
#             "wedding_place", "wedding_phone", "wedding_compliments",
#         ):
#             data[key] = form.get(key, "")

#         data["wedding_date_text"] = pretty_date(data["wedding_date"])
#         start = pretty_time(data["wedding_time"])
#         end = pretty_time(data["wedding_time_to"])
#         data["wedding_time_text"] = (
#             f"{start} to {end}" if start and end else start
#         )

#     if want_engagement:
#         for key in (
#             "eng_date", "eng_time", "eng_time_to", "eng_place",
#             "eng_phone", "eng_compliments",
#         ):
#             data[key] = form.get(key, "")

#         data["eng_date_text"] = pretty_date(data["eng_date"])
#         start = pretty_time(data["eng_time"])
#         end = pretty_time(data["eng_time_to"])
#         data["eng_time_text"] = (
#             f"{start} to {end}" if start and end else start
#         )

#     return data


# def validate(form):
#     errors = []
#     cards_for = form.get("cards_for", "Wedding")

#     if not form.get("bride_name"):
#         errors.append("Bride's name is required.")

#     if not form.get("groom_name"):
#         errors.append("Bridegroom's name is required.")

#     if cards_for in ("Wedding", "Both") and not form.get("wedding_date"):
#         errors.append("Date of marriage is required for wedding cards.")

#     if cards_for in ("Engagement", "Both") and not form.get("eng_date"):
#         errors.append("Engagement date is required for engagement cards.")

#     return errors


# # ============================================================
# # FALLBACK WORDING
# # ============================================================

# ML_EVENT = {
#     "wedding": (
#         "വിവാഹത്തിന് സ്നേഹപൂർവ്വം ക്ഷണിക്കുന്നു",
#         "മുഹൂർത്തം: ",
#     ),
#     "engagement": (
#         "ഒത്തുകല്യാണത്തിന് സ്നേഹപൂർവ്വം ക്ഷണിക്കുന്നു",
#         "സമയം: ",
#     ),
# }


# def fallback_wording(data):
#     side_en = (
#         "bride's" if data["on_behalf_of"] == "bride"
#         else "bridegroom's"
#     )
#     side_ml = (
#         "വധുവിന്റെ" if data["on_behalf_of"] == "bride"
#         else "വരന്റെ"
#     )

#     output = {}

#     for language in data["languages"]:
#         english = language == "en"

#         def parents(role):
#             father = data.get(f"{role}_father", "")
#             mother = data.get(f"{role}_mother", "")
#             names = " & ".join(x for x in (father, mother) if x)

#             if not names:
#                 return ""

#             if english:
#                 prefix = "D/o" if role == "bride" else "S/o"
#                 return f"{prefix} {names}"

#             suffix = "മകൾ" if role == "bride" else "മകൻ"
#             return f"{names} എന്നിവരുടെ {suffix}"

#         item = {
#             "opening": (
#                 "With the blessings of the Almighty"
#                 if english else "ദൈവാനുഗ്രഹത്താൽ"
#             ),
#             "hosted_by": (
#                 f"The {side_en} family cordially invite you"
#                 if english else f"{side_ml} വീട്ടുകാർ"
#             ),
#             "bride_name": data["bride_name"],
#             "groom_name": data["groom_name"],
#             "bride_parents": parents("bride"),
#             "groom_parents": parents("groom"),
#             "bride_address": data["bride_address"],
#             "groom_address": data["groom_address"],
#         }

#         if data["wedding_requested"]:
#             time_text = data.get("wedding_time_text", "")
#             item["wedding"] = {
#                 "invite_line": (
#                     "to the marriage of"
#                     if english else ML_EVENT["wedding"][0]
#                 ),
#                 "date_text": data["wedding_date_text"],
#                 "time_text": (
#                     f"Muhurtham: {time_text}" if english
#                     else ML_EVENT["wedding"][1] + time_text
#                 ) if time_text else "",
#                 "venue_text": data.get("wedding_place", ""),
#                 "closing": (
#                     "With best compliments" if english
#                     else "ഉപചാരപൂർവ്വം"
#                 ),
#                 "compliments_from": data.get("wedding_compliments", ""),
#             }

#         if data["engagement_requested"]:
#             time_text = data.get("eng_time_text", "")
#             item["engagement"] = {
#                 "invite_line": (
#                     "to the engagement of"
#                     if english else ML_EVENT["engagement"][0]
#                 ),
#                 "date_text": data["eng_date_text"],
#                 "time_text": (
#                     f"Time: {time_text}" if english
#                     else ML_EVENT["engagement"][1] + time_text
#                 ) if time_text else "",
#                 "venue_text": data.get("eng_place", ""),
#                 "closing": (
#                     "With best compliments" if english
#                     else "ഉപചാരപൂർവ്വം"
#                 ),
#                 "compliments_from": data.get("eng_compliments", ""),
#             }

#         output[language] = item

#     return output


# def normalise_wording(raw, data):
#     fallback = fallback_wording(data)
#     output = {}

#     for language in data["languages"]:
#         generated = raw.get(language) if isinstance(raw, dict) else None
#         generated = generated if isinstance(generated, dict) else {}

#         item = {}

#         for key, default in fallback[language].items():
#             if isinstance(default, dict):
#                 generated_event = generated.get(key)
#                 generated_event = (
#                     generated_event
#                     if isinstance(generated_event, dict) else {}
#                 )
#                 item[key] = {
#                     field: str(
#                         generated_event.get(field)
#                         if generated_event.get(field) is not None
#                         else value
#                     )
#                     for field, value in default.items()
#                 }
#             else:
#                 item[key] = str(
#                     generated.get(key)
#                     if generated.get(key) is not None else default
#                 )

#         output[language] = item

#     return output


# # ============================================================
# # PAGE CREATION AND RENDERING
# # ============================================================

# def build_pages(data):
#     events = []

#     if data["wedding_requested"]:
#         events.append("wedding")

#     if data["engagement_requested"]:
#         events.append("engagement")

#     pages = []

#     for event in events:
#         if data["layout"] == "same" or len(data["languages"]) == 1:
#             pages.append({
#                 "event": event,
#                 "langs": data["languages"],
#             })
#         else:
#             for language in data["languages"]:
#                 pages.append({
#                     "event": event,
#                     "langs": [language],
#                 })

#     return pages


# def render_preview(request, form, wording, design, notes):
#     data = build_data(form)

#     state = json.dumps({
#         "f": form,
#         "wording": wording,
#         "design": design,
#     }, ensure_ascii=False)

#     order = (
#         ["bride", "groom"]
#         if data["on_behalf_of"] == "bride"
#         else ["groom", "bride"]
#     )

#     return templates.TemplateResponse(
#         request,
#         "card.html",
#         {
#             "w": wording,
#             "d": data,
#             "f": form,
#             "design": design,
#             "pages": build_pages(data),
#             "order": order,
#             "notes": notes,
#             "state": state,
#         },
#     )


# def render_form(request, prefill=None, errors=None):
#     return templates.TemplateResponse(
#         request,
#         "form.html",
#         {
#             "inks": [],
#             "has_key": bool(GEMINI_KEY),
#             "prefill": prefill or {},
#             "errors": errors or [],
#         },
#     )


# @app.get("/", response_class=HTMLResponse)
# async def home(request: Request):
#     return render_form(request)


# async def form_dict(request):
#     values = await request.form()
#     return {
#         key: value.strip()
#         for key, value in values.items()
#         if isinstance(value, str)
#     }


# # ============================================================
# # GENERATE CARD
# # ============================================================

# @app.post("/generate", response_class=HTMLResponse)
# async def generate(request: Request):
#     form = await form_dict(request)
#     errors = validate(form)

#     if errors:
#         return render_form(request, form, errors)

#     data = build_data(form)
#     notes = []
#     wording_raw = None
#     design_raw = None

#     if GEMINI_KEY:
#         design_payload = {
#             "community": data["community"],
#             "style_notes": data["style_notes"],
#             "design_prompt": data["design_prompt"],
#             "creative_brief": data["creative_brief"],
#             "cards_for": data["cards_for"],
#             "languages": data["languages"],
#         }

#         results = await asyncio.gather(
#             call_gemini(WORDING_PROMPT, {**data, "customer_creative_brief": data.get("creative_brief", ""), "customer_style_notes": data.get("style_notes", "")}, 0.75),
#             call_gemini(DESIGN_PROMPT, design_payload, 0.95),
#             return_exceptions=True,
#         )

#         if isinstance(results[0], Exception):
#             notes.append(
#                 f"Gemini wording unavailable. Fallback wording used: {results[0]}"
#             )
#         else:
#             wording_raw = results[0]

#         if isinstance(results[1], Exception):
#             notes.append(
#                 f"Gemini design unavailable. Default design used: {results[1]}"
#             )
#         else:
#             design_raw = results[1]
#     else:
#         notes.append(
#             "Gemini API key is not configured. Fallback wording and design used."
#         )

#     wording = normalise_wording(wording_raw, data)
#     design = sanitize_design(
#         design_raw,
#         data["community"],
#         form.get("ink_color"),
#     )

#     return render_preview(request, form, wording, design, notes)


# # ============================================================
# # GEMINI REVISION
# # ============================================================

# @app.post("/revise", response_class=HTMLResponse)
# async def revise(request: Request):
#     form_data = await request.form()

#     try:
#         state = json.loads(form_data.get("state", "{}"))
#         form = state["f"]
#         wording = state["wording"]
#         design = state["design"]
#     except Exception:
#         return render_form(
#             request,
#             {},
#             ["Your editing session expired. Please fill the form again."],
#         )

#     instruction = str(form_data.get("instruction") or "").strip()
#     target = str(form_data.get("target") or "design").strip().lower()

#     if target not in ("design", "wording", "both", "redesign"):
#         target = "design"

#     data = build_data(form)
#     notes = []

#     if not GEMINI_KEY:
#         notes.append(
#             "Gemini API key is not configured. Your existing design was retained."
#         )
#         return render_preview(request, form, wording, design, notes)

#     jobs = {}

#     if target in ("wording", "both"):
#         jobs["wording"] = call_gemini(
#             WORDING_PROMPT,
#             {
#                 **data,
#                 "instruction": instruction,
#                 "previous_wording": wording,
#                 "customer_creative_brief": data.get("creative_brief", ""),
#             },
#             0.75,
#         )

#     if target in ("design", "both", "redesign"):
#         design_payload = {
#             "community": data["community"],
#             "style_notes": data["style_notes"],
#             "design_prompt": data["design_prompt"],
#             "creative_brief": data["creative_brief"],
#             "cards_for": data["cards_for"],
#             "customer_instruction": instruction,
#             "previous_design": design,
#             "languages": data["languages"],
#         }

#         if target == "redesign":
#             design_payload["instruction"] = (
#                 instruction
#                 or "Create a completely different, original design. "
#                    "Avoid repeating the previous palette and visual style."
#             )
#             design_payload["avoid_previous_design"] = True
#         else:
#             design_payload["instruction"] = (
#                 instruction
#                 or "Improve the current design while keeping the invitation elegant."
#             )

#         jobs["design"] = call_gemini(
#             DESIGN_PROMPT,
#             design_payload,
#             1.0 if target == "redesign" else 0.85,
#         )

#     results = await asyncio.gather(
#         *jobs.values(),
#         return_exceptions=True,
#     )

#     for name, result in zip(jobs.keys(), results):
#         if isinstance(result, Exception):
#             notes.append(f"Gemini {name} update failed: {result}")
#             continue

#         if name == "wording":
#             wording = normalise_wording(result, data)
#         elif name == "design":
#             design = sanitize_design(
#                 result,
#                 data["community"],
#                 form.get("ink_color"),
#             )

#     return render_preview(request, form, wording, design, notes)


# # ============================================================
# # RETURN TO FORM
# # ============================================================

# @app.post("/edit", response_class=HTMLResponse)
# async def edit(request: Request):
#     form_data = await request.form()

#     try:
#         state = json.loads(form_data.get("state", "{}"))
#         form = state.get("f", {})
#     except Exception:
#         form = {}

#     return render_form(request, form)


# # ============================================================
# # API TEST
# # ============================================================

# @app.get("/api/test")
# async def test_gemini():
#     info = { 
#         "key_set": bool(GEMINI_KEY),
#         "models": MODELS,
#         "proxy_enabled": bool(proxy_url()),
#     }

#     try:
#         reply = await call_gemini(
#             'Return JSON only: {"ok": true}',
#             {"test": "connection"},
#             0,
#         )
#         return {**info, "ok": True, "reply": reply}
#     except Exception as exc:
#         return JSONResponse(
#             {**info, "ok": False, "error": str(exc)},
#             status_code=502,
#         )

"""Flexible Kerala Wedding Card Generator — FastAPI + Gemini."""

import asyncio
import json
import os
import re
import random
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

# Local image assets are served from /assets. Generated card illustrations
# should be saved under assets/generated/ and referenced by local path only.
ASSET_DIR = BASE / "assets"
GENERATED_ASSET_DIR = ASSET_DIR / "generated"
GENERATED_ASSET_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/js", StaticFiles(directory=BASE / "js"), name="js")
app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")
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


# Additional offline designs used whenever Gemini is unavailable, expired,
# rate-limited, or out of quota. Community-specific ornaments are preserved.
FALLBACK_STYLE_PRESETS = [
    {"name": "Ivory & Antique Gold", "paper": "#FFF9ED", "ink": "#49351F", "accent": "#B58A3A", "display_font": "Cormorant Garamond", "body_font": "EB Garamond", "border": "double", "divider": "diamond", "pattern": "none", "name_size": "lg"},
    {"name": "Emerald Heritage", "paper": "#F2F7F1", "ink": "#174A3A", "accent": "#B99A55", "display_font": "Cinzel", "body_font": "Lora", "border": "temple", "divider": "line", "pattern": "vignette", "name_size": "lg"},
    {"name": "Rose Burgundy", "paper": "#FFF5F3", "ink": "#702B3A", "accent": "#C18A78", "display_font": "Playfair Display", "body_font": "Cormorant Garamond", "border": "corners", "divider": "diamond", "pattern": "none", "name_size": "xl"},
    {"name": "Midnight Blue", "paper": "#F5F7FA", "ink": "#1F3557", "accent": "#A7AEBB", "display_font": "Marcellus", "body_font": "Libre Baskerville", "border": "double", "divider": "line", "pattern": "lines", "name_size": "lg"},
    {"name": "Sage Botanical", "paper": "#F5F7F0", "ink": "#354B3D", "accent": "#9A9B72", "display_font": "Bodoni Moda", "body_font": "Crimson Pro", "border": "single", "divider": "dots", "pattern": "vignette", "name_size": "lg"},
    {"name": "Blush Champagne", "paper": "#FFF8F4", "ink": "#694653", "accent": "#C49A78", "display_font": "Great Vibes", "body_font": "Lora", "border": "corners", "divider": "line", "pattern": "none", "name_size": "xl"},
    {"name": "Terracotta Classic", "paper": "#FBF2E9", "ink": "#743B2D", "accent": "#B8754D", "display_font": "Prata", "body_font": "Cormorant Infant", "border": "temple", "divider": "diamond", "pattern": "dots", "name_size": "lg"},
    {"name": "Lavender Pearl", "paper": "#F8F5FA", "ink": "#51405F", "accent": "#A997B9", "display_font": "Forum", "body_font": "EB Garamond", "border": "dots", "divider": "dots", "pattern": "vignette", "name_size": "lg"},
    {"name": "Minimal Monochrome", "paper": "#FFFFFF", "ink": "#292929", "accent": "#777777", "display_font": "Montserrat", "body_font": "Raleway", "border": "single", "divider": "line", "pattern": "none", "name_size": "md"},
    {"name": "Peacock Teal", "paper": "#F0F7F6", "ink": "#164D50", "accent": "#B28A45", "display_font": "DM Serif Display", "body_font": "Cormorant Garamond", "border": "double", "divider": "diamond", "pattern": "lines", "name_size": "xl"},
]


def _brief_has(text, *terms):
    return any(term in text for term in terms)


def fallback_design(community="Other", previous=None, user_ink=None,
                   user_orientation=None, brief="", preferences=None):
    """Compose a fresh, prompt-aware design without any external API."""
    base = dict(DEFAULT_DESIGNS.get(community, DEFAULT_DESIGNS["Other"]))
    text = (brief or "").lower()

    # A broad colour library: the generator recombines these with independent
    # pattern, border, motif, composition and type choices on every redesign.
    palettes = [
        ("Ivory & antique gold", "#FFF9ED", "#49351F", "#B58A3A", "#E8D7B5"),
        ("Emerald heritage", "#F2F7F1", "#174A3A", "#B99A55", "#D4E4D5"),
        ("Rose burgundy", "#FFF5F3", "#702B3A", "#C18A78", "#F0D9D8"),
        ("Midnight sapphire", "#F5F7FC", "#1F3557", "#A7AEBB", "#DCE5F3"),
        ("Sage botanical", "#F5F7F0", "#354B3D", "#9A9B72", "#DDE6D5"),
        ("Blush champagne", "#FFF8F4", "#694653", "#C49A78", "#F3E0D8"),
        ("Terracotta silk", "#FBF2E9", "#743B2D", "#B8754D", "#EED7C5"),
        ("Lavender pearl", "#F8F5FA", "#51405F", "#A997B9", "#E7DFF0"),
        ("Peacock teal", "#F0F7F6", "#164D50", "#B28A45", "#D5EAE7"),
        ("Porcelain blue", "#F7F1E5", "#303D52", "#B78B54", "#E8DFC9"),
        ("Cinnamon silk", "#F9F0E8", "#563D35", "#C17B5B", "#EEDBCB"),
        ("Coral garden", "#FFF5EF", "#713D39", "#E47C66", "#F9D9CB"),
        ("Turquoise garden", "#EFF9F8", "#14545A", "#D28C55", "#CDEBE8"),
        ("Plum & rose", "#FBF3F8", "#582D4C", "#B66C91", "#EFD9E7"),
        ("Marigold festival", "#FFF8E7", "#65421C", "#D18A24", "#F5E2B6"),
        ("Ruby celebration", "#FFF3F2", "#6E202A", "#D49A61", "#F2D5D3"),
        ("Misty eucalyptus", "#F3F8F4", "#294C42", "#A9B98B", "#DCE9DF"),
        ("Indigo and silver", "#F3F5FA", "#26365A", "#9AA9C5", "#DDE3EF"),
        ("Peach and copper", "#FFF5EC", "#704332", "#C77C52", "#F4DCCB"),
        ("Black tie", "#F7F6F2", "#252525", "#A58B60", "#E7E1D5"),
        ("Mint and champagne", "#F1FAF5", "#245344", "#C39A5B", "#D8EEE3"),
        ("Orchid dusk", "#F7F1FA", "#4C365F", "#C18AB5", "#EADBED"),
    ]
    themes = ["botanical", "arabesque", "geometric", "celestial", "heritage",
              "watercolor", "minimal", "floral", "luxury", "art-deco",
              "coastal", "ornamental", "tropical", "romantic", "festive"]
    motifs = ["fine jasmine vines", "lotus medallions", "peacock-feather curves",
              "delicate paisley tracery", "star-map constellations", "architectural arches",
              "abstract silk-ribbon forms", "fine botanical branches", "ornamental rosettes",
              "hand-drawn wildflowers", "geometric latticework", "gold filigree flourishes",
              "banana-leaf line art", "coconut-palm silhouettes", "rose garlands",
              "orchid sprays", "sunburst medallions", "scalloped fan motifs",
              "traditional mural-inspired borders", "conch-shell linework"]
    patterns = ["none", "dots", "lines", "vignette", "floral-repeat", "paisley",
                "mandala", "damask", "botanical", "geometric-grid", "art-deco-rays",
                "wave", "scallop", "woven-textile", "starburst", "watercolor-wash"]
    borders = ["double", "temple", "corners", "single", "dots", "none"]
    compositions = ["centered", "asymmetric", "framed", "split", "editorial"]
    palette = random.choice(palettes)
    theme = random.choice(themes)
    motif = random.choice(motifs)
    previous = previous if isinstance(previous, dict) else {}
    last = (previous.get("paper"), previous.get("ink"), previous.get("accent"),
            previous.get("theme"), previous.get("motif"), previous.get("pattern"))

    for _ in range(60):
        palette = random.choice(palettes)
        theme = random.choice(themes)
        motif = random.choice(motifs)
        pattern = random.choice(patterns)
        signature = (palette[1], palette[2], palette[3], theme, motif, pattern)
        if signature != last:
            break

    candidate = {
        **base,
        "paper": palette[1], "ink": palette[2], "accent": palette[3],
        "accent_secondary": palette[4],
        "display_font": random.choice([f for f in EN_FONTS if f not in ("Tangerine",)]),
        "body_font": random.choice(["Cormorant Garamond", "Lora", "EB Garamond",
                                     "Libre Baskerville", "Crimson Pro", "Raleway", "Poppins"]),
        "ml_font": random.choice(ML_FONTS),
        "border": random.choice(borders), "divider": random.choice(DIVIDERS),
        "pattern": pattern, "name_size": random.choice(NAME_SIZES),
        "theme": theme, "motif": motif,
        "composition": random.choice(compositions),
        "decoration_density": random.choice(["sparse", "balanced", "rich"]),
        "mood": f"{palette[0]} · {theme.title()}",
        "decoration_description": motif,
        "background_description": f"{palette[0]} stationery with {theme} atmosphere",
        "orientation": "portrait",
        "background_type": "gradient" if random.random() < 0.58 else "solid",
        "gradient_start": palette[1], "gradient_end": palette[4],
        "gradient_angle": random.choice([25, 45, 90, 120, 135, 155, 180]),
        "pattern_opacity": random.choice([0.07, 0.09, 0.12, 0.15]),
        "layout_variant": random.choice(["classic", "editorial", "ornate-frame", "modern-arch", "layered-border"]),
    }

    # Explicit orientation and natural-language art direction win over random defaults.
    if user_orientation in ("portrait", "landscape"):
        candidate["orientation"] = user_orientation
    elif _brief_has(text, "landscape", "horizontal", "wide", "panoramic"):
        candidate["orientation"] = "landscape"
    elif _brief_has(text, "portrait", "vertical", "tall"):
        candidate["orientation"] = "portrait"

    theme_aliases = {
        "botanical": ("botanical", "leaves", "leaf", "greenery", "garden", "foliage"),
        "arabesque": ("arabesque", "islamic geometry", "mosaic", "lattice"),
        "geometric": ("geometric", "modern lines", "abstract geometry"),
        "celestial": ("celestial", "stars", "moon", "night sky", "constellation"),
        "heritage": ("heritage", "kerala traditional", "temple", "palace", "traditional", "mural"),
        "watercolor": ("watercolor", "watercolour", "painted", "soft wash"),
        "minimal": ("minimal", "minimalist", "simple", "no decoration", "no flowers"),
        "floral": ("floral", "flowers", "jasmine", "rose", "lotus", "orchid"),
        "luxury": ("luxury", "luxurious", "premium", "opulent", "gold foil", "royal"),
        "art-deco": ("art deco", "art-deco", "1920s", "deco"),
        "coastal": ("coastal", "ocean", "sea", "beach", "wave"),
        "tropical": ("tropical", "palm", "banana leaf", "exotic"),
        "romantic": ("romantic", "love", "soft rose", "dreamy"),
        "festive": ("festive", "vibrant", "celebration", "bright", "colorful", "colourful"),
    }
    for theme_name, words in theme_aliases.items():
        if _brief_has(text, *words):
            candidate["theme"] = theme_name
            break

    pattern_aliases = {
        "floral-repeat": ("floral pattern", "flower pattern", "floral repeat"),
        "paisley": ("paisley", "mango motif"),
        "mandala": ("mandala", "rangoli"),
        "damask": ("damask", "ornate textile"),
        "botanical": ("botanical pattern", "leaf pattern", "vine pattern"),
        "geometric-grid": ("geometric pattern", "grid pattern", "lattice pattern"),
        "art-deco-rays": ("art deco", "sunburst", "fan pattern"),
        "wave": ("wave pattern", "waves", "ocean pattern"),
        "scallop": ("scallop", "scalloped"),
        "woven-textile": ("woven", "textile", "fabric pattern", "kasavu"),
        "starburst": ("starburst", "star pattern", "stars"),
        "watercolor-wash": ("watercolor background", "watercolour background", "paint wash"),
    }
    for pattern_name, words in pattern_aliases.items():
        if _brief_has(text, *words):
            candidate["pattern"] = pattern_name
            break

    named_palettes = [
        (("emerald", "dark green", "forest green", "sage"), "#F2F7F1", "#174A3A", "#B99A55"),
        (("navy", "midnight blue", "royal blue", "sapphire"), "#F5F7FC", "#1F3557", "#A7AEBB"),
        (("burgundy", "wine", "maroon"), "#FFF5F3", "#702B3A", "#C18A78"),
        (("pink", "blush", "rose"), "#FFF8F4", "#694653", "#C49A78"),
        (("lavender", "lilac", "purple", "orchid"), "#F8F5FA", "#51405F", "#A997B9"),
        (("terracotta", "rust", "copper"), "#FBF2E9", "#743B2D", "#B8754D"),
        (("black", "monochrome", "black and white"), "#FFFFFF", "#292929", "#777777"),
        (("teal", "peacock", "turquoise"), "#F0F7F6", "#164D50", "#B28A45"),
        (("coral", "salmon"), "#FFF5EF", "#713D39", "#E47C66"),
        (("marigold", "saffron", "mustard", "yellow"), "#FFF8E7", "#65421C", "#D18A24"),
        (("mint",), "#F1FAF5", "#245344", "#C39A5B"),
        (("peach",), "#FFF5EC", "#704332", "#C77C52"),
    ]
    for words, paper, ink, accent in named_palettes:
        if _brief_has(text, *words):
            candidate.update(paper=paper, ink=ink, accent=accent,
                             gradient_start=paper, gradient_end=palette[4])
            break

    # Accept explicit HEX colours in prompts. First is the requested paper/background,
    # second is ink, third is accent; if only one is supplied it is treated as accent.
    hexes = re.findall(r"#[0-9a-fA-F]{6}", brief or "")
    if len(hexes) >= 3:
        candidate.update(paper=hexes[0].upper(), ink=hexes[1].upper(), accent=hexes[2].upper())
    elif len(hexes) == 2:
        candidate.update(paper=hexes[0].upper(), accent=hexes[1].upper())
    elif len(hexes) == 1:
        candidate["accent"] = hexes[0].upper()

    if _brief_has(text, "gold", "gold foil", "antique gold"):
        candidate["accent"] = "#B58A3A"
    if _brief_has(text, "silver", "silver foil"):
        candidate["accent"] = "#8795A8"
    if _brief_has(text, "minimal", "minimalist", "simple", "no decoration", "no flowers"):
        candidate.update(decoration_density="sparse", border="none", pattern="none")
    elif _brief_has(text, "rich decoration", "ornate", "heavily decorated", "opulent", "maximalist"):
        candidate["decoration_density"] = "rich"
    elif _brief_has(text, "colorful", "colourful", "vibrant", "bright", "rainbow"):
        candidate["decoration_density"] = "rich"

    if _brief_has(text, "asymmetric", "asymmetrical", "off-centre"):
        candidate["composition"] = "asymmetric"
    elif _brief_has(text, "split layout", "two column", "two-column"):
        candidate["composition"] = "split"
    elif _brief_has(text, "editorial", "magazine style"):
        candidate["composition"] = "editorial"
    elif _brief_has(text, "framed", "inside a frame"):
        candidate["composition"] = "framed"

    # Structured form controls take precedence over inferred prompt defaults.
    preferences = preferences if isinstance(preferences, dict) else {}
    aliases = {
        "paper_color": "paper", "background_color": "background_color",
        "ink_color": "ink", "accent_color": "accent",
        "design_theme": "theme", "design_style": "theme",
        "design_pattern": "pattern", "design_motif": "motif",
        "flower_style": "motif", "design_composition": "composition",
        "layout_style": "composition", "design_border": "border",
        "design_density": "decoration_density", "decoration_level": "decoration_density",
        "design_display_font": "display_font", "design_body_font": "body_font",
        "design_ml_font": "ml_font", "design_orientation": "orientation",
        "design_background_type": "background_type",
    }
    for source, target in aliases.items():
        value = preferences.get(source)
        if value not in (None, "", "auto") and not (source == "design_style" and value == "random"):
            candidate[target] = value
    for key in ("paper", "ink", "accent", "accent_secondary",
                "gradient_start", "gradient_end"):
        value = preferences.get(key)
        if value not in (None, ""):
            candidate[key] = value

    # Optional colour mood selector from the order form.
    colour_moods = {
        "jewel": ("#F7F3EA", "#24364B", "#B58A3A"),
        "pastel": ("#FFF8F6", "#684C5A", "#D9A7B5"),
        "bright": ("#FFF9E8", "#593B2B", "#E87942"),
        "earthy": ("#F5F0E5", "#4B4536", "#A56B43"),
        "cool": ("#F2F7FA", "#263B55", "#7898B8"),
        "monochrome": ("#FFFFFF", "#222222", "#777777"),
        "gold": ("#FFF9ED", "#49351F", "#B58A3A"),
    }
    mood = str(preferences.get("color_mood", "")).lower()
    if mood in colour_moods:
        candidate["paper"], candidate["ink"], candidate["accent"] = colour_moods[mood]
        candidate["gradient_start"] = candidate["paper"]

    if preferences.get("design_prompt"):
        candidate["decoration_description"] = str(preferences["design_prompt"])[:500]

    # Explicit user ink is accepted only when it remains readable.
    if user_ink and HEX.fullmatch(str(user_ink).strip()):
        candidate["ink"] = str(user_ink).strip().upper()

    return sanitize_design(candidate, community)


DESIGN_PROMPT = f"""
You are the creative director of a premium Kerala wedding invitation design studio.
Interpret the customer's free-form brief as the primary art direction. It may describe
colours, mood, visual references, materials, cultural details, motifs, typography,
composition, ornament density, minimalism, luxury, or an original concept.

Make a coherent, distinctive choice that expresses the brief. If the brief is
short or empty, invent a fresh, polished concept suited to the event and community.
Avoid repeating the previous design when asked to surprise or redesign.

SAFE TYPOGRAPHY OPTIONS (choose only these font names):
English: {', '.join(EN_FONTS)}
Malayalam: {', '.join(ML_FONTS)}

You are NOT restricted to a fixed template, border, ornament, pattern, or layout catalogue.
Invent an original visual concept for this couple. Return a structured design specification
using these keys: mood, paper, ink, accent, accent_secondary, background_type,
background_color, gradient_start, gradient_end, gradient_angle, display_font,
body_font, ml_font, name_size, orientation, theme, pattern, pattern_opacity,
layout_variant, composition, decoration_density, motif, border_description,
decoration_description, background_description, hero_image_enabled,
hero_image_prompt, hero_image_position, hero_image_style, floral_border_enabled,
floral_border_style, floral_border_density.

orientation must be portrait or landscape. theme should be one concise safe visual
category such as botanical, arabesque, geometric, celestial, heritage, watercolor,
minimal, floral, luxury, art-deco, coastal, tropical, romantic, or festive. pattern may
be any short safe visual treatment such as paisley, mandala, damask, woven-textile,
scallop, wave, starburst, floral-repeat, or none. composition can be centered,
asymmetric, framed, split, editorial, or freeform. decoration_density can be sparse,
balanced, or rich. motif and
decoration_description are free-form creative descriptions: you may invent motifs beyond
any existing symbol list. The renderer will interpret them using safe vector/CSS ornaments.
For a requested person, deity, or scene illustration, set hero_image_enabled=true and write a detailed hero_image_prompt describing the requested subject, respectful visual treatment, and composition. Choose hero_image_position from top-center, top-left, top-right, or bottom-center. For requested floral edging, set floral_border_enabled=true and choose a suitable floral_border_style and floral_border_density. Do not invent an image URL or file path: the application image-generation step supplies the actual local image asset separately. Do not output HTML, CSS, JavaScript, SVG, URLs, remote image references, or arbitrary code.

Use every relevant fact from the form as content context, but do not rewrite factual data
or include names/dates/venues in the design JSON. Customer instructions outrank defaults;
community is context, never a reason to override a customer's explicit preference.
Select portrait/landscape based on the brief or requested orientation. If not specified,
choose the orientation that best fits your composition. Return JSON only.
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

    # Keep text readable even when a customer chooses a vivid paper colour.
    # Choose the stronger neutral when a supplied ink cannot meet WCAG AA.
    readable_ink = max(("#171717", "#FFFFFF"),
                       key=lambda colour: contrast_ratio(colour, design["paper"]))
    if contrast_ratio(design["ink"], design["paper"]) < 4.5:
        design["ink"] = readable_ink

    if user_ink and HEX.fullmatch(str(user_ink).strip()):
        proposed_ink = user_ink.strip().upper()
        if contrast_ratio(proposed_ink, design["paper"]) >= 4.5:
            design["ink"] = proposed_ink

    design["mood"] = str(raw.get("mood") or "Original custom design")[:120]
    design["background_description"] = str(raw.get("background_description") or "")[:300]
    design["decoration_description"] = str(raw.get("decoration_description") or raw.get("motif") or "")[:500]
    design["motif"] = str(raw.get("motif") or design["decoration_description"] or "ornamental details")[:180]
    design["border_description"] = str(raw.get("border_description") or "")[:300]

    # Explicit artwork instructions for the card renderer. Gemini describes the
    # requested illustration; a separate image-generation step must create the
    # actual local image file and set hero_image_src. Never trust arbitrary URLs.
    design["hero_image_enabled"] = bool(raw.get("hero_image_enabled", False))
    design["hero_image_prompt"] = str(raw.get("hero_image_prompt") or "")[:700]
    hero_positions = {"top-center", "top-left", "top-right", "bottom-center"}
    hero_position = str(raw.get("hero_image_position") or "top-center").lower()
    design["hero_image_position"] = hero_position if hero_position in hero_positions else "top-center"
    design["hero_image_style"] = str(raw.get("hero_image_style") or "traditional devotional illustration")[:120]
    hero_src = str(raw.get("hero_image_src") or "")
    if re.fullmatch(r"/assets/generated/[A-Za-z0-9_.-]+\.(?:png|jpe?g|webp)", hero_src, re.I):
        design["hero_image_src"] = hero_src
    else:
        design["hero_image_src"] = ""

    design["floral_border_enabled"] = bool(raw.get("floral_border_enabled", False))
    floral_styles = {"mixed", "jasmine", "rose", "lotus", "marigold", "orchid", "hibiscus", "traditional"}
    floral_style = str(raw.get("floral_border_style") or "mixed").lower()
    design["floral_border_style"] = floral_style if floral_style in floral_styles else "mixed"
    floral_density = str(raw.get("floral_border_density") or "rich").lower()
    design["floral_border_density"] = floral_density if floral_density in {"sparse", "balanced", "rich"} else "rich"

    design["theme"] = str(raw.get("theme") or "floral").lower()[:40]
    if not re.fullmatch(r"[a-z0-9 -]+", design["theme"]):
        design["theme"] = "floral"
    design["composition"] = str(raw.get("composition") or "centered").lower()
    if design["composition"] not in {"centered", "asymmetric", "framed", "split", "editorial", "freeform"}:
        design["composition"] = "centered"
    design["decoration_density"] = str(raw.get("decoration_density") or "balanced").lower()
    if design["decoration_density"] not in {"sparse", "balanced", "rich"}:
        design["decoration_density"] = "balanced"
    orientation = str(raw.get("orientation") or "portrait").lower()
    design["orientation"] = orientation if orientation in ("portrait", "landscape") else "portrait"
    design["ornament_char"] = ORNAMENTS[design["ornament"]]
    # Extra renderer-friendly design tokens. Templates may use these to create
    # layered backgrounds and decorative details without executing customer code.
    design["accent_secondary"] = valid_hex(raw.get("accent_secondary"), design["accent"])
    design["pattern"] = str(raw.get("pattern") or "none")[:48]
    if not re.fullmatch(r"[a-z0-9-]+", design["pattern"]):
        design["pattern"] = "none"
    design["pattern_opacity"] = max(0.04, min(0.22, float(raw.get("pattern_opacity", 0.10))))
    design["layout_variant"] = str(raw.get("layout_variant") or "classic")[:40]
    if not re.fullmatch(r"[a-z0-9-]+", design["layout_variant"]):
        design["layout_variant"] = "classic"
    design["visual_layers"] = [
        {"kind": "background", "style": design["background_type"]},
        {"kind": "pattern", "style": design["pattern"], "opacity": design["pattern_opacity"]},
        {"kind": "ornament", "style": design["motif"], "density": design["decoration_density"]},
        {"kind": "frame", "style": design.get("border_description") or design.get("border", "single")},
    ]

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
        "orientation": form.get("orientation", "auto"),
        "design_style": form.get("design_style", "random"),
        "flower_style": form.get("flower_style", "mixed-bouquet"),
        "layout_style": form.get("layout_style", "auto"),
        "decoration_level": form.get("decoration_level", "balanced"),
        "color_mood": form.get("color_mood", "auto"),
    }
    design_keys = (
        "paper_color", "background_color", "ink_color", "accent_color",
        "paper", "ink", "accent", "accent_secondary", "gradient_start", "gradient_end",
        "design_theme", "design_pattern", "design_motif", "design_composition",
        "design_border", "design_density", "design_display_font", "design_body_font",
        "design_ml_font", "design_orientation", "design_background_type", "design_prompt",
        "design_style", "flower_style", "layout_style", "decoration_level", "color_mood",
    )
    data["design_preferences"] = {key: form[key] for key in design_keys if form.get(key)}

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
            "form_content": data,
            "requested_orientation": data.get("orientation", "auto"),
            "design_preferences": {k: data.get(k) for k in ("design_style", "flower_style", "layout_style", "decoration_level", "color_mood")},
            "customer_priorities": [data.get("creative_brief", ""), data.get("style_notes", "")],
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
    if design_raw is None:
        design = fallback_design(data["community"], user_ink=form.get("ink_color"), user_orientation=data.get("orientation"), brief=(data.get("creative_brief", "") + " " + data.get("style_notes", "") + " " + data.get("design_prompt", "")), preferences=data.get("design_preferences"))
        # notes.append(f"Offline template applied: {design.get('mood', 'Fallback design')}.")
    else:
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
        # notes.append(
        #     "Gemini API key is not configured. A fresh offline template is being used for this design change."
        # )
        if target in ("design", "both", "redesign"):
            design = fallback_design(
                data["community"], previous=design,
                user_ink=form.get("ink_color"),
                user_orientation=data.get("orientation"),
                brief=(instruction + " " + data.get("creative_brief", "") + " " +
                       data.get("style_notes", "") + " " + data.get("design_prompt", "")),
                preferences=data.get("design_preferences"),
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
            "form_content": data,
            "requested_orientation": data.get("orientation", "auto"),
            "design_preferences": {k: data.get(k) for k in ("design_style", "flower_style", "layout_style", "decoration_level", "color_mood")},
            "customer_priorities": [data.get("creative_brief", ""), data.get("style_notes", ""), instruction],
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
            if name == "design":
                design = fallback_design(
                    data["community"], previous=design,
                    user_ink=form.get("ink_color"), user_orientation=data.get("orientation"), brief=(instruction + " " + data.get("creative_brief", "") + " " + data.get("style_notes", "") + " " + data.get("design_prompt", "")),
                    preferences=data.get("design_preferences"),
                )
                # notes.append(f"Offline template applied: {design.get('mood', 'Fallback design')}.")
            continue

        if name == "wording":
            wording = normalise_wording(result, data)
        elif name == "design":
            revised_design = sanitize_design(
                result,
                data["community"],
                form.get("ink_color"),
            )
            # Keep the previous generated image unless the image-generation
            # pipeline replaces it; text-only Gemini revisions cannot create files.
            if not revised_design.get("hero_image_src") and design.get("hero_image_src"):
                revised_design["hero_image_src"] = design["hero_image_src"]
            design = revised_design

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