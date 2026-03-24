from backend.services.llm_service import azure_llm
def classify_task(question):
    return azure_llm(f"""
    Classify intent into:
    QA, SUMMARIZE, NOTES, GENERATE_DOC

    Question: {question}
    Only return one word.
    """).strip()


def handle_qa(context, question):
    return azure_llm(f"""
    Answer only from context.

    Context:
    {context}

    Question:
    {question}
    """)


def handle_summary(context):
    return azure_llm(f"Summarize:\n{context}")


def handle_notes(context):
    return azure_llm(f"Create structured notes:\n{context}")


def handle_doc(context):
    return azure_llm(f"Create document:\n{context}")