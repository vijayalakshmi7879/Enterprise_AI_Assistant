# Enterprise AI Assistant (Unified Agents)

This project is a modular, production-style Python application that combines multiple AI agents into a single unified assistant:

- **Knowledge Agent (RAG)** for HR policy / PDF questions
- **SQL Agent (Text-to-SQL)** for business data questions
- **Manager Agent** to route user queries to the right specialist
- **Gradio UI** as a simple, user-friendly web interface

It is designed to run entirely inside **GitHub Codespaces**, using a Python virtual environment, environment variables for secrets, and best practices for code organization.

---

## Features

- **Multi-agent architecture**
  - Manager Agent automatically routes questions to either the SQL Agent or the RAG Agent based on keywords.
- **Knowledge Agent (RAG)**
  - Upload HR policy PDFs.
  - Build a Chroma-based vector knowledge base.
  - Ask questions like _“How many casual leaves can an employee take?”_ with grounded answers and citations.
- **SQL Agent (Text-to-SQL)**
  - Uses a sample business SQLite database with `products`, `customers`, and `sales` tables.
  - Generates SQL (via Groq, with safe fallbacks) for questions like _“Show me the sales of April”_ or _“Which product generated the highest revenue?”_.
  - Enforces **read-only, safe SQL** (no DDL/DML).
- **Unified Gradio UI**
  - Single chat panel for all questions.
  - Right panel for PDF upload, knowledge base building, and file previews.

---

## Tech Stack

- **Python 3.11+**
- **Gradio** – Web UI
- **SQLite** – Sample business database
- **ChromaDB** – Vector store for RAG
- **sentence-transformers** – Document embeddings
- **Google Gemini** (`google-generativeai`) – RAG answer generation and tool routing
- **Groq** (`groq`) – Text-to-SQL generation (optional; falls back to hand-written SQL)

---

## Project Structure

```text
enterprise-ai-assistant-new/
├─ app/
│  ├─ __init__.py
│  ├─ config.py              # Paths, Config class, logging, app_state
│  ├─ db/
│  │  ├─ __init__.py
│  │  └─ sqlite_db.py       # SQLite schema + seed data (products/customers/sales)
│  ├─ agents/
│  │  ├─ __init__.py
│  │  ├─ manager.py         # Manager Agent routing logic + unified chat handler
│  │  └─ sql_agent.py       # SQL Agent: Groq + fallbacks + safe execution + explanations
│  ├─ rag/
│  │  ├─ __init__.py
│  │  ├─ pdf_utils.py       # PDF upload, preview, file summary
│  │  ├─ vectordb.py        # Embedding model, Chroma collection, chunking, ingestion, retrieval
│  │  └─ rag_agent.py       # RAG Agent: Gemini-based grounded answers + tool router
│  └─ ui/
│     ├─ __init__.py
│     └─ gradio_app.py      # Gradio Blocks UI (chat + PDF controls)
├─ main.py                  # Entry point to initialize DB and launch UI
├─ requirements.txt
├─ .gitignore
├─ .env                     # Local secrets (ignored by Git)
└─ README.md
```

---

## Setup (GitHub Codespaces)

1. **Open Codespace**
   - From the GitHub repo, click **Code → Codespaces → Create codespace on main**.

2. **Create and activate virtual environment**

   In the Codespaces terminal:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure secrets in `.env`**

   At the repo root, create/edit `.env`:

   ```text
   GOOGLE_API_KEY=your_real_gemini_key_here
   GROQ_API_KEY=your_real_groq_key_here
   ```

   Notes:
   - `.env` is **ignored** by `.gitignore` → keys are not committed.
   - `app/config.py` uses `python-dotenv` to load these into `Config`.

5. **Run the app**

   ```bash
   python main.py
   ```

   Codespaces will expose the Gradio app on a forwarded port (e.g. 7860). Click the port in the **Ports** panel to open the UI.

---

## How to Use

1. **Upload HR policy PDFs**
   - Use the “Upload PDF” component on the right.
   - After upload, click **“Build Knowledge Base”** to ingest and index the documents.

2. **Ask HR / policy questions (RAG)**
   - Examples:
     - `How many casual leaves can an employee take?`
     - `How many sick leaves can an employee take?`
   - The Knowledge Agent:
     - Retrieves relevant chunks from Chroma.
     - Uses Gemini to generate a grounded answer.
     - Returns citations (filename + page).

3. **Ask data / sales questions (SQL Agent)**
   - Examples:
     - `Show me the sales of April`
     - `Which product generated the highest revenue?`
     - `What is the total revenue?`
   - The SQL Agent:
     - Generates SQL via Groq, with safe fallback queries for common questions.
     - Validates SQL as read-only (no `INSERT`, `UPDATE`, `DELETE`, etc.).
     - Executes against the SQLite DB.
     - Returns:
       - SQL query
       - Markdown result table
       - Human-readable explanation (e.g. highest revenue product, April summary).

4. **Unified chat flow**
   - The Manager Agent inspects each user message and routes it:
     - To **SQL Agent** if it detects sales/database keywords.
     - To **RAG Agent** if it detects HR/policy/document keywords.
   - The chat history is maintained in `app_state["chat_history"]`.

---

## Security and Best Practices

- **Secrets**:
  - API keys are stored only in `.env` and read via environment variables.
  - `.env` is excluded from version control via `.gitignore` and should not be committed.
- **SQL safety**:
  - `validate_safe_sql` enforces:
    - Single statement only.
    - Only `SELECT` or `WITH` queries.
    - No mutating or DDL operations.
- **File handling**:
  - PDF filenames are sanitized to prevent path traversal.
  - Uploaded PDFs, logs, and vector DB directories are created under the project root.

---

## Next Steps

Planned improvements for this project:

- Migrate the business database from **SQLite** to **PostgreSQL** using a dedicated `app/db/postgres.py` module and updating `sql_agent.py` accordingly.
- Add more explanation templates for different analytics questions (e.g., monthly breakdowns, top customers).
- Enhance the UI styling, including dark mode and better layout for multi-agent responses.

---

## Running Locally (Optional)

If you want to run the project outside Codespaces:

1. Clone the repo.
2. Create and activate a virtual env (`python -m venv .venv`).
3. Install requirements (`pip install -r requirements.txt`).
4. Set `GOOGLE_API_KEY` and `GROQ_API_KEY` in `.env`.
5. Run `python main.py` and open the printed local URL.