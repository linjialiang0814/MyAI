from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from app.api.chat import router as chat_router
from app.api.agent_runs import router as agent_runs_router
from app.api.error_handlers import register_error_handlers
from app.api.evaluation import router as evaluation_router
from app.api.knowledge import router as knowledge_router
from app.api.memory import router as memory_router
from app.api.observability import router as observability_router
from app.api.task import router as task_router
from app.runtime.container import AppRuntime, build_runtime


def create_app(runtime_factory: Callable[[], AppRuntime] = build_runtime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        runtime = runtime_factory()
        application.state.runtime = runtime
        try:
            yield
        finally:
            try:
                runtime.close()
            finally:
                application.state.runtime = None

    application = FastAPI(
        title="MyAI LLM Service",
        description="Python-based LLM service for MyAI",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_error_handlers(application)
    application.include_router(agent_runs_router)
    application.include_router(chat_router)
    application.include_router(evaluation_router)
    application.include_router(knowledge_router)
    application.include_router(memory_router)
    application.include_router(observability_router)
    application.include_router(task_router)
    return application


app = create_app()
