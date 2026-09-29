"""Validacao temporaria do _raspar_mgl no Actions (remover depois)."""
import os, sys
sys.path.insert(0, ".")
os.environ.pop("ANTHROPIC_API_KEY", None)
import scraper
lotes = scraper._raspar_mgl(None, set())
print("TOTAL", len(lotes))
for l in lotes[:20]:
    print(l.get("categoria"), l.get("marca"), l.get("modelo"), l.get("lance_atual"), l.get("valor_referencia"), l.get("data_leilao"))
