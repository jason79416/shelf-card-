import io
import os
import json
import streamlit as st
from PIL import Image

# Import Google GenAI SDK (New SDK) & Legacy SDK
try:
    from google import genai
    USE_NEW_SDK = True
except ImportError:
    USE_NEW_SDK = False

import google.generativeai as genai_legacy

from reportlab.lib.pagesizes import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(page_title="Mongolian Import Store - Shelf Card Generator", page_icon="🏷️", layout="centered")

# Font loading logic
def load_cyrillic_fonts():
    possible_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/local/lib/python3.11/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf",
        "DejaVuSans.ttf"
    ]
    possible_bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/local/lib/python3.11/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf",
        "DejaVuSans-Bold.ttf"
    ]
    font_path = next((p for p in possible_paths if os.path.exists(p)), None)
    bold_path = next((p for p in possible_bold_paths if os.path.exists(p)), None)
    
    if font_path and bold_path:
        pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))
        return True
    return False

fonts_loaded = load_cyrillic_fonts()

def generate_pdf_shelf_card(data):
    buffer = io.BytesIO()
    PAGE_WIDTH, PAGE_HEIGHT = 4 * inch, 6 * inch

    doc = SimpleDocTemplate(
        buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        rightMargin=0.25*inch, leftMargin=0.25*inch,
        topMargin=0.25*inch, bottomMargin=0.25*inch
    )

    styles = getSampleStyleSheet()
    font_name = "DejaVuSans" if fonts_loaded else "Helvetica"
    font_bold = "DejaVuSans-Bold" if fonts_loaded else "Helvetica-Bold"

    title_style = ParagraphStyle('CardTitle', parent=styles['Normal'], fontName=font_bold, fontSize=12, leading=15, textColor=colors.HexColor('#B22222'), alignment=1, spaceAfter=2)
    subhead_style = ParagraphStyle('CardSubTitle', parent=styles['Normal'], fontName=font_bold, fontSize=9, leading=11, textColor=colors.HexColor('#003366'), alignment=1, spaceAfter=4)
    sec_header_en = ParagraphStyle('SecEN', parent=styles['Normal'], fontName=font_bold, fontSize=8.5, leading=10, textColor=colors.HexColor('#003366'), spaceBefore=2, spaceAfter=2)
    sec_header_mn = ParagraphStyle('SecMN', parent=styles['Normal'], fontName=font_bold, fontSize=8.5, leading=10, textColor=colors.HexColor('#B22222'), spaceBefore=2, spaceAfter=2)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontName=font_name, fontSize=7, leading=9.5, textColor=colors.HexColor('#222222'), spaceAfter=3)
    highlight_style = ParagraphStyle('Highlight', parent=styles['Normal'], fontName=font_bold, fontSize=7.5, leading=10, textColor=colors.HexColor('#1B5E20'), spaceAfter=3)

    story = []
    story.append(Paragraph(data.get('product_name_en', 'PRODUCT CARD').upper(), title_style))
    story.append(Paragraph(data.get('product_name_mn', 'БАРААНИЙ ТАЙЛБАР'), subhead_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#003366'), spaceAfter=4))

    headline_text = f"<b>🇺🇸 USA Import | {data.get('headline_mn', '')}</b>"
    story.append(Paragraph(headline_text, ParagraphStyle('Headline', parent=body_style, fontSize=8, leading=10, alignment=1, textColor=colors.HexColor('#B22222'), fontName=font_bold)))
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>[ English Description ]</b>", sec_header_en))
    story.append(Paragraph(f"<b>What It Is & How to Use:</b> {data.get('usage_en', '')}", body_style))
    story.append(Paragraph(f"<b>Why Buy This:</b> {data.get('why_buy_en', '')}", highlight_style))

    story.append(Spacer(1, 2))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#CCCCCC'), spaceAfter=3))

    story.append(Paragraph("<b>[ Монгол тайлбар ]</b>", sec_header_mn))
    story.append(Paragraph(f"<b>Энэ юу вэ? Яаж хэрэглэх вэ?:</b> {data.get('usage_mn', '')}", body_style))
    story.append(Paragraph(f"<b>Яагаад сонгох ёстой вэ?:</b> {data.get('why_buy_mn', '')}", highlight_style))

    story.append(Spacer(1, 4))

    footer_data = [[Paragraph(f"<b>Category:</b> {data.get('category_en', 'Import Goods')} | <b>Ангилал:</b> {data.get('category_mn', 'Импортын бараа')}", ParagraphStyle('Footer', parent=body_style, fontSize=6.5, leading=8.5, alignment=1))]]
    footer_table = Table(footer_data, colWidths=[3.5*inch])
    footer_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F2F4F7')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(footer_table)

    def draw_border(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#003366'))
        canvas.setLineWidth(2)
        canvas.rect(0.1*inch, 0.1*inch, PAGE_WIDTH - 0.2*inch, PAGE_HEIGHT - 0.2*inch)
        canvas.setStrokeColor(colors.HexColor('#B22222'))
        canvas.setLineWidth(0.8)
        canvas.rect(0.13*inch, 0.13*inch, PAGE_WIDTH - 0.26*inch, PAGE_HEIGHT - 0.26*inch)
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_border)
    buffer.seek(0)
    return buffer

st.title("🏷️ Import Product Shelf Card Generator")
st.sidebar.title("⚙️ Settings")
api_key = st.sidebar.text_input("Gemini API Key", type="password")

uploaded_file = st.file_uploader("Upload Product Photo / Барааны зураг оруулна уу...", type=["jpg", "jpeg", "png", "webp"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Product Image", use_column_width=True)

    if st.button("🚀 Analyze & Generate Shelf Card"):
        if not api_key:
            st.error("Please enter a Gemini API Key in the sidebar.")
        else:
            with st.spinner("Analyzing image and creating copy..."):
                try:
                    cleaned_key = api_key.strip()
                    prompt = """
                    Analyze this product image and return ONLY a valid JSON object without markdown formatting:
                    {
                        "product_name_en": "Product Name in English",
                        "product_name_mn": "Product Name in Mongolian Cyrillic",
                        "category_en": "Category in English",
                        "category_mn": "Category in Mongolian",
                        "headline_en": "Headline in English",
                        "headline_mn": "Headline in Mongolian",
                        "usage_en": "1-2 sentences on what it is and usage in English",
                        "usage_mn": "1-2 sentences on what it is and usage in natural Mongolian",
                        "why_buy_en": "Persuasive hook in English",
                        "why_buy_mn": "Persuasive hook in Mongolian"
                    }
                    """
                    
                    text_resp = None
                    last_error = None
                    
                    # Try using new google-genai SDK first
                    if USE_NEW_SDK:
                        try:
                            client = genai.Client(api_key=cleaned_key)
                            for m in ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']:
                                try:
                                    res = client.models.generate_content(model=m, contents=[prompt, image])
                                    if res and res.text:
                                        text_resp = res.text
                                        break
                                except Exception as e:
                                    last_error = e
                        except Exception as e:
                            last_error = e

                    # Fallback to google-generativeai SDK if new SDK fails or isn't installed
                    if not text_resp:
                        genai_legacy.configure(api_key=cleaned_key)
                        for m in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp']:
                            try:
                                model = genai_legacy.GenerativeModel(m)
                                res = model.generate_content([prompt, image])
                                if res and res.text:
                                    text_resp = res.text
                                    break
                            except Exception as e:
                                last_error = e

                    if not text_resp:
                        st.error(f"API Error: Unable to query Gemini models ({str(last_error)}). Please verify that your API Key is created from Google AI Studio (https://aistudio.google.com/app/apikey).")
                    else:
                        clean_json = text_resp.replace("```json", "").replace("```", "").strip()
                        data = json.loads(clean_json)

                        st.success("Card Generated Successfully!")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**[ English ]**")
                            st.write(f"**Name:** {data.get('product_name_en')}")
                            st.write(f"**Usage:** {data.get('usage_en')}")
                            st.write(f"**Why Buy:** {data.get('why_buy_en')}")
                        with col2:
                            st.markdown("**[ Монгол ]**")
                            st.write(f"**Нэр:** {data.get('product_name_mn')}")
                            st.write(f"**Хэрэглээ:** {data.get('usage_mn')}")
                            st.write(f"**Яагаад авах вэ:** {data.get('why_buy_mn')}")

                        pdf_buffer = generate_pdf_shelf_card(data)
                        st.download_button(
                            label="📥 Download Printable PDF Shelf Card (4x6)",
                            data=pdf_buffer,
                            file_name=f"{data.get('product_name_en', 'product').replace(' ', '_')}_Shelf_Card.pdf",
                            mime="application/pdf"
                        )
                except Exception as e:
                    st.error(f"Error processing image or JSON: {str(e)}")
