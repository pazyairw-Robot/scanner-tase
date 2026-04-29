from flask import Flask, jsonify, render_template_string
import requests
import os
import time
import statistics
from datetime import datetime, timedelta

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")

FUNDS = [
    # סחורות
    {"name": "קרן סל נפט", "proxy": "USO", "risk": "סחורה", "theme": "oil"},
    {"name": "קרן סל זהב / קסם זהב", "proxy": "GLD", "risk": "סחורה", "theme": "gold"},
    {"name": "קרן סל כסף", "proxy": "SLV", "risk": "סחורה", "theme": "silver"},

    # מזרח / אסיה
    {"name": "קרן סל קוריאה / מזרח אסיה", "proxy": "EWY", "risk": "רגיל", "theme": "asia"},
    {"name": "קרן סל טאיוואן / מזרח אסיה", "proxy": "EWT", "risk": "רגיל", "theme": "semis"},
    {"name": "קרן סל יפן", "proxy": "EWJ", "risk": "רגיל", "theme": "asia"},
    {"name": "קרן סל הודו", "proxy": "INDA", "risk": "רגיל", "theme": "asia"},
    {"name": "קרן סל סין", "proxy": "MCHI", "risk": "רגיל", "theme": "china"},
    {"name": "קרן שווקים מתעוררים", "proxy": "EEM", "risk": "רגיל", "theme": "emerging"},

    # שבבים / AI
    {"name": "קרן סל שבבים / Semiconductors", "proxy": "SOXX", "risk": "רגיל", "theme": "semis"},
    {"name": "קרן ממונפת פי 2 שבבים", "proxy": "SOXX", "risk": "ממונף פי 2", "theme": "semis"},
    {"name": "קרן ממונפת פי 3 שבבים", "proxy": "SOXX", "risk": "ממונף פי 3", "theme": "semis"},

    # נאסדק / טכנולוגיה
    {"name": "קרן סל נאסד״ק 100", "proxy": "QQQ", "risk": "רגיל", "theme": "tech"},
    {"name": "קרן ממונפת פי 2 נאסד״ק", "proxy": "QQQ", "risk": "ממונף פי 2", "theme": "tech"},
    {"name": "קרן ממונפת פי 3 נאסד״ק / איילון אקסטרים", "proxy": "QQQ", "risk": "ממונף פי 3", "theme": "tech"},

    # S&P / שוק כללי
    {"name": "קרן סל S&P 500", "proxy": "SPY", "risk": "רגיל", "theme": "market"},
    {"name": "קרן ממונפת פי 2 S&P 500", "proxy": "SPY", "risk": "ממונף פי 2", "theme": "market"},
    {"name": "קרן ממונפת פי 3 S&P 500 / איילון אקסטרים", "proxy": "SPY", "risk": "ממונף פי 3", "theme": "market"},

    # ישראל
    {"name": "קרן סל ישראל / ת״א 125", "proxy": "EIS", "risk": "רגיל", "theme": "israel"},
    {"name": "קרן סל ישראל / ת״א 35", "proxy": "EIS", "risk": "רגיל", "theme": "israel"},
    {"name": "קרן ממונפת פי 2 ת״א 125", "proxy": "EIS", "risk": "ממונף פי 2", "theme": "israel"},
    {"name": "קרן ממונפת פי 3 ת״א 125", "proxy": "EIS", "risk": "ממונף פי 3", "theme": "israel"},

    # סקטורים
    {"name": "קרן אנרגיה", "proxy": "VDE", "risk": "רגיל", "theme": "energy"},
    {"name": "קרן פיננסים / בנקים", "proxy": "KBE", "risk": "רגיל", "theme": "banks"},
    {"name": "קרן דולר / חשיפה לדולר", "proxy": "UUP", "risk": "מטבע", "theme": "dollar"},
]

def td_prices(symbol):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 260,
        "apikey": API_KEY
    }

    data = requests.get(url, params=params, timeout=25).json()

    if "values" not in data:
        return None

    prices = []
    for row in data["values"]:
        try:
            prices.append(float(row["close"]))
        except:
            pass

    prices.reverse()
    return prices if len(prices) >= 65 else None

def news_count(query):
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=14)

        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": 30,
            "startdatetime": start.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end.strftime("%Y%m%d%H%M%S")
        }

        data = requests.get(url, params=params, timeout=15).json()
        return len(data.get("articles", []))

    except Exception:
        return 0

def perf(prices, days):
    if not prices or len(prices) < days + 1:
        return 0
    return (prices[-1] / prices[-days] - 1) * 100

def calc_graph(prices):
    week = perf(prices, 5)
    month = perf(prices, 21)
    q3 = perf(prices, 63)
    half = perf(prices, 126) if len(prices) >= 126 else q3
    year = perf(prices, 252) if len(prices) >= 252 else half

    daily = []
    for i in range(1, len(prices)):
        if prices[i - 1] != 0:
            daily.append((prices[i] / prices[i - 1] - 1) * 100)

    vol = statistics.mean([abs(x) for x in daily[-60:]]) if daily else 0

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

def build_market_context(price_cache):
    required = ["SPY", "QQQ", "SOXX", "EEM", "EIS", "GLD", "USO", "UUP", "TLT"]

    for sym in required:
        if sym not in price_cache:
            price_cache[sym] = td_prices(sym)
            time.sleep(0.7)

    spy = perf(price_cache.get("SPY"), 21)
    qqq = perf(price_cache.get("QQQ"), 21)
    soxx = perf(price_cache.get("SOXX"), 21)
    eem = perf(price_cache.get("EEM"), 21)
    eis = perf(price_cache.get("EIS"), 21)
    gld = perf(price_cache.get("GLD"), 21)
    uso = perf(price_cache.get("USO"), 21)
    uup = perf(price_cache.get("UUP"), 21)
    tlt = perf(price_cache.get("TLT"), 21)

    news = {
        "oil": news_count("oil price OR crude oil OR OPEC OR Strait of Hormuz OR sanctions OR tanker"),
        "war": news_count("war OR missile OR iran OR israel OR gaza OR ukraine OR red sea"),
        "ai": news_count("artificial intelligence OR AI chips OR Nvidia OR semiconductor OR TSMC"),
        "rates": news_count("interest rates OR federal reserve OR inflation OR bond yields"),
        "china": news_count("china economy OR china stimulus OR property crisis china"),
        "recession": news_count("recession OR slowdown OR market crash OR credit risk")
    }

    ctx = {
        "spy": spy,
        "qqq": qqq,
        "soxx": soxx,
        "eem": eem,
        "eis": eis,
        "gld": gld,
        "uso": uso,
        "uup": uup,
        "tlt": tlt,
        "news": news,
        "summary": []
    }

    if spy > 2 and qqq > 2:
        ctx["summary"].append("🟢 שוק מניות חיובי")
    elif spy < -2 or qqq < -2:
        ctx["summary"].append("🔴 לחץ בשוק המניות")
    else:
        ctx["summary"].append("🟡 שוק מניות ניטרלי")

    if soxx > 3 and news["ai"] >= 8:
        ctx["summary"].append("🚀 שבבים / AI חזקים גם בגרף וגם באקטואליה")

    if uso > 5 and news["oil"] >= 8:
        ctx["summary"].append("⚠️ נפט חזק אך מושפע מאקטואליה — סיכון תיקון אם המתיחות תרד")

    if gld > 3 and news["war"] >= 8:
        ctx["summary"].append("⚠️ זהב נתמך מחשש גיאופוליטי")

    if uup > 2:
        ctx["summary"].append("💵 דולר מתחזק — זהירות בשווקים רגישים לריבית")

    if tlt < -2 or news["rates"] >= 10:
        ctx["summary"].append("📉 סביבת ריבית/אג״ח לוחצת על נכסי סיכון")

    if eem > 2:
        ctx["summary"].append("🌏 שווקים מתעוררים / מזרח חיוביים")

    if eis < -2 and news["war"] >= 8:
        ctx["summary"].append("🇮🇱 ישראל תחת קנס סיכון מקומי")

    return ctx

def forward_adjust(fund, ctx, data):
    theme = fund["theme"]
    risk = fund["risk"]

    adj = 0
    reasons = []

    # שוק כללי
    if ctx["spy"] > 2 and ctx["qqq"] > 2:
        if theme in ["market", "tech", "semis", "asia", "emerging"]:
            adj += 2
            reasons.append("שוק מניות עולמי תומך")
    elif ctx["spy"] < -2 or ctx["qqq"] < -2:
        if theme in ["market", "tech", "semis", "asia", "emerging"]:
            adj -= 3
            reasons.append("לחץ בשוק מניות פוגע בהמשך")

    # שבבים / AI
    if theme == "semis":
        if ctx["soxx"] > 3:
            adj += 3
            reasons.append("שבבים חזקים בגרף")
        if ctx["news"]["ai"] >= 8:
            adj += 3
            reasons.append("דיבור חזק סביב AI/שבבים")
        if ctx["qqq"] < -2:
            adj -= 2
            reasons.append("נאסד״ק חלש פוגע בשבבים")

    # טכנולוגיה / נאסדק
    if theme == "tech":
        if ctx["news"]["ai"] >= 8:
            adj += 2
            reasons.append("אקטואליית AI תומכת בטכנולוגיה")
        if ctx["uup"] > 2 or ctx["news"]["rates"] >= 10:
            adj -= 2
            reasons.append("דולר/ריבית עלולים ללחוץ על טכנולוגיה")

    # נפט
    if theme == "oil":
        if ctx["uso"] > 5 and ctx["news"]["oil"] >= 8:
            adj -= 8
            reasons.append("נפט עלה סביב אירוע אקטואלי — סיכון ירידה אם המתיחות תרד")
        elif ctx["uso"] > 5:
            adj -= 3
            reasons.append("נפט לאחר עלייה חדה — סיכון תיקון")
        elif ctx["uso"] < -3:
            adj -= 2
            reasons.append("מגמת נפט שלילית")

    # אנרגיה
    if theme == "energy":
        if ctx["uso"] > 3 and ctx["news"]["oil"] < 8:
            adj += 2
            reasons.append("אנרגיה נתמכת בנפט ללא עומס אקטואלי חריג")
        elif ctx["news"]["oil"] >= 8:
            adj -= 2
            reasons.append("אנרגיה חשופה לתיקון אם אקטואליית נפט תירגע")

    # זהב / כסף
    if theme in ["gold", "silver"]:
        if ctx["news"]["war"] >= 8 or ctx["gld"] > 3:
            adj += 3
            reasons.append("חשש גיאופוליטי תומך בסחורות הגנתיות")
        if ctx["spy"] > 2 and ctx["qqq"] > 2:
            adj -= 2
            reasons.append("שוק מניות חיובי מפחית צורך בהגנה")
        if ctx["uup"] > 2:
            adj -= 1
            reasons.append("דולר חזק מקשה על מתכות")

    # מזרח / מתעוררים
    if theme in ["asia", "emerging"]:
        if ctx["eem"] > 2:
            adj += 3
            reasons.append("מזרח/מתעוררים חזקים")
        if ctx["uup"] > 2:
            adj -= 2
            reasons.append("דולר חזק פוגע בשווקים מתעוררים")
        if ctx["news"]["recession"] >= 8:
            adj -= 2
            reasons.append("חשש האטה עולמית")

    # סין
    if theme == "china":
        if ctx["news"]["china"] >= 8:
            adj -= 2
            reasons.append("סין עם אקטואליה כלכלית רגישה")
        if ctx["eem"] > 2:
            adj += 1
            reasons.append("מתעוררים חיוביים נותנים תמיכה חלקית")

    # ישראל
    if theme == "israel":
        if ctx["eis"] > 2:
            adj += 2
            reasons.append("ישראל חיובית לפי proxy")
        if ctx["news"]["war"] >= 8:
            adj -= 3
            reasons.append("סיכון גיאופוליטי מקומי")
        if ctx["eis"] < -2:
            adj -= 2
            reasons.append("ישראל חלשה בגרף")

    # בנקים
    if theme == "banks":
        if ctx["news"]["rates"] >= 10:
            adj += 1
            reasons.append("ריבית גבוהה יכולה לתמוך במרווחי בנקים")
        if ctx["news"]["recession"] >= 8:
            adj -= 3
            reasons.append("חשש האטה/אשראי פוגע בבנקים")

    # דולר
    if theme == "dollar":
        if ctx["uup"] > 2:
            adj += 2
            reasons.append("דולר במגמת התחזקות")
        if ctx["spy"] > 2 and ctx["qqq"] > 2:
            adj -= 1
            reasons.append("Risk-on מפחית עדיפות לדולר")

    # ממונפות
    if "פי 3" in risk:
        adj -= 3
        reasons.append("ממונף פי 3 — קנס סיכון")
        if data["graph_score"] > 8 and ctx["spy"] > 2:
            adj += 2
            reasons.append("מגמה חזקה מצדיקה חלקית מינוף")
    elif "פי 2" in risk:
        adj -= 1.5
        reasons.append("ממונף פי 2 — קנס סיכון")
        if data["graph_score"] > 6:
            adj += 1
            reasons.append("מגמה תומכת במינוף מוגבל")

    if not reasons:
        reasons.append("אין איתות אקטואלי חריג")

    return round(adj, 1), " | ".join(reasons[:4])

def recommendation(score, risk):
    if "פי 3" in risk:
        if score >= 12:
            return "🟢 קנייה אגרסיבית"
        if score >= 5:
            return "🟡 מעקב / סיכון גבוה"
        return "🔴 להימנע"

    if score >= 8:
        return "🔥 חזק מאוד"
    if score >= 4:
        return "🟢 קנייה"
    if score >= 1:
        return "🟡 מעקב"
    return "🔴 להימנע"

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
body{direction:rtl;font-family:Arial;padding:12px;background:#f6f7fb}
h2{text-align:center}
button{width:100%;padding:16px;font-size:22px;border-radius:12px;border:0;background:#1976d2;color:white}
#loading{text-align:center;font-size:19px;margin:18px}
.spinner{font-size:38px;animation:flip 1s infinite}
@keyframes flip{0%{transform:rotate(0deg)}50%{transform:rotate(180deg)}100%{transform:rotate(360deg)}}
.legend{background:white;border-radius:12px;padding:12px;margin:10px 0;font-size:14px;line-height:1.6}
table{width:100%;border-collapse:collapse;background:white;margin-top:12px;font-size:12px}
th,td{border:1px solid #ddd;padding:6px;text-align:center;vertical-align:top}
th{background:#e9eef5}
.buy{color:green;font-weight:bold}
.mid{color:#b36b00;font-weight:bold}
.bad{color:red;font-weight:bold}
.reason{font-size:11px;text-align:right;min-width:140px}
</style>
</head>
<body>

<h2>📊 סורק קרנות/סל PRO</h2>

<div class="legend">
<b>מקרא ציון סופי:</b><br>
🔥 מעל 8 = חזק מאוד | 🟢 4–8 = קנייה | 🟡 1–4 = מעקב | 🔴 מתחת 1 = להימנע<br>
<b>מה הציון כולל:</b><br>
גרף + מאקרו עולמי + אקטואליה + הסתכלות קדימה + קנס סיכון למינוף/אירוע זמני.
</div>

<button onclick="run()">🔵 סריקה</button>

<div id="loading"></div>
<div id="market"></div>
<table id="t"></table>

<script>
let timer=null, seconds=0;

function startClock(){
    seconds=0;
    timer=setInterval(()=>{
        seconds++;
        document.getElementById("loading").innerHTML =
        `<div class="spinner">⏳</div><div>מנתח גרף + אקטואליה... ${seconds} שניות</div><div style="font-size:13px;color:#555">יכול לקחת עד כמה דקות</div>`;
    },1000);
}

function stopClock(msg){
    clearInterval(timer);
    document.getElementById("loading").innerText=msg;
}

async function run(){
    document.getElementById("t").innerHTML="";
    document.getElementById("market").innerHTML="";
    startClock();

    try{
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 240000);

        let r = await fetch('/scan', {signal: controller.signal});
        clearTimeout(timeoutId);

        let d = await r.json();

        document.getElementById("market").innerHTML =
            `<div class="legend"><b>מצב שוק:</b><br>${d.market.join("<br>")}</div>`;

        let html="<tr><th>#</th><th>שם לרכישה</th><th>בסיס</th><th>סיכון</th><th>חודש</th><th>3ח׳</th><th>חצי שנה</th><th>גרף</th><th>אקטואלי</th><th>סופי</th><th>המלצה</th><th>סיבה</th></tr>";

        d.results.forEach((x,i)=>{
            let cls="bad";
            if(x.reco.includes("קנייה") || x.reco.includes("חזק")) cls="buy";
            else if(x.reco.includes("מעקב")) cls="mid";

            html+=`<tr>
                <td>${i+1}</td>
                <td>${x.name}</td>
                <td>${x.proxy}</td>
                <td>${x.risk}</td>
                <td>${x.month}%</td>
                <td>${x.q3}%</td>
                <td>${x.half}%</td>
                <td>${x.graph_score}</td>
                <td>${x.forward_adj}</td>
                <td>${x.final_score}</td>
                <td class="${cls}">${x.reco}</td>
                <td class="reason">${x.reason}</td>
            </tr>`;
        });

        document.getElementById("t").innerHTML=html;
        stopClock("✅ הסריקה הסתיימה");

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
    price_cache = {}
    results = []
    errors = []

    ctx = build_market_context(price_cache)

    for fund in FUNDS:
        try:
            proxy = fund["proxy"]

            if proxy not in price_cache:
                price_cache[proxy] = td_prices(proxy)
                time.sleep(0.7)

            prices = price_cache.get(proxy)
            if not prices:
                errors.append(fund["name"])
                continue

            data = calc_graph(prices)
            adj, reason = forward_adjust(fund, ctx, data)
            final_score = round(data["graph_score"] + adj, 1)

            results.append({
                "name": fund["name"],
                "proxy": proxy,
                "risk": fund["risk"],
                **data,
                "forward_adj": adj,
                "final_score": final_score,
                "reco": recommendation(final_score, fund["risk"]),
                "reason": reason
            })

        except Exception:
            errors.append(fund["name"])

    results = sorted(results, key=lambda x: x["final_score"], reverse=True)[:10]

    return jsonify({
        "market": ctx["summary"],
        "results": results,
        "errors": errors
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
