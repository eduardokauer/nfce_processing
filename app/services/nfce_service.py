from datetime import datetime

from app.models.response_models import (
    FonteInfo,
    ItemResponse,
    Lancamento,
    NovoItemCatalogo,
    ParseInfo,
    ProcessNFCEResponse,
)
from app.services.categorizer_service import suggest_category
from app.services.fetcher_service import fetch_nfce_html
from app.services.normalizer_service import normalize_description
from app.services.parser_service import ParseError, cnpj_clean, parse_nfce_sp_html
from app.utils.hash_utils import short_sha256


async def process_nfce(link_nfce: str, tipo: str, html_override: str | None = None) -> ProcessNFCEResponse:
    html = html_override if html_override is not None else await fetch_nfce_html(link_nfce)

    parsed = parse_nfce_sp_html(html)
    cnpj_limpo = cnpj_clean(parsed.cnpj_emitente)

    items: list[ItemResponse] = []
    catalog: list[NovoItemCatalogo] = []

    for item in parsed.items:
        descricao_padrao = normalize_description(item.descricao_capturada)
        categoria, subcategoria = suggest_category(descricao_padrao)
        codigo = item.codigo_item
        item_id = f"{cnpj_limpo or 'SEM_CNPJ'}:{codigo}"
        items.append(
            ItemResponse(
                ordem_item=item.ordem_item,
                item_id=item_id,
                codigo_item=codigo,
                descricao_capturada=item.descricao_capturada,
                descricao_padrao=descricao_padrao,
                categoria_sugerida=categoria,
                subcategoria_sugerida=subcategoria,
                quantidade=item.quantidade,
                unidade=item.unidade,
                valor_unitario=item.valor_unitario,
                valor_total_item=item.valor_total_item,
            )
        )
        catalog.append(
            NovoItemCatalogo(
                item_id=item_id,
                cnpj_emitente=parsed.cnpj_emitente,
                cnpj_emitente_limpo=cnpj_limpo,
                codigo_item=codigo,
                descricao_padrao=descricao_padrao,
                descricao_ultima_capturada=item.descricao_capturada,
                categoria="Pendente",
                subcategoria=None,
                tipo_origem=tipo,
                ativo=True,
            )
        )

    campos_faltantes = []
    optional_fields = ["endereco_emitente", "numero_nota", "serie_nota", "protocolo_autorizacao", "forma_pagamento"]
    for field in optional_fields:
        if getattr(parsed, field) in (None, ""):
            campos_faltantes.append(field)
    if not items:
        campos_faltantes.append("itens")

    if parsed.qtd_itens and parsed.qtd_itens != len(items):
        parsed.warnings.append("qtd_itens divergente entre resumo e itens parseados")

    status = "ok" if not campos_faltantes and not parsed.warnings else "partial"
    parse_status = "OK" if status == "ok" else "PARTIAL"

    lancamento = Lancamento(
        id_lancamento=parsed.chave_acesso,
        chave_acesso=parsed.chave_acesso,
        tipo=tipo,
        data_emissao=parsed.data_emissao,
        hora_emissao=parsed.hora_emissao,
        data_hora_emissao=parsed.data_hora_emissao,
        mes_ref=parsed.mes_ref,
        ano_ref=parsed.ano_ref,
        emitente=parsed.emitente,
        cnpj_emitente=parsed.cnpj_emitente,
        cnpj_emitente_limpo=cnpj_limpo,
        endereco_emitente=parsed.endereco_emitente,
        numero_nota=parsed.numero_nota,
        serie_nota=parsed.serie_nota,
        protocolo_autorizacao=parsed.protocolo_autorizacao,
        valor_total_produtos=parsed.valor_total_produtos,
        valor_desconto=parsed.valor_desconto,
        valor_total_nota=parsed.valor_total_nota,
        valor_pago=parsed.valor_pago if parsed.valor_pago is not None else parsed.valor_total_nota,
        forma_pagamento=parsed.forma_pagamento,
        qtd_itens=parsed.qtd_itens or len(items),
        link=link_nfce,
    )

    return ProcessNFCEResponse(
        status=status,
        message="NFC-e processada com sucesso" if status == "ok" else "NFC-e processada parcialmente",
        processamento_em=datetime.now().astimezone(),
        fonte=FonteInfo(url=link_nfce),
        lancamento=lancamento,
        itens=items,
        novos_itens_catalogo=catalog,
        parse_info=ParseInfo(
            status_parse=parse_status,
            campos_faltantes=campos_faltantes,
            warnings=parsed.warnings,
            raw_text_hash=short_sha256(parsed.raw_text),
        ),
    )


__all__ = ["process_nfce", "ParseError"]
