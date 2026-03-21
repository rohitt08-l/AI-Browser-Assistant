from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

app = FastAPI()

embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

class RequestData(BaseModel):
    question: str
    page_content: str
    task_type: str = "auto"   # new field


# ---------------- LLM ----------------
def groq_llm(prompt):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,   # 🔥 reduces hallucination
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# ---------------- TASK CLASSIFIER ----------------
def classify_task(question):
    prompt = f"""
    Classify the user's intent into:
    QA, SUMMARIZE, NOTES, GENERATE_DOC

    Question: {question}

    Only return one word.
    """
    return groq_llm(prompt).strip()


# ---------------- TASK HANDLERS ----------------
def handle_qa(context, question):
    return groq_llm(f"""
    You are a strict AI assistant.

    RULES:
    1. Answer ONLY from the given context
    2. Do NOT use outside knowledge
    3. If answer is not in context, say:
    "I could not find this in the provided content"
    4. Be concise and accurate

    Context:
    {context}

    Question:
    {question}
    """)


def handle_summary(context):
    return groq_llm(f"""
    Summarize the following in simple points:

    {context}
    """)



def handle_notes(context):
    return groq_llm(f"""
    Create structured notes with headings, bullet points and key insights:

    {context}
    """)


def handle_doc(context):
    return groq_llm(f"""
    Create a professional document format with title, headings and paragraphs:

    {context}
    """)


# ---------------- PDF GENERATOR ----------------
def create_pdf(content):
    file_path = "output.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    story = []

    # Title
    story.append(Paragraph("Generated Document", styles['Title']))
    story.append(Spacer(1, 12))

    # Content (split into paragraphs)
    for line in content.split("\n"):
        story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 8))

    doc.build(story)

    return file_path


# ---------------- MAIN API ----------------
@app.post("/ask")
def ask(data: RequestData):

    # Split content
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50
    )
    chunks = splitter.split_text(data.page_content[:10000])

    # Vector DB
    vectorstore = FAISS.from_texts(chunks, embedding_model)

    docs_with_scores = vectorstore.similarity_search_with_score(data.question, k=5)

    filtered_docs = [doc for doc, score in docs_with_scores if score < 2.0]

    # 🔥 fallback if too strict
    if not filtered_docs:
        filtered_docs = [doc for doc, _ in docs_with_scores]

    context = "\n\n".join([doc.page_content for doc in filtered_docs])

    # Task selection
    task = data.task_type.upper()

    if task == "AUTO":
        task = classify_task(data.question)

    # Route tasks
    if task == "QA":
        answer = handle_qa(context, data.question)
        return {"answer": answer}

    elif task == "SUMMARIZE":
        answer = handle_summary(context)
        return {"answer": answer}

    elif task == "NOTES":
        answer = handle_notes(context)
        return {"answer": answer}

    elif task == "GENERATE_DOC":
        content = handle_doc(context)
        file_path = create_pdf(content)
        return {"answer": content, "file": file_path}

    else:
        return {"answer": "Task not recognized"}