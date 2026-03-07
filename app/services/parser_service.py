import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from app.services.normalizer_service import digits_only
from app.utils.date_utils import parse_datetime_br
from app.utils.money_utils import parse_brl_money
from app.utils.text_utils import html_to_text


class ParseError(Exception):
    pass


@dataclass
class ParsedItem:
    ordem_item: int
    codigo_item: str
    descricao_capturada: str
    quantidade: float | None = None
    unidade: str | None = None
    valor_unitario: float | None = None
    valor_total_item: float | None = None


@dataclass
class ParsedNFCE:
    raw_text: str
    chave_acesso: str | None = None
    emitente: str | None = None
    cnpj_emitente: str | None = None
    endereco_emitente: str | None = None
    numero_nota: str | None = None
    serie_nota: str | None = None
    data_emissao: str | None = None
    hora_emissao: str | None = None
    data_hora_emissao: str | None = None
    mes_ref: str | None = None
    ano_ref: int | None = None
    protocolo_autorizacao: str | None = None
    qtd_itens: int = 0
    valor_total_produtos: float | None = None
    valor_desconto: float | None = None
    valor_total_nota: float | None = None
    valor_pago: float | None = None
    forma_pagamento: str | None = None
    items: list[ParsedItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


FIELD_REGEX = {
    "chave_acesso": r"(?:Chave de Acesso|CHAVE DE ACESSO)\s*:?\s*(\d{44})",
    "emitente": r"(?:Emitente|EMITENTE)\s*:?\s*([^\n]+)",
    "cnpj_emitente": r"CNPJ\s*:?\s*(\d{2}[. ]?\d{3}[. ]?\d{3}[\/ ]?\d{4}-?\d{2})",
    "endereco_emitente": r"(?:Endereço|Endereco)\s*:?\s*([^\n]+)",
    "numero_nota": r"(?:Número|Numero)\s*:?\s*(\d+)",
    "serie_nota": r"(?:Série|Serie)\s*:?\s*(\d+)",
    "protocolo_autorizacao": r"Protocolo\s*de\s*Autorização\s*:?\s*(\d+)",
    "data_hora": r"(?:Data de Emissão|Emissão|Emissao)\s*:?\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})",
    "valor_total_produtos": r"Valor\s*Total\s*dos\s*Produtos\s*:?\s*R?\$?\s*([\d.,]+)",
    "valor_desconto": r"Desconto\s*:?\s*R?\$?\s*([\d.,]+)",
    "valor_total_nota": r"(?:Valor\s*Total\s*da\s*Nota|VALOR\s*A\s*PAGAR\s*R\$)\s*:?\s*R?\$?\s*([\d.,]+)",
    "valor_pago": r"(?:Valor\s*Pago|TOTAL\s*R\$)\s*:?\s*R?\$?\s*([\d.,]+)",
    "forma_pagamento": r"(?:Forma\s*de\s*Pagamento|Pagamento)\s*:?\s*([^\n]+)",
}


def _find_field(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _parse_items_structured(soup: BeautifulSoup) -> list[ParsedItem]:
    items: list[ParsedItem] = []
    rows = soup.select("table tr")
    for row in rows:
        raw = " ".join(row.stripped_strings)
        if not raw or "Código" not in raw:
            continue
        codigo = _find_field(r"Código\s*:?\s*(\w+)", raw) or ""
        descricao = _find_field(r"(?:Descrição|Descricao)\s*:?\s*([^\n]+?)\s+(?:Qtde|Quantidade|QTD)", raw) or raw
        qtd = parse_brl_money(_find_field(r"(?:Qtde|Quantidade|QTD)\s*:?\s*([\d.,]+)", raw))
        unidade = _find_field(r"(?:UN|Unidade)\s*:?\s*([A-Za-z]+)", raw)
        v_unit = parse_brl_money(_find_field(r"(?:Vl\.\s*Unit\.|Valor\s*Unit)\s*:?\s*([\d.,]+)", raw))
        v_total = parse_brl_money(_find_field(r"(?:Vl\.\s*Total|Valor\s*Total)\s*:?\s*([\d.,]+)", raw))
        if codigo:
            items.append(ParsedItem(len(items) + 1, codigo, descricao.strip(), qtd, unidade, v_unit, v_total))
    return items


def _parse_items_text(raw_text: str) -> list[ParsedItem]:
    items: list[ParsedItem] = []
    pattern = re.compile(
        r"(\d+)\s+([A-Za-z0-9\-/ ]+?)\s+\(Código:\s*(\w+)\)\s+Qtd[: ]+([\d.,]+)\s+([A-Za-z]+)\s+Vl\. Unit\.[: ]+([\d.,]+)\s+Vl\. Total[: ]+([\d.,]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(raw_text):
        ordem = int(match.group(1))
        items.append(
            ParsedItem(
                ordem_item=ordem,
                descricao_capturada=match.group(2).strip(),
                codigo_item=match.group(3).strip(),
                quantidade=parse_brl_money(match.group(4)),
                unidade=match.group(5).strip(),
                valor_unitario=parse_brl_money(match.group(6)),
                valor_total_item=parse_brl_money(match.group(7)),
            )
        )
    return items


def parse_nfce_sp_html(html: str) -> ParsedNFCE:
    raw_text = html_to_text(html)
    parsed = ParsedNFCE(raw_text=raw_text)
    soup = BeautifulSoup(html, "lxml")

    for field, pattern in FIELD_REGEX.items():
        value = _find_field(pattern, raw_text)
        if field == "data_hora" and value:
            (
                parsed.data_emissao,
                parsed.hora_emissao,
                parsed.data_hora_emissao,
                parsed.mes_ref,
                parsed.ano_ref,
            ) = parse_datetime_br(value)
        elif field.startswith("valor"):
            setattr(parsed, field, parse_brl_money(value))
        else:
            setattr(parsed, field, value)

    parsed.items = _parse_items_structured(soup)
    if not parsed.items:
        parsed.items = _parse_items_text(raw_text)
        if not parsed.items:
            parsed.warnings.append("Itens não encontrados")

    parsed.qtd_itens = len(parsed.items)
    parsed.cnpj_emitente = parsed.cnpj_emitente

    if not parsed.chave_acesso:
        from_url = re.search(r"p=(\d{44})", html)
        if from_url:
            parsed.chave_acesso = from_url.group(1)

    missing_critical = []
    for critical in ["chave_acesso", "emitente"]:
        if not getattr(parsed, critical):
            missing_critical.append(critical)
    if parsed.valor_pago is None and parsed.valor_total_nota is None:
        missing_critical.append("valor_pago|valor_total_nota")

    if missing_critical:
        raise ParseError(f"Campos críticos ausentes: {', '.join(missing_critical)}")

    return parsed


def cnpj_clean(cnpj: str | None) -> str | None:
    return digits_only(cnpj)
