import json
from typing import Any, Dict, List, Optional

import google.generativeai as genai

from app.config import Config, app_state, log_event, safe_public_error
from app.rag.vectordb import retrieve_relevant_chunks, ingest_uploaded_pdfs_to_vectordb
from app.rag.pdf_utils import get_file_summary, show_file_preview

if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)

def detect_working_gemini_model() -> Optional[str]:
    for model_name in Config.GEMINI_CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Reply with exactly: OK")
            text = getattr(response, "text", "") or ""
            if "OK" in text:
                return model_name
        except Exception as e:
            log_event("gemini_model_probe_failed", {"model_name": model_name, "error": str(e)})
            continue
    return None

app_state["working_gemini_model"] = detect_working_gemini_model()

def build_rag_prompt(user_query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    context_blocks = []
    for item in retrieved_chunks:
        meta = item["metadata"]
        block = (
            f"Source: {meta['filename']}, page {meta['page_number']}\n"
            f"Content: {item['text']}"
        )
        context_blocks.append(block)

    context_text = "\n\n".join(context_blocks)

    prompt = f"""
Use only the context below to answer the question.

If the answer is not available in the context, answer exactly:
I could not find a reliable answer in the uploaded documents.

Question:
{user_query}

Context:
{context_text}

Return valid JSON with this exact structure:
{{
  "answer": "short grounded answer",
  "citations": [
    {{"filename": "example.pdf", "page": 1}}
  ]
}}
""".strip()
    return prompt

def extract_first_json_object(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    decoder = json.JSONDecoder()
    start_positions = [i for i, ch in enumerate(text) if ch == "{"]

    for start in start_positions:
        try:
            obj, _ = decoder.raw_decode(text[start:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    raise ValueError("No valid JSON object found in model response.")

def generate_grounded_answer(user_query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    if not retrieved_chunks:
        return (
            "Agent: Knowledge Agent (RAG)\n\n"
            "I could not find a reliable answer in the uploaded documents."
        )

    model_name = app_state.get("working_gemini_model")
    if not model_name:
        top = retrieved_chunks[0]
        meta = top["metadata"]
        return (
            "Agent: Knowledge Agent (RAG)\n\n"
            "I could not generate a grounded summary right now.\n\n"
            f"Best matching source: {meta['filename']}, page {meta['page_number']}\n"
            f"Relevant excerpt:\n{top['text'][:700]}"
        )

    try:
        model = genai.GenerativeModel(model_name)
        prompt = build_rag_prompt(user_query, retrieved_chunks)
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        )

        raw_text = getattr(response, "text", "") or ""
        obj = extract_first_json_object(raw_text)

        answer = obj.get("answer", "").strip()
        citations = obj.get("citations", [])

        if not answer:
            answer = "I could not find a reliable answer in the uploaded documents."

        citation_lines = []
        for item in citations:
            filename = item.get("filename", "Unknown file")
            page = item.get("page", "Unknown page")
            citation_lines.append(f"- {filename}, page {page}")

        if not citation_lines:
            for item in retrieved_chunks[:2]:
                meta = item["metadata"]
                citation_lines.append(f"- {meta['filename']}, page {meta['page_number']}")

        return (
            "Agent: Knowledge Agent (RAG)\n\n"
            f"Answer:\n{answer}\n\n"
            "Citations:\n" + "\n".join(citation_lines)
        )

    except Exception as e:
        log_event("gemini_generation_error", {"error": str(e)})
        top = retrieved_chunks[0]
        meta = top["metadata"]
        return (
            "Agent: Knowledge Agent (RAG)\n\n"
            "I could not generate a grounded summary right now.\n\n"
            f"Best matching source: {meta['filename']}, page {meta['page_number']}\n"
            f"Relevant excerpt:\n{top['text'][:700]}"
        )

RAG_TOOLS = {
    "build_knowledge_base": ingest_uploaded_pdfs_to_vectordb,
    "retrieve_context": retrieve_relevant_chunks,
    "answer_from_context": generate_grounded_answer,
    "list_uploaded_pdfs": get_file_summary,
    "show_pdf_preview": show_file_preview,
}

def call_rag_tool(tool_name: str, **kwargs):
    if tool_name not in RAG_TOOLS:
        raise ValueError("Tool not allowed.")
    return RAG_TOOLS[tool_name](**kwargs)

def rag_function_call_router(user_query: str):
    tool_prompt = f"""
You are a RAG tool router.
Choose only one tool from:
- build_knowledge_base
- retrieve_context
- answer_from_context
- list_uploaded_pdfs
- show_pdf_preview

Return valid JSON:
{{"tool":"...", "arguments":{{...}}}}

User query:
{user_query}
""".strip()

    model_name = app_state.get("working_gemini_model")
    if not model_name:
        return "retrieve_context", {"query": user_query, "top_k": Config.TOP_K_RETRIEVAL}

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(tool_prompt, generation_config={"temperature": 0})
    raw = getattr(response, "text", "") or ""
    obj = extract_first_json_object(raw)
    return obj["tool"], obj.get("arguments", {})

def rag_agent_answer(user_query: str):
    try:
        tool_name, args = rag_function_call_router(user_query)
        result = call_rag_tool(tool_name, **args)

        if tool_name == "retrieve_context":
            return call_rag_tool(
                "answer_from_context",
                user_query=user_query,
                retrieved_chunks=result,
            )
        return str(result)
    except Exception as e:
        return safe_public_error(
            "RAG agent could not process your request right now.",
            "rag_function_call_error",
            e,
        )