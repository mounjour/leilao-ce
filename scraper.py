from playwright.sync_api import sync_playwright
import anthropic
import requests
import json
import time
import re
import os
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

CIDADES_CE = [
    "fortaleza","eusebio","maracanau","caucaia","juazeiro-do-norte",
    "sobral","crato","iguatu","horizonte","pacajus","aquiraz","russas"
]
CATEGORIAS = ["carros","motos","caminhoes","imoveis","equipamentos"]
URLS = [(f"https://leilo.com.br/leilao/{c}-ceara/{cat}", cat)
        for c in CIDADES_CE for cat in CATEGORIAS]

FIPE_API   = "https://parallelum.com.br/fipe/api/v1"
cliente_ia = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
ICONES     = {"carros":"🚗","motos":"🏍️","caminhoes":"🚛","imoveis":"🏠","equipamentos":"⚙️"}

# ─── CATEGORIZAÇÃO REAL ───────────────────────────────────────────────────────
PALAVRAS_MOTO = ['cg ','fan ','bros','titan','pcx','fazer','crosser','biz','lead',
                 'nxr','xre',' cargo','start','ybr','pop ','cb 3','ninja','factor',
                 'twister','burgman','nmax','lander','mt-','xtz','shineray','xy150',
                 'xy125','shi 175','biz','dominar','fz15']
PALAVRAS_CAMINHAO = ['fh ','fmx','constellation','actros','axor','atego','cargo truck',
                     'f-4000','sprinter','transit','master','daily','ducato','toco',
                     'truck','bi-truck','cavalo','carreta','reboque','semirreboque',
                     'randon','facchini','noma','guerra','librelato','volvo vm',
                     'volvo/fh','6x2t','re dl']
PALAVRAS_MAQUINA  = ['escavadeira','retroescavadeira','pa carregadeira','trator',
                     'empilhadeira','guindaste','munck','compactador','gerador',
                     'compressor','alinhador','balanceador','elevador','betoneira',
                     'motoniveladora','fotovoltaico','tkba','skf']
PALAVRAS_IMOVEL   = ['apartamento','casa ','terreno','lote ','sala comercial',
                     'galpao','barracão','prédio','sítio','fazenda','chácara',
                     'loja ','sobrado','cobertura','flat ','imóvel']

def detectar_categoria(modelo, marca, cat_url):
    nome = f"{marca} {modelo}".lower()
    if any(p in nome for p in PALAVRAS_IMOVEL):    return "imoveis"
    if any(p in nome for p in PALAVRAS_MAQUINA):   return "equipamentos"
    if any(p in nome for p in PALAVRAS_CAMINHAO):  return "caminhoes"
    if any(p in nome for p in PALAVRAS_MOTO):      return "motos"
    return cat_url

# ─── REFERÊNCIAS DE MERCADO ───────────────────────────────────────────────────
REFS = {
    "volvo fh": 350000, "volvo fm": 280000, "scania r": 320000,
    "mercedes actros": 300000, "mercedes axor": 220000, "mercedes atego": 180000,
    "iveco tector": 160000, "iveco daily": 120000, "ford cargo": 140000,
    "volkswagen constellation": 200000,
    "randon re dl": 90000, "randon reboque": 80000, "randon semirreboque": 100000,
    "facchini": 90000,
    "escavadeira": 300000, "retroescavadeira": 180000,
    "pa carregadeira": 250000, "trator": 120000,
    "empilhadeira": 60000, "gerador": 30000, "alinhador": 8000,
}

def buscar_referencia_mercado(marca, modelo):
    nome = f"{marca} {modelo}".lower()
    for k, v in REFS.items():
        if k in nome:
            return v, f"R$ {v:,.0f} (ref. mercado)"
    return 0, "Sem referência"

# ─── FIPE ─────────────────────────────────────────────────────────────────────
_STOPWORDS = {"de","da","do","dos","das","com","para","e","a","o","em","mt","cvt"}

def _score_modelo(fipe_nome: str, palavras: list) -> int:
    nome = fipe_nome.lower()
    return sum(1 for p in palavras if p in nome)

def buscar_fipe(marca, modelo, ano, categoria):
    if categoria in ["imoveis","equipamentos","caminhoes"]:
        return buscar_referencia_mercado(marca, modelo)
    endpoint = "motos" if categoria == "motos" else "carros"
    try:
        marcas = requests.get(f"{FIPE_API}/{endpoint}/marcas", timeout=8).json()
        marca_id = next((m["codigo"] for m in marcas if marca.lower() in m["nome"].lower()), None)
        if not marca_id: return 0, "Marca não encontrada"
        modelos_fipe = requests.get(f"{FIPE_API}/{endpoint}/marcas/{marca_id}/modelos", timeout=8).json()["modelos"]

        # Score-based matching: pontua cada variante e escolhe a mais específica
        palavras = [p for p in modelo.lower().split() if len(p) > 1 and p not in _STOPWORDS]
        scored = [(m, _score_modelo(m["nome"], palavras)) for m in modelos_fipe]
        scored = [(m, s) for m, s in scored if s > 0]
        if not scored: return 0, "Modelo não encontrado"
        # Maior pontuação; em empate, nome mais curto (variante mais simples)
        melhor = max(scored, key=lambda x: (x[1], -len(x[0]["nome"])))
        modelo_id = melhor[0]["codigo"]

        anos_f = requests.get(f"{FIPE_API}/{endpoint}/marcas/{marca_id}/modelos/{modelo_id}/anos", timeout=8).json()
        # Ano exato primeiro; depois ano mais próximo
        ano_id = next((a["codigo"] for a in anos_f if str(ano) in a["nome"]), None)
        if not ano_id:
            try:
                anos_num = [(abs(int(re.search(r'\d{4}', a["nome"]).group()) - ano), a["codigo"])
                            for a in anos_f if re.search(r'\d{4}', a["nome"])]
                ano_id = min(anos_num)[1] if anos_num else anos_f[0]["codigo"]
            except:
                ano_id = anos_f[0]["codigo"]

        dados = requests.get(f"{FIPE_API}/{endpoint}/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}", timeout=8).json()
        return float(dados["Valor"].replace("R$ ","").replace(".","").replace(",",".").strip()), dados["Valor"]
    except:
        return 0, "FIPE indisponível"

# ─── CLASSIFICAÇÃO ────────────────────────────────────────────────────────────
def classificar(lance, ref, estado):
    if estado in ["SINISTRADO","BATIDO","SUCATA"]: return "⚠️ INSPECIONAR"
    if ref == 0 or lance == 0: return "Sem referência"
    pct = (lance / ref) * 100
    if pct <= 50:   return "✅ ÓTIMO"
    elif pct <= 75: return "⚠️ MEDIANO"
    else:           return "❌ RUIM"

# ─── ANÁLISE IA ───────────────────────────────────────────────────────────────
def analisar(marca, modelo, ano, desc, km, lance, ref, categoria):
    try:
        pct = f"{round((lance/ref)*100,1)}% da referência" if ref > 0 and lance > 0 else "sem referência de preço"
        r = cliente_ia.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=400,
            messages=[{"role":"user","content":f"""Especialista em leilões no Brasil.
Item: {marca} {modelo} {ano} | Categoria: {categoria}
KM: {km or 'não informado'} | Lance: R$ {lance:,.0f} ({pct}) | Ref: R$ {ref:,.0f}
Descrição: {desc or 'sem descrição'}
REGRAS:
- Sinistrado/batido/sucata: calcule economia (ref - lance) e estime custo de reparo. Se economia > reparo, pode valer; se reparo ≈ economia, risco alto. Seja específico.
- Veículos bons: <=50%=ÓTIMO, 51-75%=BOA, >75%=REGULAR. Em leilão, 60-70% da FIPE já é bom negócio.
- Rec. financiamento: risco de alienação/restrição; oriente consulta ao cartório e leilão especializado.
- Para caminhões/equipamentos: use referência de mercado, avalie vida útil e custo de manutenção.
- Seja direto como consultor experiente de leilões; foco em ROI real do arrematante.
JSON apenas:
{{"estado":"BOM","selo":"🟢 Bom estado","oportunidade":"OTIMA","uso_sugerido":"revenda","positivos":["p1","p2"],"negativos":["n1","n2"],"avaliacao_plataforma":"análise direta de 1-2 linhas"}}
estado: BOM|BATIDO|SINISTRADO|RECUPERADO_FINANCIAMENTO|SUCATA|NAO_INFORMADO
selo: 🟢 Bom estado|🟡 Batido|🔴 Sinistrado|🔵 Rec. Financiamento|⚫ Sucata|⚪ Não informado
oportunidade: OTIMA|BOA|REGULAR|RUIM|INSPECIONAR"""}]
        )
        texto = r.content[0].text.strip()
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return json.loads(match.group() if match else texto)
    except:
        return {"estado":"NAO_INFORMADO","selo":"⚪ Não informado","oportunidade":"INSPECIONAR",
                "uso_sugerido":"verificar presencialmente","positivos":[],"negativos":[],
                "avaliacao_plataforma":"Sem dados. Recomendamos inspeção antes do leilão."}

def limpar_modelo(raw):
    m = unquote(raw)
    return re.sub(r'\(.*?\)', '', m).replace("-", " ").strip().title()

# ─── SCRAPER PRINCIPAL ────────────────────────────────────────────────────────
def raspar_leiloes():
    print("\n🚀 Scraper — Ceará | Todas as cidades e categorias\n")
    lotes, vistos = [], set()

    with sync_playwright() as p:
        browser    = p.chromium.launch(headless=True)
        ctx        = browser.new_context()
        pg_lista   = ctx.new_page()
        pg_detalhe = ctx.new_page()

        for url_base, cat_url in URLS:
            try:
                pg_lista.goto(url_base, timeout=15000, wait_until="domcontentloaded")
                pg_lista.wait_for_timeout(4000)
            except:
                continue

            # Rolar várias vezes para carregar todos os lotes dinâmicos
            for _ in range(5):
                pg_lista.keyboard.press("End")
                pg_lista.wait_for_timeout(2000)

            hrefs = []
            for link in pg_lista.query_selector_all('a'):
                try:
                    href = link.get_attribute('href') or ''
                    if '/leilao/' in href and 'ano.' in href and href not in vistos:
                        vistos.add(href); hrefs.append(href)
                except: continue

            if not hrefs: continue
            print(f"📡 {url_base.split('/leilao/')[1]} | {len(hrefs)} lotes")

            for href in hrefs[:30]:
                try:
                    pts      = href.strip('/').split('/')
                    cidade   = pts[1].replace("-ceara","").replace("-"," ").title() if len(pts)>1 else "?"
                    marca    = pts[3].title() if len(pts)>3 else "?"
                    modelo   = limpar_modelo(pts[4]) if len(pts)>4 else "?"
                    ano_str  = pts[5].replace("ano.","") if len(pts)>5 else "0"
                    ano      = int(ano_str) if ano_str.isdigit() else 0
                    url_lote = f"https://leilo.com.br{href}"
                    categoria = detectar_categoria(modelo, marca, cat_url)
                    icone     = ICONES.get(categoria, "📦")

                    try:
                        pg_detalhe.goto(url_lote, timeout=12000, wait_until="domcontentloaded")
                        pg_detalhe.wait_for_timeout(2000)
                        texto = pg_detalhe.inner_text('body')
                        html  = pg_detalhe.content()
                    except:
                        texto, html = "", ""

                    lance = 0
                    for m in re.findall(r'R\$\s*[\d]{1,3}(?:\.[\d]{3})*,[\d]{2}', texto):
                        try:
                            v = float(m.replace("R$","").replace(".","").replace(",",".").strip())
                            if v > 100: lance = min(lance, v) if lance > 0 else v
                        except: pass

                    foto = ""
                    for padrao in [r'https?://[^\s"\']+leilo\.cdndp\.com\.br[^\s"\']*\.(?:jpg|jpeg|png|webp)',
                                   r'https?://[^\s"\']+cdndp\.com\.br[^\s"\']*\.(?:jpg|jpeg|png|webp)']:
                        for f in re.findall(padrao, html, re.IGNORECASE):
                            if not any(x in f.lower() for x in ['logo','icon','avatar','banner']):
                                foto = f; break
                        if foto: break

                    km = ""
                    for m in re.findall(r'([\d]{2,3}\.[\d]{3})\s*km', texto, re.IGNORECASE):
                        if int(m.replace(".","")) >= 1000: km = f"{m} km"; break

                    descricao = ""
                    for linha in texto.split('\n'):
                        l = linha.strip()
                        if any(p in l.lower() for p in ['recuperado','sinistro','batido',
                               'financiamento','conservado','sucata','alienado']) and len(l) > 20:
                            descricao = l[:200]; break

                    ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                    analise  = analisar(marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                    classif  = classificar(lance, ref_val, analise.get("estado",""))

                    print(f"  {icone} [{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {analise['selo']} | {classif}")

                    lotes.append({
                        "categoria":            categoria,
                        "icone":                icone,
                        "marca":                marca,
                        "modelo":               modelo,
                        "ano":                  ano,
                        "cidade":               cidade + "/CE",
                        "lance_atual":          lance,
                        "fipe_valor":           ref_val,
                        "fipe_str":             ref_str,
                        "classificacao":        classif,
                        "foto":                 foto,
                        "km":                   km,
                        "descricao":            descricao,
                        "estado":               analise.get("estado","NAO_INFORMADO"),
                        "estado_selo":          analise.get("selo","⚪ Não informado"),
                        "oportunidade":         analise.get("oportunidade","INSPECIONAR"),
                        "uso_sugerido":         analise.get("uso_sugerido",""),
                        "positivos":            analise.get("positivos",[]),
                        "negativos":            analise.get("negativos",[]),
                        "avaliacao_plataforma": analise.get("avaliacao_plataforma",""),
                        "url":                  url_lote
                    })
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ⚠️ {e}"); continue

        ctx.close()
        browser.close()

    with open("leiloes.json","w",encoding="utf-8") as f:
        json.dump(lotes, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(lotes)} lotes salvos em leiloes.json")
    return lotes

if __name__ == "__main__":
    raspar_leiloes()
