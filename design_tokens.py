"""Tokens de design (--lce-*) compartilhados entre a landing e o Streamlit.

A fonte unica e site/css/tokens.css: a landing o carrega por <link>; o app o
injeta inline por aqui. Mudar uma cor naquele arquivo muda site e app juntos.
Sem dependencia de streamlit, para ser testavel isoladamente.
"""
from functools import lru_cache
from pathlib import Path

_TOKENS_CSS = Path(__file__).resolve().parent / "site" / "css" / "tokens.css"


@lru_cache(maxsize=1)
def tokens_style() -> str:
    """Retorna um bloco <style> com os tokens, pronto para st.markdown(unsafe_allow_html=True).

    Linhas em branco sao removidas: no st.markdown, uma linha em branco seguida
    de linha indentada vira bloco de codigo e quebraria o CSS.
    """
    linhas = _TOKENS_CSS.read_text(encoding="utf-8").splitlines()
    css = "\n".join(linha for linha in linhas if linha.strip())
    return f"<style>\n{css}\n</style>"
