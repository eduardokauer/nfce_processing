from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_process_nfce_success(monkeypatch) -> None:
    async def _fake_fetch(_: str) -> str:
        return _load_fixture("sample_nfce_sp.html")

    monkeypatch.setattr("app.services.nfce_service.fetch_nfce_html", _fake_fetch)
    client = TestClient(app)

    response = client.post(
        "/process-nfce",
        json={
            "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=35260371676316001975651120001006781062282698|3|1",
            "tipo": "Supermercado",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["lancamento"]["chave_acesso"] == "35260371676316001975651120001006781062282698"
    assert data["lancamento"]["emitente"] == "SUPERMERCADOS MAMBO LTDA"
    assert data["lancamento"]["valor_total_nota"] == 110.52
    assert data["lancamento"]["valor_pago"] == 110.52
    assert data["lancamento"]["forma_pagamento"] == "Dinheiro"
    assert data["lancamento"]["endereco_emitente"]
    assert len(data["itens"]) == 3
    assert data["itens"][0]["descricao_capturada"] == "SUCO DE LARANJA MOMENTO MAMBO 500ML"
    codigos = [item["codigo_item"] for item in data["itens"]]
    descricoes = [item["descricao_capturada"] for item in data["itens"]]
    assert codigos == ["277976", "277857", "223515"]
    assert len(set(codigos)) == 3
    assert descricoes[0] == "SUCO DE LARANJA MOMENTO MAMBO 500ML"
    assert descricoes[1] != descricoes[0]


def test_process_nfce_sendas_realistic(monkeypatch) -> None:
    async def _fake_fetch(_: str) -> str:
        return _load_fixture("sample_nfce_sendas.html")

    monkeypatch.setattr("app.services.nfce_service.fetch_nfce_html", _fake_fetch)
    client = TestClient(app)

    response = client.post(
        "/process-nfce",
        json={
            "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=35260306057223056630650210000274541210607969|3|1",
            "tipo": "Supermercado",
        },
    )

    assert response.status_code == 200
    data = response.json()
    codigos = [item["codigo_item"] for item in data["itens"]]

    assert data["status"] == "ok"
    assert data["parse_info"]["warnings"] == []
    assert data["parse_info"]["campos_faltantes"] == []
    assert data["lancamento"]["qtd_itens"] == 10
    assert data["lancamento"]["valor_total_produtos"] == 125.53
    assert len(data["itens"]) == 10
    assert codigos == [
        "1043171",
        "1206944",
        "1179874",
        "1188117",
        "1188117",
        "1188117",
        "1188117",
        "1188117",
        "59569",
        "1050428",
    ]
    assert codigos.count("1188117") == 5
    assert data["lancamento"]["forma_pagamento"] == "Vale Alimentação"
    assert "BISNAG KIM INT 300G" not in data["lancamento"]["endereco_emitente"]
    assert data["lancamento"]["endereco_emitente"] == "Avenida Mario Sadanori Doi 479 Jardim dos Camargos Barueri SP"
    assert data["lancamento"]["numero_nota"] == "27454"
    assert data["lancamento"]["serie_nota"] == "21"
    assert data["lancamento"]["protocolo_autorizacao"] == "135261457187156"
    assert data["lancamento"]["data_emissao"] == "2026-03-03"
    assert data["lancamento"]["hora_emissao"] == "10:38:48"
    assert data["lancamento"]["data_hora_emissao"] == "2026-03-03T10:38:48-03:00"
    assert data["lancamento"]["mes_ref"] == "2026-03"
    assert data["lancamento"]["ano_ref"] == 2026

def test_process_nfce_invalid_tipo() -> None:
    client = TestClient(app)
    response = client.post(
        "/process-nfce",
        json={
            "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=35260371676316001975651120001006781062282698|3|1",
            "tipo": "Restaurante",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["error_code"] == "INVALID_INPUT"


def test_process_nfce_invalid_link() -> None:
    client = TestClient(app)
    response = client.post(
        "/process-nfce",
        json={
            "link_nfce": "not-an-url",
            "tipo": "Supermercado",
        },
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_INPUT"


def test_process_nfce_partial_parse(monkeypatch) -> None:
    async def _fake_fetch(_: str) -> str:
        return _load_fixture("sample_nfce_sp_partial.html")

    monkeypatch.setattr("app.services.nfce_service.fetch_nfce_html", _fake_fetch)
    client = TestClient(app)

    response = client.post(
        "/process-nfce",
        json={
            "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=35260311222333000144650110000000111122223333|3|1",
            "tipo": "Outro",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert "itens" in data["parse_info"]["campos_faltantes"]


def test_process_nfce_parse_error(monkeypatch) -> None:
    async def _fake_fetch(_: str) -> str:
        return "<html><body><pre>documento sem campos crÃ­ticos</pre></body></html>"

    monkeypatch.setattr("app.services.nfce_service.fetch_nfce_html", _fake_fetch)
    client = TestClient(app)

    response = client.post(
        "/process-nfce",
        json={
            "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=1",
            "tipo": "Outro",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["error_code"] == "PARSE_ERROR"


def test_parser_text_fixture_realistic() -> None:
    from app.services.parser_service import parse_nfce_sp_html

    text_fixture = _load_fixture("sample_nfce_sp.txt")
    html = f"<html><body><pre>{text_fixture}</pre></body></html>"
    parsed = parse_nfce_sp_html(html)

    assert parsed.chave_acesso == "35260371676316001975651120001006781062282698"
    assert parsed.emitente == "SUPERMERCADOS MAMBO LTDA"
    assert parsed.cnpj_emitente == "71.676.316/0019-75"
    assert parsed.endereco_emitente and "AL RIO NEGRO" in parsed.endereco_emitente
    assert parsed.forma_pagamento == "Dinheiro"
    assert len(parsed.items) == 3
    assert [item.codigo_item for item in parsed.items] == ["277976", "277857", "223515"]
    assert parsed.items[0].descricao_capturada == "SUCO DE LARANJA MOMENTO MAMBO 500ML"
    assert parsed.items[1].descricao_capturada != parsed.items[0].descricao_capturada

