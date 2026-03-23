from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from backend.core.embeddings import embedding_model

def get_context(text, question):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50
    )

    chunks = splitter.split_text(text[:10000])

    vectorstore = FAISS.from_texts(chunks, embedding_model)

    docs = vectorstore.similarity_search_with_score(question, k=5)

    filtered = [doc for doc, score in docs if score < 2.0]

    if not filtered:
        filtered = [doc for doc, _ in docs]

    return "\n\n".join([doc.page_content for doc in filtered])