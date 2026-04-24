import os
import time
import re
import requests
import anthropic
from datetime import datetime

# ============================================================

# CONFIGURATION

# ============================================================

TELEGRAM_TOKEN    = os.getenv(“TELEGRAM_TOKEN”, “TON_TOKEN_ICI”)
CHAT_ID           = os.getenv(“CHAT_ID”, “TON_CHAT_ID_ICI”)
ANTHROPIC_API_KEY = os.getenv(“ANTHROPIC_API_KEY”, “TA_CLE_ICI”)

# APIs gratuites

ETHERSCAN_API_KEY  = os.getenv(“ETHERSCAN_API_KEY”, “”)   # etherscan.io — gratuit
BSCSCAN_API_KEY    = os.getenv(“BSCSCAN_API_KEY”, “”)     # bscscan.com  — gratuit

# ============================================================

# PARAMÈTRES

# ============================================================

SCAN_INTERVAL      = 90       # Scan toutes les 90 secondes
TOP_N_COINS        = 500      # Scanner le top 500
COINS_PER_PAGE     = 100      # CoinGecko max par page
BUY_THRESHOLD_24H  = 4.0      # Alerte achat si +4% en 24h
SELL_THRESHOLD_24H = -4.0     # Alerte vente si -4% en 24h
BUY_THRESHOLD_1H   = 2.5      # Alerte achat rapide si +2.5% en 1h
SELL_THRESHOLD_1H  = -2.5     # Alerte vente rapide si -2.5% en 1h
RSI_BUY            = 33
RSI_SELL           = 70
ALERT_COOLDOWN     = 1800     # 30 min entre alertes par coin
TOP_PICKS_INTERVAL = 3600     # Rapport “meilleures cryptos” toutes les heures

# ============================================================

# STATE

# ============================================================

client            = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
last_alert_time   = {}
last_top_picks    = 0
last_update_id    = 0         # Pour lire les commandes Telegram
all_prices_cache  = {}        # Cache du dernier scan

# ============================================================

# TELEGRAM — Envoi

# ============================================================

def send_telegram(text: str, chat_id: str = None, parse_mode: str = “HTML”):
cid = chat_id or CHAT_ID
url = f”https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage”
# Telegram limite à 4096 chars par message
chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
for chunk in chunks:
try:
requests.post(url, json={
“chat_id”: cid,
“text”: chunk,
“parse_mode”: parse_mode,
“disable_web_page_preview”: True
}, timeout=10)
time.sleep(0.3)
except Exception as e:
print(f”[TELEGRAM ERROR] {e}”)

# ============================================================

# TELEGRAM — Lire les commandes entrantes

# ============================================================

def get_updates() -> list:
global last_update_id
try:
url = f”https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates”
r = requests.get(url, params={“offset”: last_update_id + 1, “timeout”: 5}, timeout=10)
data = r.json()
updates = data.get(“result”, [])
if updates:
last_update_id = updates[-1][“update_id”]
return updates
except:
return []

def process_commands(updates: list):
for update in updates:
msg = update.get(“message”, {})
text = msg.get(“text”, “”).strip()
chat_id = str(msg.get(“chat”, {}).get(“id”, “”))
if not text or not chat_id:
continue

```
    print(f"[CMD] '{text}' from {chat_id}")

    if text.startswith("/start") or text.startswith("/aide"):
        handle_start(chat_id)
    elif text.startswith("/top"):
        handle_top(chat_id, text)
    elif text.startswith("/analyse "):
        symbol = text.replace("/analyse ", "").strip().upper()
        handle_analyse(chat_id, symbol)
    elif text.startswith("/fraude ") or text.startswith("/check "):
        address = text.split(" ", 1)[1].strip() if " " in text else ""
        handle_fraud(chat_id, address)
    elif text.startswith("/meilleur"):
        handle_best_now(chat_id)
    elif text.startswith("/marche") or text.startswith("/marché"):
        handle_market(chat_id)
    elif text.startswith("/scan"):
        handle_scan_status(chat_id)
    else:
        # Réponse libre via IA
        handle_free_question(chat_id, text)
```

# ============================================================

# COMMANDES

# ============================================================

def handle_start(chat_id: str):
send_telegram(””“🤖 <b>CryptoMind Bot v2 — Commandes disponibles</b>

📊 <b>Analyses</b>
/analyse BTC — Analyse détaillée d’une crypto
/top 10 — Top 10 cryptos du moment (par défaut: 5)
/meilleur — LA meilleure crypto où investir maintenant
/marché — État général du marché

🕵️ <b>Sécurité</b>
/fraude 0x… — Vérifie si une adresse/contrat est une arnaque
/check 0x… — Même chose (alias)

📡 <b>Surveillance</b>
/scan — Statut du scan en cours

💬 <b>Questions libres</b>
Pose n’importe quelle question crypto et l’IA répond !
Ex: “C’est quoi la différence entre BTC et ETH ?”

⚠️ <i>Pas un conseil financier — toujours faire ses propres recherches</i>”””, chat_id)

def handle_top(chat_id: str, text: str):
# Extraire le nombre demandé
parts = text.split()
n = 5
for p in parts:
if p.isdigit():
n = min(int(p), 20)
break

```
send_telegram(f"🔍 Analyse du Top {n} en cours... (données réelles)", chat_id)

if not all_prices_cache:
    send_telegram("⏳ Le scan initial est en cours, réessaie dans 30 secondes.", chat_id)
    return

# Trier par score combiné
scored = []
for cid, d in all_prices_cache.items():
    score = score_coin(d)
    scored.append((score, d))
scored.sort(reverse=True)

top = scored[:n]
lines = []
for i, (score, d) in enumerate(top, 1):
    arrow = "🟢" if d["change_24h"] >= 0 else "🔴"
    lines.append(
        f"{i}. {arrow} <b>{d['symbol']}</b> — {fmt_price(d['price'])}\n"
        f"   📈 1h: {d['change_1h']:+.1f}%  24h: {d['change_24h']:+.1f}%  7j: {d['change_7d']:+.1f}%\n"
        f"   🎯 Score IA: {score}/100"
    )

msg = f"🏆 <b>TOP {n} CRYPTOS DU MOMENT</b>\n<i>Sur {len(all_prices_cache)} cryptos analysées</i>\n\n"
msg += "\n\n".join(lines)
msg += f"\n\n<i>Mis à jour le {datetime.now().strftime('%d/%m à %H:%M')}</i>"
send_telegram(msg, chat_id)
```

def handle_analyse(chat_id: str, symbol: str):
send_telegram(f”🧠 Analyse de <b>{symbol}</b> en cours…”, chat_id)

```
coin = next((d for d in all_prices_cache.values() if d["symbol"] == symbol), None)
if not coin:
    send_telegram(f"❌ Crypto <b>{symbol}</b> non trouvée dans le top 500. Vérifie le symbole (ex: BTC, ETH, SOL).", chat_id)
    return

analysis = deep_analyze_coin(coin)
send_telegram(analysis, chat_id)
```

def handle_fraud(chat_id: str, address: str):
if not address or len(address) < 10:
send_telegram(“❌ Fournis une adresse valide.\nEx: /fraude 0x742d35Cc6634C0532925a3b8D4C9a1C3a1C6a3b”, chat_id)
return

```
send_telegram(f"🕵️ Analyse de l'adresse en cours...\n<code>{address}</code>", chat_id)
result = check_fraud(address)
send_telegram(result, chat_id)
```

def handle_best_now(chat_id: str):
send_telegram(“🔎 Recherche de la meilleure opportunité du moment…”, chat_id)
if not all_prices_cache:
send_telegram(“⏳ Scan en cours, réessaie dans 30 secondes.”, chat_id)
return
result = find_best_opportunity()
send_telegram(result, chat_id)

def handle_market(chat_id: str):
send_telegram(“📊 Récupération des données marché…”, chat_id)
result = get_market_overview()
send_telegram(result, chat_id)

def handle_scan_status(chat_id: str):
n = len(all_prices_cache)
alerts = sum(1 for t in last_alert_time.values() if time.time() - t < 3600)
send_telegram(
f”📡 <b>STATUT DU SCAN</b>\n\n”
f”✅ Cryptos surveillées : <b>{n}/500</b>\n”
f”🔔 Alertes (dernière heure) : <b>{alerts}</b>\n”
f”⏱ Intervalle : <b>{SCAN_INTERVAL}s</b>\n”
f”🕐 Dernière mise à jour : <b>{datetime.now().strftime(’%H:%M:%S’)}</b>”, chat_id)

def handle_free_question(chat_id: str, question: str):
try:
msg = client.messages.create(
model=“claude-haiku-4-5-20251001”,
max_tokens=400,
system=“Tu es CryptoMind, expert crypto. Réponds en français, de façon concise (3-5 phrases max). Toujours mentionner les risques. Pas de conseil financier certifié.”,
messages=[{“role”: “user”, “content”: question}]
)
send_telegram(f”🧠 {msg.content[0].text}”, chat_id)
except:
send_telegram(“⚠️ IA temporairement indisponible.”, chat_id)

# ============================================================

# COINGECKO — Top 500 (5 pages de 100)

# ============================================================

def fetch_top_500() -> dict:
result = {}
pages = TOP_N_COINS // COINS_PER_PAGE  # = 5 pages

```
for page in range(1, pages + 1):
    url = (
        f"https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd"
        f"&order=market_cap_desc"
        f"&per_page={COINS_PER_PAGE}"
        f"&page={page}"
        f"&sparkline=false"
        f"&price_change_percentage=1h,24h,7d"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        for coin in r.json():
            result[coin["id"]] = {
                "id":         coin["id"],
                "name":       coin["name"],
                "symbol":     coin["symbol"].upper(),
                "price":      coin["current_price"] or 0,
                "change_1h":  coin.get("price_change_percentage_1h_in_currency") or 0,
                "change_24h": coin.get("price_change_percentage_24h") or 0,
                "change_7d":  coin.get("price_change_percentage_7d_in_currency") or 0,
                "volume":     coin.get("total_volume") or 0,
                "market_cap": coin.get("market_cap") or 0,
                "high_24h":   coin.get("high_24h") or 0,
                "low_24h":    coin.get("low_24h") or 0,
                "rank":       coin.get("market_cap_rank") or 999,
            }
        print(f"[✓] Page {page}/5 récupérée ({len(result)} coins)")
        time.sleep(1.2)  # Respecter le rate limit CoinGecko gratuit
    except Exception as e:
        print(f"[COINGECKO PAGE {page} ERROR] {e}")
        time.sleep(5)

return result
```

# ============================================================

# SCORE D’UN COIN (0-100)

# ============================================================

def score_coin(d: dict) -> int:
score = 50
c1h   = d[“change_1h”]
c24h  = d[“change_24h”]
c7d   = d[“change_7d”]
vol   = d[“volume”]
mc    = d[“market_cap”]
rank  = d[“rank”]

```
# Momentum haussier
if c1h > 0:   score += min(c1h * 3, 15)
if c24h > 0:  score += min(c24h * 2, 12)
if c7d > 0:   score += min(c7d * 1, 8)

# Momentum baissier
if c1h < 0:   score += max(c1h * 3, -15)
if c24h < 0:  score += max(c24h * 2, -12)

# Volume élevé = bonne liquidité
if vol > 1_000_000_000:   score += 8
elif vol > 100_000_000:   score += 4

# Market cap = fiabilité
if mc > 10_000_000_000:   score += 5
elif mc < 10_000_000:     score -= 10  # Micro-cap = risqué

# Rang
if rank <= 10:   score += 5
elif rank > 200: score -= 5

return max(0, min(100, int(score)))
```

# ============================================================

# ANALYSE PROFONDE D’UN COIN via IA

# ============================================================

def deep_analyze_coin(d: dict) -> str:
rsi = estimate_rsi(d[“change_24h”], d[“change_1h”])
score = score_coin(d)
signal = “ACHAT” if score >= 65 else “VENTE” if score <= 35 else “NEUTRE”

```
prompt = f"""Analyse complète de {d['name']} ({d['symbol']}).
```

DONNÉES RÉELLES :
Prix: ${d[‘price’]:,.6f} | Rang: #{d[‘rank’]}
Variation 1h: {d[‘change_1h’]:+.2f}% | 24h: {d[‘change_24h’]:+.2f}% | 7j: {d[‘change_7d’]:+.2f}%
Volume 24h: ${d[‘volume’]:,.0f} | Market Cap: ${d[‘market_cap’]:,.0f}
RSI estimé: {rsi} | Score IA: {score}/100 | Signal: {signal}
Plus haut 24h: ${d[‘high_24h’]:,.6f} | Plus bas 24h: ${d[‘low_24h’]:,.6f}

Fournis en français :

1. Signal clair : ACHETER / VENDRE / ATTENDRE
1. Analyse technique (2-3 points)
1. Prix d’entrée suggéré
1. Objectif de prix (target)
1. Stop-loss recommandé
1. Risque principal à surveiller
1. Horizon conseillé (1h / 24h / 7j)

Sois direct et précis.”””

```
try:
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    analysis = msg.content[0].text
except:
    analysis = "Analyse IA indisponible."

signal_emoji = "🟢" if signal == "ACHAT" else "🔴" if signal == "VENTE" else "🟡"

return (
    f"📊 <b>ANALYSE — {d['name']} ({d['symbol']})</b>\n"
    f"Rang #{d['rank']} | Score: {score}/100\n\n"
    f"💰 Prix: <b>{fmt_price(d['price'])}</b>\n"
    f"📈 1h: {d['change_1h']:+.2f}%  |  24h: {d['change_24h']:+.2f}%  |  7j: {d['change_7d']:+.2f}%\n"
    f"📉 RSI estimé: {rsi}  |  Volume: ${d['volume']/1e6:.1f}M\n\n"
    f"{signal_emoji} <b>Signal: {signal}</b>\n\n"
    f"🧠 <b>Analyse IA :</b>\n{analysis}\n\n"
    f"<i>⚠️ Pas un conseil financier</i>"
)
```

# ============================================================

# MEILLEURE OPPORTUNITÉ DU MOMENT

# ============================================================

def find_best_opportunity() -> str:
if not all_prices_cache:
return “⏳ Données non disponibles.”

```
# 3 catégories : court terme (1h), moyen terme (24h), value (score)
by_1h    = sorted(all_prices_cache.values(), key=lambda d: d["change_1h"], reverse=True)
by_24h   = sorted(all_prices_cache.values(), key=lambda d: d["change_24h"], reverse=True)
by_score = sorted(all_prices_cache.values(), key=lambda d: score_coin(d), reverse=True)

best_1h    = by_1h[0]
best_24h   = by_24h[0]
best_score = by_score[0]

# Demander à l'IA de choisir le meilleur parmi les 3
prompt = f"""Tu es un expert en trading crypto. Voici les 3 meilleures opportunités détectées parmi 500 cryptos :
```

🚀 Meilleure 1h : {best_1h[‘name’]} ({best_1h[‘symbol’]})
Prix: ${best_1h[‘price’]:,.4f} | +{best_1h[‘change_1h’]:.1f}% en 1h | {best_1h[‘change_24h’]:+.1f}% en 24h

📈 Meilleure 24h : {best_24h[‘name’]} ({best_24h[‘symbol’]})
Prix: ${best_24h[‘price’]:,.4f} | {best_24h[‘change_1h’]:+.1f}% en 1h | +{best_24h[‘change_24h’]:.1f}% en 24h

🏆 Meilleur score global : {best_score[‘name’]} ({best_score[‘symbol’]})
Prix: ${best_score[‘price’]:,.4f} | {best_score[‘change_1h’]:+.1f}% en 1h | {best_score[‘change_24h’]:+.1f}% en 24h

Dis en 4 phrases max :

1. Quelle crypto choisir parmi les 3 et pourquoi
1. Si c’est pour investir dans l’heure (très court terme)
1. Un prix d’entrée et un objectif concret
1. Le risque principal

Réponds en français, sois direct.”””

```
try:
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=350,
        messages=[{"role": "user", "content": prompt}]
    )
    ai_pick = msg.content[0].text
except:
    ai_pick = "Analyse IA indisponible."

return (
    f"🏆 <b>MEILLEURE OPPORTUNITÉ MAINTENANT</b>\n"
    f"<i>Parmi {len(all_prices_cache)} cryptos analysées</i>\n\n"
    f"🚀 <b>Top 1h :</b> {best_1h['symbol']} {best_1h['change_1h']:+.1f}%\n"
    f"📈 <b>Top 24h :</b> {best_24h['symbol']} {best_24h['change_24h']:+.1f}%\n"
    f"🏅 <b>Top score :</b> {best_score['symbol']} ({score_coin(best_score)}/100)\n\n"
    f"🧠 <b>Recommandation IA :</b>\n{ai_pick}\n\n"
    f"<i>⚠️ Investissement court terme = risque élevé</i>"
)
```

# ============================================================

# DÉTECTION DE FRAUDE

# ============================================================

def check_fraud(address: str) -> str:
address = address.strip()
results = []
is_eth  = address.startswith(“0x”) and len(address) == 42
is_sol  = len(address) in [43, 44] and not address.startswith(“0x”)
is_btc  = address.startswith((“1”, “3”, “bc1”)) and 25 <= len(address) <= 62

```
# ---- Détection type d'adresse ----
if is_eth:
    chain = "Ethereum / BSC"
    results.append(f"🔗 Réseau détecté : <b>Ethereum / BNB Chain</b>")
elif is_sol:
    chain = "Solana"
    results.append(f"🔗 Réseau détecté : <b>Solana</b>")
elif is_btc:
    chain = "Bitcoin"
    results.append(f"🔗 Réseau détecté : <b>Bitcoin</b>")
else:
    results.append("❓ Format d'adresse non reconnu")
    chain = "inconnu"

# ---- Vérification Etherscan (contrats ETH/BSC) ----
etherscan_data = {}
if is_eth and ETHERSCAN_API_KEY:
    try:
        # Vérifier si c'est un contrat
        r = requests.get(
            "https://api.etherscan.io/api",
            params={"module":"contract","action":"getabi","address":address,"apikey":ETHERSCAN_API_KEY},
            timeout=10
        )
        data = r.json()
        if data.get("status") == "1":
            results.append("📄 Adresse : <b>Contrat intelligent (smart contract)</b>")
            etherscan_data["is_contract"] = True
        else:
            results.append("👤 Adresse : <b>Portefeuille classique</b>")
            etherscan_data["is_contract"] = False

        # Vérifier les transactions
        r2 = requests.get(
            "https://api.etherscan.io/api",
            params={"module":"account","action":"txlist","address":address,
                    "startblock":0,"endblock":99999999,"sort":"desc","apikey":ETHERSCAN_API_KEY},
            timeout=10
        )
        txdata = r2.json()
        if txdata.get("status") == "1":
            txs = txdata.get("result", [])
            etherscan_data["tx_count"] = len(txs)
            results.append(f"📊 Transactions trouvées : <b>{len(txs)}</b>")
            # Chercher des patterns suspects
            failed = sum(1 for tx in txs if tx.get("isError") == "1")
            if failed > len(txs) * 0.3 and len(txs) > 5:
                results.append(f"⚠️ Taux d'échec élevé : <b>{failed}/{len(txs)} transactions échouées</b>")
                etherscan_data["suspicious"] = True
    except Exception as e:
        results.append(f"⚠️ Etherscan indisponible : {e}")

# ---- Vérification via base de données scam connue (GoPlus) ----
goplus_risk = None
if is_eth:
    try:
        r = requests.get(
            f"https://api.gopluslabs.io/api/v1/address_security/{address}",
            timeout=10
        )
        gp = r.json()
        if gp.get("code") == 1:
            res = gp.get("result", {})
            flags = []
            if res.get("cybercrime") == "1":       flags.append("🚨 Cybercriminalité")
            if res.get("money_laundering") == "1": flags.append("🚨 Blanchiment d'argent")
            if res.get("phishing_activities") == "1": flags.append("🚨 Phishing détecté")
            if res.get("blacklist_doubt") == "1":  flags.append("⚠️ Liste noire")
            if res.get("stealing_attack") == "1":  flags.append("🚨 Attaque de vol détectée")
            if res.get("fake_kyc") == "1":         flags.append("🚨 Faux KYC")
            if res.get("darkweb_transactions") == "1": flags.append("🚨 Transactions darkweb")
            if res.get("sanctioned") == "1":       flags.append("🚨 SANCTIONNÉ (OFAC/gouvernement)")

            if flags:
                results.append("\n🔴 <b>SIGNAUX D'ALARME DÉTECTÉS :</b>")
                results.extend(flags)
                goplus_risk = "HIGH"
            else:
                results.append("✅ <b>Aucun signal d'arnaque connu (GoPlus)</b>")
                goplus_risk = "LOW"
    except:
        results.append("⚠️ GoPlus API indisponible (vérification manuelle recommandée)")

# ---- Analyse IA finale ----
prompt = f"""Analyse cette adresse crypto pour détecter une fraude potentielle.
```

Adresse : {address}
Réseau : {chain}
Données collectées :
{chr(10).join(results)}

Données supplémentaires : {etherscan_data}
Niveau de risque GoPlus : {goplus_risk}

Donne en français :

1. Verdict clair : ARNAQUE PROBABLE / SUSPECT / SEMBLE LÉGITIME
1. Niveau de risque : 🔴 ÉLEVÉ / 🟡 MOYEN / 🟢 FAIBLE
1. Raisons principales (2-3 points)
1. Que faire : investir ou éviter ?
1. Comment vérifier manuellement (1 conseil)

Sois direct et prudent.”””

```
try:
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    ai_verdict = msg.content[0].text
except:
    ai_verdict = "Analyse IA indisponible — vérifie manuellement sur etherscan.io"

report = (
    f"🕵️ <b>RAPPORT D'ANALYSE FRAUDE</b>\n"
    f"<code>{address[:20]}...{address[-6:]}</code>\n\n"
    + "\n".join(results) +
    f"\n\n🧠 <b>Verdict IA :</b>\n{ai_verdict}\n\n"
    f"🔗 Vérifie aussi sur :\n"
    f"• <a href='https://etherscan.io/address/{address}'>Etherscan</a>\n"
    f"• <a href='https://gopluslabs.io/'>GoPlus Security</a>"
)
return report
```

# ============================================================

# RAPPORT MARCHÉ GLOBAL

# ============================================================

def get_market_overview() -> str:
if not all_prices_cache:
return “⏳ Données non disponibles.”

```
coins = list(all_prices_cache.values())
gainers_1h  = sorted(coins, key=lambda d: d["change_1h"],  reverse=True)[:5]
losers_1h   = sorted(coins, key=lambda d: d["change_1h"])[:5]
gainers_24h = sorted(coins, key=lambda d: d["change_24h"], reverse=True)[:5]
vol_top     = sorted(coins, key=lambda d: d["volume"],     reverse=True)[:3]

bullish = sum(1 for c in coins if c["change_24h"] > 0)
bearish = len(coins) - bullish
sentiment = "🟢 Haussier" if bullish > bearish else "🔴 Baissier"

def coin_line(d, key):
    v = d[key]
    e = "🟢" if v >= 0 else "🔴"
    return f"  {e} <b>{d['symbol']}</b> {v:+.1f}%"

msg = (
    f"📊 <b>APERÇU MARCHÉ — {datetime.now().strftime('%H:%M')}</b>\n"
    f"<i>Top 500 cryptos analysées</i>\n\n"
    f"🌡 Sentiment : <b>{sentiment}</b>\n"
    f"🟢 Haussières : {bullish} | 🔴 Baissières : {bearish}\n\n"
    f"⚡ <b>Top hausses 1h :</b>\n" + "\n".join(coin_line(d,"change_1h") for d in gainers_1h) + "\n\n"
    f"💥 <b>Top baisses 1h :</b>\n" + "\n".join(coin_line(d,"change_1h") for d in losers_1h) + "\n\n"
    f"🏆 <b>Top hausses 24h :</b>\n" + "\n".join(coin_line(d,"change_24h") for d in gainers_24h) + "\n\n"
    f"💧 <b>Top volumes :</b>\n" + "\n".join(f"  💰 <b>{d['symbol']}</b> ${d['volume']/1e9:.2f}B" for d in vol_top)
)
return msg
```

# ============================================================

# RAPPORT HORAIRE — Meilleures opportunités

# ============================================================

def send_hourly_picks():
global last_top_picks
now = time.time()
if now - last_top_picks < TOP_PICKS_INTERVAL:
return
last_top_picks = now

```
if not all_prices_cache:
    return

# Top 3 opportunités du moment
scored = sorted(all_prices_cache.values(), key=lambda d: score_coin(d), reverse=True)
top3 = scored[:3]

lines = []
for i, d in enumerate(top3, 1):
    s = score_coin(d)
    lines.append(
        f"{i}. 🏅 <b>{d['symbol']}</b> — {fmt_price(d['price'])}\n"
        f"   1h: {d['change_1h']:+.1f}%  24h: {d['change_24h']:+.1f}%  Score: {s}/100"
    )

msg = (
    f"⏰ <b>RAPPORT HORAIRE — {datetime.now().strftime('%H:%M')}</b>\n"
    f"<i>Meilleures opportunités parmi 500 cryptos</i>\n\n"
    + "\n\n".join(lines) +
    f"\n\n💬 Tape /analyse BTC pour une analyse détaillée\n"
    f"💬 Tape /meilleur pour la recommandation IA"
)
send_telegram(msg)
print("[✓] Rapport horaire envoyé")
```

# ============================================================

# VÉRIFICATION DES SEUILS ET ALERTES AUTOMATIQUES

# ============================================================

def check_alerts(prices: dict):
now = time.time()

```
for coin_id, d in prices.items():
    c1h  = d["change_1h"]
    c24h = d["change_24h"]
    rsi  = estimate_rsi(c24h, c1h)

    # Cooldown
    if now - last_alert_time.get(coin_id, 0) < ALERT_COOLDOWN:
        continue

    signal_type = None
    reasons     = []

    # Signaux ACHAT
    if c1h >= BUY_THRESHOLD_1H and c24h > 0:
        signal_type = "buy"
        reasons.append(f"⚡ Accélération +{c1h:.1f}% en 1h")
    if c24h >= BUY_THRESHOLD_24H:
        signal_type = "buy"
        reasons.append(f"📈 Hausse +{c24h:.1f}% en 24h")
    if rsi <= RSI_BUY:
        signal_type = "buy"
        reasons.append(f"📊 RSI bas ({rsi}) — zone de survente")

    # Signaux VENTE
    if c1h <= SELL_THRESHOLD_1H and c24h < 0:
        signal_type = "sell"
        reasons = [f"⚡ Chute {c1h:.1f}% en 1h"]
    if c24h <= SELL_THRESHOLD_24H:
        signal_type = "sell"
        reasons = [f"📉 Baisse {c24h:.1f}% en 24h"]
    if rsi >= RSI_SELL:
        signal_type = "sell"
        reasons = [f"📊 RSI élevé ({rsi}) — zone de surachat"]

    if signal_type is None:
        continue

    # Analyse IA rapide
    try:
        ai_prompt = f"""{d['name']} ({d['symbol']}) : signal {signal_type.upper()} détecté.
```

Prix: ${d[‘price’]:,.6f} | 1h: {c1h:+.1f}% | 24h: {c24h:+.1f}% | RSI: {rsi}
En 2 phrases : pourquoi ce signal et que faire maintenant ?”””
ai_msg = client.messages.create(
model=“claude-haiku-4-5-20251001”,
max_tokens=150,
messages=[{“role”:“user”,“content”:ai_prompt}]
)
ai_text = ai_msg.content[0].text
except:
ai_text = “Analyse IA indisponible.”

```
    icon  = "🚀" if signal_type == "buy" else "🔻"
    label = "ACHAT" if signal_type == "buy" else "VENTE"
    emoji = "🟢" if signal_type == "buy" else "🔴"

    msg = (
        f"{icon} <b>{label} — {d['name']} ({d['symbol']})</b>\n"
        f"Rang #{d['rank']} | {emoji}\n\n"
        f"💰 Prix : <b>{fmt_price(d['price'])}</b>\n"
        f"📊 1h: {c1h:+.1f}%  |  24h: {c24h:+.1f}%  |  7j: {d['change_7d']:+.1f}%\n\n"
        f"<b>Raisons :</b>\n" + "\n".join(f"  {r}" for r in reasons) + f"\n\n"
        f"🧠 <b>IA :</b> {ai_text}\n\n"
        f"<i>💬 /analyse {d['symbol']} pour analyse complète</i>\n"
        f"<i>🕐 {datetime.now().strftime('%H:%M:%S')} — ⚠️ Pas un conseil financier</i>"
    )

    send_telegram(msg)
    last_alert_time[coin_id] = now
    print(f"[🔔] Alerte {label} : {d['name']} ({d['symbol']})")
```

# ============================================================

# UTILITAIRES

# ============================================================

def fmt_price(p: float) -> str:
if p >= 1000:   return f”${p:,.2f}”
elif p >= 1:    return f”${p:.4f}”
elif p >= 0.01: return f”${p:.5f}”
else:           return f”${p:.8f}”

def estimate_rsi(change_24h: float, change_1h: float) -> int:
base = 50 + change_24h * 2.5 + change_1h * 5
return max(10, min(90, int(base)))

# ============================================================

# DÉMARRAGE

# ============================================================

def send_startup():
send_telegram(
f”🤖 <b>CryptoMind Bot v2 — DÉMARRÉ ✅</b>\n\n”
f”📡 Scan du <b>Top 500 cryptos</b> en cours…\n”
f”⏱ Intervalle : toutes les {SCAN_INTERVAL}s\n”
f”⚡ Alertes 1h : seuil ±{BUY_THRESHOLD_1H}%\n”
f”📈 Alertes 24h : seuil ±{BUY_THRESHOLD_24H}%\n\n”
f”💬 Tape /aide pour voir toutes les commandes\n”
f”🏆 Tape /meilleur pour la meilleure crypto maintenant\n”
f”🕵️ Tape /fraude 0x… pour vérifier une adresse”
)

# ============================================================

# BOUCLE PRINCIPALE

# ============================================================

def main():
print(”=” * 55)
print(”  CryptoMind Alert Bot v2 — Démarrage”)
print(”=” * 55)
send_startup()

```
scan_count = 0

while True:
    scan_count += 1
    print(f"\n[SCAN #{scan_count}] {datetime.now().strftime('%H:%M:%S')}")

    # 1. Lire les commandes Telegram
    updates = get_updates()
    if updates:
        process_commands(updates)

    # 2. Récupérer les prix du top 500
    prices = fetch_top_500()
    if prices:
        all_prices_cache.update(prices)
        print(f"[✓] {len(prices)} cryptos mises à jour")

        # 3. Vérifier les alertes automatiques
        check_alerts(prices)

        # 4. Rapport horaire
        send_hourly_picks()
    else:
        print("[!] Erreur de récupération, nouvelle tentative...")
        time.sleep(30)
        continue

    print(f"[⏱] Prochain scan dans {SCAN_INTERVAL}s")
    time.sleep(SCAN_INTERVAL)
```

if **name** == “**main**”:
main()
