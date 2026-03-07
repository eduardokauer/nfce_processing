from fastapi import APIRouter

from app.core.errors import ApiError
from app.models.request_models import ProcessNFCERequest
from app.models.response_models import ErrorResponse, ProcessNFCEResponse
from app.services.fetcher_service import FetchError
from app.services.nfce_service import ParseError, process_nfce

router = APIRouter()


@router.post(
    "/process-nfce",
    response_model=ProcessNFCEResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def process_nfce_endpoint(payload: ProcessNFCERequest) -> ProcessNFCEResponse:
    try:
        return await process_nfce(str(payload.link_nfce), payload.tipo.value)
    except FetchError as exc:
        raise ApiError(status_code=502, message="erro ao buscar página NFC-e", error_code="FETCH_ERROR", details=[str(exc)]) from exc
    except ParseError as exc:
        raise ApiError(status_code=422, message="erro de parse da NFC-e", error_code="PARSE_ERROR", details=[str(exc)]) from exc
