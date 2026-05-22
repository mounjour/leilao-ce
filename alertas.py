import json
import os
import requests
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL         = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
EVOLUTION_URL        = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_KEY        = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE   = os.getenv("EVOLUTION_INSTANCE", "")


def _sb():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _format_phone(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if not digits:
        return ""
    if not digits.startswith("55"):
        digits = "55" + digits
    return digits


def send_whatsapp(phone: str, message: str) -> bool:
    number = _format_phone(phone)
    if not number or len(number) < 12:
        print(f"  Telefone inválido: {phone!r}")
        return False
    try:
        url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
        headers = {"apikey": EVOLUTION_KEY, "Content-Type": "application/json"}
        payload = {"number": number, "text": message}
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code in (200, 201):
            return True
        print(f"  Evolution API erro {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"  WhatsApp exception: {e}")
        return False


def build_message(lote: dict, old_lance: float, new_lance: float) -> str:
    diff_pct = ((new_lance - old_lance) / old_lance * 100) if old_lance > 0 else 0
    arrow = "▲" if new_lance > old_lance else "▼"
    marca  = lote.get("marca", "")
    modelo = lote.get("modelo", "")
    ano    = lote.get("ano", "")
    cidade = lote.get("cidade", "")
    url    = lote.get("url", "")
    fipe   = lote.get("fipe_valor", 0)
    pct_fipe = f"\n💡 {(new_lance/fipe*100):.0f}% da FIPE" if fipe > 0 else ""

    return (
        f"🚗 *LeilãoCE — Lance Atualizado*\n\n"
        f"*{marca} {modelo} {ano}*\n"
        f"📍 {cidade}\n\n"
        f"Lance anterior: R$ {old_lance:,.0f}\n"
        f"Lance atual: *R$ {new_lance:,.0f}* {arrow} {abs(diff_pct):.0f}%"
        f"{pct_fipe}\n\n"
        f"🔗 {url}"
    )


def run():
    missing = []
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        missing.append("Supabase credentials")
    if not EVOLUTION_URL or not EVOLUTION_KEY or not EVOLUTION_INSTANCE:
        missing.append("Evolution API credentials")
    if missing:
        print(f"[alertas] Pulando — faltam: {', '.join(missing)}")
        return

    if not os.path.exists("leiloes.json"):
        print("[alertas] leiloes.json não encontrado")
        return

    with open("leiloes.json", "r", encoding="utf-8") as f:
        lotes = json.load(f)

    current = {lote["url"]: lote for lote in lotes if lote.get("url")}
    if not current:
        print("[alertas] Nenhum lote atual")
        return

    sb = _sb()

    favs = sb.table("favorites").select("id, user_id, lote_url, lote_data").execute()
    if not favs.data:
        print("[alertas] Nenhum favorito cadastrado")
        return

    user_ids = list({row["user_id"] for row in favs.data})
    profiles = sb.table("profiles").select("id, phone").in_("id", user_ids).execute()
    phone_map = {row["id"]: row.get("phone", "") for row in (profiles.data or [])}

    sent = 0
    updated = 0

    for fav in favs.data:
        url        = fav["lote_url"]
        old_data   = fav["lote_data"] or {}
        old_lance  = float(old_data.get("lance_atual", 0))
        current_lot = current.get(url)

        if not current_lot:
            continue

        new_lance = float(current_lot.get("lance_atual", 0))

        if new_lance != old_lance and old_lance > 0 and new_lance > 0:
            phone = phone_map.get(fav["user_id"], "")
            print(f"  Lance mudou: {url[:60]} | {old_lance:.0f} → {new_lance:.0f}")
            if phone:
                msg = build_message(current_lot, old_lance, new_lance)
                if send_whatsapp(phone, msg):
                    sent += 1
                    print(f"  ✓ Alerta enviado para {phone[:4]}***")
            else:
                print(f"  Sem telefone para user {fav['user_id'][:8]}")

        if new_lance != old_lance and new_lance > 0:
            sb.table("favorites").update({"lote_data": current_lot})\
              .eq("id", fav["id"]).execute()
            updated += 1

    print(f"[alertas] Concluído — {sent} alertas enviados, {updated} favoritos atualizados")


if __name__ == "__main__":
    run()
