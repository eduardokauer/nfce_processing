from enum import Enum

from pydantic import BaseModel, HttpUrl


class TipoLancamento(str, Enum):
    supermercado = "Supermercado"
    farmacia = "Farmácia"
    outro = "Outro"


class ProcessNFCERequest(BaseModel):
    link_nfce: HttpUrl
    tipo: TipoLancamento
