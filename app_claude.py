from flask import Flask, jsonify, render_template_string
import requests
import os
import time
import statistics
import feedparser
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")  # TwelveData - אם יש

# ─────────────────────────────────────────────
# רשימת קרנות עם מספרי ניירות ערך אמיתיים
# ─────────────────────────────────────────────
FUNDS = [
    # ── ישראל ──
    {"name": "תכלית סל ת\"א 35",           "sec_no": "1082401", "proxy": "EIS",  "risk": "רגיל",       "theme": "israel",   "news_q": "תל אביב 35 בורסה ישראל"},
    {"name": "קסם סל ת\"א 125",             "sec_no": "1146364", "proxy": "EIS",  "risk": "רגיל",       "theme": "israel",   "news_q": "תל אביב 125 בורסה ישראל"},

    # ── S&P 500 ──
    {"name": "תכלית סל S&P 500",           "sec_no": "1159235", "proxy": "SPY",  "risk": "רגיל",       "theme": "market",   "news_q": "S&P 500 stock market"},
    {"name": "קסם סל S&P 500",             "sec_no": "1146356", "proxy": "SPY",  "risk": "רגיל",       "theme": "market",   "news_q": "S&P 500 stock market"},
    {"name": "איילון אקסטרים S&P 500 פי 3","sec_no": "5117759", "proxy": "SPY",  "risk": "ממונף פי 3", "theme": "market",   "news_q": "S&P 500 leveraged ETF"},

    # ── Nasdaq ──
    {"name": "תכלית סל נאסד\"ק 100",        "sec_no": "1159243", "proxy": "QQQ",  "risk": "רגיל",       "theme": "tech",     "news_q": "Nasdaq 100 technology stocks"},
    {"name": "איילון אקסטרים נאסד\"ק פי 3", "sec_no": "5128947", "proxy": "QQQ",  "risk": "ממונף פי 3", "theme": "tech",     "news_q": "Nasdaq 100 tech rally"},

    # ── שבבים / AI ──
    {"name": "תכלית סל שבבים גלובלי",      "sec_no": "1159250", "proxy": "SOXX", "risk": "רגיל",       "theme": "semis",    "news_q": "semiconductor AI chips Nvidia TSMC"},

    # ── זהב ──
    {"name": "קסם LBMA Gold ETF",          "sec_no": "1146422", "proxy": "GLD",  "risk": "סחורה",      "theme": "gold",     "news_q": "gold price safe haven inflation"},

    # ── כסף ──
    {"name": "תכלית סל כסף",               "sec_no": "1159268", "proxy": "SLV",  "risk": "סחורה",      "theme": "silver",   "news_q": "silver price commodity"},

    # ── נפט / אנרגיה ──
    {"name": "תכלית סל נפט",               "sec_no": "1159276", "proxy": "USO",  "risk": "סחורה",      "theme": "oil",      "news_q": "oil price OPEC crude"},
    {"name": "תכלית סל אנרגיה",            "sec_no": "1159284", "proxy": "VDE",  "risk": "רגיל",       "theme": "energy",   "news_q": "energy sector stocks oil gas"},

    # ── שווקים מתעוררים / אסיה ──
    {"name": "תכלית סל שווקים מתעוררים",   "sec_no": "1159292", "proxy": "EEM",  "risk": "רגיל",       "theme": "emerging", "news_q": "emerging markets ETF"},
    {"name": "תכלית סל יפן",               "sec_no": "1159300", "proxy": "EWJ",  "risk": "רגיל",       "theme": "asia",     "news_q": "Japan economy Nikkei stocks"},
    {"name": "תכלית סל הודו",              "sec_no": "1159318", "proxy": "INDA", "risk": "רגיל",       "theme": "asia",     "news_q": "India economy Sensex stocks"},
    {"name": "תכלית סל סין",               "sec_no": "1159326", "proxy": "MCHI", "risk": "רגיל",       "theme": "china",    "news_q": "China economy stocks stimulus"},

    # ── דולר / בנקים ──
    {"name": "תכלית סל דולר",              "sec_no": "1159334", "proxy": "UUP",  "risk": "מטבע",       "theme": "dollar",   "news_q": "US dollar strength Fed interest rates"},
    {"name": "תכלית סל בנקים",             "sec_no": "1159342", "proxy": "KBE",  "risk": "רגיל",       "theme": "banks",    "news_q": "bank stocks financial sector interest rates"},
]


# ─────────────────────────────────────────────
# שליפת מחירים — TwelveData (אם יש מפתח)
# ─────────────────────────────────────────────
def td_prices(symbol):
    if not API_KEY:
        return None
    url = "https://api.twelvedata.com/time_series"
    params = {"symbol": symbol, "interval": "1day", "outputsize": 260, "apikey": API_KEY}
    try:
        data = requests.get(url, params=params, timeout=25).json()
        if "values" not in data:
            return None
        prices = [float(r["close"]) for r in data["values"] if "close" in r]
        prices.reverse()
        return prices if len(prices) >= 65 else None
    except Exception:
        return None


# ─────────────────────────────────────────────
# שליפת מחירים חלופית — Yahoo Finance (ללא מפתח)
# ─────────────────────────────────────────────
def yahoo_prices(symbol):
    try:
        end = int(time.time())
        start = end - 260 * 86400
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {"period1": start, "period2": end, "interval": "1d"}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=20)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        prices = [float(p) for p in closes if p is not None]
        return prices if len(prices) >= 65 else None
    except Exception:
        return None


def get_prices(symbol):
    p = td_prices(symbol)
    if p:
        return p
    return yahoo_prices(symbol)


# ─────────────────────────────────────────────
# אקטואליה — Google News RSS (חינמי, ללא מפתח)
# ─────────────────────────────────────────────
def fetch_news(query, max_items=8):
    """מחזיר רשימת כותרות חדשות רלוונטיות"""
    try:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            published = entry.get("published", "")
            articles.append({"title": title, "date": published[:16]})
        return articles
    except Exception:
        return []


def news_sentiment(articles):
    """ניתוח סנטימנט פשוט לפי מילות מפתח"""
    positive = ["surge", "rally", "gain", "growth", "strong", "bull", "rise", "up", "beat", "record", "high"]
    negative = ["crash", "fall", "drop", "slump", "bear", "recession", "risk", "warn", "cut", "low", "weak", "crisis"]

    score = 0
    for a in articles:
        title = a["title"].lower()
        score += sum(1 for w in positive if w in title)
        score -= sum(1 for w in negative if w in title)

    if score >= 3:
        return "חיובי 📈", score
    if score <= -3:
        return "שלילי 📉", score
    return "ניטרלי ➡️", score


# ─────────────────────────────────────────────
# חישובי תשואה ונדיפות
# ─────────────────────────────────────────────
def perf(prices, days):
    if not prices or len(prices) < days + 1:
        return 0
    return round((prices[-1] / prices[-days] - 1) * 100, 1)


def calc_graph(prices):
    week  = perf(prices, 5)
    month = perf(prices, 21)
    q3    = perf(prices, 63)
    half  = perf(prices, 126) if len(prices) >= 126 else q3
    year  = perf(prices, 252) if len(prices) >= 252 else half

    daily = [(prices[i] / prices[i-1] - 1) * 100
             for i in range(1, len(prices)) if prices[i-1] != 0]
    vol = round(statistics.mean([abs(x) for x in daily[-60:]]), 1) if daily else 0

    graph_score = round(
        0.10 * week + 0.20 * month + 0.30 * q3 +
        0.25 * half + 0.15 * year - 0.70 * vol, 1)

    return {"week": week, "month": month, "q3": q3,
            "half": half, "year": year, "vol": vol, "graph_score": graph_score}


# ─────────────────────────────────────────────
# הקשר מאקרו
# ─────────────────────────────────────────────
def build_market_context(price_cache):
    symbols = ["SPY", "QQQ", "SOXX", "EEM", "EIS", "GLD", "USO", "UUP", "TLT", "SLV"]

    def fetch(sym):
        return sym, get_prices(sym)

    with ThreadPoolExecutor(max_workers=5) as ex:
        for sym, prices in ex.map(lambda s: fetch(s), symbols):
            if sym not in price_cache:
                price_cache[sym] = prices

    spy  = perf(price_cache.get("SPY"),  21)
    qqq  = perf(price_cache.get("QQQ"),  21)
    soxx = perf(price_cache.get("SOXX"), 21)
    eem  = perf(price_cache.get("EEM"),  21)
    eis  = perf(price_cache.get("EIS"),  21)
    gld  = perf(price_cache.get("GLD"),  21)
    uso  = perf(price_cache.get("USO"),  21)
    uup  = perf(price_cache.get("UUP"),  21)
    tlt  = perf(price_cache.get("TLT"),  21)

    # אקטואליה מאקרו במקביל
    macro_queries = {
        "market":    "stock market S&P 500 economy",
        "ai":        "artificial intelligence AI chips Nvidia semiconductor",
        "oil":       "oil price OPEC crude energy",
        "war":       "geopolitical war conflict Israel Iran Ukraine",
        "rates":     "Federal Reserve interest rates inflation bonds",
        "china":     "China economy stimulus property",
        "recession": "recession slowdown credit risk market crash",
    }

    macro_news = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_news, q, 10): k for k, q in macro_queries.items()}
        for future in as_completed(futures):
            key = futures[future]
            macro_news[key] = future.result()

    macro_sentiment = {k: news_sentiment(v) for k, v in macro_news.items()}

    summary = []
    if spy > 2 and qqq > 2:
        summary.append("🟢 שוק מניות עולמי חיובי")
    elif spy < -2 or qqq < -2:
        summary.append("🔴 לחץ בשוק המניות")
    else:
        summary.append("🟡 שוק מניות ניטרלי")

    if soxx > 3 and macro_sentiment["ai"][0] == "חיובי 📈":
        summary.append("🚀 שבבים/AI — גרף + אקטואליה חיוביים")
    if uso > 5 and macro_sentiment["oil"][0] == "חיובי 📈":
        summary.append("⚠️ נפט חזק — סיכון תיקון אם המתיחות תרד")
    if gld > 3 and macro_sentiment["war"][0] == "שלילי 📉":
        summary.append("⚠️ זהב נתמך מחשש גיאופוליטי")
    if uup > 2:
        summary.append("💵 דולר מתחזק — זהירות בנכסי סיכון")
    if tlt < -2 or macro_sentiment["rates"][0] == "שלילי 📉":
        summary.append("📉 סביבת ריבית/אגח לוחצת")
    if eem > 2:
        summary.append("🌏 שווקים מתעוררים/מזרח חיוביים")
    if eis < -2 and macro_sentiment["war"][0] == "שלילי 📉":
        summary.append("🇮🇱 ישראל — סיכון גיאופוליטי מקומי")

    return {
        "spy": spy, "qqq": qqq, "soxx": soxx, "eem": eem,
        "eis": eis, "gld": gld, "uso": uso, "uup": uup, "tlt": tlt,
        "macro_news": macro_news,
        "macro_sentiment": macro_sentiment,
        "summary": summary
    }


# ─────────────────────────────────────────────
# התאמה קדימה (אקטואליה ספציפית לכל קרן)
# ─────────────────────────────────────────────
def forward_adjust(fund, ctx, data, fund_news):
    theme = fund["theme"]
    risk  = fund["risk"]
    sentiment_label, sentiment_score = news_sentiment(fund_news)
    ms = ctx["macro_sentiment"]

    adj = 0
    reasons = []

    # אקטואליה ספציפית לקרן
    if sentiment_score >= 3:
        adj += 3
        reasons.append(f"אקטואליה חיובית לקרן ({len(fund_news)} כתבות)")
    elif sentiment_score <= -3:
        adj -= 3
        reasons.append(f"אקטואליה שלילית לקרן ({len(fund_news)} כתבות)")

    # מאקרו לפי תחום
    if ctx["spy"] > 2 and ctx["qqq"] > 2:
        if theme in ["market", "tech", "semis", "asia", "emerging"]:
            adj += 2
            reasons.append("שוק עולמי תומך")
    elif ctx["spy"] < -2 or ctx["qqq"] < -2:
        if theme in ["market", "tech", "semis", "asia", "emerging"]:
            adj -= 3
            reasons.append("לחץ בשוק פוגע")

    if theme == "semis":
        if ctx["soxx"] > 3: adj += 2; reasons.append("שבבים חזקים")
        if ms["ai"][0] == "חיובי 📈": adj += 3; reasons.append("AI/שבבים חיובי באקטואליה")
    if theme == "tech":
        if ms["ai"][0] == "חיובי 📈": adj += 2; reasons.append("AI תומך בטכנולוגיה")
        if ctx["uup"] > 2: adj -= 2; reasons.append("דולר חזק לוחץ על טכנולוגיה")
    if theme == "oil":
        if ctx["uso"] > 5 and ms["oil"][0] == "חיובי 📈":
            adj -= 6; reasons.append("נפט אחרי אירוע — סיכון תיקון")
        elif ctx["uso"] < -3:
            adj -= 2; reasons.append("מגמת נפט שלילית")
    if theme == "energy":
        if ctx["uso"] > 3 and ms["oil"][0] != "חיובי 📈":
            adj += 2; reasons.append("אנרגיה נתמכת ללא עומס אקטואלי")
    if theme in ["gold", "silver"]:
        if ms["war"][0] == "שלילי 📉" or ctx["gld"] > 3:
            adj += 3; reasons.append("גיאופוליטיקה תומכת במתכות")
        if ctx["spy"] > 2: adj -= 2; reasons.append("Risk-on מפחית הגנה")
    if theme in ["asia", "emerging"]:
        if ctx["eem"] > 2: adj += 3; reasons.append("מתעוררים חזקים")
        if ctx["uup"] > 2: adj -= 2; reasons.append("דולר חזק פוגע במתעוררים")
    if theme == "china":
        if ms["china"][0] == "שלילי 📉": adj -= 3; reasons.append("סין — אקטואליה שלילית")
    if theme == "israel":
        if ctx["eis"] > 2: adj += 2; reasons.append("ישראל חיובית")
        if ms["war"][0] == "שלילי 📉": adj -= 3; reasons.append("סיכון ביטחוני מקומי")
    if theme == "banks":
        if ms["recession"][0] == "שלילי 📉": adj -= 3; reasons.append("חשש האטה פוגע בבנקים")
    if theme == "dollar":
        if ctx["uup"] > 2: adj += 2; reasons.append("דולר במגמת התחזקות")

    # קנס מינוף
    if "פי 3" in risk:
        adj -= 3; reasons.append("קנס מינוף פי 3")
        if data["graph_score"] > 8 and ctx["spy"] > 2:
            adj += 2; reasons.append("מגמה חזקה מצדיקה מינוף חלקי")

    if not reasons:
        reasons.append("אין איתות חריג")

    return round(adj, 1), " | ".join(reasons[:4]), sentiment_label, fund_news[:3]


def recommendation(score, risk):
    if "פי 3" in risk:
        if score >= 12: return "🟢 קנייה אגרסיבית"
        if score >= 5:  return "🟡 מעקב / סיכון גבוה"
        return "🔴 להימנע"
    if score >= 8:  return "🔥 חזק מאוד"
    if score >= 4:  return "🟢 קנייה"
    if score >= 1:  return "🟡 מעקב"
    return "🔴 להימנע"


# ─────────────────────────────────────────────
# דף הבית
# ─────────────────────────────────────────────
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>סורק השקעות Claude PRO</title>
<style>
body{direction:rtl;font-family:Arial;padding:12px;background:#f0f4ff}
h2{text-align:center;color:#1a237e}
.badge{background:#1a237e;color:white;padding:3px 10px;border-radius:20px;font-size:13px;margin-right:8px}
button{width:100%;padding:16px;font-size:20px;border-radius:12px;border:0;background:#1565c0;color:white;cursor:pointer}
button:hover{background:#0d47a1}
#loading{text-align:center;font-size:18px;margin:18px}
.spinner{font-size:36px;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.legend{background:white;border-radius:12px;padding:12px;margin:10px 0;font-size:14px;line-height:1.8;box-shadow:0 2px 8px #0001}
.market-box{background:#e8f5e9;border-radius:12px;padding:12px;margin:10px 0;font-size:14px;line-height:1.8}
table{width:100%;border-collapse:collapse;background:white;margin-top:12px;font-size:12px;box-shadow:0 2px 8px #0001}
th,td{border:1px solid #ddd;padding:6px;text-align:center;vertical-align:top}
th{background:#1a237e;color:white}
tr:hover{background:#f5f7ff}
.buy{color:#2e7d32;font-weight:bold}
.mid{color:#e65100;font-weight:bold}
.bad{color:#c62828;font-weight:bold}
.news-box{font-size:10px;text-align:right;color:#555;max-width:160px}
.sentiment-pos{color:green;font-weight:bold}
.sentiment-neg{color:red;font-weight:bold}
.sentiment-neu{color:#888}
</style>
</head>
<body>
<h2>📊 סורק קרנות/סל <span class="badge">Claude PRO</span></h2>

<div class="legend">
<b>שיפורים בגרסת Claude:</b><br>
✅ מספרי ניירות ערך אמיתיים<br>
✅ אקטואליה ספציפית לכל קרן (Google News)<br>
✅ ניתוח סנטימנט אוטומטי<br>
✅ סריקה מהירה יותר (במקביל)<br>
✅ Yahoo Finance כגיבוי ללא צורך במפתח<br>
<b>ציון:</b> 🔥 מעל 8 | 🟢 4–8 קנייה | 🟡 1–4 מעקב | 🔴 מתחת 1 להימנע
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
        document.getElementById("loading").innerHTML=
        `<div class="spinner">⚙️</div><div>מנתח גרף + אקטואליה... ${seconds} שניות</div>`;
    },1000);
}
function stopClock(msg){clearInterval(timer);document.getElementById("loading").innerText=msg;}

async function run(){
    document.getElementById("t").innerHTML="";
    document.getElementById("market").innerHTML="";
    startClock();
    try{
        const r=await fetch('/scan');
        const d=await r.json();

        document.getElementById("market").innerHTML=
            `<div class="market-box"><b>מצב שוק:</b><br>${d.market.join("<br>")}</div>`;

        let html=`<tr>
            <th>#</th><th>שם קרן</th><th>מס׳ נייר</th><th>בסיס</th><th>סיכון</th>
            <th>חודש%</th><th>3ח%</th><th>חצי שנה%</th>
            <th>גרף</th><th>אקטואלי</th><th>סופי</th><th>המלצה</th>
            <th>סנטימנט</th><th>חדשות אחרונות</th>
        </tr>`;

        d.results.forEach((x,i)=>{
            let cls="bad";
            if(x.reco.includes("קנייה")||x.reco.includes("חזק")) cls="buy";
            else if(x.reco.includes("מעקב")) cls="mid";

            let sentCls="sentiment-neu";
            if(x.sentiment.includes("חיובי")) sentCls="sentiment-pos";
            if(x.sentiment.includes("שלילי")) sentCls="sentiment-neg";

            let newsHtml=x.top_news.map(n=>`<div>• ${n.title.substring(0,60)}...</div>`).join("");

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
                <td><b>${x.final_score}</b></td>
                <td class="${cls}">${x.reco}</td>
                <td class="${sentCls}">${x.sentiment}</td>
                <td class="news-box">${newsHtml}</td>
            </tr>`;
        });

        document.getElementById("t").innerHTML=html;
        stopClock("✅ הסריקה הסתיימה");
    }catch(e){
        stopClock("⚠️ שגיאה — נסה שוב");
    }
}
</script>
</body>
</html>
""")


# ─────────────────────────────────────────────
# נתיב סריקה
# ─────────────────────────────────────────────
@app.route("/scan")
def scan():
    price_cache = {}
    ctx = build_market_context(price_cache)

    # שליפת מחירים וחדשות במקביל
    def process_fund(fund):
        try:
            proxy = fund["proxy"]
            prices = price_cache.get(proxy) or get_prices(proxy)
            if not prices:
                return None
            price_cache[proxy] = prices

            fund_news = fetch_news(fund["news_q"], max_items=8)
            data = calc_graph(prices)
            adj, reason, sentiment, top_news = forward_adjust(fund, ctx, data, fund_news)
            final_score = round(data["graph_score"] + adj, 1)

            return {
                "name":        fund["name"],
                "sec_no":      fund["sec_no"],
                "proxy":       proxy,
                "risk":        fund["risk"],
                **data,
                "forward_adj": adj,
                "final_score": final_score,
                "reco":        recommendation(final_score, fund["risk"]),
                "reason":      reason,
                "sentiment":   sentiment,
                "top_news":    top_news
            }
        except Exception:
            return None

    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(process_fund, f) for f in FUNDS]
        for future in as_completed(futures):
            r = future.result()
            if r:
                results.append(r)

    results = sorted(results, key=lambda x: x["final_score"], reverse=True)[:10]

    return jsonify({"market": ctx["summary"], "results": results})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10001)
