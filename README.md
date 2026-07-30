# Bilingual Shelf Card Generator

1. Create a Gemini API key in Google AI Studio.
2. In Streamlit Community Cloud, open **App settings → Secrets** and add:

```toml
GEMINI_API_KEY = "paste-your-key-here"
# Optional: choose a model available to your API key.
# GEMINI_MODEL = "gemini-2.5-flash"
```

3. Commit this folder to GitHub and deploy it with Streamlit Community Cloud.

The application deliberately uses `google-genai`, Google's current Python SDK. It requests JSON-structured text from a current stable model and tries two compatible fallbacks only if Google reports that the configured model is unavailable. Do not add your API key to `app.py` or commit it to GitHub.
