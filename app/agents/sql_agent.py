# app/agents/sql_agent.py

import re
from typing import Tuple, Optional

import pandas as pd
from groq import Groq

from app.config import Config, log_event, safe_public_error
from app.db.postgres import get_db_connection

# ---------- DB schema and prompt ----------

DB_SCHEMA = """
Tables:

products(
    id SERIAL PRIMARY KEY,
    name TEXT,
    category TEXT,
    price NUMERIC
)

customers(
    id SERIAL PRIMARY KEY,
    name TEXT,
    city TEXT
)

sales(
    id SERIAL PRIMARY KEY,
    sale_date DATE,
    product_id INTEGER,
    customer_id INTEGER,
    quantity INTEGER,
    total_amount NUMERIC
)
""".strip()


def build_sql_agent_prompt(user_question: str) -> str:
    return f"""
You are a precise PostgreSQL SQL generator.

Database schema:
{DB_SCHEMA}

Rules:
- Return only SQL, no explanation.
- Use PostgreSQL syntax.
- Generate a single read-only query.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, PRAGMA, REPLACE, TRUNCATE.
- Prefer explicit columns when possible.
- When answering about highest revenue by product, join products and sales and aggregate SUM(total_amount).
- For month filtering, use PostgreSQL-compatible date logic (e.g., TO_CHAR(sale_date, 'MM')).

User question:
{user_question}
""".strip()

# ---------- Fallback SQL for common questions ----------

def fallback_sql_from_question(user_question: str) -> Optional[str]:
    q = user_question.lower().strip()

    # April sales (PostgreSQL date function)
    if (
        "sales of april" in q
        or "show sales of april" in q
        or "april sales" in q
        or "sales of april month" in q
    ):
        return """
SELECT s.id, s.sale_date, p.name AS product_name, c.name AS customer_name,
       s.quantity, s.total_amount
FROM sales s
JOIN products p ON s.product_id = p.id
JOIN customers c ON s.customer_id = c.id
WHERE TO_CHAR(s.sale_date, 'MM') = '04'
ORDER BY s.sale_date;
""".strip()

    # Highest revenue product
    if (
        "highest revenue" in q
        or "generated the highest revenue" in q
        or "top revenue product" in q
        or "which product generated" in q
        or "which product has the highest revenue" in q
    ):
        return """
SELECT p.name AS product_name, SUM(s.total_amount) AS total_revenue
FROM sales s
JOIN products p ON s.product_id = p.id
GROUP BY p.name
ORDER BY total_revenue DESC
LIMIT 1;
""".strip()

    # Sales by product
    if "sales by product" in q or "total sales by product" in q:
        return """
SELECT p.name AS product_name, SUM(s.total_amount) AS total_sales
FROM sales s
JOIN products p ON s.product_id = p.id
GROUP BY p.name
ORDER BY total_sales DESC;
""".strip()

    # Sales by month (PostgreSQL date function)
    if "sales by month" in q or "monthly sales" in q:
        return """
SELECT TO_CHAR(sale_date, 'YYYY-MM') AS month, SUM(total_amount) AS total_sales
FROM sales
GROUP BY TO_CHAR(sale_date, 'YYYY-MM')
ORDER BY month;
""".strip()

    # Total revenue
    if "total revenue" in q:
        return """
SELECT SUM(total_amount) AS total_revenue
FROM sales;
""".strip()

    return None

# ---------- Groq client ----------

groq_client = None
if Config.GROQ_API_KEY:
    groq_client = Groq(api_key=Config.GROQ_API_KEY)

# ---------- Helpers: clean SQL + validate ----------

def clean_sql_output(sql: str) -> str:
    sql = (sql or "").strip()
    if sql.startswith("```sql"):
        sql = sql.replace("```sql", "", 1).strip()
    if sql.startswith("```"):
        sql = sql.replace("```", "", 1).strip()
    if sql.endswith("```"):
        sql = sql[:-3].strip()
    return sql

def validate_safe_sql(sql: str) -> None:
    if not sql or not isinstance(sql, str):
        raise ValueError("SQL is empty.")

    normalized = " ".join(sql.strip().split())
    upper_sql = normalized.upper()

    forbidden_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "ATTACH",
        "DETACH",
        "PRAGMA",
        "REPLACE",
        "TRUNCATE",
    ]

    for keyword in forbidden_keywords:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise ValueError(f"Unsafe SQL detected: {keyword}")

    if ";" in normalized[:-1]:
        raise ValueError("Multiple SQL statements are not allowed.")

    allowed_starts = ("SELECT", "WITH")
    if not upper_sql.startswith(allowed_starts):
        raise ValueError("Only read-only SELECT/WITH queries are allowed.")

# ---------- Run SQL on PostgreSQL ----------

def run_sql_query(sql: str) -> pd.DataFrame:
    validate_safe_sql(sql)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

        df = pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()

    if len(df) > Config.MAX_SQL_ROWS:
        df = df.head(Config.MAX_SQL_ROWS)

    return df

# ---------- LLM SQL generation ----------

def generate_sql_from_question(user_question: str) -> Tuple[str, str]:
    """
    Returns (sql, mode) where mode is 'groq' or 'fallback'.
    """
    fallback_sql = fallback_sql_from_question(user_question)
    prompt = build_sql_agent_prompt(user_question)

    if groq_client is None:
        if fallback_sql:
            return fallback_sql, "fallback"
        raise RuntimeError("Groq client is not configured.")

    try:
        completion = groq_client.chat.completions.create(
            model=Config.SQL_MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a precise SQL generator."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        sql = clean_sql_output(completion.choices[0].message.content)
        return sql, "groq"
    except Exception as e:
        print("SQL generation error:", repr(e))
        log_event("sql_generation_error", {"error": str(e)})
        if fallback_sql:
            return fallback_sql, "fallback"
        raise RuntimeError("SQL generation failed and no fallback rule matched.")

# ---------- Explanation helper ----------

def explain_sql_result(user_question: str, sql: str, df: pd.DataFrame, mode: str = "groq") -> str:
    if df is None or df.empty:
        return "The query returned no rows for this question."

    q = (user_question or "").lower().strip()

    # Special-case for April sales summary.
    if "april" in q and "sale" in q:
        total_amount = float(df["total_amount"].sum()) if "total_amount" in df.columns else 0
        total_qty = int(df["quantity"].sum()) if "quantity" in df.columns else 0
        return (
            f"April 2025 sales include {len(df)} transactions. "
            f"The total quantity sold was {total_qty}, and the total revenue was {total_amount:.0f}."
        )

    # If result is a single row with product_name and some revenue column,
    # always explain it as the highest revenue product.
    if len(df) == 1 and "product_name" in df.columns:
        product_name = df.iloc[0]["product_name"]
        # Try to find a revenue column name.
        revenue_col = None
        for col in df.columns:
            if "revenue" in col.lower() or "amount" in col.lower() or "total" in col.lower():
                revenue_col = col
                break
        if revenue_col is not None:
            revenue_value = df.iloc[0][revenue_col]
            return (
                f"The product that generated the highest revenue is {product_name}, "
                f"with a total revenue of {revenue_value}."
            )
        else:
            return f"The product that generated the highest revenue is {product_name}."

    # Total revenue explanation for single-value query.
    if "total revenue" in q and len(df) == 1 and len(df.columns) == 1:
        value = df.iloc[0, 0]
        return f"The total revenue is {value}."

    # Generic explanation for single-value result.
    if len(df) == 1 and len(df.columns) == 1:
        col_name = df.columns[0]
        value = df.iloc[0, 0]
        return f"The result for {col_name} is {value}."

    # Generic explanation for small two-column tables.
    if len(df) == 1 and len(df.columns) >= 2:
        v1 = df.iloc[0, 0]
        v2 = df.iloc[0, 1]
        second_col = df.columns[1]
        return f"The result shows {v1} with a value of {v2} for {second_col}."

    # Fallback explanation for arbitrary tables.
    return f"The query returned {len(df)} rows with {len(df.columns)} columns matching your question."

# ---------- Public SQL Agent entry ----------

def sql_agent_answer(user_question: str):
    """
    Main entry point used by the Manager agent.
    Returns (response_text, dataframe).
    """
    try:
        sql, mode = generate_sql_from_question(user_question)
        df = run_sql_query(sql)

        # Debug prints (optional)
        print("DEBUG rows:", len(df), "columns:", df.columns.tolist())
        print(df)

        try:
            explanation = explain_sql_result(user_question, sql, df, mode=mode)
        except Exception as e:
            log_event("sql_explanation_error", {"error": str(e)})
            explanation = "No detailed explanation was generated, but the result data is shown below."

        table_text = df.to_markdown(index=False) if not df.empty else "No rows returned."

        response = (
            "Agent: SQL Agent (Text-to-SQL)\n\n"
            f"Mode: {mode}\n\n"
            f"SQL Query:\n\n{sql}\n\n"
            f"Result Table:\n\n{table_text}\n\n"
            f"Explanation:\n\n{explanation}"
        )

        log_event(
            "sql_query_success",
            {"user_question": user_question, "mode": mode, "row_count": len(df)},
        )

        return response, df
    except Exception as e:
        message = safe_public_error(
            "SQL Agent could not process your question right now.",
            "sql_agent_error",
            e,
            {"user_question": user_question},
        )
        return f"Agent: SQL Agent (Text-to-SQL)\n\n{message}", pd.DataFrame()