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
            "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=35260306057223056630650210000274541210607969|3|1",
            "tipo": "Supermercado",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "partial"  # campos opcionais/heurísticas podem variar
    assert data["lancamento"]["chave_acesso"] == "35260306057223056630650210000274541210607969"
    assert data["lancamento"]["qtd_itens"] == 2
    assert len(data["itens"]) == 2


def test_process_nfce_invalid_tipo() -> None:
    client = TestClient(app)
    response = client.post(
        "/process-nfce",
        json={
            "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=35260306057223056630650210000274541210607969|3|1",
            "tipo": "Restaurante",
        },
    )
    assert response.status_code == 400


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


def test_process_nfce_partial_parse(monkeypatch) -> None:
    async def _fake_fetch(_: str) -> str:
        return _load_fixture("sample_nfce_sp_partial.html")

    monkeypatch.setattr("app.services.nfce_service.fetch_nfce_html", _fake_fetch)
    client = TestClient(app)

    response = client.post(
        "/process-nfce",
        json={
            "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=35260306057223056630650210000274541210607969|3|1",
            "tipo": "Outro",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert "itens" in data["parse_info"]["campos_faltantes"]


def test_parser_text_fixture() -> None:
    from app.services.parser_service import parse_nfce_sp_html

    text_fixture = _load_fixture("sample_nfce_sp.txt")
    html = f"<html><body><pre>{text_fixture}</pre></body></html>"
    parsed = parse_nfce_sp_html(html)

    assert parsed.chave_acesso == "35260306057223056630650210000274541210607969"
    assert parsed.emitente == "SENDAS DISTRIBUIDORA S/A"
    assert parsed.items
