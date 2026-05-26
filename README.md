# Virtual Chat PDF Q&A Generator

A Flask-based PDF Q&A application that extracts text from uploaded PDF files and uses generative AI to produce high-quality question-answer pairs. The app supports both OpenRouter and Google Gemini APIs for embeddings and content generation.

## Key Features

- Upload a PDF and extract readable text automatically
- Generate question-answer pairs from document content
- Support for whole-document, chapter-wise, or topic-wise question generation
- Select number of questions and question style
- Ask follow-up questions against the uploaded document using retrieval-augmented answers
- Show inferred sections or topics for generated Q&A
- Lightweight frontend with a clean upload UI

## Technology Stack

- Python 3
- Flask — web server and API routing
- PyPDF2 — PDF text extraction
- NumPy — cosine similarity calculations
- Requests — OpenRouter HTTP API integration
- `google-genai` — Google Gemini integration
- `python-dotenv` — environment variable loading
- HTML/CSS/JavaScript — frontend file upload interface

## Requirements

- Python 3.10 or newer
- `pip` package manager
- Valid API key for either:
  - `GOOGLE_API_KEY` (Google Gemini)
  - `OPENROUTER_API_KEY` (OpenRouter)

## Installation

1. Clone the repository or download the project files.
2. Create a Python virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and add your API keys.

## Environment Variables

Create a `.env` file with the following values:

```dotenv
GOOGLE_API_KEY=your_google_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL=gpt-4o-mini
OPENROUTER_EMBEDDING_MODEL=text-embedding-3-large
```

> Only one of `GOOGLE_API_KEY` or `OPENROUTER_API_KEY` is required. If both are present, OpenRouter will be used.

## Running the App

Start the server with:

```bash
python3 app.py
```

Then open the app in your browser:

```bash
http://127.0.0.1:5000
```

If port `5000` is occupied, set a different port before running:

```bash
PORT=5001 python3 app.py
```

## Usage

1. Open the browser UI.
2. Choose a PDF file.
3. Select the question mode:
   - `Whole document` — generate Q&A from the full text
   - `Chapter-wise` — group questions by chapter or section
   - `Topic-wise` — group questions by inferred topics
4. Enter the desired number of questions (up to 80).
5. Select a question style:
   - `Mixed`
   - `Factual`
   - `Conceptual`
   - `Exam-style`
6. Click `Analyze PDF`.
8. After the PDF is processed, use the new Ask-the-document box to send follow-up questions and receive retrieval-augmented answers based on the uploaded content.

The generated output includes questions, answers, and optional inferred section/topic metadata. The follow-up chat uses only the document content to answer, which improves precision and reduces hallucinations.

## Project Structure

- `app.py` — main Flask application and document processing logic
- `requirements.txt` — Python library dependencies
- `public/index.html` — frontend user interface
- `public/script.js` — frontend request handling and results rendering
- `.env` — runtime configuration (not committed)

## Notes

- This project uses the Flask development server. For production use, deploy with a WSGI server such as Gunicorn.
- If text extraction fails, the PDF may contain scanned images or non-searchable content.
- The quality of generated questions depends on the document content and the configured AI model.

## Troubleshooting

- `Missing API key` error: ensure `.env` contains `GOOGLE_API_KEY` or `OPENROUTER_API_KEY`.
- `Uploaded file must be a PDF`: upload a file with `.pdf` extension.
- `Document text is too short`: the PDF may contain too little readable text.
- `Port already in use`: start the app with `PORT=5001 python3 app.py` or free the occupied port.

## License

Include a license file or choose an appropriate license for your repository.
