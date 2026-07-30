import hashlib
import io
import json
import os
import time
from html import escape

import streamlit as st
from google import genai
from google.genai import types
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image as PdfImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


st.set_page_config(
    page_title="Shelf Card Generator",
    page_icon="🏷️",
    layout="centered",
)

CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "product_name_en": {"type": "string"},
        "product_name_mn": {"type": "string"},
        "category_en": {"type": "string"},
        "category_mn": {"type": "string"},
        "headline_en": {"type": "string"},
        "headline_mn": {"type": "string"},
        "usage_en": {"type": "string"},
        "usage_mn": {"type": "string"},
        "why_buy_en": {"type": "string"},
        "why_buy_mn": {"type": "string"},
    },
    "required": [
        "product_name_en", "product_name_mn", "category_en", "category_mn",
        "headline_en", "headline_mn", "usage_en", "usage_mn",
        "why_buy_en", "why_buy_mn",
    ],
}

PROMPT = """
You are creating a small bilingual shelf card for an imported U.S. product sold
in Mongolia. Look carefully at the product image. Return the requested JSON
only, following the schema exactly.

Writing requirements:
- Translate into natural, friendly Mongolian Cyrillic, not word-for-word text.
- Briefly explain what the product is and its ordinary use. Each usage field
  must be 1–2 short sentences, at most 38 words in English and 45 words in
  Mongolian.
- Write a concise, appealing purchase reason. Make it warm and useful, not
  pushy. Never invent ingredients, certifications, prices, discounts, health
  benefits, safety claims, or product facts that cannot be seen in the image.
- If the image does not show enough information to identify the item, use a
  simple generic name and describe only what is visually clear.
- Do not include emoji, Markdown, HTML, or quotation marks around values.
"""


def get_api_key() -> str:
    """Prefer a Streamlit Cloud secret; sidebar input is only a local fallback."""
    secret = st.secrets.get("GEMINI_API_KEY", "")
    if secret:
        return secret.strip()
    return st.sidebar.text_input(
        "Gemini API key", type="password", help="For deployment, store this in Streamlit Secrets instead."
    ).strip()


def load_cyrillic_fonts() -> bool:
    """Use the DejaVu font package installed by packages.txt on Streamlit Cloud."""
    regular_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        r"C:\Windows\Fonts\DejaVuSans.ttf",
    ]
    bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
    ]
    regular = next((path for path in regular_paths if os.path.exists(path)), None)
    bold = next((path for path in bold_paths if os.path.exists(path)), None)
    if not regular or not bold:
        return False
    try:
        pdfmetrics.registerFont(TTFont("ShelfCard", regular))
        pdfmetrics.registerFont(TTFont("ShelfCardBold", bold))
    except KeyError:
        pass  # Fonts were registered during a Streamlit rerun.
    return True


FONTS_READY = load_cyrillic_fonts()


def resolve_model_name() -> str:
    """Permit a model override without putting it in source control."""
    return str(st.secrets.get("GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.6-flash"))).strip()


def model_candidates(client: genai.Client) -> list[str]:
    """Discover models available to this particular API key before making a call.

    Gemini's available models differ by API key, country, account type, and time.
    Hard-coding a retired model is therefore fragile. The configured model remains
    the first choice, but the API's own model list supplies the fallbacks.
    """
    configured = resolve_model_name().removeprefix("models/")
    discovered = []
    try:
        for model in client.models.list():
            actions = getattr(model, "supported_actions", []) or []
            name = str(getattr(model, "name", "")).removeprefix("models/")
            if name and "generateContent" in actions:
                discovered.append(name)
    except Exception:
        # A configured model can still work if the models endpoint is temporarily unavailable.
        pass

    # Prefer general-purpose Flash models. They are suitable for product image
    # understanding and normally lower cost than Pro or image-generation models.
    def preference(name: str) -> tuple[int, int, str]:
        lower = name.lower()
        return (
            0 if "flash" in lower else 1,
            1 if "image" in lower or "tts" in lower or "live" in lower else 0,
            lower,
        )

    return list(dict.fromkeys([configured, *sorted(discovered, key=preference)]))


def generate_card_copy(api_key: str, image: PILImage.Image) -> dict:
    """Call the current Google Gen AI SDK and retry only temporary failures."""
    client = genai.Client(api_key=api_key)
    unique_models = model_candidates(client)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CARD_SCHEMA,
        temperature=0.55,
    )
    last_error = None

    for model_name in unique_models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[PROMPT, image],
                    config=config,
                )
                if not response.text:
                    raise RuntimeError("Gemini returned an empty response.")
                data = json.loads(response.text)
                missing = [key for key in CARD_SCHEMA["required"] if not str(data.get(key, "")).strip()]
                if missing:
                    raise RuntimeError("Gemini returned an incomplete shelf card.")
                return data
            except Exception as error:  # The SDK error class varies by installed SDK version.
                last_error = error
                message = str(error).lower()
                is_model_error = any(word in message for word in (
                    "not found", "not supported", "404", "invalid argument", "400",
                ))
                is_temporary = any(word in message for word in ("429", "resource exhausted", "500", "503", "timeout"))
                if is_temporary and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                if is_model_error:
                    break  # Try the next supported fallback model.
                raise

    raise RuntimeError(
        "Gemini did not accept any image-capable model available to this API key. "
        "Check that the key is an active Gemini API key from Google AI Studio. "
        f"Models tried: {', '.join(unique_models[:8])}. Last API message: {last_error}"
    )


def paragraph_text(value: str) -> str:
    return escape(str(value or "")).replace("\n", "<br/>")


def generate_pdf_shelf_card(data: dict, product_image: PILImage.Image) -> bytes:
    if not FONTS_READY:
        raise RuntimeError("The PDF font package is missing. Confirm that packages.txt contains fonts-dejavu.")

    buffer = io.BytesIO()
    page_width, page_height = 4 * inch, 6 * inch
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(page_width, page_height),
        rightMargin=0.24 * inch,
        leftMargin=0.24 * inch,
        topMargin=0.24 * inch,
        bottomMargin=0.24 * inch,
    )
    styles = getSampleStyleSheet()
    base = "ShelfCard"
    bold = "ShelfCardBold"
    title = ParagraphStyle("title", parent=styles["Normal"], fontName=bold, fontSize=12, leading=14, alignment=1, textColor=colors.HexColor("#123458"))
    mongolian_title = ParagraphStyle("mn_title", parent=styles["Normal"], fontName=bold, fontSize=9.5, leading=11, alignment=1, textColor=colors.HexColor("#A2342B"), spaceAfter=3)
    label = ParagraphStyle("label", parent=styles["Normal"], fontName=bold, fontSize=7.5, leading=9, textColor=colors.HexColor("#123458"), spaceBefore=2, spaceAfter=1)
    body = ParagraphStyle("body", parent=styles["Normal"], fontName=base, fontSize=7, leading=9.2, textColor=colors.HexColor("#17212B"))
    highlight = ParagraphStyle("highlight", parent=body, fontName=bold, fontSize=7.3, leading=9.5, textColor=colors.HexColor("#245B38"))
    headline = ParagraphStyle("headline", parent=styles["Normal"], fontName=bold, fontSize=8, leading=10, alignment=1, textColor=colors.HexColor("#A2342B"), spaceAfter=3)

    picture = product_image.copy().convert("RGB")
    picture.thumbnail((int(2.25 * inch), int(1.35 * inch)))
    picture_bytes = io.BytesIO()
    picture.save(picture_bytes, format="JPEG", quality=90)
    picture_bytes.seek(0)
    pdf_picture = PdfImage(picture_bytes, width=picture.width, height=picture.height, kind="proportional")
    pdf_picture.hAlign = "CENTER"

    story = [
        Paragraph(paragraph_text(data["product_name_en"]).upper(), title),
        Paragraph(paragraph_text(data["product_name_mn"]), mongolian_title),
        HRFlowable(width="100%", thickness=1.3, color=colors.HexColor("#123458"), spaceAfter=3),
        pdf_picture,
        Spacer(1, 3),
        Paragraph(paragraph_text(data["headline_en"]), headline),
        Paragraph(paragraph_text(data["headline_mn"]), headline),
        Paragraph("ENGLISH", label),
        Paragraph("<b>What it is & how to use:</b> " + paragraph_text(data["usage_en"]), body),
        Paragraph("<b>Why choose it:</b> " + paragraph_text(data["why_buy_en"]), highlight),
        HRFlowable(width="100%", thickness=0.55, color=colors.HexColor("#CBD5E1"), spaceBefore=3, spaceAfter=2),
        Paragraph("МОНГОЛ", label),
        Paragraph("<b>Энэ юу вэ, хэрхэн хэрэглэх вэ:</b> " + paragraph_text(data["usage_mn"]), body),
        Paragraph("<b>Яагаад сонгох вэ:</b> " + paragraph_text(data["why_buy_mn"]), highlight),
        Spacer(1, 4),
    ]
    footer = Paragraph(
        "<b>Category:</b> " + paragraph_text(data["category_en"]) + "  |  <b>Ангилал:</b> " + paragraph_text(data["category_mn"]),
        ParagraphStyle("footer", parent=body, fontSize=6.2, leading=7.8, alignment=1),
    )
    footer_table = Table([[footer]], colWidths=[3.48 * inch])
    footer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F5F8")),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(footer_table)

    def draw_border(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#123458"))
        canvas.setLineWidth(1.6)
        canvas.rect(0.1 * inch, 0.1 * inch, page_width - 0.2 * inch, page_height - 0.2 * inch)
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_border)
    return buffer.getvalue()


def clean_filename(name: str) -> str:
    keep = "".join(char if char.isalnum() or char in "-_ " else "" for char in name)
    return (keep.strip().replace(" ", "_") or "shelf_card")[:60]


st.title("🏷️ Bilingual Shelf Card Generator")
st.caption("Upload a product photo. The PDF shelf card is created automatically in English and Mongolian.")
st.sidebar.header("Settings")
api_key = get_api_key()
uploaded_file = st.file_uploader("Upload product photo", type=["jpg", "jpeg", "png", "webp"])

if uploaded_file:
    image_bytes = uploaded_file.getvalue()
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    image = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
    st.image(image, caption="Uploaded product", use_container_width=True)

    if not api_key:
        st.info("Add your Gemini API key in the sidebar, or save GEMINI_API_KEY in Streamlit Secrets.")
    else:
        cache_key = "generated_" + image_hash
        if cache_key not in st.session_state:
            with st.spinner("Creating your bilingual shelf card…"):
                try:
                    copy = generate_card_copy(api_key, image)
                    st.session_state[cache_key] = {
                        "copy": copy,
                        "pdf": generate_pdf_shelf_card(copy, image),
                    }
                except Exception as error:
                    st.error("Could not create the shelf card. " + str(error))

        result = st.session_state.get(cache_key)
        if result:
            st.success("Your shelf card is ready to print.")
            st.download_button(
                "Download printable PDF (4 × 6 in)",
                data=result["pdf"],
                file_name=clean_filename(result["copy"]["product_name_en"]) + "_Shelf_Card.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
