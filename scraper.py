from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from datetime import datetime, timedelta
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
_IA_ATIVA = True  # circuit breaker: False quando créditos esgotam

_FALLBACK_IA = {"estado":"NAO_INFORMADO","selo":"⚪ Não informado","oportunidade":"INSPECIONAR",
                "uso_sugerido":"verificar presencialmente","positivos":[],"negativos":[],
                "avaliacao_plataforma":"Sem dados. Recomendamos inspeção antes do leilão."}

def analisar(marca, modelo, ano, desc, km, lance, ref, categoria):
    global _IA_ATIVA
    if not _IA_ATIVA:
        return _FALLBACK_IA
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
    except Exception as e:
        msg = str(e)
        if "credit balance is too low" in msg or "insufficient_quota" in msg:
            _IA_ATIVA = False
            print("  ⚠️ IA desativada: créditos Anthropic esgotados. Recarregue em console.anthropic.com")
        else:
            print(f"  ⚠️ IA error: {e}")
        return _FALLBACK_IA

def limpar_modelo(raw):
    m = unquote(raw)
    return re.sub(r'\(.*?\)', '', m).replace("-", " ").strip().title()

def _lote_dict(fonte, categoria, marca, modelo, ano, cidade, lance,
               ref_val, ref_str, classif, foto, km, descricao, analise, url, data_leilao=""):
    return {
        "fonte":                fonte,
        "categoria":            categoria,
        "icone":                ICONES.get(categoria, "📦"),
        "marca":                marca,
        "modelo":               modelo,
        "ano":                  ano,
        "cidade":               cidade,
        "lance_atual":          lance,
        "fipe_valor":           ref_val,
        "fipe_str":             ref_str,
        "classificacao":        classif,
        "foto":                 foto,
        "km":                   km,
        "descricao":            descricao,
        "estado":               analise.get("estado", "NAO_INFORMADO"),
        "estado_selo":          analise.get("selo", "⚪ Não informado"),
        "oportunidade":         analise.get("oportunidade", "INSPECIONAR"),
        "uso_sugerido":         analise.get("uso_sugerido", ""),
        "positivos":            analise.get("positivos", []),
        "negativos":            analise.get("negativos", []),
        "avaliacao_plataforma": analise.get("avaliacao_plataforma", ""),
        "url":                  url,
        "data_leilao":          data_leilao,
    }

def _extrair_lance(texto):
    # Retorna o PRIMEIRO valor >= 500 encontrado no texto.
    # Evita pegar incrementos/taxas pequenas (que aparecem depois do lance real).
    for m in re.findall(r'R\$[\xa0\s]*[\d]{1,3}(?:\.[\d]{3})*,[\d]{2}', texto):
        try:
            v = float(m.replace("R$","").replace("\xa0","").replace(" ","")
                       .replace(".","").replace(",",".").strip())
            if v >= 500:
                return v
        except:
            pass
    # fallback: qualquer valor > 100
    for m in re.findall(r'R\$[\xa0\s]*[\d]{1,3}(?:\.[\d]{3})*,[\d]{2}', texto):
        try:
            v = float(m.replace("R$","").replace("\xa0","").replace(" ","")
                       .replace(".","").replace(",",".").strip())
            if v > 100:
                return v
        except:
            pass
    return 0

def _extrair_foto(html, dominios=('cdndp.com.br',)):
    for dom in dominios:
        pat = rf'https?://[^\s"\']+{re.escape(dom)}[^\s"\']*\.(?:jpg|jpeg|png|webp)'
        for f in re.findall(pat, html, re.IGNORECASE):
            if not any(x in f.lower() for x in ['logo','icon','avatar','banner','no-image']):
                return f
    return ""

def _extrair_km(texto):
    for m in re.findall(r'([\d]{2,3}\.[\d]{3})\s*km', texto, re.IGNORECASE):
        if int(m.replace(".","")) >= 1000:
            return f"{m} km"
    return ""

def _extrair_descricao(texto):
    for linha in texto.split('\n'):
        l = linha.strip()
        if any(p in l.lower() for p in ['recuperado','sinistro','batido',
               'financiamento','conservado','sucata','alienado']) and len(l) > 20:
            return l[:200]
    return ""

_MESES_PT = {
    'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,
    'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12,
}

def _extrair_data_leilao(texto):
    # Mega: "1ª Praça: 28/05/2026 às 10:30"
    m = re.search(r'1[ªa]\s*Pra[çc]a:\s*(\d{2}/\d{2}/\d{4})\s*[àa]s?\s*(\d{2}:\d{2})', texto, re.IGNORECASE)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M").strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Pacto: "Finaliza em 18h3m42s"
    m = re.search(r'Finaliza em\s*(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', texto, re.IGNORECASE)
    if m and any(m.group(i) for i in range(1, 4)):
        try:
            dt = datetime.now() + timedelta(
                hours=int(m.group(1) or 0),
                minutes=int(m.group(2) or 0),
                seconds=int(m.group(3) or 0)
            )
            return dt.strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Leilo: countdown "X dias Y horas Z min" (ou "X dia Y hora")
    m = re.search(r'(\d+)\s*dia[s]?\D{1,10}(\d+)\s*hora[s]?\D{1,10}(\d+)\s*min', texto, re.IGNORECASE)
    if m:
        try:
            dt = datetime.now() + timedelta(
                days=int(m.group(1)), hours=int(m.group(2)), minutes=int(m.group(3))
            )
            return dt.strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Leilo: countdown "X dias Y horas" (sem minutos)
    m = re.search(r'(\d+)\s*dia[s]?\D{1,10}(\d+)\s*hora[s]?', texto, re.IGNORECASE)
    if m:
        try:
            dt = datetime.now() + timedelta(days=int(m.group(1)), hours=int(m.group(2)))
            return dt.strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Genérico: "DD de mês de YYYY ... HH:MM"
    m = re.search(
        r'(\d{1,2})\s+de\s+(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4}).*?(\d{2}:\d{2})',
        texto, re.IGNORECASE | re.DOTALL
    )
    if m:
        try:
            mes = _MESES_PT.get(m.group(2).lower().replace('ç','c'), 0)
            if mes:
                dt = datetime(int(m.group(3)), mes, int(m.group(1)),
                              int(m.group(4)[:2]), int(m.group(4)[3:]))
                return dt.strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Genérico: "DD/MM/YYYY" próximo de horário — texto completo, aceita multilinha
    m = re.search(r'(\d{2}/\d{2}/\d{4})\D{0,30}(\d{2}:\d{2})', texto, re.DOTALL)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M").strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    return ""

# ─── SCRAPER LEILO.COM.BR ─────────────────────────────────────────────────────
def _raspar_leilo(pg_lista, pg_detalhe, vistos):
    lotes = []
    for url_base, cat_url in URLS:
        try:
            pg_lista.goto(url_base, timeout=15000, wait_until="domcontentloaded")
            pg_lista.wait_for_timeout(4000)
        except:
            continue

        for _ in range(5):
            pg_lista.keyboard.press("End")
            pg_lista.wait_for_timeout(2000)

        # Extrai data do evento da listagem — fallback para todos os lotes desta página
        try:
            data_evento = _extrair_data_leilao(pg_lista.inner_text('body'))
        except:
            data_evento = ""

        hrefs = []
        for link in pg_lista.query_selector_all('a'):
            try:
                href = link.get_attribute('href') or ''
                if '/leilao/' in href and 'ano.' in href and href not in vistos:
                    vistos.add(href); hrefs.append(href)
            except:
                continue

        if not hrefs:
            continue
        print(f"📡 Leilo {url_base.split('/leilao/')[1]} | {len(hrefs)} lotes")

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

                try:
                    pg_detalhe.goto(url_lote, timeout=12000, wait_until="domcontentloaded")
                    pg_detalhe.wait_for_timeout(2000)
                    texto = pg_detalhe.inner_text('body')
                    html  = pg_detalhe.content()
                except:
                    texto, html = "", ""

                lance     = _extrair_lance(texto)
                foto      = _extrair_foto(html, ('leilo.cdndp.com.br', 'cdndp.com.br'))
                km        = _extrair_km(texto)
                descricao = _extrair_descricao(texto)

                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = analisar(marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado",""))

                icone = ICONES.get(categoria, "📦")
                data_leilao = _extrair_data_leilao(texto) or data_evento
                print(f"  {icone} [Leilo/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {analise['selo']} | {classif} | {data_leilao or 'sem data'}")

                lotes.append(_lote_dict("leilo", categoria, marca, modelo, ano,
                                        cidade+"/CE", lance, ref_val, ref_str,
                                        classif, foto, km, descricao, analise, url_lote, data_leilao))
                time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠️ Leilo: {e}"); continue

    return lotes

# ─── SCRAPER MEGA LEILÕES ─────────────────────────────────────────────────────
_MEGA_URLS = [
    "https://www.megaleiloes.com.br/veiculos/ce",
    "https://www.megaleiloes.com.br/imoveis/ce",
]
_MEGA_CAT = {
    "carros":"carros","motos":"motos","caminhoes":"caminhoes","pesados":"caminhoes",
    "casas":"imoveis","imoveis":"imoveis","imoveis-comerciais":"imoveis",
    "terrenos":"imoveis","apartamentos":"imoveis","predios":"imoveis",
}

def _parse_mega_lot(href, titulo):
    path   = href.replace("https://www.megaleiloes.com.br","").split("?")[0]
    parts  = [p for p in path.split("/") if p]
    tipo   = parts[0] if parts else "veiculos"
    subcat = parts[1] if len(parts) > 1 else "carros"
    cidade = parts[3].replace("-"," ").title() if len(parts) > 3 else "?"
    slug   = parts[4] if len(parts) > 4 else ""

    categoria = "imoveis" if tipo == "imoveis" else _MEGA_CAT.get(subcat, "carros")

    if categoria == "imoveis":
        return categoria, cidade, "Imóvel", titulo, 0

    slug = re.sub(r'-[a-z]\d+$', '', slug)
    slug = re.sub(r'^(?:carro|moto|caminhao|veiculo)-', '', slug)

    ano = 0
    m8 = re.search(r'(\d{4})(\d{4})', slug)
    if m8:
        ano  = int(m8.group(2))
        slug = slug.replace(m8.group(0), "").strip("-")
    else:
        m4 = re.search(r'(\d{4})', slug)
        if m4 and 1980 <= int(m4.group(1)) <= 2030:
            ano  = int(m4.group(1))
            slug = slug.replace(m4.group(0), "").strip("-")

    parts_s = [p for p in slug.split("-") if p]
    marca  = parts_s[0].title() if parts_s else "?"
    modelo = " ".join(p.title() for p in parts_s[1:]) if len(parts_s) > 1 else "?"
    return categoria, cidade, marca, modelo, ano

def _raspar_mega(pg, vistos):
    lotes = []
    for url_base in _MEGA_URLS:
        for pagina in range(1, 15):
            url = f"{url_base}?pagina={pagina}"
            try:
                pg.goto(url, timeout=15000, wait_until="networkidle")
                pg.wait_for_timeout(2000)
            except:
                break

            cards = pg.query_selector_all('.card.open')
            if not cards:
                break
            print(f"📡 Mega {url_base.split('/')[-1]} p.{pagina} | {len(cards)} cards")

            for card in cards:
                try:
                    title_el = card.query_selector('.card-title')
                    price_el = card.query_selector('.card-price')
                    img_el   = card.query_selector('.card-image')
                    if not title_el:
                        continue

                    href = (title_el.get_attribute('href') or '').split('?')[0]
                    if not href or href in vistos:
                        continue
                    vistos.add(href)

                    titulo    = title_el.inner_text().strip()
                    preco_str = price_el.inner_text().strip() if price_el else ""
                    lance     = _extrair_lance(preco_str) or _extrair_lance(pg.inner_text('body'))

                    foto = ""
                    if img_el:
                        bg = img_el.get_attribute('data-bg') or ""
                        if bg and 'no-image' not in bg:
                            foto = bg

                    categoria, cidade, marca, modelo, ano = _parse_mega_lot(href, titulo)
                    icone = ICONES.get(categoria, "📦")

                    ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                    analise = analisar(marca, modelo, ano, "", "", lance, ref_val, categoria)
                    classif = classificar(lance, ref_val, analise.get("estado",""))

                    data_leilao = _extrair_data_leilao(card.inner_text())
                    print(f"  {icone} [Mega/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
                    lotes.append(_lote_dict("mega", categoria, marca, modelo, ano,
                                            f"{cidade}/CE", lance, ref_val, ref_str,
                                            classif, foto, "", "", analise, href, data_leilao))
                    time.sleep(0.3)
                except Exception as e:
                    print(f"  ⚠️ Mega: {e}"); continue

    return lotes

# ─── SCRAPER PACTO LEILÕES ────────────────────────────────────────────────────
_PACTO_CIDADES = ["fortaleza","eusebio","maracanau","caucaia","horizonte",
                  "pacajus","aquiraz","russas","juazeiro-do-norte","sobral"]
_PACTO_CAT_MAP = {
    "carros":"carros","motos":"motos","pesados":"caminhoes",
    "utilitarios":"caminhoes","sucatas":"carros","imoveis":"imoveis",
}

def _raspar_pacto(pg, _pg_d, vistos):
    lotes = []
    for cidade in _PACTO_CIDADES:
        url_base = f"https://www.pactoleiloes.com.br/leilao/{cidade}-ceara"
        try:
            pg.goto(url_base, timeout=20000, wait_until="networkidle")
            pg.wait_for_timeout(2000)
        except:
            continue

        for _ in range(6):
            pg.keyboard.press("End")
            pg.wait_for_timeout(700)

        # Concatena todos os textos de links com mesmo href (preço, km, data ficam juntos)
        items = pg.eval_on_selector_all(
            'a[href*="/leilao/"][href*="/ano."]',
            '''els => Object.entries(
                els.reduce((acc, e) => {
                    const h = e.href;
                    acc[h] = (acc[h] || "") + " " + e.innerText.trim();
                    return acc;
                }, {})
            ).map(([href, text]) => ({href, text: text.trim()}))'''
        )
        novos = [it for it in items if it['href'] not in vistos and '/ano.' in it['href']]
        for it in novos:
            vistos.add(it['href'])

        if not novos:
            continue
        print(f"📡 Pacto {cidade} | {len(novos)} lotes")

        for it in novos[:50]:
            href = it['href']
            try:
                pts       = href.replace('https://www.pactoleiloes.com.br','').strip('/').split('/')
                if len(pts) < 6:
                    continue
                cidade_s  = pts[1].replace("-ceara","").replace("-"," ").title()
                cat_url   = pts[2]
                marca     = pts[3].title() if len(pts) > 3 else "?"
                modelo    = limpar_modelo(pts[4]) if len(pts) > 4 else "?"
                ano_str   = pts[5].replace("ano.","") if len(pts) > 5 else "0"
                ano       = int(ano_str) if ano_str.isdigit() else 0
                categoria = detectar_categoria(modelo, marca, _PACTO_CAT_MAP.get(cat_url, cat_url))
                icone     = ICONES.get(categoria, "📦")

                # Extrai lance do texto do card (sem navegar ao detalhe)
                lance = _extrair_lance(it['text'])
                km    = _extrair_km(it['text'])

                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = analisar(marca, modelo, ano, "", km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado",""))

                data_leilao = _extrair_data_leilao(it['text'])
                print(f"  {icone} [Pacto/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {analise['selo']} | {classif}")
                lotes.append(_lote_dict("pacto", categoria, marca, modelo, ano,
                                        f"{cidade_s}/CE", lance, ref_val, ref_str,
                                        classif, "", km, "", analise, href, data_leilao))
                time.sleep(0.1)
            except Exception as e:
                print(f"  ⚠️ Pacto: {e}"); continue

    return lotes

# ─── SCRAPER CONSTRUBEM ───────────────────────────────────────────────────────
_CONSTRUBEM_BASES = [
    "https://construbemleiloes.plataformasoleon.com.br",
    "https://www.construbemleiloes.com.br",
]
_CONSTRUBEM_PATHS = ["/lotes", "/leiloes", "/veiculos", "/imoveis", "/"]

def _raspar_construbem(pg_lista, pg_detalhe, vistos):
    lotes = []
    # Aplica stealth nas duas páginas para tentar passar pelo Cloudflare
    try:
        stealth_sync(pg_lista)
        stealth_sync(pg_detalhe)
    except Exception as e:
        print(f"  ⚠️ Construbem stealth: {e}")

    for base in _CONSTRUBEM_BASES:
        encontrou = False
        for path in _CONSTRUBEM_PATHS:
            url = base + path
            try:
                pg_lista.goto(url, timeout=20000, wait_until="domcontentloaded")
                pg_lista.wait_for_timeout(5000)  # aguarda JS renderizar
            except Exception as e:
                print(f"  ⚠️ Construbem goto {url}: {e}")
                continue

            for _ in range(6):
                pg_lista.keyboard.press("End")
                pg_lista.wait_for_timeout(800)

            url_final = pg_lista.url
            print(f"📡 Construbem | tentou={url} | final={url_final}")

            # Coleta hrefs — tenta padrão Soleon e padrões genéricos BR
            hrefs = []
            todos_hrefs = []
            for link in pg_lista.query_selector_all('a[href]'):
                try:
                    href = link.get_attribute('href') or ''
                    full = href if href.startswith('http') else base + href
                    todos_hrefs.append(href)
                    if full in vistos:
                        continue
                    if re.search(r'/(lote[s]?|veiculo[s]?|bem[s]?|imovel|imoveis|produto[s]?|item[s]?)/\S', href, re.I):
                        hrefs.append(full)
                        vistos.add(full)
                except:
                    continue

            if not hrefs:
                texto = pg_lista.inner_text('body')
                # Mostra amostra de links encontrados para diagnóstico
                amostra = [h for h in todos_hrefs if h and not h.startswith('#')][:10]
                print(f"  [diag] links={amostra}")
                print(f"  [diag] texto={texto[:300].replace(chr(10), ' ')}")
                continue

            print(f"  {len(hrefs)} lotes encontrados")
            encontrou = True

            for url_lote in hrefs[:40]:
                try:
                    try:
                        pg_detalhe.goto(url_lote, timeout=15000, wait_until="domcontentloaded")
                        pg_detalhe.wait_for_timeout(2000)
                        texto = pg_detalhe.inner_text('body')
                        html  = pg_detalhe.content()
                    except:
                        texto, html = "", ""

                    # Tenta extrair marca/modelo do slug da URL
                    slug = re.sub(r'\?.*', '', url_lote).rstrip('/').split('/')[-1]
                    slug = re.sub(r'-\d+$', '', slug)           # remove ID numérico final
                    palavras = [p for p in slug.split('-') if p]
                    marca  = palavras[0].title() if palavras else "?"
                    modelo = ' '.join(p.title() for p in palavras[1:3]) if len(palavras) > 1 else "?"

                    # Ano no slug ou no texto
                    ano = 0
                    m = re.search(r'\b(19[89]\d|20[012]\d)\b', slug + ' ' + texto[:500])
                    if m:
                        ano = int(m.group())

                    # Cidade
                    cidade = "CE"
                    for c in CIDADES_CE:
                        if c.replace('-', ' ') in texto.lower():
                            cidade = c.replace('-', ' ').title() + '/CE'
                            break

                    lance      = _extrair_lance(texto)
                    foto       = _extrair_foto(html, ('construbem', 'soleon', 's3.amazonaws', 'cloudfront'))
                    km         = _extrair_km(texto)
                    descricao  = _extrair_descricao(texto)
                    data_leilao = _extrair_data_leilao(texto)

                    categoria = detectar_categoria(modelo, marca, "carros")
                    icone     = ICONES.get(categoria, "📦")

                    ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                    analise  = analisar(marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                    classif  = classificar(lance, ref_val, analise.get("estado", ""))

                    print(f"  {icone} [Construbem/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif} | {data_leilao or 'sem data'}")
                    lotes.append(_lote_dict("construbem", categoria, marca, modelo, ano,
                                           cidade, lance, ref_val, ref_str,
                                           classif, foto, km, descricao, analise, url_lote, data_leilao))
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ⚠️ Construbem: {e}")
                    continue

            break  # achou lotes neste path, não tenta o próximo

        if encontrou:
            break  # achou no primeiro base, não tenta o segundo

    return lotes

# ─── SCRAPER DANIEL GARCIA LEILÕES ───────────────────────────────────────────
_DG_BASE  = "https://www.danielgarcialeiloes.com.br"
_DG_PATHS = [
    "/leiloes?estado=CE", "/leiloes?uf=ce", "/leiloes/ceara",
    "/veiculos?estado=CE", "/lotes?estado=CE", "/leiloes", "/",
]

def _raspar_daniel_garcia(pg_lista, pg_detalhe, vistos):
    lotes = []
    try:
        stealth_sync(pg_lista)
        stealth_sync(pg_detalhe)
    except Exception as e:
        print(f"  ⚠️ DanielGarcia stealth: {e}")

    for path in _DG_PATHS:
        url = _DG_BASE + path
        try:
            pg_lista.goto(url, timeout=20000, wait_until="domcontentloaded")
            pg_lista.wait_for_timeout(5000)
        except Exception as e:
            print(f"  ⚠️ DanielGarcia goto {url}: {e}")
            continue

        for _ in range(5):
            pg_lista.keyboard.press("End")
            pg_lista.wait_for_timeout(800)

        url_final = pg_lista.url
        print(f"📡 DanielGarcia | tentou={url} | final={url_final}")

        # Filtra somente lotes com CE no texto (pode ser nacional)
        hrefs = []
        todos_hrefs = []
        for link in pg_lista.query_selector_all('a[href]'):
            try:
                href = link.get_attribute('href') or ''
                full = href if href.startswith('http') else _DG_BASE + href
                todos_hrefs.append(href)
                if full in vistos:
                    continue
                if re.search(r'/(lote[s]?|lot[s]?|veiculo[s]?|bem[s]?|item[s]?|produto[s]?)/\S', href, re.I):
                    hrefs.append(full)
                    vistos.add(full)
            except:
                continue

        if not hrefs:
            texto = pg_lista.inner_text('body')
            amostra = [h for h in todos_hrefs if h and not h.startswith('#')][:10]
            print(f"  [diag] links={amostra}")
            print(f"  [diag] texto={texto[:300].replace(chr(10), ' ')}")
            continue

        # Filtra somente lotes com referência a CE/Ceará
        hrefs_ce = [h for h in hrefs if any(
            c in h.lower() for c in ['ceara', 'fortaleza', '/ce/', '-ce-', '-ce/']
        )] or hrefs  # se não achou filtro CE, usa todos (podem não ter CE na URL)

        print(f"  {len(hrefs_ce)} lotes CE de {len(hrefs)} totais")

        for url_lote in hrefs_ce[:40]:
            try:
                try:
                    pg_detalhe.goto(url_lote, timeout=15000, wait_until="domcontentloaded")
                    pg_detalhe.wait_for_timeout(2000)
                    texto = pg_detalhe.inner_text('body')
                    html  = pg_detalhe.content()
                except:
                    texto, html = "", ""

                # Verifica se o lote é do CE
                if texto and not any(c in texto.lower() for c in ['ceará', 'ceara', 'fortaleza',
                    'caucaia', 'maracanau', 'juazeiro', 'sobral', 'crato']):
                    continue

                slug    = re.sub(r'\?.*', '', url_lote).rstrip('/').split('/')[-1]
                slug    = re.sub(r'-\d+$', '', slug)
                palavras = [p for p in slug.split('-') if p]
                marca   = palavras[0].title() if palavras else "?"
                modelo  = ' '.join(p.title() for p in palavras[1:3]) if len(palavras) > 1 else "?"

                ano = 0
                m = re.search(r'\b(19[89]\d|20[012]\d)\b', slug + ' ' + texto[:500])
                if m:
                    ano = int(m.group())

                cidade = "CE"
                for c in CIDADES_CE:
                    if c.replace('-', ' ') in texto.lower():
                        cidade = c.replace('-', ' ').title() + '/CE'
                        break

                lance      = _extrair_lance(texto)
                foto       = _extrair_foto(html, ('danielgarcia', 's3.amazonaws', 'cloudfront'))
                km         = _extrair_km(texto)
                descricao  = _extrair_descricao(texto)
                data_leilao = _extrair_data_leilao(texto)

                categoria = detectar_categoria(modelo, marca, "carros")
                icone     = ICONES.get(categoria, "📦")

                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = analisar(marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado", ""))

                print(f"  {icone} [DanielGarcia/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif} | {data_leilao or 'sem data'}")
                lotes.append(_lote_dict("danielgarcia", categoria, marca, modelo, ano,
                                        cidade, lance, ref_val, ref_str,
                                        classif, foto, km, descricao, analise, url_lote, data_leilao))
                time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠️ DanielGarcia: {e}")
                continue

        break  # achou lotes, não tenta próximo path

    return lotes

# ─── SCRAPER PRINCIPAL ────────────────────────────────────────────────────────
def raspar_leiloes():
    print("\n🚀 Scraper — Ceará | Leilo + Mega + Pacto + DanielGarcia\n")
    lotes, vistos = [], set()

    with sync_playwright() as p:
        browser    = p.chromium.launch(headless=True)
        ctx        = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )
        pg_lista   = ctx.new_page()
        pg_detalhe = ctx.new_page()

        lotes += _raspar_leilo(pg_lista, pg_detalhe, vistos)
        lotes += _raspar_mega(pg_lista, vistos)
        lotes += _raspar_pacto(pg_lista, pg_detalhe, vistos)
        # Construbem bloqueado por Cloudflare nos IPs do GitHub Actions
        # lotes += _raspar_construbem(pg_lista, pg_detalhe, vistos)
        lotes += _raspar_daniel_garcia(pg_lista, pg_detalhe, vistos)

        ctx.close()
        browser.close()

    with open("leiloes.json","w",encoding="utf-8") as f:
        json.dump(lotes, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(lotes)} lotes salvos em leiloes.json")
    return lotes

if __name__ == "__main__":
    raspar_leiloes()
