# main.py
from agents.manager import run

def main():
    print("Enterprise RAG System")
    print("Type 'exit' to quit.\n")
    while True:
        query = input("Ask a question: ").strip()
        if query.lower() in ["exit", "quit"]:
            break
        if not query:
            continue
        try:
            run(query)
        except Exception as e:
            print(f"\nError: {e}\nTry again in a moment.\n") #Added a protection layer incase Google keeps giving 503

if __name__ == "__main__":
    main()