import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel

from openarchitect.core.schemas import ArchitectureReviewRequest, WorkflowResult
from openarchitect.modules.ingestion import extract_text_from_upload
from openarchitect.storage import InMemoryWorkflowStore
from openarchitect.workflow import run_review_workflow

load_dotenv()

app = FastAPI(title="OpenArchitect", version="0.1.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "OPENARCHITECT_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
store = InMemoryWorkflowStore()
ENGINE_VERSION = "evidence-bound-graph-v3"


class WorkflowRunResponse(BaseModel):
    run_id: str
    result: WorkflowResult


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": ENGINE_VERSION}


@app.post("/workflows/architecture-review", response_model=WorkflowRunResponse)
async def create_architecture_review(
    request: ArchitectureReviewRequest,
) -> WorkflowRunResponse:
    try:
        result = await run_review_workflow(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    run_id = store.save(result)
    return WorkflowRunResponse(run_id=run_id, result=result)


@app.post("/workflows/architecture-review/upload", response_model=WorkflowRunResponse)
async def upload_architecture_review(
    file: UploadFile = File(...),
) -> WorkflowRunResponse:
    content = await file.read()
    try:
        document_text = extract_text_from_upload(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = await run_review_workflow(ArchitectureReviewRequest(document_text=document_text))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    run_id = store.save(result)
    return WorkflowRunResponse(run_id=run_id, result=result)


@app.get("/workflows/{run_id}", response_model=WorkflowResult)
def get_workflow(run_id: str) -> WorkflowResult:
    result = store.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return result
