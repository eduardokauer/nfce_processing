import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse

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


def _find(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_access_key(raw_text: str, html: str) -> str | None:
    key_block = _find(r"Chave\s*de\s*Acesso\s*:?\s*([\d\s]{44,80})", raw_text)
    if key_block:
        cleaned = digits_only(key_block)
        if cleaned and len(cleaned) == 44:
            return cleaned

    for candidate in re.findall(r"(?:\d\s*){44,60}", raw_text):
        cleaned = digits_only(candidate)
        if cleaned and len(cleaned) == 44:
            return cleaned

    query_candidates = re.findall(r"https?://[^\s'\"]+", html)
    for url in query_candidates:
        parsed_url = urlparse(unquote(url))
        p_values = parse_qs(parsed_url.query).get("p", [])
        if p_values:
            cleaned = digits_only(p_values[0].split("|")[0])
            if cleaned and len(cleaned) == 44:
                return cleaned

    fallback_match = re.search(r"[?&]p=([^\s'\"<]+)", html, re.IGNORECASE)
    if fallback_match:
        cleaned = digits_only(unquote(fallback_match.group(1)).split("|")[0])
        if cleaned and len(cleaned) == 44:
            return cleaned

    return None


def _extract_emitente(raw_text: str) -> str | None:
    labeled = _find(r"(?:Emitente|EMITENTE)\s*:?\s*([^\n]+)", raw_text)
    if labeled:
        return labeled

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if "DOCUMENTO AUXILIAR DA NOTA FISCAL" in line.upper():
            for next_line in lines[idx + 1 : idx + 8]:
                upper = next_line.upper()
                if any(token in upper for token in ("CNPJ", "CPF", "CHAVE", "QTD.", "VALOR ")):
                    continue
                return next_line

    for idx, line in enumerate(lines):
        if "CNPJ" in line.upper() and idx > 0:
            candidate = lines[idx - 1]
            if not any(token in candidate.upper() for token in ("DOCUMENTO", "NFC-E", "ELETRÔNICA")):
                return candidate

    return None


def _extract_endereco(raw_text: str) -> str | None:
    labeled = _find(r"(?:Endere[cç]o)\s*:?\s*([^\n]+)", raw_text)
    if labeled:
        return labeled

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if "CNPJ" in line.upper() and idx + 1 < len(lines):
            maybe_addr = lines[idx + 1]
            if len(maybe_addr) > 10 and any(token in maybe_addr.upper() for token in (",", "SP", "RJ", "MG", "PR")):
                return maybe_addr
    return None


def _extract_payment(raw_text: str) -> tuple[str | None, float | None]:
    payment_line = _find(r"Valor\s*pago\s*R\$\s*:?[ \t]*(.+)", raw_text)
    if payment_line:
        money_matches = re.findall(r"\d+[\d.,]*", payment_line)
        value = parse_brl_money(money_matches[-1]) if money_matches else None
        method = payment_line
        if money_matches:
            method = payment_line.replace(money_matches[-1], "").strip(" -:")
        return method or None, value

    section = _find(r"Forma\s*de\s*pagamento\s*:?\s*([\s\S]{0,120})", raw_text)
    if section:
        line = section.splitlines()[0].strip()
        return line or None, None

    return None, None


def _extract_items_structured(soup: BeautifulSoup) -> list[ParsedItem]:
    items: list[ParsedItem] = []
    candidate_nodes = soup.select("tr, li, div, p")
    for node in candidate_nodes:
        block = " ".join(node.stripped_strings)
        if "Código" not in block or "Qtde" not in block:
            continue
        item = _parse_item_block(block, len(items) + 1)
        if item:
            items.append(item)
    return items


def _parse_item_block(block: str, ordem: int) -> ParsedItem | None:
    pattern = re.compile(
        r"(?P<desc>.+?)\s*\(C[oó]digo:\s*(?P<codigo>[\w.-]+)\s*\)\s*"
        r"Qtde\.?\s*:?\s*(?P<qtd>[\d.,]+)\s*UN\s*:?\s*(?P<un>[A-Za-z]{1,6})\s*"
        r"Vl\.\s*Unit\.?\s*:?\s*(?P<vunit>[\d.,]+)\s*Vl\.\s*Total\s*:?\s*(?P<vtotal>[\d.,]+)?",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(block)
    if not match:
        return None
    return ParsedItem(
        ordem_item=ordem,
        codigo_item=match.group("codigo").strip(),
        descricao_capturada=re.sub(r"\s+", " ", match.group("desc")).strip(),
        quantidade=parse_brl_money(match.group("qtd")),
        unidade=match.group("un").upper().strip(),
        valor_unitario=parse_brl_money(match.group("vunit")),
        valor_total_item=parse_brl_money(match.group("vtotal")) if match.group("vtotal") else None,
    )


def _extract_items_text(raw_text: str) -> list[ParsedItem]:
    block_pattern = re.compile(
        r"(?P<desc>[^\n]+?)\s*\(C[oó]digo:\s*(?P<codigo>[\w.-]+)\s*\)\s*\n"
        r"Qtde\.?\s*:?\s*(?P<qtd>[\d.,]+)\s*UN\s*:?\s*(?P<un>[A-Za-z]{1,6})\s*"
        r"Vl\.\s*Unit\.?\s*:?\s*(?P<vunit>[\d.,]+)\s*Vl\.\s*Total\s*\n?\s*(?P<vtotal>[\d.,]+)",
        re.IGNORECASE,
    )
    items: list[ParsedItem] = []
    for idx, match in enumerate(block_pattern.finditer(raw_text), start=1):
        items.append(
            ParsedItem(
                ordem_item=idx,
                codigo_item=match.group("codigo").strip(),
                descricao_capturada=match.group("desc").strip(),
                quantidade=parse_brl_money(match.group("qtd")),
                unidade=match.group("un").upper().strip(),
                valor_unitario=parse_brl_money(match.group("vunit")),
                valor_total_item=parse_brl_money(match.group("vtotal")),
            )
        )
    return items


def parse_nfce_sp_html(html: str) -> ParsedNFCE:
    raw_text = html_to_text(html)
    parsed = ParsedNFCE(raw_text=raw_text)
    soup = BeautifulSoup(html, "lxml")

    parsed.chave_acesso = _extract_access_key(raw_text, html)
    parsed.emitente = _extract_emitente(raw_text)
    parsed.cnpj_emitente = _find(r"CNPJ\s*:?\s*(\d{2}[.\s]?\d{3}[.\s]?\d{3}[\/\s]?\d{4}-?\d{2})", raw_text)
    parsed.endereco_emitente = _extract_endereco(raw_text)

    parsed.numero_nota = _find(r"N[úu]mero\s*:?\s*(\d+)", raw_text)
    parsed.serie_nota = _find(r"S[ée]rie\s*:?\s*(\d+)", raw_text)
    parsed.protocolo_autorizacao = _find(r"Protocolo\s*de\s*Autoriza[çc][ãa]o\s*:?\s*(\d+)", raw_text)
    dt = _find(r"(?:Data\s*de\s*Emiss[ãa]o|Emiss[ãa]o)\s*:?\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})", raw_text)
    (
        parsed.data_emissao,
        parsed.hora_emissao,
        parsed.data_hora_emissao,
        parsed.mes_ref,
        parsed.ano_ref,
    ) = parse_datetime_br(dt)

    parsed.qtd_itens = int(_find(r"Qtd\.\s*total\s*de\s*itens\s*:?\s*(\d+)", raw_text) or 0)
    parsed.valor_total_produtos = parse_brl_money(
        _find(r"Valor\s*total\s*dos\s*produtos\s*R\$\s*:?\s*([\d.,]+)", raw_text)
    )
    subtotal = parse_brl_money(_find(r"Valor\s*total\s*R\$\s*:?\s*([\d.,]+)", raw_text))
    parsed.valor_desconto = parse_brl_money(_find(r"Descontos?\s*R\$\s*:?\s*([\d.,]+)", raw_text))
    valor_a_pagar = parse_brl_money(_find(r"Valor\s*a\s*pagar\s*R\$\s*:?\s*([\d.,]+)", raw_text))

    parsed.forma_pagamento, parsed.valor_pago = _extract_payment(raw_text)

    parsed.valor_total_nota = valor_a_pagar
    if parsed.valor_total_nota is None and subtotal is not None and parsed.valor_desconto is not None:
        parsed.valor_total_nota = max(subtotal - parsed.valor_desconto, 0.0)
    if parsed.valor_total_nota is None:
        parsed.valor_total_nota = subtotal

    if parsed.valor_total_produtos is None and subtotal is not None:
        parsed.valor_total_produtos = subtotal
        parsed.warnings.append("valor_total_produtos inferido de valor total")

    if parsed.valor_pago is None and parsed.valor_total_nota is not None:
        parsed.valor_pago = parsed.valor_total_nota
        parsed.warnings.append("valor_pago ausente; usando valor_total_nota")

    parsed.items = _extract_items_structured(soup)
    if not parsed.items:
        parsed.items = _extract_items_text(raw_text)
    if not parsed.items:
        parsed.warnings.append("Itens não encontrados")

    if parsed.qtd_itens == 0:
        parsed.qtd_itens = len(parsed.items)

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
