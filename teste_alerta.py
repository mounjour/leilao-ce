"""
Script de teste dos alertas WhatsApp.
Uso: python teste_alerta.py <telefone>
Ex:  python teste_alerta.py 85999999999
"""
import json
import os
import sys
from dotenv import load_dotenv
from alertas import send_whatsapp, _sb, build_message

load_dotenv()


def test_whatsapp(phone: str):
    print(f"\n[1/3] Enviando mensagem de teste para {phone}...")
    msg = (
        "✅ *LeilãoCE — Teste de Alerta*\n\n"
        "Alertas configurados com sucesso!\n\n"
        "Você receberá uma mensagem como esta sempre que o lance "
        "de um lote favoritado mudar. 🚗"
    )
    ok = send_whatsapp(phone, msg)
    print("  ✓ Mensagem enviada!" if ok else "  ✗ Falhou — verifique as credenciais Evolution API")
    return ok


def test_supabase():
    print("\n[2/3] Verificando favoritos no Supabase...")
    try:
        sb = _sb()
        favs = sb.table("favorites").select("id, user_id, lote_url, lote_data").execute()
        count = len(favs.data or [])
        print(f"  ✓ {count} favorito(s) encontrado(s)")
        return favs.data or []
    except Exception as e:
        print(f"  ✗ Erro Supabase: {e}")
        return []


def test_alert_simulation(phone: str, favs: list):
    print("\n[3/3] Simulando mudança de lance...")
    if not os.path.exists("leiloes.json"):
        print("  ✗ leiloes.json não encontrado")
        return

    with open("leiloes.json", "r", encoding="utf-8") as f:
        lotes = json.load(f)

    if not lotes:
        print("  ✗ leiloes.json está vazio")
        return

    lote = lotes[0]
    lance_atual = lote.get("lance_atual", 0)
    lance_fake  = lance_atual * 0.85  # simula queda de 15%

    print(f"  Lote: {lote.get('marca')} {lote.get('modelo')}")
    print(f"  Lance simulado: R$ {lance_fake:,.0f} → R$ {lance_atual:,.0f}")

    msg = build_message(lote, lance_fake, lance_atual)
    ok = send_whatsapp(phone, msg)
    print("  ✓ Alerta simulado enviado!" if ok else "  ✗ Falhou")


if __name__ == "__main__":
    phone = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TEST_PHONE", "")
    if not phone:
        print("Uso: python teste_alerta.py <telefone>")
        print("Ex:  python teste_alerta.py 85999999999")
        sys.exit(1)

    print("=" * 50)
    print("LeilãoCE — Teste de Alertas WhatsApp")
    print("=" * 50)

    ok = test_whatsapp(phone)
    favs = test_supabase()
    if ok:
        test_alert_simulation(phone, favs)

    print("\n" + "=" * 50)
    print("Teste concluído.")
