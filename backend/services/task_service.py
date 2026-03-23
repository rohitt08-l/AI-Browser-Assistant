from backend.services.llm_service import groq_llm

def classify_task(question):
    return groq_llm(f"""
    Classify intent into:
    QA, SUMMARIZE, NOTES, GENERATE_DOC

    Question: {question}
    Only return one word.
    """).strip()


def handle_qa(context, question):
    return groq_llm(f"""
    Answer only from context.

    Context:
    {context}

    Question:
    {question}
    """)


def handle_summary(context):
    return groq_llm(f"Summarize:\n{context}")


def handle_notes(context):
    return groq_llm(f"Create structured notes:\n{context}")


def handle_doc(context):
    return groq_llm(f"Create document:\n{context}")