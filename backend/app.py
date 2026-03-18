from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import os
from dotenv import load_dotenv
load_dotenv()
api_key= os.getenv("GROQ_API_KEY")
print(f"API Key: {api_key}")
# if not api_key:
#     raise ValueError("GROQ_API_KEY not found")

client = Groq(api_key=api_key)
app = FastAPI()


embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

class RequestData(BaseModel):
    question: str
    page_content: str


def groq_llm(prompt):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


@app.post("/ask")
def ask(data: RequestData):

    # Split content
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )
    chunks = splitter.split_text(data.page_content[:10000])  # limit for speed

    # Create vector DB
    vectorstore = FAISS.from_texts(chunks, embedding_model)

    # Retrieve relevant docs
    docs = vectorstore.similarity_search(data.question, k=3)
    context = "\n\n".join([doc.page_content for doc in docs])

    prompt = f"""
    Answer based only on the context below.

    Context:
    {context}

    Question:
    {data.question}
    """

    answer = groq_llm(prompt)

    return {"answer": answer}