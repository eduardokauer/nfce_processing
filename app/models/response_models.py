from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FonteInfo(BaseModel):
    url: str
    uf: str = "SP"
    modelo_documento: str = "NFC-e"


class Lancamento(BaseModel):
    id_lancamento: str
    chave_acesso: str
    tipo: str
    data_emissao: str | None = None
    hora_emissao: str | None = None
    data_hora_emissao: str | None = None
    mes_ref: str | None = None
    ano_ref: int | None = None
    emitente: str
    cnpj_emitente: str | None = None
    cnpj_emitente_limpo: str | None = None
    endereco_emitente: str | None = None
    numero_nota: str | None = None
    serie_nota: str | None = None
    protocolo_autorizacao: str | None = None
    valor_total_produtos: float | None = None
    valor_desconto: float | None = None
    valor_total_nota: float | None = None
    valor_pago: float | None = None
    forma_pagamento: str | None = None
    qtd_itens: int = 0
    link: str


class ItemResponse(BaseModel):
    ordem_item: int
    item_id: str
    codigo_item: str
    descricao_capturada: str
    descricao_padrao: str
    categoria_sugerida: str
    subcategoria_sugerida: str | None = None
    quantidade: float | None = None
    unidade: str | None = None
    valor_unitario: float | None = None
    valor_total_item: float | None = None


class NovoItemCatalogo(BaseModel):
    item_id: str
    cnpj_emitente: str | None = None
    cnpj_emitente_limpo: str | None = None
    codigo_item: str
    descricao_padrao: str
    descricao_ultima_capturada: str
    categoria: str = "Pendente"
    subcategoria: str | None = None
    tipo_origem: str
    ativo: bool = True


class ParseInfo(BaseModel):
    status_parse: Literal["OK", "PARTIAL", "ERROR"]
    campos_faltantes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_text_hash: str


class ProcessNFCEResponse(BaseModel):
    status: Literal["ok", "partial"]
    message: str
    processamento_em: datetime
    fonte: FonteInfo
    lancamento: Lancamento
    itens: list[ItemResponse]
    novos_itens_catalogo: list[NovoItemCatalogo]
    parse_info: ParseInfo


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str
    error_code: str
    details: list[Any] = Field(default_factory=list)
