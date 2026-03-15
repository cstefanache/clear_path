from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, projects, settings as settings_routes, chat, benchmark, executions

app = FastAPI(title="Clear Route API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])
app.include_router(chat.router, prefix="/api/projects", tags=["chat"])
app.include_router(benchmark.router, prefix="/api/projects", tags=["benchmark"])
app.include_router(executions.router, prefix="/api/projects", tags=["executions"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
