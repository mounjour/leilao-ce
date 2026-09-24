"""Health check do scraper — pega fonte ativa que parou de render lote.

Contexto: o scraper roda 2x/dia e sobrescreve o leiloes.json. Se uma fonte
muda de site e o parser quebra, ela simplesmente para de aparecer no JSON e
ninguem nota (foi o que aconteceu com a Celso Cunha: 119 lotes/run ate 26/08,
0 por ~12 dias sem alarme). Este modulo mantem um placar por fonte em
scraper_health.json (commitado junto com o leiloes.json, porque o runner do
GitHub Actions e efemero) e, quando uma fonte que DEVERIA render fica N runs
seguidos com zero lote, loga um ::warning:: e manda um WhatsApp pro dono.

Alem da contagem, vigia a QUALIDADE dos campos-chave (lance e foto): se uma
fonte que costumava preenche-los passa a traze-los vazios em massa (caso do
Pacto em 21/09: 29 lotes, 0 com lance e 0 com foto, e a contagem sozinha nao
acusou), alerta igual.

Chamado no fim de raspar_leiloes() via processar(lotes) — best-effort, nunca
derruba o run. Tambem roda solto: `python scraper_health.py`.
"""
from __future__ import annotations

import collections
import json
import os
from datetime import datetime, timezone

_ARQUIVO = "scraper_health.json"

# Runs seguidos com 0 lote antes de alertar. Scraper roda 2x/dia -> 3 ~= 1,5 dia.
_LIMITE_STREAK = 3
# Enquanto a fonte seguir zerada, re-alerta a cada N runs (~1 semana) pra nao
# esquecer, sem mandar WhatsApp todo run.
_RENOTIFICAR_A_CADA = 14

# Campos-chave vigiados por fonte: nome -> predicado sobre o lote.
_CAMPOS = {
    "lance": lambda l: (l.get("lance_atual") or 0) > 0,
    "foto": lambda l: bool(l.get("foto")),
}
# So avalia a fonte se trouxe ao menos N lotes (amostra pequena oscila).
_MIN_LOTES_CAMPOS = 5
# Queda (fracao 0-1) sobre a taxa de referencia que conta como "vazio em
# massa", e taxa de referencia minima pro campo valer ser vigiado (campo que a
# fonte nunca preenche, ex. foto no Construbem, nao alerta).
_QUEDA_CAMPOS = 0.5
_REF_MIN_CAMPOS = 0.5
# Runs seguidos degradados antes de alertar (scraper roda 1x/dia).
_LIMITE_STREAK_CAMPOS = 2

# Fontes que se espera render lote todo run. Se uma destas zerar, alerta.
FONTES_ATIVAS = {
    "leilo", "mega", "pacto", "montenegro",
    "mj", "receita_sle", "francisco_freitas", "grupo_lance", "maria_fixer",
    "spy_leiloes",
}

# Fontes rastreadas mas que NAO disparam alerta ao ficar em zero — hoje nao
# produzem de proposito. Tirar daqui quando uma voltar a funcionar.
FONTES_ESPERADAS_ZERO = {
    "mgl",          # Cloudflare bloqueia o IP do runner (ver docs/contexto/MGL_SCRAPER_PENDENTE.md)
    "construbem",   # Zenrows sem credito
    "danielgarcia",  # ScraperAPI com timeout
    "celsocunha",   # dormente — site reconstruido, sem leilao ativo (ver docs/contexto/CELSO_CUNHA_DORMENTE.md)
    "pereira",      # leiloeiro unico de leiloes municipais, cadencia de semanas/
                    # meses entre leiloes (normal, nao e fonte quebrada) — ver
                    # docs/contexto/PEREIRA_LEILOES_ADICIONADO.md. Promover pra
                    # FONTES_ATIVAS se a cadencia se mostrar mais constante.
}


def _agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _registro_novo() -> dict:
    return {
        "zero_streak": 0,
        "ultima_contagem": 0,
        "ultimo_nonzero": None,
        "alertado_streak": 0,
    }


def carregar_estado(arquivo: str = _ARQUIVO) -> dict:
    """Le scraper_health.json. Retorna estado vazio se ausente ou corrompido."""
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            estado = json.load(f)
        if not isinstance(estado, dict):
            raise ValueError("estrutura inesperada")
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        estado = {}
    estado.setdefault("fontes", {})
    return estado


def salvar_estado(estado: dict, arquivo: str = _ARQUIVO) -> None:
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2, sort_keys=True)


def aplicar_run(estado: dict, contagem: dict, *, agora: str | None = None) -> dict:
    """Atualiza as streaks por fonte com a contagem deste run. Funcao pura
    (muta e devolve o mesmo dict). Nao envia nada."""
    agora = agora or _agora()
    fontes = estado.setdefault("fontes", {})
    conhecidas = set(fontes) | set(contagem) | FONTES_ATIVAS | FONTES_ESPERADAS_ZERO
    for fonte in conhecidas:
        n = int(contagem.get(fonte, 0))
        reg = fontes.setdefault(fonte, _registro_novo())
        reg["ultima_contagem"] = n
        if n > 0:
            reg["zero_streak"] = 0
            reg["ultimo_nonzero"] = agora
            reg["alertado_streak"] = 0
        else:
            reg["zero_streak"] = int(reg.get("zero_streak", 0)) + 1
    estado["ultimo_run"] = agora
    return estado


def taxas_de_campos(lotes: list) -> dict:
    """Por fonte: {"n": total de lotes, "lance": fracao 0-1, "foto": fracao 0-1}."""
    grupos = collections.defaultdict(list)
    for l in lotes:
        if isinstance(l, dict):
            grupos[l.get("fonte") or "?"].append(l)
    return {
        fonte: {"n": len(ls),
                **{c: sum(1 for l in ls if pred(l)) / len(ls) for c, pred in _CAMPOS.items()}}
        for fonte, ls in grupos.items()
    }


def aplicar_campos(estado: dict, taxas: dict) -> dict:
    """Atualiza, por fonte ativa e campo, a taxa de referencia (ultima taxa
    saudavel) e a streak de degradacao. Pura (muta e devolve o dict)."""
    fontes = estado.setdefault("fontes", {})
    for fonte in FONTES_ATIVAS:
        t = taxas.get(fonte)
        if not t or t["n"] < _MIN_LOTES_CAMPOS:
            continue  # sem amostra suficiente: nao mexe no estado
        campos = fontes.setdefault(fonte, _registro_novo()).setdefault("campos", {})
        for campo in _CAMPOS:
            taxa = round(t[campo], 3)
            c = campos.setdefault(campo, {"ref": taxa, "degradado_streak": 0, "alertado_streak": 0})
            ref = float(c.get("ref", taxa))
            c["taxa"] = taxa
            if ref >= _REF_MIN_CAMPOS and taxa <= ref - _QUEDA_CAMPOS:
                c["degradado_streak"] = int(c.get("degradado_streak", 0)) + 1  # ref fica congelada
            else:
                c["ref"] = taxa
                c["degradado_streak"] = 0
                c["alertado_streak"] = 0
    return estado


def alvos_de_campos(estado: dict) -> list[tuple[str, str, float, float, int]]:
    """(fonte, campo, ref, taxa, streak) que merecem alerta AGORA (mesma regra
    de primeira vez / re-notificacao periodica de alvos_de_alerta)."""
    alvos = []
    for fonte, reg in sorted(estado.get("fontes", {}).items()):
        if fonte in FONTES_ESPERADAS_ZERO:
            continue
        for campo, c in sorted(reg.get("campos", {}).items()):
            streak = int(c.get("degradado_streak", 0))
            if streak < _LIMITE_STREAK_CAMPOS:
                continue
            ja = int(c.get("alertado_streak", 0))
            if ja == 0 or (streak - ja) >= _RENOTIFICAR_A_CADA:
                alvos.append((fonte, campo, float(c["ref"]), float(c["taxa"]), streak))
    return alvos


def alvos_de_alerta(estado: dict) -> list[tuple[str, int]]:
    """Fontes cuja streak de zero merece alerta AGORA: cruzou o limite pela
    primeira vez, ou re-notificacao periodica. Ignora as esperadas-zero."""
    alvos = []
    for fonte, reg in sorted(estado.get("fontes", {}).items()):
        if fonte in FONTES_ESPERADAS_ZERO:
            continue
        streak = int(reg.get("zero_streak", 0))
        if streak < _LIMITE_STREAK:
            continue
        ja = int(reg.get("alertado_streak", 0))
        if ja == 0 or (streak - ja) >= _RENOTIFICAR_A_CADA:
            alvos.append((fonte, streak))
    return alvos


def _montar_mensagem(alvos: list[tuple[str, int]]) -> str:
    linhas = "\n".join(f"- {fonte}: {streak} runs seguidos sem lote"
                       for fonte, streak in alvos)
    return (
        "🩺 *Achadin Leilões — scraper*\n\n"
        f"{len(alvos)} fonte(s) que deveriam render estão zeradas:\n{linhas}\n\n"
        "Provável mudança no site da fonte. Ver os logs do GitHub Actions."
    )


def _montar_mensagem_campos(alvos: list) -> str:
    linhas = "\n".join(
        f"- {fonte}: {campo} preenchido em {taxa:.0%} dos lotes (antes {ref:.0%}), {streak} runs"
        for fonte, campo, ref, taxa, streak in alvos
    )
    return (
        "🩺 *Achadin Leilões — scraper*\n\n"
        f"{len(alvos)} campo(s) vieram vazios em massa:\n{linhas}\n\n"
        "Provável mudança de layout no site da fonte. Ver os logs do GitHub Actions."
    )


def _enviar_whatsapp(mensagem: str) -> None:
    telefone = os.getenv("OWNER_WHATSAPP", "").strip()
    if not telefone:
        print("[scraper_health] OWNER_WHATSAPP não configurado — só ::warning::, sem WhatsApp.")
        return
    try:
        from alertas import send_whatsapp  # import tardio: só quando há alerta
        send_whatsapp(telefone, mensagem, origem="scraper_health")
    except Exception as exc:
        print(f"[scraper_health] não foi possível enviar WhatsApp: {exc}")


def processar(lotes: list, *, arquivo: str = _ARQUIVO) -> int:
    """Conta os lotes por fonte, atualiza o placar, e alerta se preciso.
    Retorna o número de fontes em alerta. Best-effort: não levanta."""
    contagem = collections.Counter(
        (l.get("fonte") or "?") for l in lotes if isinstance(l, dict)
    )
    estado = carregar_estado(arquivo)
    aplicar_run(estado, contagem)
    aplicar_campos(estado, taxas_de_campos(lotes))
    alvos = alvos_de_alerta(estado)
    alvos_c = alvos_de_campos(estado)

    if alvos:
        nomes = [f for f, _ in alvos]
        print(f"::warning::scraper_health: {len(alvos)} fonte(s) ativa(s) zerada(s): {nomes}")
        _enviar_whatsapp(_montar_mensagem(alvos))
        for fonte, streak in alvos:
            estado["fontes"][fonte]["alertado_streak"] = streak
    if alvos_c:
        resumo = [f"{f}.{c}" for f, c, *_ in alvos_c]
        print(f"::warning::scraper_health: {len(alvos_c)} campo(s) vazio(s) em massa: {resumo}")
        _enviar_whatsapp(_montar_mensagem_campos(alvos_c))
        for fonte, campo, _ref, _taxa, streak in alvos_c:
            estado["fontes"][fonte]["campos"][campo]["alertado_streak"] = streak
    if not alvos and not alvos_c:
        ativas_ok = sum(
            1 for f in FONTES_ATIVAS
            if estado["fontes"].get(f, {}).get("ultima_contagem", 0) > 0
        )
        print(f"[scraper_health] OK — {ativas_ok}/{len(FONTES_ATIVAS)} fontes ativas com lote neste run.")

    salvar_estado(estado, arquivo)
    return len(alvos) + len(alvos_c)


if __name__ == "__main__":
    try:
        with open("leiloes.json", "r", encoding="utf-8") as f:
            _lotes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[scraper_health] leiloes.json ilegível: {exc}")
        raise SystemExit(0)
    processar(_lotes)
