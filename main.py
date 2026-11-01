import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel, Field, field_validator

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
REQUIRED_KEYS = ("GROQ_API_KEY", "TAVILY_API_KEY")
MAX_ACTIVE_JOBS = 1
MAX_RETAINED_JOBS = 50


@dataclass
class ResearchJob:
    id: str
    topic: str
    max_analysts: int
    status: str = "starting"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    analysts: list[dict[str, Any]] = field(default_factory=list)
    report: str | None = None
    error: str | None = None


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    max_analysts: int = Field(default=2, ge=1, le=3, strict=True)

    @field_validator("topic", mode="before")
    @classmethod
    def normalize_topic(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class FeedbackRequest(BaseModel):
    approved: bool
    feedback: str | None = Field(default=None, max_length=500)

    @field_validator("feedback", mode="before")
    @classmethod
    def normalize_feedback(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


app = FastAPI(
    title="DataHelix Research Studio",
    description="A dark, demo-ready interface for the multi-agent research workflow.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=ROOT / "src" / "ui"), name="static")

_jobs: dict[str, ResearchJob] = {}
_jobs_lock = threading.Lock()
_research_graph: Any = None
_graph_lock = threading.Lock()


def _get_graph() -> Any:
    global _research_graph
    if _research_graph is None:
        with _graph_lock:
            if _research_graph is None:
                from src.agent.deep_agent import graph

                _research_graph = graph
    return _research_graph


def _job_response(job: ResearchJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "topic": job.topic,
        "status": job.status,
        "created_at": job.created_at,
        "analysts": job.analysts,
        "report": job.report,
        "error": job.error,
    }


def _update_job(job_id: str, **updates: Any) -> ResearchJob | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None:
            for name, value in updates.items():
                setattr(job, name, value)
        return job


def _failure_message(error: Exception, stage: str) -> str:
    status_code = getattr(error, "status_code", None)
    message = str(error).casefold()
    error_type = type(error).__name__.casefold()

    if status_code == 401:
        return "A research provider rejected its API key. Check the server credentials."
    if status_code == 404 and (
        "model_not_found" in message or "model" in error_type
    ):
        return (
            "The configured Groq model was not found. Check the model ID in "
            "src/agent/utils/llm.py."
        )
    if status_code == 429:
        return "A provider rate limit was reached. Wait a little and try again."
    if "timeout" in error_type or isinstance(error, TimeoutError):
        return "A research provider timed out. Please try again."
    return f"{stage} failed. Check provider setup and server logs."


def _save_approval_state(job: ResearchJob, graph: Any, config: dict[str, Any]) -> None:
    snapshot = graph.get_state(config)
    analysts = snapshot.values.get("analysts", [])
    interrupts = [
        interrupt
        for task in snapshot.tasks
        for interrupt in task.interrupts
    ]

    if interrupts:
        _update_job(
            job.id,
            status="awaiting_approval",
            analysts=[
                analyst.model_dump() if hasattr(analyst, "model_dump") else analyst
                for analyst in analysts
            ],
        )
        return

    report = snapshot.values.get("final_report")
    if report:
        _update_job(job.id, status="completed", report=report)
        return

    raise RuntimeError(
        "The research workflow stopped without an approval prompt or report."
    )


def _run_research(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return

    try:
        _update_job(job_id, status="generating_analysts")
        graph = _get_graph()
        config = {"configurable": {"thread_id": job.id}}
        graph.invoke(
            {
                "topic": job.topic,
                "max_analysts": job.max_analysts,
                "sections": [],
            },
            config,
        )
        _save_approval_state(job, graph, config)
    except Exception as error:
        logger.exception("Research job %s failed while generating analysts", job_id)
        _update_job(
            job_id,
            status="failed",
            error=_failure_message(error, "Analyst generation"),
        )


def _resume_research(job_id: str, response: str) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return

    try:
        graph = _get_graph()
        config = {"configurable": {"thread_id": job.id}}
        graph.invoke(Command(resume=response), config)
        _save_approval_state(job, graph, config)
    except Exception as error:
        logger.exception(
            "Research job %s failed while running the research workflow", job_id
        )
        _update_job(
            job_id,
            status="failed",
            error=_failure_message(error, "Research"),
        )


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(ROOT / "src" / "ui" / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    configured = {
        key: bool(os.getenv(key, "").strip()) for key in REQUIRED_KEYS
    }
    return {
        "status": "ok",
        "ready": all(configured.values()),
        "services": configured,
    }


@app.post("/api/research", status_code=202)
def start_research(
    payload: ResearchRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    missing_keys = [key for key in REQUIRED_KEYS if not os.getenv(key, "").strip()]
    if missing_keys:
        raise HTTPException(
            status_code=503,
            detail=(
                "Research is unavailable until these server settings are configured: "
                f"{', '.join(missing_keys)}."
            ),
        )

    with _jobs_lock:
        active_jobs = sum(
            job.status
            in {
                "starting",
                "generating_analysts",
                "awaiting_approval",
                "researching",
            }
            for job in _jobs.values()
        )
        if active_jobs >= MAX_ACTIVE_JOBS:
            raise HTTPException(
                status_code=429,
                detail=(
                    "The demo is at capacity. Please wait for an active research "
                    "run to finish."
                ),
            )

        if len(_jobs) >= MAX_RETAINED_JOBS:
            for old_id, old_job in list(_jobs.items()):
                if old_job.status in {"completed", "failed"}:
                    del _jobs[old_id]
                    if len(_jobs) < MAX_RETAINED_JOBS:
                        break
        if len(_jobs) >= MAX_RETAINED_JOBS:
            raise HTTPException(
                status_code=429,
                detail=(
                    "The demo has reached its temporary job-history limit. "
                    "Please try again later."
                ),
            )

        job = ResearchJob(
            id=str(uuid.uuid4()),
            topic=payload.topic,
            max_analysts=payload.max_analysts,
        )
        _jobs[job.id] = job

    background_tasks.add_task(_run_research, job.id)
    return {"id": job.id, "status": job.status}


@app.get("/api/research/{job_id}")
def get_research(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research run not found.")
        return _job_response(job)


@app.post("/api/research/{job_id}/approval", status_code=202)
def submit_approval(
    job_id: str,
    payload: FeedbackRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Research run not found.")
        if job.status != "awaiting_approval":
            raise HTTPException(
                status_code=409,
                detail="This research run is not waiting for analyst approval.",
            )
        if not payload.approved and not payload.feedback:
            raise HTTPException(
                status_code=422,
                detail="Add feedback before requesting revised analysts.",
            )
        response = "perfect" if payload.approved else payload.feedback
        job.status = "researching" if payload.approved else "generating_analysts"

    background_tasks.add_task(_resume_research, job.id, response)
    return {"id": job.id, "status": job.status}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )