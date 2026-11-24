"""Download endpoint for generated documents."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter(tags=["files"])


@router.get("/files/{file_id}", name="download_file")
async def download_file(file_id: str, request: Request) -> FileResponse:
    path = request.app.state.files.path(file_id)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found or expired")
    return FileResponse(path, media_type="application/pdf", filename="ai-assistant-document.pdf")
