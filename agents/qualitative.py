# agents/qualitative.py
import os
import chromadb
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = SentenceTransformer("all-MiniLM-L6-v2")

def retrieve(query: str, top_k: int = 3) -> list[dict]: #changed from 5 to 3 to save on tokens for optimisation
    chroma = chromadb.PersistentClient(path="./data/chroma")
    collection = chroma.get_collection("enterprise-docs")
    embedding = model.encode([query]).tolist()
    results = collection.query(query_embeddings=embedding, n_results=top_k)
    return [
        {
            "content": doc,
            "source": meta["source"],
            "chunk": meta["chunk"]
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]

def build_prompt(query: str, chunks: list[dict]) -> str:
    context = ""
    for i, chunk in enumerate(chunks):
        context += f"[Source {i+1}: {chunk['source']}]\n{chunk['content']}\n\n"

    return f"""You are a helpful enterprise documentation assistant.
Answer the question using ONLY the context provided below.
If the answer is not in the context, say "I cannot find this information in the provided documents."
Always cite the source number(s) you used.

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""

def run(query: str) -> dict:
    chunks = retrieve(query)
    prompt = build_prompt(query, chunks)
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=2048, #Kept getting cut off at 1024
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )
    usage = response.usage_metadata
    return {
        "answer": response.text or "",
        "chunks": chunks,
        "input_tokens": usage.prompt_token_count,
        "output_tokens": (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    }