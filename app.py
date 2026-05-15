from flask import Flask, jsonify, render_template_string, request
import requests
import os
import time
import statistics
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, time as dtime
from urllib.parse import quote_plus

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


app = Flask(__name__)
API_KEY = os.getenv("API_KEY")

# ============================================================
# הגדרות Cache
# ============================================================

ISRAEL_TZ_NAME = "Asia/Jerusalem"
ISRAEL_TZ = ZoneInfo(ISRAEL_TZ_NAME) if ZoneInfo else None

RESULT_CACHE_FILE = "scanner_results_cache.json"
RESULT_CACHE_TTL_SECONDS = 4 * 60 * 60      # 4 שעות
DAILY_RESET_HOUR = 23
DAILY_RESET_MINUTE = 30

PRICE_CACHE = {}
NEWS_CACHE = {}
IN_MEMORY_CACHE_SECONDS = 900               # cache פנימי למחירים/חדשות בזמן ריצה


# ============================================================
# רשימת קרנות להצגה
# חשוב:
# 1. כל מוצר כאן חייב להיות ניתן לרכישה בישראל.
# 2. אין יותר "בדוק בבנק".
# 3. אם לא בטוח שמוצר קיים — enabled=False והוא לא יוצג.
# 4. proxy = בסיס הניתוח הגרפי/אקטואלי בחו"ל.
# 5. sec_no = מספר נייר ישראלי לרכישה בארץ.
# ============================================================

FUNDS = [
    # ========================================================
    # סחורות
    # ========================================================
    {"enabled": True, "name": "קסם LBMA Gold Price PM USD ETF", "sec_no": "1146422", "proxy": "GLD", "risk": "סחורה", "theme": "gold", "exposure_type": "זהב / חשיפה לסחורה"},
    {"enabled": True, "name": "תכלית סל Bloomberg Silver", "sec_no": "1144542", "proxy": "SLV", "risk": "סחורה", "theme": "silver", "exposure_type": "כסף / חשיפה לסחורה"},

    # ========================================================
    # ארה״ב - מדדים רחבים
    # ========================================================
    {"enabled": True, "name": "קסם S&P 500 ETF", "sec_no": "1146471", "proxy": "SPY", "risk": "רגיל", "theme": "market", "exposure_type": "חשיפה ל-S&P 500 דרך מוצר ישראלי"},
    {"enabled": True, "name": "iShares Core S&P 500 UCITS ETF - נסחר בארץ", "sec_no": "1159250", "proxy": "SPY", "risk": "רגיל", "theme": "market", "exposure_type": "קרן חוץ נסחרת בארץ על S&P 500"},
    {"enabled": True, "name": "Invesco S&P 500 UCITS ETF - נסחר בארץ", "sec_no": "1183441", "proxy": "SPY", "risk": "רגיל", "theme": "market", "exposure_type": "קרן חוץ נסחרת בארץ על S&P 500"},
    {"enabled": True, "name": "קסם S&P 500 KTF", "sec_no": "5124482", "proxy": "SPY", "risk": "רגיל", "theme": "market", "exposure_type": "קרן ישראלית מחקה S&P 500"},

    # ========================================================
    # נאסד״ק / טכנולוגיה
    # ========================================================
    {"enabled": True, "name": "תכלית סל NASDAQ 100 מנוטרלת מט״ח", "sec_no": "1143734", "proxy": "QQQ", "risk": "רגיל", "theme": "tech", "exposure_type": "חשיפה ל-Nasdaq 100 דרך מוצר ישראלי"},
    {"enabled": True, "name": "iShares NASDAQ 100 UCITS ETF - נסחר בארץ", "sec_no": "1159243", "proxy": "QQQ", "risk": "רגיל", "theme": "tech", "exposure_type": "קרן חוץ נסחרת בארץ על Nasdaq 100"},

    # ========================================================
    # ממונפות
    # ========================================================
    {"enabled": True, "name": "איילון אקסטרים Nasdaq 100 פי 3", "sec_no": "5128947", "proxy": "QQQ", "risk": "ממונף פי 3", "theme": "tech", "exposure_type": "חשיפה ממונפת לנאסד״ק"},
    {"enabled": True, "name": "איילון אקסטרים S&P 500 פי 3", "sec_no": "5117759", "proxy": "SPY", "risk": "ממונף פי 3", "theme": "market", "exposure_type": "חשיפה ממונפת ל-S&P 500"},

    # ========================================================
    # שבבים / AI / סייבר / רובוטיקה
    # ========================================================
    {"enabled": True, "name": "תכלית סל PHLX Semiconductor Sector", "sec_no": "1170703", "proxy": "SOXX", "risk": "רגיל", "theme": "semis", "exposure_type": "שבבים / Semiconductor"},
    {"enabled": True, "name": "קסם ISE Cyber Security ETF", "sec_no": "1168715", "proxy": "HACK", "risk": "רגיל", "theme": "cyber", "exposure_type": "סייבר"},
    {"enabled": True, "name": "תכלית סל ISE Cyber Security", "sec_no": "1144252", "proxy": "HACK", "risk": "רגיל", "theme": "cyber", "exposure_type": "סייבר"},
    {"enabled": True, "name": "אי.בי.אי. מחקה ISE Cyber Security", "sec_no": "5132527", "proxy": "HACK", "risk": "רגיל", "theme": "cyber", "exposure_type": "סייבר"},
    {"enabled": True, "name": "קסם אקטיב מניות רובוטיקה חו״ל", "sec_no": "5127253", "proxy": "BOTZ", "risk": "רגיל", "theme": "robotics", "exposure_type": "רובוטיקה / אוטומציה / AI"},

    # ========================================================
    # ביטחון / גרעין / אורניום
    # ========================================================
    {"enabled": True, "name": "קסם KTF אינדקס תעשיות ביטחוניות גלובלי", "sec_no": "5138748", "proxy": "ITA", "risk": "רגיל", "theme": "defense", "exposure_type": "תעשיות ביטחוניות גלובליות"},
    {"enabled": True, "name": "אי.בי.אי. מחקה Indxx Nuclear Energy Industry מנוטרלת דולר", "sec_no": "5140298", "proxy": "URA", "risk": "רגיל", "theme": "nuclear", "exposure_type": "אנרגיה גרעינית / אורניום"},

    # ========================================================
    # גלובלי / אירופה
    # ========================================================
    {"enabled": True, "name": "MTF מחקה MSCI World", "sec_no": "5122569", "proxy": "URTH", "risk": "רגיל", "theme": "world", "exposure_type": "מניות גלובליות / MSCI World"},
    {"enabled": True, "name": "iShares Core MSCI Europe UCITS ETF - נסחר בארץ", "sec_no": "1159094", "proxy": "VGK", "risk": "רגיל", "theme": "europe", "exposure_type": "אירופה / MSCI Europe"},

    # ========================================================
    # אסיה / מתעוררים
    # ========================================================
    {"enabled": True, "name": "קסם KOSPI 200 ETF", "sec_no": "1145754", "proxy": "EWY", "risk": "רגיל", "theme": "asia", "exposure_type": "חשיפה ישירה לקוריאה"},
    {"enabled": True, "name": "קסם MSCI India ETF", "sec_no": "1145747", "proxy": "INDA", "risk": "רגיל", "theme": "asia", "exposure_type": "חשיפה להודו"},
    {"enabled": True, "name": "תכלית סל MSCI India", "sec_no": "1144112", "proxy": "INDA", "risk": "רגיל", "theme": "asia", "exposure_type": "חשיפה להודו"},
    {"enabled": True, "name": "קסם MSCI Emerging Markets ETF מנוטרלת דולר", "sec_no": "1146737", "proxy": "EEM", "risk": "רגיל", "theme": "emerging", "exposure_type": "שווקים מתעוררים"},
    {"enabled": True, "name": "iShares Core MSCI EM IMI UCITS ETF - נסחר בארץ", "sec_no": "1159169", "proxy": "EEM", "risk": "רגיל", "theme": "emerging", "exposure_type": "קרן חוץ נסחרת בארץ על שווקים מתעוררים"},
    {"enabled": True, "name": "Invesco MSCI Emerging Markets UCITS ETF - נסחר בארץ", "sec_no": "1183490", "proxy": "EEM", "risk": "רגיל", "theme": "emerging", "exposure_type": "קרן חוץ נסחרת בארץ על שווקים מתעוררים"},

    # ========================================================
    # ישראל
    # ========================================================
    {"enabled": True, "name": "MTF סל ת״א 125", "sec_no": "1150283", "proxy": "EIS", "risk": "רגיל", "theme": "israel", "exposure_type": "ישראל / ת״א 125"},
    {"enabled": True, "name": "תכלית סל כשרה ת״א 125", "sec_no": "1155373", "proxy": "EIS", "risk": "רגיל", "theme": "israel", "exposure_type": "ישראל / ת״א 125"},

    # ========================================================
    # טייוואן
    # אין כרגע מוצר ישראלי ישיר פעיל שאומת, לכן EWT לא מוצג.
    # אם בעתיד נמצא מספר נייר ישראלי פעיל לטייוואן, מוסיפים כאן enabled=True עם proxy="EWT".
    # ========================================================
]

# ============================================================
# חדשות
# ============================================================

NEWS_QUERIES = {
    "oil": "oil price OR crude oil OR OPEC OR Strait of Hormuz OR sanctions OR tanker",
    "war": "war OR missile OR iran OR israel OR gaza OR ukraine OR red sea",
    "ai": "artificial intelligence OR AI chips OR Nvidia OR semiconductor OR TSMC",
    "rates": "interest rates OR federal reserve OR inflation OR bond yields",
    "china": "china economy OR china stimulus OR property crisis china",
    "recession": "recession OR slowdown OR market crash OR credit risk",
    "banks": "banks OR financial sector OR credit risk OR loan losses",
    "gold": "gold price OR safe haven OR treasury yields OR dollar",
    "cyber": "cybersecurity OR cyber attack OR ransomware OR hacking OR Palo Alto OR CrowdStrike",
    "robotics": "robotics OR automation OR industrial automation OR AI robotics",
    "defense": "defense stocks OR aerospace defense OR military spending OR defense contractors",
    "nuclear": "nuclear energy OR uranium OR reactors OR nuclear power OR uranium miners",
    "world": "global equities OR world stocks OR MSCI World OR developed markets",
    "europe": "Europe stocks OR ECB OR eurozone economy OR European equities",
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


# ============================================================
# פונקציות זמן ו-Cache תוצאות מלאות
# ============================================================

def now_israel():
    if ISRAEL_TZ:
        return datetime.now(ISRAEL_TZ)
    return datetime.now()


def timestamp_to_israel_datetime(ts):
    if ISRAEL_TZ:
        return datetime.fromtimestamp(ts, ISRAEL_TZ)
    return datetime.fromtimestamp(ts)


def today_reset_datetime():
    n = now_israel()
    return datetime.combine(
        n.date(),
        dtime(DAILY_RESET_HOUR, DAILY_RESET_MINUTE),
        tzinfo=ISRAEL_TZ
    ) if ISRAEL_TZ else datetime.combine(
        n.date(),
        dtime(DAILY_RESET_HOUR, DAILY_RESET_MINUTE)
    )


def result_cache_is_valid(cache_data):
    if not cache_data:
        return False

    saved_ts = cache_data.get("timestamp")
    if not saved_ts:
        return False

    current_ts = time.time()
    age_seconds = current_ts - saved_ts

    # חוק 1: תוצאה תקפה עד 4 שעות
    if age_seconds > RESULT_CACHE_TTL_SECONDS:
        return False

    # חוק 2: אם עברנו את 23:30 מאז הסריקה האחרונה — חובה לסרוק מחדש
    saved_dt = timestamp_to_israel_datetime(saved_ts)
    current_dt = now_israel()
    reset_dt = today_reset_datetime()

    if saved_dt < reset_dt <= current_dt:
        return False

    return True


def load_result_cache():
    if not os.path.exists(RESULT_CACHE_FILE):
        return None

    try:
        with open(RESULT_CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        if result_cache_is_valid(cache_data):
            return cache_data

        return None

    except Exception:
        return None


def save_result_cache(payload):
    cache_data = {
        "timestamp": time.time(),
        "saved_at": now_israel().strftime("%Y-%m-%d %H:%M:%S"),
        "payload": payload
    }

    with open(RESULT_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


def clear_result_cache():
    try:
        if os.path.exists(RESULT_CACHE_FILE):
            os.remove(RESULT_CACHE_FILE)
        return True
    except Exception:
        return False


def next_cache_reset_text():
    n = now_israel()
    reset_dt = today_reset_datetime()

    if n >= reset_dt:
        reset_dt = reset_dt + timedelta(days=1)

    return reset_dt.strftime("%Y-%m-%d %H:%M")


# ============================================================
# Cache פנימי למחירים/חדשות
# ============================================================

def cached(key, cache):
    item = cache.get(key)
    if not item:
        return None

    t, value = item
    if time.time() - t > IN_MEMORY_CACHE_SECONDS:
        return None

    return value


def set_cache(key, cache, value):
    cache[key] = (time.time(), value)


# ============================================================
# בדיקת כשירות להצגה בישראל
# ============================================================

def is_valid_israel_security_number(sec_no):
    if not sec_no:
        return False

    s = str(sec_no).strip()

    if s == "בדוק בבנק":
        return False

    if not s.isdigit():
        return False

    # ברוב המקרים מספר נייר ישראלי הוא 7 ספרות.
    # לא מחייבים 7 כדי לא לחסום חריגים, אבל כן דורשים מספר בלבד.
    return True


def get_enabled_tradeable_funds():
    clean = []

    for fund in FUNDS:
        if not fund.get("enabled", True):
            continue

        if not is_valid_israel_security_number(fund.get("sec_no")):
            continue

        if not fund.get("proxy"):
            continue

        clean.append(fund)

    return clean


# ============================================================
# Twelve Data
# ============================================================

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


# ============================================================
# חדשות
# ============================================================

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


# ============================================================
# גרף/ניקוד
# ============================================================

def perf(prices, days):
    if not prices or len(prices) < days + 1:
        return 0

    if prices[-days] == 0:
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

    # משקל חזק ל-3 חודשים כפי שביקשת בעבר
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
    required = ["SPY", "QQQ", "SOXX", "EEM", "EIS", "GLD", "USO", "UUP", "TLT", "HACK", "BOTZ", "ITA", "URA", "URTH", "VGK", "SLV"]

    for sym in required:
        if sym not in price_cache:
            price_cache[sym] = td_prices(sym)
            time.sleep(0.15)

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
        "hack": perf(price_cache.get("HACK"), 21),
        "botz": perf(price_cache.get("BOTZ"), 21),
        "ita": perf(price_cache.get("ITA"), 21),
        "ura": perf(price_cache.get("URA"), 21),
        "urth": perf(price_cache.get("URTH"), 21),
        "vgk": perf(price_cache.get("VGK"), 21),
        "slv": perf(price_cache.get("SLV"), 21),
        "news": {
            "oil": news_context("oil"),
            "war": news_context("war"),
            "ai": news_context("ai"),
            "rates": news_context("rates"),
            "china": news_context("china"),
            "recession": news_context("recession"),
            "banks": news_context("banks"),
            "gold": news_context("gold"),
            "cyber": news_context("cyber"),
            "robotics": news_context("robotics"),
            "defense": news_context("defense"),
            "nuclear": news_context("nuclear"),
            "world": news_context("world"),
            "europe": news_context("europe"),
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
    if theme == "cyber":
        return "cyber"
    if theme == "robotics":
        return "robotics"
    if theme == "defense":
        return "defense"
    if theme == "nuclear":
        return "nuclear"
    if theme in ["oil", "energy"]:
        return "oil"
    if theme in ["gold", "silver"]:
        return "gold"
    if theme in ["asia", "china", "emerging"]:
        return "china"
    if theme == "world":
        return "world"
    if theme == "europe":
        return "europe"
    if theme == "world":
        if ctx.get("urth", 0) > 2:
            adj += 2
            reasons.append("מניות גלובליות חזקות")
        if ctx["spy"] > 2 and ctx["qqq"] > 2:
            adj += 1
            reasons.append("שוק אמריקאי תומך גם בגלובלי")
        if ctx["news"]["recession"]["score"] < -1:
            adj -= 2
            reasons.append("חשש האטה עולמית")

    if theme == "europe":
        if ctx.get("vgk", 0) > 2:
            adj += 2
            reasons.append("אירופה חזקה בגרף")
        if ctx["news"]["europe"]["score"] > 1:
            adj += 1.5
            reasons.append("אקטואליית אירופה תומכת")
        if ctx["news"]["recession"]["score"] < -1:
            adj -= 2
            reasons.append("חשש האטה פוגע באירופה")

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

    if theme == "cyber":
        if ctx.get("hack", 0) > 2:
            adj += 2
            reasons.append("סייבר חזק בגרף")
        if ctx["news"]["cyber"]["score"] > 1:
            adj += 2
            reasons.append("אקטואליית סייבר תומכת")
        if ctx["qqq"] < -2:
            adj -= 2
            reasons.append("נאסד״ק חלש פוגע בסקטור סייבר")

    if theme == "robotics":
        if ctx.get("botz", 0) > 2:
            adj += 2
            reasons.append("רובוטיקה/אוטומציה חזקות בגרף")
        if ctx["news"]["robotics"]["score"] > 1 or ctx["news"]["ai"]["score"] > 1:
            adj += 2
            reasons.append("AI/רובוטיקה נתמכים בכותרות")
        if ctx["qqq"] < -2:
            adj -= 2
            reasons.append("חולשה בטכנולוגיה פוגעת ברובוטיקה")

    if theme == "defense":
        if ctx.get("ita", 0) > 2:
            adj += 2
            reasons.append("תעשיות ביטחוניות חזקות בגרף")
        if ctx["news"]["defense"]["score"] > 1 or ctx["news"]["war"]["score"] < -1:
            adj += 2
            reasons.append("ביטחון נתמך בתקציבי הגנה/מתיחות")
        if ctx["spy"] < -3:
            adj -= 1
            reasons.append("חולשת שוק כללית מגבילה גם ביטחון")

    if theme == "nuclear":
        if ctx.get("ura", 0) > 2:
            adj += 3
            reasons.append("גרעין/אורניום חזקים בגרף")
        if ctx["news"]["nuclear"]["score"] > 1:
            adj += 2
            reasons.append("אקטואליית גרעין/אורניום תומכת")
        if ctx.get("ura", 0) < -3:
            adj -= 2
            reasons.append("חולשה באורניום/גרעין")

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

    if theme == "world":
        if ctx.get("urth", 0) > 2:
            adj += 2
            reasons.append("מניות גלובליות חזקות")
        if ctx["spy"] > 2 and ctx["qqq"] > 2:
            adj += 1
            reasons.append("שוק אמריקאי תומך גם בגלובלי")
        if ctx["news"]["recession"]["score"] < -1:
            adj -= 2
            reasons.append("חשש האטה עולמית")

    if theme == "europe":
        if ctx.get("vgk", 0) > 2:
            adj += 2
            reasons.append("אירופה חזקה בגרף")
        if ctx["news"]["europe"]["score"] > 1:
            adj += 1.5
            reasons.append("אקטואליית אירופה תומכת")
        if ctx["news"]["recession"]["score"] < -1:
            adj -= 2
            reasons.append("חשש האטה פוגע באירופה")

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

    # קנס מינוף
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


# ============================================================
# HTML
# ============================================================

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
button{width:100%;padding:16px;font-size:22px;border-radius:12px;border:0;background:#1976d2;color:white;margin-top:8px}
button.force{background:#c62828}
#loading{text-align:center;font-size:19px;margin:18px}
.spinner{font-size:38px;animation:flip 1s infinite}
@keyframes flip{0%{transform:rotate(0deg)}50%{transform:rotate(180deg)}100%{transform:rotate(360deg)}}
.legend{background:white;border-radius:12px;padding:12px;margin:10px 0;font-size:14px;line-height:1.6}
.cacheBox{background:#fff8e1;border:1px solid #f1d27a;border-radius:12px;padding:10px;margin:10px 0;font-size:14px;line-height:1.5}
table{width:100%;border-collapse:collapse;background:white;margin-top:12px;font-size:12px}
th,td{border:1px solid #ddd;padding:6px;text-align:center;vertical-align:top}
th{background:#e9eef5}
.buy{color:green;font-weight:bold}
.mid{color:#b36b00;font-weight:bold}
.bad{color:red;font-weight:bold}
.reason{font-size:11px;text-align:right;min-width:260px;line-height:1.45}
.small{font-size:12px;color:#555}
</style>
</head>
<body>

<h2>📊 סורק מוצרי השקעה PRO</h2>

<div class="legend">
<b>מקרא:</b><br>
🔥 מעל 8 = חזק מאוד | 🟢 4–8 = קנייה | 🟡 1–4 = מעקב | 🔴 מתחת 1 = להימנע<br>
<b>מה הציון כולל:</b><br>
הסורק מדרג מאגר רחב של מוצרים עם מספר נייר ישראלי מוגדר בלבד. אין הצגה של "בדוק בבנק" או מוצר שלא הוגדר כבר־רכישה בישראל. הציון כולל גרף + מאקרו + אקטואליה מ־GDELT ו־Google News RSS + הסתכלות קדימה + קנס סיכון.
</div>

<div class="cacheBox">
<b>ריענון:</b><br>
תוצאה נשמרת ל־4 שעות. בשעה 23:30 לפי שעון ישראל מתבצע איפוס יומי אוטומטי, גם אם טרם עברו 4 שעות.<br>
כפתור "סריקה מחודשת" מוחק Cache ומריץ סריקה חדשה מיד.
</div>

<button onclick="run(false)">🔵 סריקה רגילה</button>
<button class="force" onclick="run(true)">🔴 סריקה מחודשת / איפוס Cache</button>

<div id="loading"></div>
<div id="cache"></div>
<div id="market"></div>
<table id="t"></table>

<script>
let timer=null, seconds=0;

function startClock(isForce){
    seconds=0;
    timer=setInterval(()=>{
        seconds++;
        document.getElementById("loading").innerHTML =
        `<div class="spinner">⏳</div>
         <div>${isForce ? "מבצע סריקה מחודשת..." : "בודק Cache / מנתח גרף + אקטואליה..."} ${seconds} שניות</div>
         <div class="small">בסריקה רגילה תוצאה קיימת עד 4 שעות תחזור מהר. סריקה מחודשת יכולה לקחת כמה דקות.</div>`;
    },1000);
}

function stopClock(msg){
    clearInterval(timer);
    document.getElementById("loading").innerText=msg;
}

function render(data){
    document.getElementById("cache").innerHTML =
        `<div class="cacheBox">
            <b>סטטוס:</b> ${data.from_cache ? "הוצג מתוך Cache" : "בוצעה סריקה חדשה"}<br>
            <b>נשמר בתאריך:</b> ${data.saved_at || "-"}<br>
            <b>איפוס יומי הבא:</b> ${data.next_daily_reset || "-"}<br>
            <b>מספר מוצרים שהוצגו:</b> ${(data.results || []).length}
        </div>`;

    document.getElementById("market").innerHTML =
        `<div class="legend"><b>מצב שוק:</b><br>${(data.market || []).join("<br>")}</div>`;

    let html="<tr><th>#</th><th>שם מוצר / קרן</th><th>מס׳ נייר בישראל</th><th>בסיס ניתוח</th><th>חשיפה</th><th>סוג / סיכון</th><th>חודש</th><th>3ח׳</th><th>חצי שנה</th><th>גרף</th><th>אקטואלי</th><th>סופי</th><th>המלצה</th><th>אקטואליה — למה?</th></tr>";

    (data.results || []).forEach((x,i)=>{
        let cls="bad";
        if(x.reco.includes("קנייה") || x.reco.includes("חזק")) cls="buy";
        else if(x.reco.includes("מעקב")) cls="mid";

        html+=`<tr>
            <td>${i+1}</td>
            <td>${x.name}</td>
            <td>${x.sec_no}</td>
            <td>${x.proxy}</td>
            <td>${x.exposure_type || ""}</td>
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
}

async function run(force){
    document.getElementById("t").innerHTML="";
    document.getElementById("market").innerHTML="";
    document.getElementById("cache").innerHTML="";
    startClock(force);

    try{
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 240000);

        let url = force ? "/scan?force=1&ts=" + Date.now() : "/scan?ts=" + Date.now();
        let r = await fetch(url, {signal: controller.signal, cache: "no-store"});
        clearTimeout(timeoutId);

        let d = await r.json();
        render(d);

        stopClock(force ? "✅ הסריקה המחודשת הסתיימה" : "✅ הסריקה הסתיימה");

    }catch(e){
        stopClock("⚠️ הסריקה נתקעה או חרגה מזמן. נסה שוב.");
    }
}
</script>

</body>
</html>
""")


# ============================================================
# סריקה
# ============================================================

def run_full_scan():
    price_cache = {}
    results = []
    errors = []

    ctx = build_market_context(price_cache)
    tradeable_funds = get_enabled_tradeable_funds()

    for fund in tradeable_funds:
        try:
            proxy = fund["proxy"]

            if proxy not in price_cache:
                price_cache[proxy] = td_prices(proxy)
                time.sleep(0.15)

            prices = price_cache.get(proxy)

            if not prices:
                errors.append(f"{fund['name']} - אין נתוני מחיר עבור proxy {proxy}")
                continue

            data = calc_graph(prices)
            adj, reasons = forward_adjust(fund, ctx, data)
            final_score = round(data["graph_score"] + adj, 1)

            results.append({
                "name": fund["name"],
                "sec_no": fund["sec_no"],
                "proxy": proxy,
                "risk": fund["risk"],
                "theme": fund["theme"],
                "exposure_type": fund.get("exposure_type", ""),
                **data,
                "forward_adj": adj,
                "final_score": final_score,
                "reco": recommendation(final_score, fund["risk"]),
                "reason": make_news_lines(fund, ctx, adj, reasons)
            })

        except Exception as e:
            errors.append(f"{fund.get('name', 'Unknown')}: {e}")

    results = sorted(results, key=lambda x: x["final_score"], reverse=True)

    # מציגים TOP 10 מתוך כל הקרנות המאומתות שניתן לרכוש בארץ.
    results = results[:10]

    payload = {
        "market": ctx["summary"],
        "results": results,
        "errors": errors,
        "tradeable_count": len(tradeable_funds),
        "next_daily_reset": next_cache_reset_text()
    }

    return payload


@app.route("/scan")
def scan():
    force = request.args.get("force") == "1"

    if force:
        clear_result_cache()

    if not force:
        cached_payload = load_result_cache()
        if cached_payload:
            payload = cached_payload.get("payload", {})
            payload["from_cache"] = True
            payload["saved_at"] = cached_payload.get("saved_at")
            payload["next_daily_reset"] = next_cache_reset_text()
            return jsonify(payload)

    payload = run_full_scan()
    payload["from_cache"] = False
    payload["saved_at"] = now_israel().strftime("%Y-%m-%d %H:%M:%S")
    payload["next_daily_reset"] = next_cache_reset_text()

    save_result_cache(payload)

    return jsonify(payload)


@app.route("/reset-cache", methods=["POST"])
def reset_cache():
    ok = clear_result_cache()
    return jsonify({
        "ok": ok,
        "message": "Cache אופס" if ok else "לא היה Cache למחיקה או שהמחיקה נכשלה"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
