"""
Task API — now backed by a real SQLite database (tasks.db) instead of an
in-memory list. Same endpoints, same request/response shapes as Assignment 1
— only the storage layer changed.

Run with:
    uvicorn main:app --reload --port 8000

Then visit:
    http://localhost:8000/         -> API info
    http://localhost:8000/docs     -> Swagger UI (interactive docs)

The database file (tasks.db) is created automatically on first run, with its
table and three seed tasks. Delete tasks.db and restart to start fresh.
"""

import sqlite3
from contextlib import closing
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DB_PATH = "tasks.db"

app = FastAPI(
    title="Task API",
    version="2.0",
    description="A to-do list API backed by SQLite — CRUD practice project.",
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Renders errors as {"error": "..."} instead of FastAPI's default {"detail": "..."}."""
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """A malformed/missing request body is a client mistake -> 400, not FastAPI's default 422."""
    first = exc.errors()[0]
    field = first["loc"][-1] if first.get("loc") else "body"
    return JSONResponse(status_code=400, content={"error": f"{field}: {first['msg']}"})


# ---------------------------------------------------------------------------
# Database — Stage 0: create the file, table, and seed data
# ---------------------------------------------------------------------------

SEED_TASKS = [
    ("Buy milk", 0),
    ("Write README", 0),
    ("Ship the API", 1),
]


def get_conn() -> sqlite3.Connection:
    """One connection per call, closed by the caller (or by `closing(...)`)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Creates tasks.db and its table if missing, and seeds it only when empty."""
    with closing(get_conn()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT    NOT NULL,
                done  INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)", SEED_TASKS
            )
        conn.commit()


init_db()


def row_to_task(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(..., description="What the task is")


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


class Task(BaseModel):
    id: int
    title: str
    done: bool


# ---------------------------------------------------------------------------
# Stage: root & health (unchanged from A1)
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"], summary="API info")
def read_root():
    return {"name": "Task API", "version": "2.0", "endpoints": ["/tasks"]}


@app.get("/health", tags=["meta"], summary="Health check")
def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Stage 1 — Read, from SQLite
# ---------------------------------------------------------------------------

@app.get("/tasks", response_model=List[Task], tags=["tasks"], summary="List tasks")
def list_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    """Reads tasks from tasks.db. Optional filters: done, search (SQL LIKE), limit/offset."""
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list = []

    if done is not None:
        query += " AND done = ?"
        params.append(1 if done else 0)

    if search:
        query += " AND title LIKE ?"
        params.append(f"%{search}%")

    query += " ORDER BY id"

    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    elif offset:
        query += " LIMIT -1 OFFSET ?"
        params.append(offset)

    with closing(get_conn()) as conn:
        rows = conn.execute(query, params).fetchall()

    return [row_to_task(r) for r in rows]


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"], summary="Get one task")
def get_task(task_id: int):
    """Fetches one row with a parameterized query. 404 if it doesn't exist."""
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return row_to_task(row)


# ---------------------------------------------------------------------------
# Stage 2 — Create, via INSERT
# ---------------------------------------------------------------------------

@app.post(
    "/tasks",
    response_model=Task,
    status_code=201,
    tags=["tasks"],
    summary="Create a task",
)
def create_task(payload: TaskCreate):
    """Inserts a new row. The database assigns the id. Same validation as A1."""
    title = payload.title.strip() if payload.title else ""
    if not title:
        raise HTTPException(status_code=400, detail="title is required and cannot be empty")

    with closing(get_conn()) as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)", (title, 0)
        )
        conn.commit()
        new_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone()

    return row_to_task(row)


# ---------------------------------------------------------------------------
# Stage 3 — Update & Delete, via UPDATE / DELETE
# ---------------------------------------------------------------------------

@app.put("/tasks/{task_id}", response_model=Task, tags=["tasks"], summary="Update a task")
def update_task(task_id: int, payload: TaskUpdate):
    """Updates title and/or done. Unknown id -> 404. Empty/invalid body -> 400."""
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        if payload.title is None and payload.done is None:
            raise HTTPException(
                status_code=400,
                detail="request body must include at least one of: title, done",
            )

        new_title = row["title"]
        if payload.title is not None:
            new_title = payload.title.strip()
            if not new_title:
                raise HTTPException(status_code=400, detail="title cannot be empty")

        new_done = row["done"] if payload.done is None else (1 if payload.done else 0)

        conn.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (new_title, new_done, task_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    return row_to_task(updated)


@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"], summary="Delete a task")
def delete_task(task_id: int):
    """Deletes a row. Unknown id -> 404. Returns 204 with no body on success."""
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()

    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# Extras — stats and reset, now computed/executed in SQL
# ---------------------------------------------------------------------------

@app.get("/stats", tags=["extras"], summary="Task stats")
def get_stats():
    """Counts computed with SQL instead of in Python."""
    with closing(get_conn()) as conn:
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE done = 1").fetchone()[0]

    return {"total": total, "done": done_count, "open": total - done_count}


@app.post("/reset", response_model=List[Task], tags=["extras"], summary="Reset to seed data")
def reset_tasks():
    """Wipes the table and reseeds the 3 example tasks. Handy for demos."""
    with closing(get_conn()) as conn:
        conn.execute("DELETE FROM tasks")
        conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", SEED_TASKS)
        conn.commit()
        rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()

    return [row_to_task(r) for r in rows]
