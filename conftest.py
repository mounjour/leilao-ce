"""Configuracao de testes (pytest) na raiz do repo.

Faz duas coisas, nesta ordem, ANTES de qualquer teste importar `scraper`:

1. Garante a raiz do repo no `sys.path` (para `import scraper` funcionar a
   partir de `tests/`).
2. Substitui por stub as dependencias pesadas que `scraper.py` importa no topo
   do modulo (Playwright, anthropic, dotenv). Nenhuma delas e necessaria para
   exercitar as funcoes puras de parsing/classificacao, e o cliente Anthropic e
   instanciado em tempo de import — sem o stub, a suite exigiria browser e chave
   de API so para carregar o modulo.

Se algum dia `scraper.py` ganhar um novo `import` de biblioteca externa no topo
do arquivo, adicione o nome do modulo em `_MODULOS_STUB` abaixo.
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

_MODULOS_STUB = (
    "playwright",
    "playwright.sync_api",
    "playwright_stealth",
    "anthropic",
    "dotenv",
)

for _mod in _MODULOS_STUB:
    sys.modules.setdefault(_mod, MagicMock())
