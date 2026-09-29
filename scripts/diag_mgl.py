"""Diagnostico temporario do acesso da MGL via Zenrows (rodar so no Actions).

Testa 3 caminhos e imprime o que cada um devolve. Nao imprime a chave.
Remover depois que o _raspar_mgl estiver consertado.
"""
import json
import os
import re
import sys

import requests

KEY = os.getenv("ZENROWS_API_KEY", "").strip()
BASE = "https://www.mgl.com.br"
BUSCA = BASE + "/busca/#Engine=Start&Pagina=1&Busca=&Mapa=&ID_Categoria=0"
API = "https://api.zenrows.com/v1/"
BODY = {
    "Bairro": "", "Busca": "", "BuscaProcesso": "", "CFGs": "",
    "CamposDinamicos": [], "CodLeilao": "", "DataAbertura": "",
    "DataEncerramento": "", "ID_Categoria": 0, "ID_Cidade": 0,
    "ID_Estado": 23, "ID_Leiloes_Status": [], "ID_Modelo": 0,
    "ID_Regiao": 0, "IgnoreScopo": 0, "Mapa": "", "NomesPartes": "",
    "OrdSt": 0, "Ordem": 0, "OrientacaoBusca": 0, "Pagina": 1,
    "PaginaIndex": 1, "PracaAtual": 0, "QtdPorPagina": 48, "RangeValores": 0,
    "Scopo": 0, "SubStatus": [], "TiposLeiloes": [], "ValorMaxSelecionado": 0,
    "ValorMinSelecionado": 0, "sInL": "",
}


def snip(t, n=300):
    return re.sub(r"\s+", " ", t or "")[:n]


def api_get(nome, **extra):
    params = {"apikey": KEY, "url": BASE + "/busca/", **extra}
    try:
        r = requests.get(API, params=params, timeout=120)
        print(f"[{nome}] GET status={r.status_code} len={len(r.text)} "
              f"JsonParametrosBusca={'JsonParametrosBusca' in r.text}")
        print(f"   corpo: {snip(r.text)}")
    except Exception as e:
        print(f"[{nome}] GET erro: {e}")


def api_post(nome, **extra):
    url = f"{BASE}/apiplugin/GetBusca/1/1/0?"
    params = {"apikey": KEY, "url": url, **extra}
    try:
        r = requests.post(API, params=params, json=BODY, timeout=120,
                          headers={"Content-Type": "application/json"})
        print(f"[{nome}] POST status={r.status_code} len={len(r.text)}")
        try:
            d = r.json()
            print(f"   CountTotal={d.get('CountTotal')} lotes={len(d.get('Lotes') or [])}")
        except Exception:
            print(f"   corpo: {snip(r.text)}")
    except Exception as e:
        print(f"[{nome}] POST erro: {e}")


def cdp():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.connect_over_cdp(f"wss://browser.zenrows.com?apikey={KEY}")
        except Exception as e:
            print(f"[cdp] falha ao conectar: {e}")
            return
        try:
            ctx = b.contexts[0] if b.contexts else b.new_context()
            pg = ctx.new_page()
            pg.on("response", lambda r: print(f"   resp {r.status} {r.url[:110]}")
                  if "mgl.com.br" in r.url and r.status >= 400 else None)
            try:
                pg.goto(BUSCA, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"[cdp] goto: {e}")
            for t in (5, 15, 30):
                pg.wait_for_timeout(t * 1000 if t == 5 else 10000)
                try:
                    tem = pg.evaluate("typeof window.JsonParametrosBusca !== 'undefined'")
                    print(f"[cdp] +{t}s title={pg.title()!r} url={pg.url[:90]} spa={tem}")
                    if tem:
                        break
                except Exception as e:
                    print(f"[cdp] eval: {e}")
            try:
                print(f"   body: {snip(pg.inner_text('body'))}")
            except Exception as e:
                print(f"   body erro: {e}")
        finally:
            b.close()


if not KEY:
    print("sem ZENROWS_API_KEY")
    sys.exit(1)

r = requests.post(API, params={"apikey": KEY, "url": f"{BASE}/apiplugin/GetBusca/1/1/0?",
                               "premium_proxy": "true", "proxy_country": "br"}, json=BODY, timeout=120)
d = r.json()
lotes = d.get("Lotes") or []
print("lotes", len(lotes), "campos", sorted(lotes[0].keys())[:40] if lotes else None)
for l in lotes[:3]:
    url = BASE + "/" + (l.get("URLlote") or "").lstrip("/")
    for nome, extra in (("det-premium-br", {}), ("det-render-br", {"js_render": "true"})):
        try:
            rr = requests.get(API, params={"apikey": KEY, "url": url, "premium_proxy": "true",
                                           "proxy_country": "br", **extra}, timeout=120)
            t = rr.text
            print(f"[{nome}] {url[-60:]} status={rr.status_code} len={len(t)} "
                  f"Avalia={'Avalia' in t} MODELO={'MODELO:' in t} Informa={'Informa' in t}")
            if rr.status_code != 200:
                print("   corpo:", snip(t, 200))
        except Exception as e:
            print(f"[{nome}] erro {e}")
