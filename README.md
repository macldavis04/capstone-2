# Unit 2 Capstone: Enterprise RAG System
### Maclaren Davis

A multi-agent system that answers questions about Meridian Technologies' policies (RAG over ChromaDB) and business data (NL to SQL over SQLite), with validation and token cost logging on every response. Uses Gemini 3.5 Flash-Lite.

## Setup
- python -m venv venv
- source venv/bin/activate
- pip install -r requirements.txt
- echo "GEMINI_API_KEY=your-key" > .env
- python ingest.py
- python main.py

data/database.sqlite is included. create_db.py rebuilds it with fixed seed data if needed.

## Architecture
```text
User query (main.py CLI)
        │
        ▼
Manager (agents/manager.py)
  • rewrite follow-up using history.json
  • classify: qualitative / quantitative / both
        │                         │
        ▼                         ▼
Qualitative agent           Quantitative agent
  • ChromaDB top_k=3          • Gemini NL → SQL
  • Gemini cited answer       • validate_sql (SELECT only)
                              • SQLite → Gemini summary
        │                         │
        └───────────┬─────────────┘
                    ▼
     Validation layer (validation/validator.py)
                    ▼
     Tokenomics logger → tokenomics_log.jsonl
                    ▼
            Response to user
```

- agents/manager.py classifies each question as qualitative, quantitative, or both, and routes it.
- agents/manager.py saves the last 10 questions to history.json and rewrites follow-ups into standalone questions before routing, so context carries across sessions.
- agents/qualitative.py retrieves the top 3 chunks from ChromaDB and answers with source citations.
- agents/quantitative.py generates SQL, blocks anything that isn't a SELECT, runs it, and summarizes the results.
- validation/validator.py checks citations on qualitative answers and SQL status on quantitative ones.
- tokenomics/logger.py logs input tokens, output tokens, and cost for every model call to tokenomics_log.jsonl.

## Model
- Started on Gemini 3.6 Flash, then tried 3.8 Flash, which rejects the "minimal" thinking level, so all calls moved to "low".
- Both 3.6 and 3.8 Flash returned 503 "high demand" errors for several hours, so the final version uses Gemini 3.5 Flash-Lite, which passed every test query.

## Trust-but-Verify
- **"What were our Q4 sales for the North region?"** Gemini wrote EXTRACT(QUARTER FROM date) = 4 with region = 'north', and the validation layer flagged it as SQL validation status: ERROR because SQLite has no EXTRACT function. I accepted the flag and updated the schema prompt to name SQLite, show the strftime quarter pattern, and list the exact capitalized region values.
- **"Explain the code review process"** Gemini returned a well-cited answer that stopped mid-word at "Privacy/Security/", and the validation layer did not flag it because sources were cited. The log showed 1,020 of 1,024 output tokens used, since thinking counts toward the cap, so I raised the limit to 2,048 and the rerun was complete.
- **"Delete all customers who churned"** Gemini generated DELETE FROM customers WHERE churn_date IS NOT NULL;, and the validation layer blocked it with Blocked keyword: DELETE before it reached the database. I accepted this unchanged, because the model will write any SQL it is asked for, so validate_sql has to be the safeguard.
- **Output I did not immediately trust.** After the dialect fix, the Q4 North query ran cleanly but filtered on 2023, returned NULL, and Gemini blamed "missing data," while the validation layer flagged nothing. I knew from building the database that the answer was $400,593.08, so I added the data's 2025 date range and a worked example to the schema prompt, and the rerun returned the correct figure.

## Tokenomics
- Prices: $0.10 per 1M input tokens and $0.40 per 1M output tokens. Gemini bills thinking tokens as output.
- Average cost per query: about $0.0004, or about $0.39 per 1,000 queries.
- Qualitative queries cost about 8 times more than quantitative ones ($0.0008 vs. $0.0001), because the 3 retrieved chunks add about 2,500 input tokens per call.
- Blocked write attempts are the cheapest queries, because validate_sql stops them.

## Tokenomics Optimization
- I found that at top_k=5, qualitative answers only ever cited Sources 1 to 3 across every test run. Sources 4 and 5 added about 1,000 input tokens per call that the model never used.
- Reduced top_k from 5 to 3 in agents/qualitative.py.
- As a result the average qualitative input dropped by about 40%. "Explain the code review process" went from 2,716 to 1,418 tokens, and "How do we handle customer complaints?" went from 2,755 to 1,823.
- When I checked both answers kept every key policy detail, including the 400-line PR limit, the 1 and 2 approval rules, the 30-minute complaint logging requirement, and all five handling steps. The top_k=3 complaints answer also included the $100 goodwill rule, which the top_k=5 answer had left out.

## Known Limitations
- Validation checks that SQL ran and a source was cited, not that the answer is right (see Trust-but-Verify).
- "Both" questions print two separate answers instead of one combined answer.
- validate_sql uses substring matching, so a column like last_updated would be falsely blocked.
- The database connection is not read-only, so validate_sql is the only barrier to writes.