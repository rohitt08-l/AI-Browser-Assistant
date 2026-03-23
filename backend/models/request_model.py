from pydantic import BaseModel

class RequestData(BaseModel):
    question: str
    page_content: str
    task_type: str = "auto"