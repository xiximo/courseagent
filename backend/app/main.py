import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.errors import ApiBusinessError
from app.config import get_settings
from app.db.session import engine
from app.routers import (
    auth,
    course_agent,
    harness,
    health,
    indexing,
    llm_settings,
    processing,
    qa,
    qibiao,
    settings as settings_router,
    sync,
)
from app.course_agent.bootstrap import init_database
from app.storage import get_storage

logger = logging.getLogger(__name__)
app_settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connected: %s", app_settings.database_url.split("@")[-1])
    except Exception:
        logger.exception("PostgreSQL connection failed — check DATABASE_URL")

    try:
        init_database()
        logger.info("Course Agent schema and seed data ready")
    except Exception:
        logger.exception("Database bootstrap failed — check DATABASE_URL and PostgreSQL")

    try:
        storage = get_storage()
        storage.ensure_bucket()
        backend = (app_settings.storage_backend or "local").strip().lower()
        if backend == "minio":
            logger.info(
                "Object storage ready (minio): %s @ %s",
                app_settings.minio_bucket,
                app_settings.minio_endpoint,
            )
        else:
            logger.info(
                "Object storage ready (local): %s/%s",
                app_settings.local_storage_root,
                storage.bucket,
            )
    except Exception:
        logger.exception(
            "Object storage init failed — check STORAGE_BACKEND / LOCAL_STORAGE_ROOT"
        )

    yield


app = FastAPI(
    title=app_settings.app_name,
    debug=app_settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiBusinessError)
async def api_business_error_handler(_request: Request, exc: ApiBusinessError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "code": exc.code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后重试",
            "data": None,
        },
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(settings_router.router)
app.include_router(sync.router)
app.include_router(processing.router)
app.include_router(indexing.router)
app.include_router(qa.router)
app.include_router(llm_settings.router)
app.include_router(harness.router)
app.include_router(qibiao.router)
app.include_router(course_agent.router)
