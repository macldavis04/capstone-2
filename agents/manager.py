# agents/manager.py
import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agents import qualitative, quantitative
from validation.validator import validate_qualitative, validate_quantitative
from tokenomics.logger import log
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def classify(query: str) -> str:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"""Classify this query as exactly one of: qualitative, quantitative, both.

qualitative = questions about policies, processes, procedures, explanations, documentation
quantitative = questions about numbers, metrics, trends, comparisons, SQL-queryable data
both = questions that need both document search and data analysis

Query: {query}

Reply with one word only: qualitative, quantitative, or both.""",
        config=types.GenerateContentConfig(
            max_output_tokens=150,
            thinking_config=types.ThinkingConfig(thinking_level="low"), #changed to low since minimal isn't supported for 3.8
        ),
    )
    route = (response.text or "").strip().lower().strip(".")
    usage = response.usage_metadata
    log(query, "manager-classifier", usage.prompt_token_count,
        (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
    return route if route in ["qualitative", "quantitative", "both"] else "qualitative"

HISTORY_FILE = "history.json"  # saves recent questions so follow-ups work after a restart
try:
    with open(HISTORY_FILE) as f:
        history = json.load(f)
except FileNotFoundError:
    history = []

def rewrite(query: str) -> str:
    if not history:
        return query
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"Previous questions: {history[-10:]}\n"
                 f"Rewrite this follow-up as a standalone question. Reply with only the question.\n"
                 f"Follow-up: {query}",
        config=types.GenerateContentConfig(
            max_output_tokens=512,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )
    usage = response.usage_metadata
    log(query, "manager-rewriter", usage.prompt_token_count,
        (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
    return (response.text or "").strip() or query

def run(query: str):
    print(f"\nQuery: {query}")
    query = rewrite(query)
    print(f"Rewritten: {query}")
    history.append(query)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-10:], f)
    route = classify(query)
    print(f"Route: {route}")

    qual_result = None
    quant_result = None

    if route in ["qualitative", "both"]:
        qual_result = qualitative.run(query)
        validation = validate_qualitative(qual_result["answer"], qual_result["chunks"])
        log(query, "qualitative", qual_result["input_tokens"], qual_result["output_tokens"])
        if validation["flag"]:
            print(f"\n⚠️  VALIDATION WARNING: {validation['warning']}")
        print(f"\n[Qualitative]\n{qual_result['answer']}")

    if route in ["quantitative", "both"]:
        quant_result = quantitative.run(query)
        validation = validate_quantitative(
            quant_result["answer"],
            quant_result["sql"],
            quant_result["validation"]
        )
        log(query, "quantitative", quant_result["input_tokens"], quant_result["output_tokens"])
        if validation["flag"]:
            print(f"\n⚠️  VALIDATION WARNING: {validation['warning']}")
        print(f"\n[Quantitative]\n{quant_result['answer']}")
        print(f"SQL used: {quant_result['sql']}")