import json
import os
import re
from pathlib import Path

import numpy as np
import requests
import google.genai as genai
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from PyPDF2 import PdfReader
from werkzeug.exceptions import HTTPException

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1").rstrip("/")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "gpt-4o-mini")
OPENROUTER_EMBEDDING_MODEL = os.getenv("OPENROUTER_EMBEDDING_MODEL", "text-embedding-3-large")

if not GOOGLE_API_KEY and not OPENROUTER_API_KEY:
    raise RuntimeError(
        "Missing API key. Set GOOGLE_API_KEY or OPENROUTER_API_KEY in .env."
    )

use_openrouter = bool(OPENROUTER_API_KEY)

if use_openrouter:
    openrouter_session = requests.Session()
    openrouter_session.headers.update(
        {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
    )
    EMBEDDING_MODEL = OPENROUTER_EMBEDDING_MODEL
    GENERATION_MODEL = OPENROUTER_MODEL
else:
    # If GOOGLE_API_KEY is missing, we fail fast with a clearer error.
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "Missing API keys. Set GOOGLE_API_KEY or OPENROUTER_API_KEY in .env."
        )
    client = genai.Client(api_key=GOOGLE_API_KEY)
    EMBEDDING_MODEL = "gemini-embedding-001"
    GENERATION_MODEL = "gemini-1.5"

app = Flask(__name__, static_folder="public", static_url_path="")

document_store = {
    "chunks": [],
    "embeddings": [],
    "source": "",
}


@app.errorhandler(Exception)
def handle_exception(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
        message = e.description
    else:
        message = str(e)

    app.logger.exception(e)
    return jsonify({"error": message}), code


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/upload", methods=["POST"])
def upload_pdf():
    pdf_file = request.files.get("pdfFile")
    if not pdf_file:
        return jsonify({"error": "No PDF file uploaded."}), 400

    if not pdf_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Uploaded file must be a PDF."}), 400

    text = extract_text_from_pdf(pdf_file)
    if not text:
        return jsonify({"error": "Could not extract text from the PDF."}), 400

    chunks = split_text(text)
    if not chunks:
        return jsonify({"error": "Document text is too short or could not be chunked."}), 400

    question_mode = request.form.get("questionMode", "whole").lower()
    if question_mode not in {"whole", "chapter", "topic"}:
        question_mode = "whole"

    question_style = request.form.get("questionStyle", "mixed").lower()
    question_count = request.form.get("questionCount", "0")
    try:
        question_count = int(question_count)
    except ValueError:
        question_count = 0

    chunk_embeddings = [get_embedding(chunk) for chunk in chunks]
    document_store["chunks"] = chunks
    document_store["embeddings"] = chunk_embeddings
    document_store["source"] = text

    result = generate_qa_pairs(
        chunks,
        chunk_embeddings,
        mode=question_mode,
        style=question_style,
        question_count=question_count,
    )
    return jsonify({"qa": result})


@app.route("/chat", methods=["POST"])
def chat_document():
    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    if not document_store["chunks"]:
        return jsonify({"error": "Upload a PDF first so the document can be indexed."}), 400

    top_chunks = retrieve_relevant_chunks(question, top_k=6)
    if not top_chunks:
        return jsonify({"error": "No relevant document content was found."}), 500

    answer = generate_rag_answer(question, top_chunks)
    return jsonify({"answer": answer})


def retrieve_relevant_chunks(query: str, top_k: int = 5) -> list[str]:
    query_embedding = get_embedding(query)
    scored_chunks = [
        (cosine_similarity(query_embedding, embedding), chunk)
        for embedding, chunk in zip(document_store["embeddings"], document_store["chunks"])
    ]
    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:top_k]]


def generate_rag_answer(question: str, top_chunks: list[str]) -> str:
    context_text = "\n\n---\n\n".join(top_chunks)
    prompt = (
        "Use only the document content below to answer the user question. "
        "Do not hallucinate or invent answers. If the document does not contain the answer, "
        "respond with: 'I don't know based on the provided document.'\n\n"
        "Document content:\n"
        f"{context_text}\n\n"
        "Question: "
        f"{question}\n\n"
        "Answer:" 
    )

    if use_openrouter:
        return get_openrouter_completion(prompt)

    response = client.models.generate_content(
        model=GENERATION_MODEL,
        contents=prompt,
        config={"temperature": 0.2, "max_output_tokens": 1024},
    )
    return extract_generated_text(response)


def extract_text_from_pdf(pdf_file) -> str:
    reader = PdfReader(pdf_file)
    pages = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text:
            pages.append(page_text)
    return "\n\n".join(pages).strip()


def split_text(text: str, chunk_size: int = 1800, overlap: int = 300) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current.strip())
            if len(sentence) > chunk_size:
                for i in range(0, len(sentence), chunk_size - overlap):
                    chunks.append(sentence[i : i + chunk_size].strip())
                current = ""
            else:
                current = sentence.strip()

    if current:
        chunks.append(current.strip())

    return chunks


def get_embedding(text: str) -> list[float]:
    if use_openrouter:
        return get_openrouter_embedding(text)

    response = client.models.embed_content(model=EMBEDDING_MODEL, contents=[text])
    embeddings = []
    if response.embeddings:
        for item in response.embeddings:
            if item is None:
                continue
            values = getattr(item, "values", None)
            if values is not None:
                embeddings.append(list(values))
    if not embeddings:
        raise RuntimeError(f"Unexpected embedding response shape: {response}")
    return embeddings[0]


def get_openrouter_embedding(text: str) -> list[float]:
    url = f"{OPENROUTER_API_BASE}/embeddings"
    payload = {"model": EMBEDDING_MODEL, "input": text}
    response = openrouter_session.post(url, json=payload, timeout=60)
    response.raise_for_status()
    payload = response.json()

    data = payload.get("data") or []
    if not data or not isinstance(data, list):
        raise RuntimeError(f"Unexpected OpenRouter embedding response: {payload}")

    first = data[0]
    embedding = first.get("embedding")
    if not isinstance(embedding, list):
        raise RuntimeError(f"Unexpected OpenRouter embedding shape: {payload}")

    return embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_np = np.array(a, dtype=np.float32).ravel()
    b_np = np.array(b, dtype=np.float32).ravel()
    if a_np.size == 0 or b_np.size == 0 or np.linalg.norm(a_np) == 0 or np.linalg.norm(b_np) == 0:
        return 0.0
    return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))


def generate_qa_pairs(
    chunks: list[str],
    chunk_embeddings: list[list[float]],
    question_count: int = 20,
    mode: str = "whole",
    style: str = "mixed",
) -> list[dict[str, str]]:
    if question_count <= 0:
        question_count = min(80, max(30, len(chunks) * 3))
    else:
        question_count = min(80, max(question_count, 5))

    query_text = "Create as many high-quality question and answer pairs as possible using the document content."
    query_embedding = get_embedding(query_text)

    scored_chunks = [
        (cosine_similarity(query_embedding, chunk_embeddings[i]), chunks[i])
        for i in range(len(chunks))
    ]
    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    selected_chunks = [chunk for _, chunk in scored_chunks[: min(12, len(chunks))]]

    context = "\n\n".join(selected_chunks)
    style_text = {
        "mixed": "a mix of factual, conceptual, and applied questions",
        "factual": "focused factual questions",
        "conceptual": "conceptual and understanding-based questions",
        "exam": "exam-style questions suitable for study and assessment",
    }.get(style, "a mix of factual, conceptual, and applied questions")

    if mode == "chapter":
        instruction = (
            "Organize the questions by inferred chapters or sections, and include a `section` field for each item. "
            "If explicit chapter labels are not present, infer reasonable chapter headings from the content. "
        )
        output_example = '{"qa": [{"question": "...", "answer": "...", "section": "Chapter 1"}]}'
    elif mode == "topic":
        instruction = (
            "Organize the questions by main topics, and include a `topic` field for each item. "
            "If explicit topics are not present, infer the most relevant topic for each question. "
        )
        output_example = '{"qa": [{"question": "...", "answer": "...", "topic": "Key Topic"}]}'
    else:
        instruction = "Generate questions across the document without grouping by chapter or topic. "
        output_example = '{"qa": [{"question": "...", "answer": "..."}]}'

    prompt = (
        "Use only the context from the document below to generate as many non-repetitive, high-quality question and answer pairs as possible. "
        f"Aim for up to {question_count} pairs, but if the document supports fewer, return the best available set. "
        f"The questions should be {style_text}. "
        f"{instruction}Return valid JSON with a `qa` array of objects. Each object must contain `question` and `answer` fields. "
        "Do not invent facts outside the provided context.\n\n"
        "Document context:\n"
        f"{context}\n\n"
        "Output example:\n"
        f"{output_example}"
    )

    if use_openrouter:
        raw_text = get_openrouter_completion(prompt)
    else:
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt,
            config={"temperature": 0.2, "max_output_tokens": 1024},
        )
        raw_text = extract_generated_text(response)

    qa_list = parse_qa_json(raw_text)
    return qa_list


def get_openrouter_completion(prompt: str) -> str:
    url = f"{OPENROUTER_API_BASE}/chat/completions"
    payload = {
        "model": GENERATION_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    response = openrouter_session.post(url, json=payload, timeout=60)
    response.raise_for_status()
    payload = response.json()

    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"Unexpected OpenRouter completion response: {payload}")

    first = choices[0]
    message = first.get("message") or {}
    content = message.get("content")
    if isinstance(content, dict):
        text = content.get("text") or content.get("message") or ""
    else:
        text = content or ""

    if not text:
        text = first.get("text", "")

    return str(text)


def extract_generated_text(response) -> str:
    text_parts = []

    if getattr(response, "candidates", None):
        for candidate in response.candidates:
            if candidate is None or candidate.content is None:
                continue
            if getattr(candidate.content, "parts", None):
                for part in candidate.content.parts:
                    if part is None:
                        continue
                    text_part = getattr(part, "text", None)
                    if text_part:
                        text_parts.append(text_part)

    if text_parts:
        return "".join(text_parts)

    return getattr(response, "text", "") or ""


def parse_qa_json(raw_text: str) -> list[dict[str, str]]:
    json_text = extract_json(raw_text)
    if not json_text:
        return [{"question": "Could not parse document output.", "answer": raw_text}]

    try:
        payload = json.loads(json_text)
        if isinstance(payload, dict) and "qa" in payload and isinstance(payload["qa"], list):
            result = []
            for item in payload["qa"]:
                if not isinstance(item, dict):
                    continue

                entry = {
                    "question": str(item.get("question", "")).strip(),
                    "answer": str(item.get("answer", "")).strip(),
                }
                if "section" in item:
                    entry["section"] = str(item.get("section", "")).strip()
                if "topic" in item:
                    entry["topic"] = str(item.get("topic", "")).strip()
                result.append(entry)
            return result
    except json.JSONDecodeError:
        pass

    return [{"question": "Could not parse document output.", "answer": raw_text}]


def extract_json(text: str) -> str | None:
    match = re.search(r"\{\s*\"qa\"[\s\S]*\}", text)
    return match.group(0) if match else None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
