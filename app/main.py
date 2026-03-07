import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.api.routes.process_nfce import router as nfce_router
from app.core.config import settings
from app.core.errors import ApiError
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(health_router)
app.include_router(nfce_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "message": "payload inválido",
            "error_code": "INVALID_INPUT",
            "details": exc.errors(),
        },
    )


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro inesperado na API", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "erro inesperado",
            "error_code": "INTERNAL_ERROR",
            "details": [],
        },
    )
