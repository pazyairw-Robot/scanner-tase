from flask import Flask, jsonify, render_template_string
import requests
import os
import time
import statistics

try:
    from pytrends.request import TrendReq
except Exception:
    TrendReq = None

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")

FUNDS = [
    {"name": "קרן סל נאסד״ק 100", "proxy": "QQQ", "risk": "רגיל", "sector": "tech"},
    {"name": "איילון / קרן ממונפת פי 3 נאסד״ק", "proxy": "QQQ", "risk": "פי 3", "sector": "tech"},
    {"name": "קרן ממונפת פי 2 נאסד״ק", "proxy": "QQQ", "risk": "פי 2", "sector": "tech"},

    {"name": "קרן סל S&P 500", "proxy": "SPY", "risk": "רגיל", "sector": "market"},
    {"name": "איילון / קרן ממונפת פי 3 S&P 500", "proxy": "SPY", "risk": "פי 3", "sector": "market"},
    {"name": "קרן ממונפת פי 2 S&P 500", "proxy": "SPY", "risk": "פי 2", "sector": "market"},

    {"name": "קרן סל ישראל / ת״א 125", "proxy": "EIS", "risk": "רגיל", "sector": "israel"},
    {"name": "קרן ממונפת פי 3 ת״א 125", "proxy": "EIS", "risk": "פי 3", "sector": "israel"},

    {"name": "קרן סל שווקים מתעוררים", "proxy": "EEM", "risk": "רגיל", "sector": "emerging"},
    {"name": "קרן סל טאיוואן / מזרח אסיה", "proxy": "EWT", "risk": "רגיל", "sector": "asia"},
    {"name": "קרן סל קוריאה / מזרח אסיה", "proxy": "EWY", "risk": "רגיל", "sector": "asia"},
    {"name": "קרן סל יפן", "proxy": "EWJ", "risk": "רגיל", "sector": "asia"},
    {"name": "קרן סל הודו", "proxy": "INDA", "risk": "רגיל", "sector": "asia"},

    {"name": "קרן סל זהב / קסם זהב", "proxy": "GLD", "risk": "סחורה", "sector": "gold"},
    {"name": "קרן סל כסף", "proxy": "SLV", "risk": "סחורה", "sector": "metal"},
    {"name": "קרן סל נפט", "proxy": "USO", "risk": "סחורה", "sector": "oil"},
    {"name": "קרן דולר / חשיפה לדולר", "proxy": "UUP", "risk": "מטבע", "sector": "dollar"},
]

MACRO_SYMBOLS = {
    "SPY": "שוק אמריקאי",
    "QQQ": "טכנולוגיה",
    "EEM": "שווקים מתעוררים",
    "GLD": "זהב",
    "USO": "נפט",
    "UUP": "דולר",
    "EIS": "ישראל",
}

def fetch_prices(symbol):
    if not API_KEY:
        return None

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 260,
        "apikey": API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        data = response.json()

        if "values" not in data:
            return None

        prices = []
        for row in data["values"]:
            try:
                prices.append(float(row["close"]))
            except Exception:
                pass

        prices.reverse()
        return prices if len(prices) >= 65 else None

    except Exception:
        return None

def calc_metrics(prices):
    last = prices[-1]

    week = (last / prices[-5] - 1) * 100
    month = (last / prices[-21] - 1) * 100
    q3 = (last / prices[-63] - 1) * 100
    half = (last / prices[-126] - 1) * 100 if len(prices) >= 126 else q3
    year = (last / prices[-252] - 1) * 100 if len(prices) >= 252 else half

    daily_returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] != 0:
            daily_returns.append((prices[i] / prices[i - 1] - 1) * 100)

    vol = statistics.mean([abs(x) for x in daily_returns[-60:]]) if daily_returns else 0

    graph_score = (
        0.10 * week +
        0.20 * month +
        0.30 * q3 +
        0.25 * half +
        0.15 * year -
        0.70 * vol
    )

    return {
        "week": round(week, 1),
        "month": round(month, 1),
        "q3": round(q3, 1),
        "half": round(half, 1),
        "year": round(year, 1),
        "vol": round(vol, 1),
        "graph_score": round(graph_score, 1)
    }

def trend_sentiment():
    if TrendReq is None:
        return {
            "label": "ללא נתוני חיפוש",
            "tech_boost": 0,
            "fear_boost": 0,
            "inflation_penalty": 0
        }

    try:
        pytrend = TrendReq(hl="en-US", tz=0)
        words = ["recession", "AI", "inflation", "stock market crash"]
        pytrend.build_payload(words, timeframe="now 7-d")
        data = pytrend.interest_over_time()

        if data.empty:
            return {"label": "סנטימנט ניטרלי", "tech_boost": 0, "fear_boost": 0, "inflation_penalty": 0}

        recession = float(data["recession"].mean())
        ai = float(data["AI"].mean())
        inflation = float(data["inflation"].mean())
        crash = float(data["stock market crash"].mean())

        tech_boost = 2 if ai > 50 else 0
        fear_boost = 2 if recession > 50 or crash > 40 else 0
        inflation_penalty = -1.5 if inflation > 50 else 0

        if ai > 50 and recession < 50:
            label = "🚀 דיבור חזק על AI / טכנולוגיה"
        elif recession > 50 or crash > 40:
            label = "⚠️ דיבור מוגבר על פחד / מיתון"
        elif inflation > 50:
            label = "📉 דיבור מוגבר על אינפלציה"
        else:
            label = "🟢 סנטימנט רגיל"

        return {
            "label": label,
            "tech_boost": tech_boost,
            "fear_boost": fear_boost,
            "inflation_penalty": inflation_penalty
        }

    except Exception:
        return {
            "label": "ללא נתוני סנטימנט זמינים",
            "tech_boost": 0,
            "fear_boost": 0,
            "inflation_penalty": 0
        }

def macro_context(price_cache):
    scores = {}
    for sym in MACRO_SYMBOLS:
        prices = price_cache.get(sym)
        if prices:
            scores[sym] = calc_metrics(prices)
        else:
            scores[sym] = None

    qqq = scores.get("QQQ")
    spy = scores.get("SPY")
    eem = scores.get("EEM")
    gold = scores.get("GLD")
    oil = scores.get("USO")
    dollar = scores.get("UUP")
    israel = scores.get("EIS")

    macro_boosts = {
        "tech": 0,
        "market": 0,
        "asia": 0,
        "emerging": 0,
        "gold": 0,
        "oil": 0,
        "dollar": 0,
        "israel": 0,
        "metal": 0
    }

    notes = []

    if spy and spy["month"] > 0 and spy["q3"] > 0:
        macro_boosts["market"] += 2
        macro_boosts["tech"] += 1
        notes.append("שוק אמריקאי חיובי")

    if qqq and qqq["month"] > 0 and qqq["q3"] > 0:
        macro_boosts["tech"] += 2
        notes.append("טכנולוגיה / נאסד״ק במומנטום חיובי")

    if eem and eem["month"] > 0 and eem["q3"] > 0:
        macro_boosts["emerging"] += 2
        macro_boosts["asia"] += 1
        notes.append("שווקים מתעוררים חיוביים")

    if gold and gold["month"] > 0:
        macro_boosts["gold"] += 2
        notes.append("זהב חיובי — סימן לביקוש הגנתי / סחורות")

    if oil and oil["month"] > 0:
        macro_boosts["oil"] += 2
        notes.append("נפט חיובי — תומך באנרגיה")

    if dollar and dollar["month"] > 0:
        macro_boosts["dollar"] += 1
        notes.append("דולר חיובי")

    if israel and israel["month"] > 0 and israel["q3"] > 0:
        macro_boosts["israel"] += 2
        notes.append("ישראל חיובית לפי proxy EIS")

    if not notes:
        notes.append("אין כיוון מאקרו מובהק")

    if qqq and spy and qqq["q3"] > 0 and spy["q3"] > 0:
        regime = "🟢 Risk ON — שוק מנייתי חיובי"
    elif gold and gold["month"] > 0 and (not spy or spy["month"] < 0):
        regime = "⚠️ מצב הגנתי — זהב חזק מול מניות"
    else:
        regime = "🟡 שוק מעורב / לא חד־משמעי"

    return regime, macro_boosts, notes

def final_score(metrics, fund, macro_boosts, sentiment):
    score = metrics["graph_score"]

    score += macro_boosts.get(fund["sector"], 0)

    if fund["sector"] == "tech":
        score += sentiment["tech_boost"]

    if fund["sector"] == "gold":
        score += sentiment["fear_boost"]

    score += sentiment["inflation_penalty"]

    if fund["risk"] == "פי 3":
        score = score * 1.20 - 2.0
    elif fund["risk"] == "פי 2":
        score = score * 1.10 - 1.0

    return round(score, 1)

def recommendation(score, risk):
    if risk == "פי 3":
        if score >= 10:
            return "🟢 קנייה אגרסיבית"
        if score >= 4:
            return "🟡 מעקב / סיכון גבוה"
        return "🔴 להימנע"

    if score >= 8:
        return "🔥 חזק מאוד"
    if score >= 5:
        return "🟢 קנייה"
    if score >= 1:
        return "🟡 מעקב"
    return "🔴 להימנע"

def reason_text(fund, metrics, macro_boosts, sentiment):
    reasons = []

    if metrics["q3"] > 5:
        reasons.append("מומנטום 3 חודשים חיובי")
    elif metrics["q3"] < 0:
        reasons.append("3 חודשים שלילי")

    if metrics["month"] > 2:
        reasons.append("חודש חיובי")
    elif metrics["month"] < 0:
        reasons.append("חודש שלילי")

    if macro_boosts.get(fund["sector"], 0) > 0:
        reasons.append("מאקרו תומך")

    if fund["sector"] == "tech" and sentiment["tech_boost"] > 0:
        reasons.append("דיבור חזק על AI/טכנולוגיה")

    if fund["sector"] == "gold" and sentiment["fear_boost"] > 0:
        reasons.append("דיבור פחד תומך בזהב")

    if fund["risk"] in ["פי 2", "פי 3"]:
        reasons.append("ממונף — מתאים רק לסיכון גבוה")

    return " | ".join(reasons[:3]) if reasons else "אין יתרון ברור"

@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>סורק השקעות PRO</title>
<style>
body{direction:rtl;font-family:Arial;padding:16px;background:#f6f7fb}
h2{text-align:center;margin-bottom:8px}
.card{background:white;padding:12px;border-radius:12px;margin:10px 0;box-shadow:0 1px 5px #ddd}
button{width:100%;padding:16px;font-size:22px;border-radius:12px;border:0;background:#1976d2;color:white}
#loading{text-align:center;font-size:20px;margin:18px}
.spinner{font-size:40px;animation:flip 1s infinite;display:inline-block}
@keyframes flip{0%{transform:rotate(0deg)}50%{transform:rotate(180deg)}100%{transform:rotate(360deg)}}
table{width:100%;border-collapse:collapse;background:white;margin-top:12px;font-size:13px}
th,td{border:1px solid #ddd;padding:7px;text-align:center}
th{background:#e9eef5}
.buy{color:green;font-weight:bold}
.mid{color:#b36b00;font-weight:bold}
.bad{color:red;font-weight:bold}
.small{font-size:12px;color:#555}
</style>
</head>
<body>

<h2>📊 סורק קרנות/סל PRO</h2>

<div class="card small">
<b>📘 מקרא ציון:</b><br>
ציון 10+ → 🔥 חזק מאוד<br>
ציון 5–10 → 🟢 קנייה / חיובי<br>
ציון 1–5 → 🟡 מעקב<br>
ציון מתחת 1 → 🔴 להימנע<br><br>

<b>מה הציון כולל:</b><br>
75% ניתוח גרפי: שבוע, חודש, 3 חודשים, חצי שנה, שנה ותנודתיות.<br>
25% מאקרו/אקטואליה: מצב שוק עולמי, דולר, זהב, נפט, ישראל, שווקים מתעוררים ודיבור שוק דרך Google Trends.<br><br>

<b>שים לב:</b> ממונפות פי 2/3 מקבלות קנס סיכון. גם המלצת קנייה בהן היא אגרסיבית בלבד.
</div>

<button onclick="run()">🔵 סריקה</button>

<div id="loading"></div>
<div id="market" class="card"></div>
<table id="t"></table>
<div id="errors" class="small"></div>

<script>
let timer = null;
let seconds = 0;

function startClock(){
    seconds = 0;
    const loading = document.getElementById("loading");
    timer = setInterval(()=>{
        seconds++;
        loading.innerHTML = `
            <div class="spinner">⏳</div>
            <div>מבצע ניתוח... ${seconds} שניות</div>
            <div style="font-size:14px;color:#555">בודק גרפים, מאקרו ודיבור שוק</div>
        `;
    },1000);
}

function stopClock(msg){
    clearInterval(timer);
    document.getElementById("loading").innerText = msg;
}

async function run(){
    document.getElementById("t").innerHTML = "";
    document.getElementById("errors").innerHTML = "";
    document.getElementById("market").innerHTML = "";
    startClock();

    try{
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 240000);

        let r = await fetch('/scan', {signal: controller.signal});
        clearTimeout(timeoutId);

        let d = await r.json();

        if(!d.results || d.results.length === 0){
            stopClock("⚠️ לא התקבלו נתונים. נסה שוב מאוחר יותר.");
            return;
        }

        document.getElementById("market").innerHTML =
            "<b>🌍 מצב שוק:</b><br>" +
            d.regime + "<br>" +
            "<b>🧠 דיבור שוק:</b><br>" +
            d.sentiment + "<br>" +
            "<b>📌 הערות:</b><br>" +
            d.notes.join("<br>");

        let html = "<tr><th>#</th><th>שם לרכישה</th><th>בסיס ניתוח</th><th>סיכון</th><th>חודש</th><th>3ח׳</th><th>חצי שנה</th><th>ציון</th><th>המלצה</th><th>למה</th></tr>";

        d.results.forEach((x,i)=>{
            let cls = "bad";
            if(x.reco.includes("קנייה") || x.reco.includes("חזק")) cls = "buy";
            else if(x.reco.includes("מעקב")) cls = "mid";

            html += `<tr>
                <td>${i+1}</td>
                <td>${x.name}</td>
                <td>${x.proxy}</td>
                <td>${x.risk}</td>
                <td>${x.month}%</td>
                <td>${x.q3}%</td>
                <td>${x.half}%</td>
                <td>${x.score}</td>
                <td class="${cls}">${x.reco}</td>
                <td>${x.reason}</td>
            </tr>`;
        });

        document.getElementById("t").innerHTML = html;
        stopClock("✅ הסריקה הסתיימה");

        if(d.errors && d.errors.length > 0){
            document.getElementById("errors").innerHTML = "לא נטענו: " + d.errors.join(", ");
        }

    }catch(e){
        stopClock("⚠️ הסריקה נתקעה או חרגה מזמן. נסה שוב.");
    }
}
</script>

</body>
</html>
""")

@app.route("/scan")
def scan():
    results = []
    errors = []
    price_cache = {}

    all_symbols = set([f["proxy"] for f in FUNDS] + list(MACRO_SYMBOLS.keys()))

    for sym in all_symbols:
        prices = fetch_prices(sym)
        price_cache[sym] = prices
        time.sleep(1.1)

    regime, macro_boosts, notes = macro_context(price_cache)
    sent = trend_sentiment()

    for fund in FUNDS:
        try:
            prices = price_cache.get(fund["proxy"])
            if not prices:
                errors.append(fund["name"])
                continue

            metrics = calc_metrics(prices)
            score = final_score(metrics, fund, macro_boosts, sent)
            reco = recommendation(score, fund["risk"])

            results.append({
                "name": fund["name"],
                "proxy": fund["proxy"],
                "risk": fund["risk"],
                "month": metrics["month"],
                "q3": metrics["q3"],
                "half": metrics["half"],
                "score": score,
                "reco": reco,
                "reason": reason_text(fund, metrics, macro_boosts, sent)
            })
        except Exception:
            errors.append(fund["name"])

    results = sorted(results, key=lambda x: x["score"], reverse=True)[:10]

    return jsonify({
        "results": results,
        "errors": errors,
        "regime": regime,
        "sentiment": sent["label"],
        "notes": notes
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
