"""Testes de design_tokens.py (tokens --lce-* compartilhados com a landing)."""
from design_tokens import tokens_style


def test_envolve_em_style_e_traz_os_tokens_do_tema():
    css = tokens_style()
    assert css.startswith("<style>") and css.endswith("</style>")
    for token in ("--lce-bg", "--lce-surface", "--lce-text", "--lce-primary", "--lce-radius"):
        assert token in css


def test_tem_tema_escuro():
    assert "prefers-color-scheme: dark" in tokens_style()


def test_sem_linha_em_branco_que_viraria_bloco_de_codigo_no_markdown():
    assert "\n\n" not in tokens_style()
