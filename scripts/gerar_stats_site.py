"""Gera site/stats.json: numeros agregados e preco exibidos na landing estatica.

Roda no deploy (antes de copiar site/ para o Nginx). Nao expoe nenhum dado de
lote individual — so contagens, a data da ultima raspagem e o preco do plano.
A landing funciona sem esse arquivo (os mesmos valores vao como fallback no
HTML), entao a ausencia dele nao quebra a pagina.

Uso: python scripts/gerar_stats_site.py
"""
import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PRECO_PADRAO = "R$ 47"  # mesmo default de _PLAN_PRICE_LABEL em auth.py


def gerar_stats(lotes: list[dict], preco: str = PRECO_PADRAO) -> dict:
    """Agrega a lista de lotes em contagens publicas e a data da ultima coleta."""
    fontes = {lote.get("fonte") for lote in lotes if lote.get("fonte")}
    coletas = [lote["scraped_at"] for lote in lotes if lote.get("scraped_at")]
    return {
        "lotes": len(lotes),
        "fontes": len(fontes),
        "atualizado_em": max(coletas) if coletas else None,
        "preco": preco,
    }


def _preco_do_ambiente() -> str:
    """STRIPE_PLAN_PRICE_LABEL do ambiente ou do .env (mesma chave de auth.py)."""
    valor = os.getenv("STRIPE_PLAN_PRICE_LABEL")
    if not valor:
        from dotenv import dotenv_values

        valor = dotenv_values(RAIZ / ".env").get("STRIPE_PLAN_PRICE_LABEL")
    return (valor or PRECO_PADRAO).strip()


def main() -> None:
    arquivo = RAIZ / "leiloes.json"
    lotes = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else []
    stats = gerar_stats(lotes, _preco_do_ambiente())
    destino = RAIZ / "site" / "stats.json"
    destino.write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")
    print(f"{destino}: {stats}")


if __name__ == "__main__":
    main()
