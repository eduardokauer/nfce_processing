from fastapi import APIRouter, HTTPException, status

from app.models.request_models import ProcessNFCERequest
from app.models.response_models import ProcessNFCEResponse
from app.services.fetcher_service import FetchError
from app.services.nfce_service import ParseError, process_nfce

router = APIRouter()


@router.post("/process-nfce", response_model=ProcessNFCEResponse)
async def process_nfce_endpoint(payload: ProcessNFCERequest) -> ProcessNFCEResponse:
    try:
        result = await process_nfce(str(payload.link_nfce), payload.tipo.value)
    except FetchError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro inesperado") from exc

    return result
