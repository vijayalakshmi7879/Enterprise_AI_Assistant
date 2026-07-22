# app/rag/vectordb.py

import uuid
from typing import Any, Dict, List

from sentence_transformers import SentenceTransformer
import chromadb

from app.config import Config, VECTORDB_DIR, app_state, log_event, safe_public_error
from app.rag.pdf_utils import extract_pdf_pages


# Load embedding model
embedding_model = SentenceTransformer(f"sentence-transformers/{Config.EMBED_MODEL_NAME}")

# Persistent Chroma client storing vector DB on disk.
chroma_client = chromadb.PersistentClient(path=str(VECTORDB_DIR))
COLLECTION_NAME = "enterprise_docs"


def get_or_create_collection():
    return chroma_client.get_or_create_collection(name=COLLECTION_NAME)


# Global collection handle reused by retrieval functions.
collection = get_or_create_collection()


def reset_collection():
    """Delete and recreate the Chroma collection (used before re-ingesting KB)."""
    global collection
    try:
        chroma_client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        # Ignore errors when deleting; we'll recreate anyway.
        pass
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)


def chunk_text(
    text: str,
    chunk_size: int = Config.CHUNK_SIZE,
    chunk_overlap: int = Config.CHUNK_OVERLAP,
) -> List[str]:
    """Split long text into overlapping chunks for better retrieval."""
    chunks = []
    text = (text or "").strip()
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += max(1, chunk_size - chunk_overlap)

    return chunks


def create_document_chunks() -> List[Dict[str, Any]]:
    """Build chunk objects with metadata for all uploaded PDFs."""
    all_chunks = []

    for pdf in app_state["uploaded_files"]:
        file_path = pdf["filepath"]
        filename = pdf["filename"]

        page_items = extract_pdf_pages(file_path)

        for page in page_items:
            split_chunks = chunk_text(page["text"])

            for idx, chunk in enumerate(split_chunks, start=1):
                all_chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "text": chunk,
                        "metadata": {
                            "filename": filename,
                            "page_number": page["page_number"],
                            "chunk_index": idx,
                            "source": f"{filename} - page {page['page_number']}",
                        },
                    }
                )
    return all_chunks


def ingest_uploaded_pdfs_to_vectordb() -> str:
    """
    Ingest all uploaded PDFs into the Chroma vector DB with embeddings.
    Used when the user clicks 'Build Knowledge Base' in the UI.
    """
    global collection
    try:
        if not app_state["uploaded_files"]:
            return "No uploaded PDFs found. Please upload at least one PDF first."

        chunks = create_document_chunks()
        if not chunks:
            return "No extractable text chunks were created from the uploaded PDFs."

        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        ids = [c["id"] for c in chunks]

        # Encode all chunks with the sentence-transformers model.
        embeddings = embedding_model.encode(documents, show_progress_bar=True).tolist()

        # Reset and re-add the collection to ensure a clean KB.
        reset_collection()
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        app_state["knowledge_base_ready"] = True
        app_state["total_chunks"] = len(chunks)

        log_event(
            "knowledge_base_built",
            {"total_files": len(app_state["uploaded_files"]), "total_chunks": len(chunks)},
        )

        return f"Knowledge base built successfully. Total chunks indexed: {len(chunks)}"
    except Exception as e:
        app_state["knowledge_base_ready"] = False
        return safe_public_error(
            "Error while building the knowledge base.",
            "knowledge_base_error",
            e,
        )


def retrieve_relevant_chunks(query: str, top_k: int = Config.TOP_K_RETRIEVAL) -> List[Dict[str, Any]]:
    """
    Retrieve top-k document chunks relevant to the user query.
    Returns a list of dicts with 'text' and 'metadata'.
    """
    if not app_state.get("knowledge_base_ready"):
        return []

    query_embedding = embedding_model.encode([query]).tolist()[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    retrieved = []
    if results and results.get("documents"):
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        for doc, meta in zip(docs, metas):
            retrieved.append({"text": doc, "metadata": meta})

    return retrieved