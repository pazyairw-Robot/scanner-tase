from flask import Flask, render_template_string
import requests
import statistics
from datetime import datetime

import os
API_KEY = os.getenv("TWELVE_API_KEY")
app = Flask(__name__)

# סימבולים תקינים בלבד
FUNDS = [
    {"name": "שבבים", "symbol": "SOXX", "sector": "semiconductors"},
    {"name": "נאסד״ק 100", "symbol": "QQQ", "sector": "tech"},
    {"name": "S&P 500", "symbol": "SPY", "sector": "sp500"},
    {"name": "מתכות", "symbol": "XME", "sector": "metals"},
    {"name": "זהב", "symbol": "GLD", "sector": "gold"},
    {"name": "אנרגיה", "symbol": "XLE", "sector": "energy"},
    {"name": "פיננסים", "symbol": "XLF", "sector": "financials"},
]

# ======================
# שליפת נתונים (עם הגנה!)
# ======================
def get_data(symbol):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 60,
        "apikey": API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=10).json()

        if "values" not in r:
            print("API ERROR:", r)
            return []

        values = list(reversed(r["values"]))
        return [float(v["close"]) for v in values]

    except Exception as e:
        print("REQUEST FAILED:", e)
        return []

# ======================
# חישובים
# ======================
def pct_change(data, days):
    if len(data) <= days:
        return 0
    return (data[-1] - data[-days-1]) / data[-days-1] * 100

def volatility(data):
    if len(data) < 20:
        return 0
    returns = []
    for i in range(1, 20):
        r = (data[-i] - data[-i-1]) / data[-i-1] * 100
        returns.append(r)
    return statistics.stdev(returns)

# ======================
# דולר
# ======================
def usd_ils():
    data = get_data("USD/ILS")
    if len(data) < 5:
        return 0
    return pct_change(data, 3)

# ======================
# אקטואליה קצרה (לפי סקטור)
# ======================
def forward_text(sector, w, m, usd):

    if sector == "semiconductors":
        base = "AI תומך בשבבים"
        risk = "אך יש סיכון מימושים"
    elif sector == "metals":
        base = "מתכות תלויות בסין ובתעשייה"
        risk = "לכן תנודתיות גבוהה"
    elif sector == "energy":
        base = "נפט משפיע על הסקטור"
        risk = "רגיש לירידות מחיר"
    elif sector == "financials":
        base = "ריבית תומכת בפיננסים"
        risk = "אך האטה פוגעת"
    else:
        base = "תלוי שוק כללי"
        risk = "תנודתי"

    if usd > 0.5:
        fx = "דולר תומך"
    elif usd < -0.5:
        fx = "דולר פוגע"
    else:
        fx = "מט״ח ניטרלי"

    if w > 0 and m > 0:
        direction = "חיובי"
        decision = "להחזיק"
    elif w < 0 and m > 0:
        direction = "נחלש"
        decision = "מעקב"
    else:
        direction = "שלילי"
        decision = "להיזהר"

    text = f"{base}, {risk}. {fx}. מגמה {direction} → {decision}"

    return direction, text, decision

# ======================
# סריקה
# ======================
def scan():
    results = []
    usd = usd_ils()

    for f in FUNDS:
        data = get_data(f["symbol"])

        if len(data) < 20:
            continue

        w = pct_change(data, 5)
        m = pct_change(data, 22)
        v = volatility(data)

        score = 50 + w*2 + m*1.5 - v*1.5

        direction, text, decision = forward_text(f["sector"], w, m, usd)

        results.append({
            "name": f["name"],
            "symbol": f["symbol"],
            "weekly": round(w,2),
            "monthly": round(m,2),
            "vol": round(v,2),
            "score": round(score,1),
            "direction": direction,
            "text": text,
            "decision": decision
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# ======================
# UI
# ======================
HTML = """
<html dir="rtl">
<head>
<meta charset="UTF-8">
<style>
body {font-family: Arial; padding:20px;}
table {width:100%; border-collapse:collapse;}
th,td {padding:10px; border-bottom:1px solid #ccc;}
th {background:black; color:white;}
</style>
</head>
<body>

<h2>סורק קרנות</h2>

<table>
<tr>
<th>קרן</th>
<th>שבוע</th>
<th>חודש</th>
<th>ציון</th>
<th>כיוון</th>
<th>אקטואליה קדימה</th>
<th>החלטה</th>
</tr>

{% for r in data %}
<tr>
<td>{{r.name}}</td>
<td>{{r.weekly}}%</td>
<td>{{r.monthly}}%</td>
<td>{{r.score}}</td>
<td>{{r.direction}}</td>
<td>{{r.text}}</td>
<td>{{r.decision}}</td>
</tr>
{% endfor %}

</table>

</body>
</html>
"""

@app.route("/")
def home():
    data = scan()
    return render_template_string(HTML, data=data)

if __name__ == "__main__":
    app.run()
