# Virtual Chat PDF Q&A

A simple Flask app that accepts PDF uploads, extracts content, and generates question-answer pairs using Google Gemini.

## Setup

1. Copy `.env.example` to `.env`.
2. Set `GOOGLE_API_KEY` in `.env`.
3. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   python3 app.py
   ```
5. Open `http://localhost:5000` in your browser.

## Files

- `app.py` — Flask backend and Gemini integration.
- `requirements.txt` — Python dependencies.
- `public/index.html` — file upload UI.
- `public/script.js` — frontend upload logic.
- `.env.example` — example environment variable file.
- `.gitignore` — ignores Python caches and local environment.
