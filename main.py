"""
Task API — a small in-memory CRUD API built with FastAPI.

Run with:
    uvicorn main:app --reload --port 8000

Then visit:
    http://localhost:8000/         -> API info
    http://localhost:8000/docs     -> Swagger UI (interactive docs)
"""

from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A tiny in-memory to-do list API — CRUD practice project.",
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Renders errors as {"error": "..."} instead of FastAPI's default {"detail": "..."}."""
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    A malformed/missing request body (e.g. POST /tasks with no "title") is a
    client mistake, so this maps FastAPI's default 422 down to the 400 the
    assignment spec asks for, in the same {"error": "..."} shape.
    """
    first = exc.errors()[0]
    field = first["loc"][-1] if first.get("loc") else "body"
    return JSONResponse(status_code=400, content={"error": f"{field}: {first['msg']}"})

# ---------------------------------------------------------------------------
# "Database" — just a list in memory. Data resets every time the server
# restarts. That's expected at this stage (a real database comes next week).
# ---------------------------------------------------------------------------

SEED_TASKS = [
    {"id": 1, "title": "Buy milk", "done": False},
    {"id": 2, "title": "Write README", "done": False},
    {"id": 3, "title": "Ship the API", "done": True},
]

tasks: List[dict] = [dict(t) for t in SEED_TASKS]
next_id: int = len(tasks) + 1


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(..., description="What the task is")

    class Config:
        json_schema_extra = {"example": {"title": "Buy milk"}}


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

    class Config:
        json_schema_extra = {"example": {"title": "Buy oat milk", "done": True}}


class Task(BaseModel):
    id: int
    title: str
    done: bool


# ---------------------------------------------------------------------------
# Stage 1 — root & health
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"], summary="API info")
def read_root():
    """Describes what this API is and what it offers."""
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"],
    }


@app.get("/health", tags=["meta"], summary="Health check")
def health_check():
    """Used to confirm the server is alive."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Stage 2 — Read
# ---------------------------------------------------------------------------

def find_task(task_id: int) -> Optional[dict]:
    return next((t for t in tasks if t["id"] == task_id), None)


@app.get("/tasks", response_model=List[Task], tags=["tasks"], summary="List tasks")
def list_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    """
    Returns all tasks.

    Optional query parameters (stretch goals):
    - done: filter by completion status (true/false)
    - search: only tasks whose title contains this text (case-insensitive)
    - limit / offset: pagination
    """
    result = tasks

    if done is not None:
        result = [t for t in result if t["done"] == done]

    if search:
        needle = search.lower()
        result = [t for t in result if needle in t["title"].lower()]

    result = result[offset:]
    if limit is not None:
        result = result[:limit]

    return result


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"], summary="Get one task")
def get_task(task_id: int):
    """Returns a single task, or 404 if it doesn't exist."""
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


# ---------------------------------------------------------------------------
# Stage 3 — Create
# ---------------------------------------------------------------------------

@app.post(
    "/tasks",
    response_model=Task,
    status_code=201,
    tags=["tasks"],
    summary="Create a task",
)
def create_task(payload: TaskCreate):
    """
    Creates a new task. `title` is required and cannot be blank.
    Returns the created task with status 201.
    """
    global next_id

    title = payload.title.strip() if payload.title else ""
    if not title:
        raise HTTPException(status_code=400, detail="title is required and cannot be empty")

    new_task = {"id": next_id, "title": title, "done": False}
    tasks.append(new_task)
    next_id += 1
    return new_task


# ---------------------------------------------------------------------------
# Stage 4 — Update & Delete
# ---------------------------------------------------------------------------

@app.put("/tasks/{task_id}", response_model=Task, tags=["tasks"], summary="Update a task")
def update_task(task_id: int, payload: TaskUpdate):
    """
    Replaces a task's title and/or done status.
    Unknown id -> 404. Empty/invalid body -> 400.
    """
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if payload.title is None and payload.done is None:
        raise HTTPException(
            status_code=400,
            detail="request body must include at least one of: title, done",
        )

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="title cannot be empty")
        task["title"] = title

    if payload.done is not None:
        task["done"] = payload.done

    return task


@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"], summary="Delete a task")
def delete_task(task_id: int):
    """Removes a task. Unknown id -> 404. Returns 204 with no body on success."""
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    tasks.remove(task)
    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# Extras — stats and reset (optional stretch goals)
# ---------------------------------------------------------------------------

@app.get("/stats", tags=["extras"], summary="Task stats")
def get_stats():
    """Returns counts instead of raw data — the server computing, not just storing."""
    total = len(tasks)
    done_count = sum(1 for t in tasks if t["done"])
    return {"total": total, "done": done_count, "open": total - done_count}


@app.post("/reset", response_model=List[Task], tags=["extras"], summary="Reset to seed data")
def reset_tasks():
    """Restores the 3 example tasks. Handy for demos and re-testing."""
    global tasks, next_id
    tasks = [dict(t) for t in SEED_TASKS]
    next_id = len(tasks) + 1
    return tasks
