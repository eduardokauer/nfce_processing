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


CODIGO_TOKEN = r"(?:C(?:o|ó|Ã³|ÃƒÂ³)digo)"
ITEM_HEADER_PATTERN = re.compile(rf"[^\n]{{2,260}}\({CODIGO_TOKEN}:\s*[\w.-]+\s*\)", re.IGNORECASE)


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


def _slice_items_section(raw_text: str) -> tuple[str, int | None]:
    start_match = ITEM_HEADER_PATTERN.search(raw_text)
    if not start_match:
        return "", None

    start = start_match.start()
    tail = raw_text[start:]
    end_markers = [
        r"(?im)^Qtd\.\s*total\s*de\s*itens\s*:",
        r"(?im)^Valor\s*total\s*R\$\s*:",
        r"(?im)^INFORMA(?:Ã‡Ã•ES|Ãƒâ€¡Ãƒâ€¢ES)\s+GERAIS\s+DA\s+NOTA",
        r"(?im)^CHAVE\s+DE\s+ACESSO",
    ]
    ends = [m.start() for marker in end_markers if (m := re.search(marker, tail))]
    end = min(ends) if ends else len(tail)
    return tail[:end].strip(), start


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
            if not any(token in candidate.upper() for token in ("DOCUMENTO", "NFC-E", "ELETRÃ”NICA", "ELETRÃƒâ€NICA")):
                return candidate

    return None


def _extract_endereco(raw_text: str, item_start: int | None) -> str | None:
    labeled = _find(r"(?:Endere(?:Ã§o|cÃƒÂ§o))\s*:?\s*([^\n]+)", raw_text)
    if labeled:
        return labeled

    cnpj_match = re.search(r"CNPJ\s*:?\s*\d{2}[.\s]?\d{3}[.\s]?\d{3}[\/\s]?\d{4}-?\d{2}", raw_text, re.IGNORECASE)
    if not cnpj_match:
        return None

    start = cnpj_match.end()
    end = item_start if item_start and item_start > start else len(raw_text)
    candidate = raw_text[start:end]
    lines = [line.strip(" ,") for line in candidate.splitlines() if line.strip()]
    if not lines:
        return None

    address_parts: list[str] = []
    for line in lines:
        upper = line.upper()
        if any(
            stop in upper
            for stop in (
                "QTD. TOTAL",
                "VALOR TOTAL",
                "FORMA DE PAGAMENTO",
                "INFORMAÃ‡Ã•ES GERAIS",
                "INFORMAÃƒâ€¡Ãƒâ€¢ES GERAIS",
                "CHAVE DE ACESSO",
            )
        ):
            break
        if "(" in line and ("CÃ“DIGO" in upper or "CÃƒâ€œDIGO" in upper):
            break
        address_parts.append(line)

    endereco = " ".join(address_parts).strip(" ,")
    return re.sub(r"\s+", " ", endereco) if endereco else None


def _extract_payment(raw_text: str) -> tuple[str | None, float | None]:
    compact = re.sub(r"\s+", " ", raw_text)
    combined = re.search(
        r"Forma\s*de\s*pagamento\s*:\s*Valor\s*pago\s*R\$\s*:\s*([^\d]+?)\s+(\d+[\d.,]*)",
        compact,
        re.IGNORECASE,
    )
    if combined:
        return combined.group(1).strip(" -:"), parse_brl_money(combined.group(2))

    payment_line = _find(r"Valor\s*pago\s*R\$\s*:?\s*(.+)", raw_text)
    if payment_line:
        money_matches = re.findall(r"\d+[\d.,]*", payment_line)
        value = parse_brl_money(money_matches[-1]) if money_matches else None
        method = payment_line
        if money_matches:
            method = payment_line.replace(money_matches[-1], "").strip(" -:")
        return method or None, value

    section = _find(r"Forma\s*de\s*pagamento\s*:?\s*([^\n]+)", raw_text)
    if section:
        return section.strip(), None

    return None, None


def _parse_item_block(block: str, ordem: int) -> ParsedItem | None:
    pattern = re.compile(
        rf"(?P<desc>[^\n]+?)\s*\({CODIGO_TOKEN}:\s*(?P<codigo>[\w.-]+)\s*\)\s*"
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


def _extract_items_structured(soup: BeautifulSoup) -> list[ParsedItem]:
    items: list[ParsedItem] = []
    seen_blocks: set[str] = set()
    for node in soup.select("tr, li, div, p"):
        block = " ".join(node.stripped_strings)
        if ("(Código:" not in block and "(CÃ³digo:" not in block) or "Qtde" not in block:
            continue
        if block.count("(Código:") + block.count("(CÃ³digo:") != 1:
            continue
        normalized_block = re.sub(r"\s+", " ", block).strip()
        if normalized_block in seen_blocks:
            continue
        seen_blocks.add(normalized_block)
        item = _parse_item_block(block, len(items) + 1)
        if item:
            items.append(item)
    return items




def _split_item_chunks(items_text: str) -> list[str]:
    starts = [m.start() for m in ITEM_HEADER_PATTERN.finditer(items_text)]
    if not starts:
        return []
    starts.append(len(items_text))

    chunks: list[str] = []
    for idx in range(len(starts) - 1):
        chunk = items_text[starts[idx] : starts[idx + 1]].strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def _extract_items_text(items_text: str) -> list[ParsedItem]:
    single_pattern = re.compile(
        rf"(?P<desc>[^\n]+?)\s*\({CODIGO_TOKEN}:\s*(?P<codigo>[\w.-]+)\s*\)\s*"
        r"(?:\n\s*)?Qtde\.?\s*:?\s*(?P<qtd>[\d.,]+)\s*UN\s*:?\s*(?P<un>[A-Za-z]{1,6})\s*"
        r"Vl\.\s*Unit\.?\s*:?\s*(?P<vunit>[\d.,]+)\s*Vl\.\s*Total\s*(?:\n\s*|\s+)(?P<vtotal>[\d.,]+)",
        re.IGNORECASE | re.DOTALL,
    )

    items: list[ParsedItem] = []
    for idx, match in enumerate(single_pattern.finditer(items_text), start=1):
        items.append(
            ParsedItem(
                ordem_item=idx,
                codigo_item=match.group("codigo").strip(),
                descricao_capturada=re.sub(r"\s+", " ", match.group("desc")).strip(),
                quantidade=parse_brl_money(match.group("qtd")),
                unidade=match.group("un").upper().strip(),
                valor_unitario=parse_brl_money(match.group("vunit")),
                valor_total_item=parse_brl_money(match.group("vtotal")),
            )
        )

    if items:
        return items

    for idx, chunk in enumerate(_split_item_chunks(items_text), start=1):
        match = single_pattern.search(chunk)
        if not match:
            continue
        items.append(
            ParsedItem(
                ordem_item=idx,
                codigo_item=match.group("codigo").strip(),
                descricao_capturada=re.sub(r"\s+", " ", match.group("desc")).strip(),
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
    items_text, items_start = _slice_items_section(raw_text)

    parsed.chave_acesso = _extract_access_key(raw_text, html)
    parsed.emitente = _extract_emitente(raw_text)
    parsed.cnpj_emitente = _find(r"CNPJ\s*:?\s*(\d{2}[.\s]?\d{3}[.\s]?\d{3}[\/\s]?\d{4}-?\d{2})", raw_text)
    parsed.endereco_emitente = _extract_endereco(raw_text, items_start)

    parsed.numero_nota = _find(r"N(?:Ãºmero|ÃƒÂºmero|umero)\s*:?\s*(\d+)", raw_text)
    parsed.serie_nota = _find(r"S(?:Ã©rie|ÃƒÂ©rie|erie)\s*:?\s*(\d+)", raw_text)
    parsed.protocolo_autorizacao = _find(
        r"Protocolo\s*de\s*Autoriza(?:Ã§Ã£o|ÃƒÂ§ÃƒÂ£o|cao)\s*:?\s*(\d+)", raw_text
    )
    dt = _find(
        r"(?:Data\s*de\s*Emiss(?:Ã£o|ÃƒÂ£o)|Emiss(?:Ã£o|ÃƒÂ£o))\s*:?\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})",
        raw_text,
    )
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

    if items_text:
        parsed.items = _extract_items_text(items_text)

    if not parsed.items:
        parsed.items = _extract_items_structured(soup)

    if not parsed.items and items_text:
        parsed.warnings.append("itens nÃ£o parseados no bloco identificado")
    elif not parsed.items:
        parsed.warnings.append("Itens nÃ£o encontrados")

    if parsed.qtd_itens == 0:
        parsed.qtd_itens = len(parsed.items)

    if not parsed.endereco_emitente:
        parsed.warnings.append("endereco_emitente nÃ£o encontrado")

    missing_critical = []
    for critical in ["chave_acesso", "emitente"]:
        if not getattr(parsed, critical):
            missing_critical.append(critical)
    if parsed.valor_pago is None and parsed.valor_total_nota is None:
        missing_critical.append("valor_pago|valor_total_nota")

    if missing_critical:
        raise ParseError(f"Campos crÃ­ticos ausentes: {', '.join(missing_critical)}")

    return parsed


def cnpj_clean(cnpj: str | None) -> str | None:
    return digits_only(cnpj)



