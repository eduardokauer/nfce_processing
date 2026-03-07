# NFC-e Processor API (SEFAZ SP)

API backend em FastAPI para processar links públicos de NFC-e, extrair dados e retornar JSON estruturado para automações (ex.: Make.com).

## Stack
- Python 3.11+
- FastAPI + Uvicorn
- Pydantic
- httpx
- BeautifulSoup4 + lxml
- pytest

## Estrutura

```text
app/
  main.py
  api/routes/
  core/
  models/
  services/
  utils/
tests/
  fixtures/
```

## Como rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

### `GET /health`
Retorna status básico da API.

### `POST /process-nfce`
Exemplo:

```bash
curl -X POST 'http://localhost:8000/process-nfce' \
  -H 'Content-Type: application/json' \
  -d '{
    "link_nfce": "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=35260306057223056630650210000274541210607969|3|1",
    "tipo": "Supermercado"
  }'
```

## Testes

```bash
pytest -q
```

## Deploy no Render

1. Crie um novo **Web Service** apontando para este repositório.
2. Runtime: **Python 3.11+**.
3. Build Command:
   ```bash
   pip install -r requirements.txt
   ```
4. Start Command:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. (Opcional) Configure variáveis de ambiente conforme `.env.example`.

## Limitações atuais
- Parser focado em layout público da NFC-e SP; variações grandes de HTML podem cair no modo parcial.
- Estratégia de extração de itens usa parse estruturado com fallback regex textual; pode precisar ajustes para novos layouts.
- `novos_itens_catalogo` retorna todos os itens como potenciais novos itens com categoria inicial `Pendente`.
