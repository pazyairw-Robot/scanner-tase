from flask import Flask, jsonify, render_template_string
import requests
import os
import time
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote_plus

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")

FUNDS = [
    {"name": "קסם LBMA Gold Price PM USD ETF", "sec_no": "1146422", "proxy": "GLD", "risk": "סחורה", "theme": "gold"},

    {"name": "איילון אקסטרים Nasdaq 100 פי 3", "sec_no": "5128947", "proxy": "QQQ", "risk": "ממונף פי 3", "theme": "tech"},
    {"name": "איילון אקסטרים S&P 500 פי 3", "sec_no": "5117759", "proxy": "SPY", "risk": "ממונף פי 3", "theme": "market"},

    {"name": "קרן סל ישראלית עוקבת Nasdaq 100", "sec_no": "בדוק בבנק", "proxy": "QQQ", "risk": "רגיל", "theme": "tech"},
    {"name": "קרן סל ישראלית עוקבת S&P 500", "sec_no": "בדוק בבנק", "proxy": "SPY", "risk": "רגיל", "theme": "market"},

    {"name": "קרן סל / קרן מחקה חשיפה לשבבים", "sec_no": "בדוק בבנק", "proxy": "SOXX", "risk": "רגיל", "theme": "semis"},

    {"name": "קרן סל קוריאה / מזרח אסיה", "sec_no": "בדוק בבנק", "proxy": "EWY", "risk": "רגיל", "theme": "asia"},
    {"name": "קרן סל טאיוואן / מזרח אסיה", "sec_no": "בדוק בבנק", "proxy": "EWT", "risk": "רגיל", "theme": "semis"},
    {"name": "קרן סל יפן", "sec_no": "בדוק בבנק", "proxy": "EWJ", "risk": "רגיל", "theme": "asia"},
    {"name": "קרן סל הודו", "sec_no": "בדוק בבנק", "proxy": "INDA", "risk": "רגיל", "theme": "asia"},
    {"name": "קרן סל סין", "sec_no": "בדוק בבנק", "proxy": "MCHI", "risk": "רגיל", "theme": "china"},
    {"name": "קרן שווקים מתעוררים", "sec_no": "בדוק בבנק", "proxy": "EEM", "risk": "רגיל", "theme": "emerging"},

    {"name": "קרן סל ישראל / ת״א 125 - proxy ישראל", "sec_no": "בדוק בבנק", "proxy": "EIS", "risk": "רגיל", "theme": "israel"},
    {"name": "קרן סל ישראל / ת״א 35 - proxy ישראל", "sec_no": "בדוק בבנק", "proxy": "EIS", "risk": "רגיל", "theme": "israel"},

    {"name": "קרן אנרגיה", "sec_no": "בדוק בבנק", "proxy": "VDE", "risk": "רגיל", "theme": "energy"},
    {"name": "קרן פיננסים / בנקים", "sec_no": "בדוק בבנק", "proxy": "KBE", "risk": "רגיל", "theme": "banks"},
    {"name": "קרן דולר / חשיפה לדולר", "sec_no": "בדוק בבנק", "proxy": "UUP", "risk": "מטבע", "theme": "dollar"},
    {"name": "קרן סל נפט", "sec_no": "בדוק בבנק", "proxy": "USO", "risk": "סחורה", "theme": "oil"},
    {"name": "קרן סל כסף", "sec_no": "בדוק בבנק", "proxy": "SLV", "risk": "סחורה", "theme": "silver"},
]

NEWS_QUERIES = {
    "oil": "oil price OR crude oil OR OPEC OR Strait of Hormuz OR sanctions OR tanker",
    "war": "war OR missile OR iran OR israel OR gaza OR ukraine OR red sea",
    "ai": "artificial intelligence OR AI chips OR Nvidia OR semiconductor OR TSMC",
    "rates": "interest rates OR federal reserve OR inflation OR bond yields",
    "china": "china economy OR china stimulus OR property crisis china",
    "recession": "recession OR slowdown OR market crash OR credit risk",
    "banks": "banks OR financial sector OR credit risk OR loan losses",
    "gold": "gold price OR safe haven OR treasury yields OR dollar",
}

POS_WORDS = [
    "surge", "gain", "rise", "rally", "boost", "strong", "record", "optimism",
    "stimulus", "growth", "demand", "beat", "upgrade", "bullish", "rebound"
]

NEG_WORDS = [
    "fall", "drop", "decline", "weak", "risk", "war", "missile", "recession",
    "slowdown", "inflation", "higher rates", "sanctions", "crisis", "loss",
    "bearish", "concern", "fear", "cut", "slump"
]

PRICE_CACHE = {}
NEWS_CACHE = {}
CACHE_SECONDS = 900


def cached(key, cache):
    item = cache.get(key)
    if not item:
        return None
    t, value = item
    if time.time() - t > CACHE_SECONDS:
        return None
    return value


def set_cache(key, cache, value):
    cache[key] = (time.time(), value)


def td_prices(symbol):
    cached_value = cached(symbol, PRICE_CACHE)
    if cached_value is not None:
        return cached_value

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
        data = requests.get(url, params=params, timeout=25).json()
        if "values" not in data:
            return None

        prices = []
        for row in data["values"]:
            try:
                prices.append(float(row["close"]))
            except Exception:
                pass

        prices.reverse()
        result = prices if len(prices) >= 65 else None
        set_cache(symbol, PRICE_CACHE, result)
        return result
    except Exception:
        return None


def google_news_rss(query, max_items=6):
    try:
        url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(query)
            + "&hl=en-US&gl=US&ceid=US:en"
        )

        xml = requests.get(url, timeout=15).text
        root = ET.fromstring(xml)

        items = []
        for item in root.findall("./channel/item")[:max_items]:
            title = item.findtext("title") or ""
            source = ""
            src = item.find("source")
            if src is not None and src.text:
                source = src.text

            if title:
                items.append({
                    "title": title,
                    "source": source or "Google News"
                })

        return items
    except Exception:
        return []


def gdelt_news(query, max_items=6):
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=14)

        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": max_items,
            "startdatetime": start.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end.strftime("%Y%m%d%H%M%S")
        }

        data = requests.get(url, params=params, timeout=15).json()
        articles = data.get("articles", [])

        items = []
        for a in articles[:max_items]:
            title = a.get("title", "")
            source = a.get("domain", "")
            if title:
                items.append({
                    "title": title,
                    "source": source or "GDELT"
                })

        return items
    except Exception:
        return []


def score_news_items(items):
    text = " ".join([x["title"].lower() for x in items])
    pos = sum(1 for w in POS_WORDS if w in text)
    neg = sum(1 for w in NEG_WORDS if w in text)

    raw = pos - neg

    if len(items) >= 8:
        raw += 1
    elif len(items) <= 2:
        raw -= 0.5

    return max(-5, min(5, raw))


def news_context(topic):
    cached_value = cached(topic, NEWS_CACHE)
    if cached_value is not None:
        return cached_value

    query = NEWS_QUERIES.get(topic, topic)

    gdelt = gdelt_news(query, 6)
    google = google_news_rss(query, 6)

    combined = []
    seen = set()

    for item in gdelt + google:
        key = item["title"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            combined.append(item)

    combined = combined[:8]
    news_score = score_news_items(combined)

    headlines = []
    for item in combined[:3]:
        src = item["source"]
        title = item["title"]
        headlines.append(f"{title} ({src})")

    result = {
        "count": len(combined),
        "score": round(news_score, 1),
        "headlines": headlines,
    }

    set_cache(topic, NEWS_CACHE, result)
    return result


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
        0.15 * week +
        0.30 * month +
        0.40 * q3 +
        0.15 * half -
        0.75 * vol
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
            time.sleep(0.3)

    ctx = {
        "spy": perf(price_cache.get("SPY"), 21),
        "qqq": perf(price_cache.get("QQQ"), 21),
        "soxx": perf(price_cache.get("SOXX"), 21),
        "eem": perf(price_cache.get("EEM"), 21),
        "eis": perf(price_cache.get("EIS"), 21),
        "gld": perf(price_cache.get("GLD"), 21),
        "uso": perf(price_cache.get("USO"), 21),
        "uup": perf(price_cache.get("UUP"), 21),
        "tlt": perf(price_cache.get("TLT"), 21),
        "news": {
            "oil": news_context("oil"),
            "war": news_context("war"),
            "ai": news_context("ai"),
            "rates": news_context("rates"),
            "china": news_context("china"),
            "recession": news_context("recession"),
            "banks": news_context("banks"),
            "gold": news_context("gold"),
        },
        "summary": []
    }

    if ctx["spy"] > 2 and ctx["qqq"] > 2:
        ctx["summary"].append("🟢 שוק מניות חיובי לפי SPY/QQQ")
    elif ctx["spy"] < -2 or ctx["qqq"] < -2:
        ctx["summary"].append("🔴 לחץ בשוק המניות לפי SPY/QQQ")
    else:
        ctx["summary"].append("🟡 שוק מניות ניטרלי")

    if ctx["soxx"] > 3 and ctx["news"]["ai"]["score"] > 0:
        ctx["summary"].append("🚀 שבבים/AI חיוביים: גם SOXX חזק וגם כותרות תומכות")

    if ctx["uso"] > 5 and ctx["news"]["oil"]["count"] >= 5:
        ctx["summary"].append("⚠️ נפט בתנועה חדה + עומס חדשות: סיכון לתיקון אם האירוע יירגע")

    if ctx["uup"] > 2:
        ctx["summary"].append("💵 דולר מתחזק — תומך חשיפה דולרית, אך יכול ללחוץ סחורות/שווקים מתעוררים")

    if ctx["tlt"] < -2 or ctx["news"]["rates"]["score"] < 0:
        ctx["summary"].append("📉 ריבית/אג״ח לוחצים על נכסי סיכון")

    return ctx


def topic_for_theme(theme):
    if theme in ["semis", "tech"]:
        return "ai"
    if theme in ["oil", "energy"]:
        return "oil"
    if theme in ["gold", "silver"]:
        return "gold"
    if theme in ["asia", "china", "emerging"]:
        return "china"
    if theme == "israel":
        return "war"
    if theme == "banks":
        return "banks"
    if theme == "dollar":
        return "rates"
    return "rates"


def make_news_lines(fund, ctx, adj, reasons):
    topic = topic_for_theme(fund["theme"])
    n = ctx["news"].get(topic, {"count": 0, "score": 0, "headlines": []})

    lines = []
    lines.append(f"ניקוד אקטואלי: {adj}. מקור: GDELT + Google News RSS, {n['count']} כותרות רלוונטיות ב־14 יום.")

    if n["score"] > 1:
        lines.append("כיוון חדשות: חיובי/תומך — רוב הכותרות תומכות בהמשך המגמה.")
    elif n["score"] < -1:
        lines.append("כיוון חדשות: שלילי/זהיר — הכותרות כוללות סיכוני מאקרו/ירידות/חשש.")
    else:
        lines.append("כיוון חדשות: מעורב — אין יתרון חד משמעי מהאקטואליה בלבד.")

    if reasons:
        lines.append("מסקנה קדימה: " + " | ".join(reasons[:3]))

    if n["headlines"]:
        lines.append("כותרות לדוגמה:")
        for h in n["headlines"][:3]:
            lines.append("• " + h)
    else:
        lines.append("לא נמצאו כותרות מספיק ברורות לנושא — הניקוד נשען בעיקר על הגרף/מאקרו.")

    return "<br>".join(lines)


def forward_adjust(fund, ctx, data):
    theme = fund["theme"]
    risk = fund["risk"]

    adj = 0
    reasons = []

    topic = topic_for_theme(theme)
    topic_news = ctx["news"].get(topic, {"score": 0, "count": 0})
    news_score = topic_news["score"]

    # השפעת חדשות אמיתיות
    adj += news_score * 0.8
    if news_score > 1:
        reasons.append("חדשות רלוונטיות תומכות בכיוון")
    elif news_score < -1:
        reasons.append("חדשות רלוונטיות מזהירות מהמשך")

    # שוק כללי
    if ctx["spy"] > 2 and ctx["qqq"] > 2:
        if theme in ["market", "tech", "semis", "asia", "emerging"]:
            adj += 2
            reasons.append("שוק מניות עולמי תומך")
    elif ctx["spy"] < -2 or ctx["qqq"] < -2:
        if theme in ["market", "tech", "semis", "asia", "emerging"]:
            adj -= 3
            reasons.append("לחץ בשוק מניות פוגע בהמשך")

    if theme == "semis":
        if ctx["soxx"] > 3:
            adj += 3
            reasons.append("שבבים חזקים בגרף")
        if ctx["news"]["ai"]["score"] > 1:
            adj += 2
            reasons.append("AI/שבבים נתמכים בכותרות")
        if ctx["qqq"] < -2:
            adj -= 2
            reasons.append("נאסד״ק חלש פוגע בשבבים")

    if theme == "tech":
        if ctx["news"]["ai"]["score"] > 1:
            adj += 2
            reasons.append("אקטואליית AI תומכת בטכנולוגיה")
        if ctx["uup"] > 2 or ctx["news"]["rates"]["score"] < -1:
            adj -= 2
            reasons.append("דולר/ריבית עלולים ללחוץ על טכנולוגיה")

    if theme == "oil":
        if ctx["uso"] > 5 and ctx["news"]["oil"]["count"] >= 5:
            adj -= 6
            reasons.append("נפט עלה סביב עומס אקטואלי — סיכון ירידה אם המתיחות תרד")
        elif ctx["uso"] > 5:
            adj -= 3
            reasons.append("נפט לאחר עלייה חדה — סיכון תיקון")
        elif ctx["uso"] < -3:
            adj -= 2
            reasons.append("מגמת נפט שלילית")

    if theme == "energy":
        if ctx["uso"] > 3 and ctx["news"]["oil"]["score"] >= 0:
            adj += 2
            reasons.append("אנרגיה נתמכת בנפט ובחדשות שאינן שליליות")
        elif ctx["news"]["oil"]["count"] >= 5:
            adj -= 2
            reasons.append("אנרגיה חשופה לתיקון אם אקטואליית נפט תירגע")

    if theme in ["gold", "silver"]:
        if ctx["news"]["war"]["score"] < -1 or ctx["gld"] > 3:
            adj += 3
            reasons.append("חשש/תנודתיות תומכים בסחורות הגנתיות")
        if ctx["spy"] > 2 and ctx["qqq"] > 2:
            adj -= 2
            reasons.append("שוק מניות חיובי מפחית צורך בהגנה")
        if ctx["uup"] > 2:
            adj -= 1
            reasons.append("דולר חזק מקשה על מתכות")

    if theme in ["asia", "emerging"]:
        if ctx["eem"] > 2:
            adj += 3
            reasons.append("שווקים מתעוררים חזקים")
        if ctx["uup"] > 2:
            adj -= 2
            reasons.append("דולר חזק פוגע בשווקים מתעוררים")
        if ctx["news"]["recession"]["score"] < -1:
            adj -= 2
            reasons.append("חשש האטה עולמית")

    if theme == "china":
        if ctx["news"]["china"]["score"] < -1:
            adj -= 3
            reasons.append("חדשות סין שליליות/רגישות")
        elif ctx["news"]["china"]["score"] > 1:
            adj += 2
            reasons.append("חדשות סין תומכות/תמריצים")
        if ctx["eem"] > 2:
            adj += 1
            reasons.append("מתעוררים חיוביים נותנים תמיכה חלקית")

    if theme == "israel":
        if ctx["eis"] > 2:
            adj += 2
            reasons.append("ישראל חיובית לפי proxy")
        if ctx["news"]["war"]["score"] < -1:
            adj -= 3
            reasons.append("סיכון גיאופוליטי מקומי")
        if ctx["eis"] < -2:
            adj -= 2
            reasons.append("ישראל חלשה בגרף")

    if theme == "banks":
        if ctx["news"]["rates"]["score"] > 0:
            adj += 1
            reasons.append("ריבית יכולה לתמוך במרווחי בנקים")
        if ctx["news"]["recession"]["score"] < -1 or ctx["news"]["banks"]["score"] < -1:
            adj -= 3
            reasons.append("חשש האטה/אשראי פוגע בבנקים")

    if theme == "dollar":
        if ctx["uup"] > 2:
            adj += 2
            reasons.append("דולר במגמת התחזקות")
        if ctx["spy"] > 2 and ctx["qqq"] > 2:
            adj -= 1
            reasons.append("Risk-on מפחית עדיפות לדולר")

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

    return round(adj, 1), reasons


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
.reason{font-size:11px;text-align:right;min-width:260px;line-height:1.45}
</style>
</head>
<body>

<h2>📊 סורק מוצרי השקעה PRO</h2>

<div class="legend">
<b>מקרא:</b><br>
🔥 מעל 8 = חזק מאוד | 🟢 4–8 = קנייה | 🟡 1–4 = מעקב | 🔴 מתחת 1 = להימנע<br>
<b>מה הציון כולל:</b><br>
הסורק מדרג מוצרי השקעה: קרנות סל, קרנות מחקות, קרנות נאמנות, מדדים וקרנות ממונפות. הציון כולל גרף + מאקרו + אקטואליה אמיתית מ־GDELT ו־Google News RSS + הסתכלות קדימה + קנס סיכון.
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
        `<div class="spinner">⏳</div><div>מנתח גרף + אקטואליה אמיתית... ${seconds} שניות</div><div style="font-size:13px;color:#555">יכול לקחת עד כמה דקות</div>`;
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

        let r = await fetch('/scan?ts=' + Date.now(), {signal: controller.signal, cache: "no-store"});
        clearTimeout(timeoutId);

        let d = await r.json();

        document.getElementById("market").innerHTML =
            `<div class="legend"><b>מצב שוק:</b><br>${d.market.join("<br>")}</div>`;

let html="<tr><th>#</th><th>שם מוצר / קרן / מדד</th><th>מס׳ נייר</th><th>בסיס ניתוח</th><th>סוג / סיכון</th><th>חודש</th><th>3ח׳</th><th>חצי שנה</th><th>גרף</th><th>אקטואלי</th><th>סופי</th><th>המלצה</th><th>אקטואליה — למה?</th></tr>";
        d.results.forEach((x,i)=>{
            let cls="bad";
            if(x.reco.includes("קנייה") || x.reco.includes("חזק")) cls="buy";
            else if(x.reco.includes("מעקב")) cls="mid";

            html+=`<tr>
                <td>${i+1}</td>
                <td>${x.name}</td>
                <td>${x.sec_no}</td>
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
                time.sleep(0.3)

            prices = price_cache.get(proxy)
            if not prices:
                errors.append(fund["name"])
                continue

            data = calc_graph(prices)
            adj, reasons = forward_adjust(fund, ctx, data)
            final_score = round(data["graph_score"] + adj, 1)

            results.append({
                "name": fund["name"],
                "sec_no": fund["sec_no"],
                "proxy": proxy,
                "risk": fund["risk"],
                **data,
                "forward_adj": adj,
                "final_score": final_score,
                "reco": recommendation(final_score, fund["risk"]),
                "reason": make_news_lines(fund, ctx, adj, reasons)
            })

        except Exception as e:
            errors.append(f"{fund['name']}: {e}")

    results = sorted(results, key=lambda x: x["final_score"], reverse=True)[:10]

    return jsonify({
        "market": ctx["summary"],
        "results": results,
        "errors": errors
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
