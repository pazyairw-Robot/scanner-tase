from flask import Flask, render_template_string, request
import requests, os, statistics
from datetime import datetime

app = Flask(__name__)

API_KEY = os.environ.get("TWELVE_API_KEY", "").strip()

FUNDS = [
    {"name": "שבבים ארה״ב", "symbol": "SOXX", "sector": "AI תומך בשבבים, אך אחרי ריצה חזקה יש סיכון מימושים."},
    {"name": "נאסד״ק 100", "symbol": "QQQ", "sector": "טכנולוגיה רגישה לריבית אך נהנית ממומנטום חזק."},
    {"name": "S&P 500", "symbol": "SPY", "sector": "מדד רחב, תלוי ריבית ואינפלציה בארה״ב."},
    {"name": "מתכות וכרייה", "symbol": "XME", "sector": "תלוי סין, ביקוש תעשייתי ודולר."},
    {"name": "זהב", "symbol": "GLD", "sector": "מושפע מדולר, תשואות אג״ח ופחד בשוק."},
    {"name": "אנרגיה / נפט", "symbol": "XLE", "sector": "תלוי מחירי נפט, מלאים וביקוש עולמי."},
    {"name": "פיננסים ארה״ב", "symbol": "XLF", "sector": "ריבית גבוהה תומכת, האטה כלכלית פוגעת."},
    {"name": "קוריאה", "symbol": "EWY", "sector": "מושפעת משבבים, יצוא וסחר עולמי."},
    {"name": "סין", "symbol": "FXI", "sector": "תלויה בתמריצים, נדל״ן ונתוני מאקרו."},
    {"name": "אירופה", "symbol": "VGK", "sector": "תלויה בצמיחה, ריבית ואירו/דולר."},
]

def get_closes(symbol):
    if not API_KEY:
        return [], "חסר TWELVE_API_KEY ב־Render Environment"

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 90,
        "apikey": API_KEY,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if "values" not in data:
            return [], str(data)

        values = list(reversed(data["values"]))
        closes = [float(v["close"]) for v in values]
        return closes, ""

    except Exception as e:
        return [], str(e)

def pct(closes, days):
    if len(closes) <= days:
        return 0
    return (closes[-1] - closes[-days - 1]) / closes[-days - 1] * 100

def vol(closes):
    if len(closes) < 22:
        return 0
    returns = []
    recent = closes[-20:]
    for i in range(1, len(recent)):
        returns.append((recent[i] - recent[i-1]) / recent[i-1] * 100)
    return statistics.stdev(returns) if len(returns) > 1 else 0

def make_decision(w, m, score):
    if w > 0 and m > 0 and score >= 65:
        return "חיובי — החזקה / קנייה זהירה"
    if w < 0 and m > 0:
        return "נחלש — מעקב, לא לרדוף"
    if w < 0 and m < 0:
        return "שלילי — לא לקנות כרגע"
    return "ניטרלי — מעקב בלבד"

def scan():
    rows = []

    for f in FUNDS:
        closes, error = get_closes(f["symbol"])

        if error:
            rows.append({
                "name": f["name"],
                "symbol": f["symbol"],
                "week": "שגיאה",
                "month": "שגיאה",
                "quarter": "שגיאה",
                "score": 0,
                "direction": "אין נתונים",
                "forward": error,
                "decision": "בדוק API KEY / Twelve Data",
                "is_error": True,
            })
            continue

        w = pct(closes, 5)
        m = pct(closes, 22)
        q = pct(closes, 66)
        v = vol(closes)

        score = 50 + w * 2 + m * 1.4 + q * 0.5 - v * 1.2
        score = round(max(0, min(100, score)), 1)

        if w > 0 and m > 0:
            direction = "חיובי"
        elif w < 0 and m > 0:
            direction = "נחלש"
        elif w < 0 and m < 0:
            direction = "שלילי"
        else:
            direction = "מעורב"

        decision = make_decision(w, m, score)

        forward = f"{f['sector']} שבוע: {w:.2f}%, חודש: {m:.2f}%. לכן הכיוון כרגע: {direction}."

        rows.append({
            "name": f["name"],
            "symbol": f["symbol"],
            "week": f"{w:.2f}%",
            "month": f"{m:.2f}%",
            "quarter": f"{q:.2f}%",
            "score": score,
            "direction": direction,
            "forward": forward,
            "decision": decision,
            "is_error": False,
        })

    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows

HTML = """
<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<title>סורק קרנות וסל</title>
<style>
body {font-family: Arial; background:#f3f4f6; margin:0; padding:30px;}
h1 {margin:0 0 8px 0;}
.top {display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;}
button, .btn {background:#2563eb; color:white; padding:12px 20px; border:0; border-radius:8px; font-size:16px; cursor:pointer; text-decoration:none;}
table {width:100%; border-collapse:collapse; background:white; box-shadow:0 4px 14px #0002;}
th {background:#111827; color:white; padding:12px;}
td {padding:12px; border-bottom:1px solid #ddd; vertical-align:top;}
.err {color:#b91c1c; direction:ltr; text-align:left; font-size:12px;}
.score {font-weight:bold; font-size:18px;}
.small {color:#6b7280;}
</style>
</head>
<body>

<div class="top">
  <div>
    <h1>סורק קרנות וסל — TOP 10</h1>
    <div class="small">רענון אחרון: {{ now }}</div>
  </div>
  <a class="btn" href="/?run={{ stamp }}">סריקה חדשה</a>
</div>

<table>
<tr>
<th>דירוג</th>
<th>קרן</th>
<th>סימבול</th>
<th>שבוע</th>
<th>חודש</th>
<th>3 חודשים</th>
<th>ציון</th>
<th>כיוון</th>
<th>אקטואליה קדימה</th>
<th>החלטה</th>
</tr>

{% for r in rows %}
<tr>
<td>{{ loop.index }}</td>
<td><b>{{ r.name }}</b></td>
<td>{{ r.symbol }}</td>
<td>{{ r.week }}</td>
<td>{{ r.month }}</td>
<td>{{ r.quarter }}</td>
<td class="score">{{ r.score }}</td>
<td>{{ r.direction }}</td>
<td class="{% if r.is_error %}err{% endif %}">{{ r.forward }}</td>
<td><b>{{ r.decision }}</b></td>
</tr>
{% endfor %}
</table>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(
        HTML,
        rows=scan(),
        now=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        stamp=datetime.now().timestamp()
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
