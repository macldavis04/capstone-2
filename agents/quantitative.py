# agents/quantitative.py
import os
import sqlite3
from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-3.6-flash"

SCHEMA_CONTEXT = """
Available tables:
- sales(id, region, product, revenue, date, units_sold)
- customers(id, name, industry, churn_date, satisfaction_score)
- employees(id, department, satisfaction_score, tenure_years)
"""

def call_gemini(prompt: str, max_tokens: int, thinking_level: str):
    return client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
        ),
    )

def output_tokens(usage) -> int:
    return (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)

def validate_sql(query: str) -> dict:
    blocked = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    for word in blocked:
        if word in query.upper():
            return {"valid": False, "reason": f"Blocked keyword: {word}"}
    if not query.strip().upper().startswith("SELECT"):
        return {"valid": False, "reason": "Only SELECT queries are permitted"}
    return {"valid": True, "reason": "OK"}

def generate_sql(query: str) -> dict:
    response = call_gemini(
        f"{SCHEMA_CONTEXT}\n\nGenerate a SQL query for: {query}\n\nReturn ONLY the SQL query, nothing else.",
        max_tokens=256,
        thinking_level="minimal",
    )
    sql = (response.text or "").strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return {
        "sql": sql,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": output_tokens(response.usage_metadata)
    }

def run(query: str) -> dict:
    sql_result = generate_sql(query)
    sql = sql_result["sql"]
    validation = validate_sql(sql)

    if not validation["valid"]:
        return {
            "answer": f"Query blocked: {validation['reason']}",
            "sql": sql,
            "rows": [],
            "validation": "FAILED",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"]
        }

    try:
        conn = sqlite3.connect("./data/database.sqlite")
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        conn.close()

        interpretation = call_gemini(
            f"The user asked: {query}\n\nSQL query used: {sql}\n\nResults:\nColumns: {cols}\nData: {rows[:20]}\n\nProvide a clear, concise interpretation of these results.",
            max_tokens=1024,
            thinking_level="low",
        )

        return {
            "answer": interpretation.text or "",
            "sql": sql,
            "columns": cols,
            "rows": rows,
            "validation": "PASSED",
            "input_tokens": sql_result["input_tokens"] + interpretation.usage_metadata.prompt_token_count,
            "output_tokens": sql_result["output_tokens"] + output_tokens(interpretation.usage_metadata)
        }

    except Exception as e:
        return {
            "answer": f"Query execution failed: {str(e)}",
            "sql": sql,
            "rows": [],
            "validation": "ERROR",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"]
        }