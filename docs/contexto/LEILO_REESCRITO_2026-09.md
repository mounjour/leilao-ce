# Leilo — bug de categoria/nome de lote e vazamento de outro estado (2026-09-16)

Reportado pelo dono: no dashboard em produção, o filtro "Categoria: motos"
mostrava caminhões, "Categoria: caminhões" mostrava carros, e alguns nomes
de lote apareciam com texto estranho (ex.: "Leilao-De-Seguradoras-15-09-26
Honda Xre 300..." em vez de só "Honda Xre 300..."). Investigação encontrou
a causa raiz — e um problema mais sério além do relatado.

## Causa raiz: o site do Leilo mudou de estrutura

1. **A navegação por cidade+categoria parou de filtrar.** O scraper antigo
   pedia `https://leilo.com.br/leilao/{cidade}-ceara/{categoria}` (ex.:
   `.../eusebio-ceara/caminhoes`). Hoje esse formato **não filtra mais
   nada** — cai num feed genérico/nacional (testado ao vivo: `/motos` e
   `/caminhoes` devolviam exatamente os mesmos lotes, de cidades como
   Aparecida de Goiânia/GO, Taguatinga/DF, Alvorada/RS). Só
   `/leilao/{cidade}-ceara` **sem** sufixo de categoria continua
   funcionando como filtro de verdade — e hoje só existe **um** grupo de
   busca ativo pro Nordeste: `fortaleza-ceara` (cobre o pátio físico em
   Eusébio/CE; não há filtro fino por cidade do interior).
2. **A URL do lote ganhou um segmento novo.** Antes:
   `/leilao/{cidade}/{categoria}/{marca}/{modelo}/ano.NNNN`. Agora o site
   agrupa lotes por "leilão nomeado" (ex.:
   `leilao-de-seguradoras-15-09-26`), inserido **entre** a categoria e o
   veículo, que também passou a vir num slug só (marca+modelo juntos):
   `/leilao/{cidade}/{categoria}/{nome-do-leilao}/{marca-modelo}/ano.NNNN`.
   O parser antigo lia por índice fixo (`pts[3]` = marca, `pts[4]` =
   modelo) — com o segmento novo no meio, `pts[3]` virou o nome do leilão
   ("Leilao-De-Seguradoras-15-09-26") e `pts[4]` o slug marca+modelo
   inteiro. Daí o nome de lote esquisito (achado 2 do dono).

## O problema mais sério: lote de outro estado rotulado como CE

Como o problema 1 faz `/caminhoes`, `/motos` etc. caírem no feed nacional
sem filtro, e o scraper antigo **nunca validava a UF real do lote** (só
confiava que a URL pedida já tinha filtrado), lotes de **outros estados**
estavam sendo salvos no `leiloes.json` com `/CE` colado por engano.
Confirmado direto no arquivo em produção antes da correção:

```
{'Taguatinga Df/CE', 'Cuiaba Mt/CE', 'Candeias Ba/CE', 'Benevides Pa/CE',
 'Manaus Am/CE', 'Aparecida De Goiania Go/CE', 'Eusebio Ce/CE'}
```

Ou seja: usuário em Fortaleza via lote de Cuiabá/MT ou Taguatinga/DF como
se fosse do Ceará. Isso é mais grave que a categoria errada — é dado
geograficamente incorreto indo pro usuário final.

## Correção (`_raspar_leilo` reescrita)

- Uma única URL: `https://leilo.com.br/leilao/fortaleza-ceara` (sem
  sufixo de categoria).
- Site é **server-rendered** — confirmado com `requests.get()` cru, sem
  Playwright. Cada card da listagem já traz tudo que precisamos prontos:
  título como `"MARCA/MODELO"` (atributo `aria-label`/`title`, mais
  confiável que remontar da URL), UF (`cl__uf`), cidade (`cl__info--local`
  title), km, lance, data do leilão e foto. Não precisa mais abrir a
  página de detalhe por lote — scraper passou de Playwright pra "requests
  direto", junto com MJ/Receita SLE/Francisco Freitas/Grupo Lance.
- Categoria vem do **segmento da própria URL do lote**
  (`/leilao/{cidade}/{categoria}/...`), não de um valor "pedido" — a
  página é uma listagem só, não há mais o que pedir por categoria.
- **Rede de segurança contra o vazamento de outro estado**: cada card só
  é aceito se `cl__uf` = `"CE"` **e** a cidade (`cl__info--local`) termina
  em `/CE`. Se o filtro da URL cair de novo no futuro, os lotes de outro
  estado são descartados em vez de herdar `/CE` por engano — a mesma
  falha do parágrafo anterior não devia se repetir silenciosamente.
- Cobertura: 36 lotes/run no teste (antes o scraper tentava 60 URLs —
  12 cidades × 5 categorias — mas a maioria caía no mesmo feed genérico
  sem filtro, então o ganho real de cobertura daquele esquema já era
  ilusório). Não há paginação disponível nessa listagem (testado: query
  params `?pagina=`/`?page=`/scroll incremental não trazem lotes além dos
  ~36 iniciais, apesar do badge do site dizer "124 Lotes" — mismatch da
  própria UI do Leilo, não algo o scraper pode contornar sem descobrir o
  mecanismo real de paginação deles).
- Imóveis/equipamentos do Leilo vivem numa seção separada do site
  (`/leilao/imoveis`) e não passam por essa listagem — fora do escopo
  desta correção (o scraper antigo também nunca trouxe nenhum lote dessas
  categorias via Leilo, então não é uma regressão).

## Testes

`tests/test_scraper.py` — `TestLeiloParseListagem`, com HTML real
capturado em 16/09/2026 (um card de carro em CE) mais dois cards
sintéticos (moto em CE, carro em GO) pra cobrir o mapeamento de categoria
pela URL e a rede de segurança contra lote de outro estado.

## Pendência

O `leiloes.json` commitado ainda tem os dados antigos (com o vazamento de
outro estado) até o próximo run do GitHub Actions (`scraper.yml`, 1x/dia
às 06h UTC) ou um disparo manual (`workflow_dispatch`) regenerar o
arquivo com o scraper corrigido.
