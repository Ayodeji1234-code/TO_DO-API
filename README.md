# TO_DO-API

A small in-memory CRUD API for managing a to-do list, built with **Python + FastAPI**.
Built as Assignment A1 (Week 2, Backend Track) for the FlyRank Internship.

Data lives only in memory — restarting the server resets the task list back to the seed data. A real database is next week's problem.

## How to install & run

Requires Python 3.10+.

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The server starts at `http://localhost:8000`. Interactive Swagger docs are available for free at `http://localhost:8000/docs`.

## Endpoints

| Method | Path            | Description                          | Success | Errors |
|--------|-----------------|---------------------------------------|---------|--------|
| GET    | `/`             | API info                              | 200     | —      |
| GET    | `/health`       | Health check                          | 200     | —      |
| GET    | `/tasks`        | List all tasks (supports `?done=`, `?search=`, `?limit=&offset=`) | 200 | — |
| GET    | `/tasks/{id}`   | Get a single task                     | 200     | 404 if not found |
| POST   | `/tasks`        | Create a task (`{"title": "..."}`)    | 201     | 400 if `title` missing/empty |
| PUT    | `/tasks/{id}`   | Update a task's `title` and/or `done` | 200     | 400 if body empty/invalid, 404 if not found |
| DELETE | `/tasks/{id}`   | Delete a task                         | 204     | 404 if not found |
| GET    | `/stats`        | Task counts (`total`, `done`, `open`) | 200     | — |
| POST   | `/reset`        | Restore the 3 seed tasks              | 200     | — |

## Example request

```bash
curl -i -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"Buy milk"}'
```

```
HTTP/1.1 201 Created
content-type: application/json

{"id":4,"title":"Buy milk","done":false}
```

## Swagger UI

`/docs` lists every endpoint and lets you run the full CRUD cycle with "Try it out."

<img width="2555" height="1296" alt="swagger screenshot png" src="https://github.com/user-attachments/assets/1b3dba22-3bb8-4937-93a0-0b1e1a062442" />



## The mortality experiment

Create a task, restart the server, then `GET /tasks` again — the task you added is gone. Since the task list is just a Python list held in memory, it only exists for as long as the process is running. This is what next week's database work solves.
