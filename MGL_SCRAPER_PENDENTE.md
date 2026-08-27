# MGL Leilões — scraper quebrado (investigação de 2026-08-27)

`_raspar_mgl` em `scraper.py` retorna **0 lotes** em produção há semanas.
Log do GitHub Actions: `⚠️ MGL listagem: Page.wait_for_selector: Timeout
30000ms exceeded` esperando `.dg-leiloes-item`.

Esta investigação foi feita ao vivo pelo Browser pane contra o site real.
Ainda **não corrigido** — fix é de várias etapas e envolve decisão de
infra (Zenrows). Documentado aqui pra retomar depois.

## O que foi descoberto

### 1. A URL de busca do scraper está obsoleta

`_MGL_BUSCA_VEICULOS_CE` hoje é:

```
https://www.mgl.com.br/busca/#Engine=StartMGL&modelo=Ve%C3%ADculos&estado=23&Pagina=0&PaginaIndex=1&
```

O site trocou o esquema de parâmetros do hash. Formato atual (tirado dos
links reais do menu do site):

```
https://www.mgl.com.br/busca/#Engine=Start&Pagina=1&Busca=&Mapa=&ID_Categoria=<N>
```

Mudanças:

| Antigo | Atual |
|---|---|
| `Engine=StartMGL` | `Engine=Start` |
| `modelo=Veículos` | removido — agora é `ID_Categoria=<N>` |
| `estado=23` | **não existe mais como parâmetro de hash** (ver item 3) |

IDs de categoria observados no menu:

| ID_Categoria | Rótulo |
|---|---|
| 88 | CARROS E MOTOS |
| 108 | Carros |
| 116 | Motos |
| 117 | Caminhonetes |
| 189 | CAMINHÕES, ÔNIBUS E VANS |
| 223 | MÁQUINAS PESADAS & AGRÍCOLAS |
| 226 | IMÓVEIS |

### 2. O seletor `.dg-leiloes-item` continua existindo

Não foi renomeado. Com a URL nova (`#Engine=Start&...&ID_Categoria=88`)
a página renderiza 24 `.dg-leiloes-item` normalmente e mostra
"Encontrados (3374) resultados". O timeout de 30s acontece porque a URL
antiga não retorna resultado nenhum, não porque o seletor sumiu.

URLs de lote agora são `https://www.mgl.com.br/lote/ferro/<id>/`
(antes `/lote/<id>/`). O `a[href*="/lote/"]` do scraper ainda casa.

### 3. Filtro de estado (Ceará) — ainda não resolvido

- O select de estado na página ainda usa **código 23 = Ceará**
  (`23=Ceará` nas `<option>`).
- Mas passar `&ID_Estado=23` no hash **não filtra** — testado ao vivo:
  continua "Encontrados (3374)" com resultados de MG/PE/SP.
- `window.JsonParametrosBusca` (objeto de filtros da SPA) fica com
  `ID_Estado: 0` mesmo com `ID_Estado=23` no hash → a página não lê esse
  parâmetro do hash. Os campos que ela parece ler são `ID_Categoria`,
  `Pagina`, `Busca`, `Mapa`.
- Existe um `<input type="hidden" id="Mapa" name="Mapa">` e a API Google
  Maps é carregada — o filtro geográfico atual pode passar por `Mapa=`
  (formato desconhecido) ou por um POST à API `apiplugin/GetBusca/...`.
- **Próximo passo:** abrir `/busca/`, selecionar "Ceará" no filtro de
  estado pela UI e capturar (a) como o hash muda e (b) o payload da
  chamada XHR `apiplugin/GetBusca`. Aí dá pra montar a URL/He request
  correta.

### 4. Provável bloqueio no runner do GitHub Actions

`document.documentElement.innerHTML` tem referência a Cloudflare. No
Browser pane (IP residencial, Chrome real) a página renderiza sem
desafio. No runner do GHA (IP de datacenter) o timeout de 30s pode ser
**bloqueio de WAF/Cloudflare**, mesma classe do problema do Daniel
Garcia/Construbem (que só dá 403/402 a partir do IP dos runners — ver
`project-scraper-sources-status` na memória).

Não dá pra confirmar isso do Browser pane. Formas de checar:
- rodar `_raspar_mgl` isolado a partir de um IP de datacenter, ou
- adicionar um dump de `page.content()` no `except` do `_raspar_mgl` e
  olhar o HTML que o runner recebe no próximo run agendado.

## Plano de correção (quando for retomado)

1. Descobrir via UI o parâmetro real de filtro por estado (item 3) e
   atualizar `_MGL_BUSCA_VEICULOS_CE` — provavelmente uma URL por
   categoria (carros/motos, caminhões, máquinas), como as outras fontes.
2. Trocar `wait_until`/espera: a SPA carrega os itens por XHR após o
   `domcontentloaded`. Ou esperar o texto "Encontrados (" aparecer, ou
   dar um scroll (padrão Montenegro em `_scroll_ate_carregar_todos`).
3. Se o item 4 se confirmar (bloqueio no runner): rotear a listagem
   pelo Zenrows quando `ZENROWS_API_KEY` estiver setada — reaproveitar
   o padrão já usado em `_raspar_soleon`. **Depende do crédito Zenrows
   estar recarregado** (hoje está zerado — retorna HTTP 402).
4. Revalidar o parser da página de detalhe (`MARCA/MODELO:`,
   `ANO/MODELO:`, `img[src*="/imagens-complete/"]`) contra a página
   `/lote/ferro/<id>/` atual — pode ter mudado junto.
