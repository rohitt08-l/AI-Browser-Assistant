from fastapi import APIRouter
from backend.models.request_model import RequestData
from backend.services.rag_service import get_context
from backend.services.task_service import *
from backend.services.pdf_service import create_pdf

router = APIRouter()

@router.post("/ask")
def ask(data: RequestData):

    context = get_context(data.page_content, data.question)

    task = data.task_type.upper()

    if task == "AUTO":
        task = classify_task(data.question)

    if task == "QA":
        return {"answer": handle_qa(context, data.question)}

    elif task == "SUMMARIZE":
        return {"answer": handle_summary(context)}

    elif task == "NOTES":
        return {"answer": handle_notes(context)}

    elif task == "GENERATE_DOC":
        content = handle_doc(context)
        file_path = create_pdf(content)
        return {"answer": content, "file": file_path}

    return {"answer": "Invalid task"}