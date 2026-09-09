# Imagem do site (dashboard.py / Streamlit) para deploy no Coolify (VPS Hostinger).
# Build deterministico: a mesma imagem em qualquer maquina. Instala SO as deps
# do site (requirements-web.txt) — sem playwright/anthropic, que sao do scraper.

FROM python:3.11-slim

WORKDIR /app

# Deps primeiro, para aproveitar o cache de camada quando so o codigo muda.
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Resto do projeto. Inclui leiloes.json e historico_tokens_ia.jsonl, que o
# scraper commita 2x/dia no main — cada push rebuilda a imagem com dado fresco.
COPY . .

EXPOSE 8501

# Healthcheck nativo do Streamlit. O Coolify usa isto para saber quando a nova
# versao esta pronta antes de trocar (deploy sem downtime).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').read().strip()==b'ok' else 1)"

# --server.headless evita o prompt de e-mail do Streamlit no 1o boot.
# CORS/XSRF ficam no default (o Traefik do Coolify termina o TLS e repassa;
# se o WebSocket reclamar, ver SETUP_VPS.md > Troubleshooting).
CMD ["streamlit", "run", "dashboard.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
