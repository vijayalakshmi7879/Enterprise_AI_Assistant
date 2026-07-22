from app.rag.rag_agent import rag_agent_answer
from app.agents.sql_agent import sql_agent_answer
from app.config import safe_user_message, app_state, log_event

def manager_agent_route(user_question: str) -> str:
    q = (user_question or "").lower().strip()

    sql_keywords = [
        "sales", "revenue", "product", "highest", "database", "total", "amount",
        "customer", "customers", "month", "monthly", "april", "may", "june",
        "show", "list", "count", "sum", "average", "top",
    ]

    rag_keywords = [
        "policy", "leave", "casual leave", "employee", "employees", "hr",
        "safety", "document", "pdf", "handbook", "guideline", "rules",
    ]

    if any(word in q for word in sql_keywords):
        return "SQL_AGENT"

    if any(word in q for word in rag_keywords):
        return "RAG_AGENT"

    return "RAG_AGENT"

def unified_chat_response(message, history):
    from app.rag.pdf_utils import get_file_summary
    from app.config import app_state

    if history is None:
        history = []

    user_message = safe_user_message(message)
    if not user_message:
        return history, ""

    try:
        log_event("chat_message", {"user_message": user_message})

        route = manager_agent_route(user_message)

        if route == "SQL_AGENT":
            assistant_response, _ = sql_agent_answer(user_message)
        else:
            if not app_state["uploaded_files"]:
                assistant_response = (
                    "Agent: Knowledge Agent (RAG)\n\n"
                    "No PDFs are uploaded yet. Please upload at least one PDF first."
                )
            elif not app_state.get("knowledge_base_ready"):
                assistant_response = (
                    "Agent: Knowledge Agent (RAG)\n\n"
                    "PDFs are uploaded, but the knowledge base is not built yet.\n"
                    "Please click the 'Build Knowledge Base' button first."
                )
            else:
                assistant_response = rag_agent_answer(user_message)

        assistant_response = str(assistant_response)

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_response})
        app_state["chat_history"] = history

        return history, ""
    except Exception as e:
        log_event("unified_chat_error", {"user_message": user_message, "error": str(e)})
        history.append(
            {
                "role": "assistant",
                "content": "Something went wrong while handling your question. Please try again.",
            }
        )
        return history, ""