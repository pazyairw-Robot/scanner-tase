from flask import Flask, jsonify, render_template_string
import requests
import os
import time

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")

# רשימה ישראלית סגורה — ניירות/קרנות סל/ממונפות שאמורות להיות ניתנות לרכישה בישראל
# symbol = סימול/מספר לבדיקה ב-Twelve Data. אם נייר לא נתמך, הוא יוצג כ"שגיאה" ולא ייכנס לדירוג.
FUNDS = [
    {"symbol": "1146422", "name": "קסם LBMA Gold Price PM USD ETF", "sec_no": "1146422", "type": "סחורה / זהב"},
    {"symbol": "TA125", "name": "מדד תל אביב 125", "sec_no": "INDEX", "type": "מדד ישראל"},
    {"symbol": "TA35", "name": "מדד תל אביב 35", "sec_no": "INDEX", "type": "מדד ישראל"},
    {"symbol": "TA-BANKS5", "name": "מדד ת״א בנקים", "sec_no": "INDEX", "type": "מדד ישראל"},
    {"symbol": "TA-REAL", "name": "מדד ת״א נדל״ן", "sec_no": "INDEX", "type": "מדד ישראל"},

    # קרנות/סלים ישראליים - צריך לוודא תמיכה לפי Twelve Data
    {"symbol": "1159093", "name": "קרן סל ישראלית עוקבת Nasdaq 100", "sec_no": "1159093", "type": "חו״ל / נאסד״ק"},
    {"symbol": "1159028", "name": "קרן סל ישראלית עוקבת S&P 500", "sec_no": "1159028", "type": "חו״ל / S&P"},
    {"symbol": "1159259", "name": "קרן סל ישראלית עוקבת MSCI World", "sec_no": "1159259", "type": "חו״ל / עולם"},
    {"symbol": "1159515", "name": "איילון/קרן ממונפת פי 3 Nasdaq", "sec_no": "1159515", "type": "ממונפת"},
    {"symbol": "1159531", "name": "איילון/קרן ממונפת פי 3 S&P 500", "sec_no": "1159531", "type": "ממונפת"},
    {"symbol": "1159614", "name": "קרן ממונפת פי 3 ת״א 125", "sec_no": "1159614", "type": "ממונפת"},
    {"symbol": "1159507", "name": "קרן ממונפת פי 2 Nasdaq", "sec_no": "1159507", "type": "ממונפת"},
    {"symbol": "1159523", "name": "קרן ממונפת פי 2 S&P 500", "sec_no": "1159523", "type": "ממונפת"},
]

def fetch_series(symbol):
    candidates = [
        symbol,
        f"{symbol}:XTAE",
        f"{symbol}.TA",
    ]

    for s in candidates:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": s,
            "interval": "1day",
            "outputsize": 260,
            "apikey": API_KEY
        }

        try:
            r = requests.get(url, params=params, timeout=12)
            data = r.json()

            if "values" in data and len(data["values"]) >= 65:
                prices = []
                for row in data["values"]:
                    try:
                        prices.append(float(row["close"]))
                    except:
                        pass

                prices.reverse()
                return prices, s

        except Exception:
            pass

    return None, None

def calc(prices):
    if not prices or len(prices) < 65:
        return None

    last = prices[-1]
    week = (last / prices[-5] - 1) * 100 if len(prices) >= 5 else 0
    month = (last / prices[-21] - 1) * 100
    q3 = (last / prices[-63] - 1) * 100
    half = (last / prices[-126] - 1) * 100 if len(prices) >= 126 else q3
    year = (last / prices[-252] - 1) * 100 if len(prices) >= 252 else half

    # תנודתיות יומית ממוצעת
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] != 0:
            returns.append((prices[i] / prices[i-1] - 1) * 100)

    vol = sum(abs(x) for x in returns[-60:]) / max(len(returns[-60:]), 1)

    # ציון מומנטום: 3 חודשים וחצי שנה מקבלים משקל גבוה
    score = (
        0.10 * week +
        0.20 * month +
        0.30 * q3 +
        0.25 * half +
        0.15 * year -
        0.60 * vol
    )

    return {
        "week": round(week, 1),
        "month": round(month, 1),
        "q3": round(q3, 1),
        "half": round(half, 1),
        "year": round(year, 1),
        "vol": round(vol, 1),
        "score": round(score, 1)
    }

def recommendation(score, fund_type):
    if "ממונפת" in fund_type:
        if score >= 8:
            return "🟢 קנייה אגרסיבית"
        if score >= 3:
            return "🟡 מעקב / סיכון גבוה"
        return "🔴 להימנע כרגע"

    if score >= 6:
        return "🟢 קנייה"
    if score >= 2:
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
<title>סורק השקעות ישראלי</title>
<style>
body{direction:rtl;font-family:Arial;padding:16px;background:#f7f7f7}
h2{text-align:center}
button{width:100%;padding:14px;font-size:20px;border-radius:10px;border:0;background:#1976d2;color:white}
#loading{text-align:center;font-size:18px;margin:14px;color:#333}
table{width:100%;border-collapse:collapse;background:white;margin-top:12px;font-size:14px}
th,td{border:1px solid #ddd;padding:8px;text-align:center}
th{background:#eee}
.buy{color:green;font-weight:bold}
.mid{color:#b36b00;font-weight:bold}
.bad{color:red;font-weight:bold}
.small{font-size:12px;color:#555}
</style>
</head>
<body>

<h2>📊 סורק קרנות/סל ישראלי</h2>
<button onclick="run()">🔵 סריקה</button>

<div id="loading"></div>
<table id="t"></table>
<div id="errors" class="small"></div>

<script>
async function run(){
    const loading = document.getElementById("loading");
    const table = document.getElementById("t");
    const errors = document.getElementById("errors");

    loading.innerText = "⏳ מבצע סריקה... עד דקה";
    table.innerHTML = "";
    errors.innerHTML = "";

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 90000);

        let r = await fetch('/scan', { signal: controller.signal });
        clearTimeout(timeoutId);

        let d = await r.json();

        if (!d.results || d.results.length === 0) {
            loading.innerText = "⚠️ לא התקבלו נתונים. ייתכן שהספק לא תומך במספרי הנייר האלה.";
            if (d.errors) errors.innerHTML = "נכשלו: " + d.errors.join(", ");
            return;
        }

        let html = "<tr><th>#</th><th>מס׳ נייר</th><th>שם</th><th>סוג</th><th>חודש</th><th>3ח׳</th><th>חצי שנה</th><th>ציון</th><th>המלצה</th></tr>";

        d.results.forEach((x,i)=>{
            let cls = "bad";
            if (x.reco.includes("קנייה")) cls = "buy";
            else if (x.reco.includes("מעקב")) cls = "mid";

            html += `<tr>
                <td>${i+1}</td>
                <td>${x.sec_no}</td>
                <td>${x.name}</td>
                <td>${x.type}</td>
                <td>${x.month}%</td>
                <td>${x.q3}%</td>
                <td>${x.half}%</td>
                <td>${x.score}</td>
                <td class="${cls}">${x.reco}</td>
            </tr>`;
        });

        table.innerHTML = html;
        loading.innerText = "✅ הסריקה הסתיימה";

        if (d.errors && d.errors.length > 0) {
            errors.innerHTML = "לא נטענו: " + d.errors.join(", ");
        }

    } catch(e) {
        loading.innerText = "⚠️ הסריקה נתקעה או נחסמה. נסה שוב בעוד כמה דקות.";
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

    for fund in FUNDS:
        prices, used_symbol = fetch_series(fund["symbol"])
        data = calc(prices)

        if data:
            score = data["score"]
            results.append({
                "sec_no": fund["sec_no"],
                "name": fund["name"],
                "type": fund["type"],
                "used_symbol": used_symbol,
                **data,
                "reco": recommendation(score, fund["type"])
            })
        else:
            errors.append(fund["name"])

        time.sleep(1)

    results = sorted(results, key=lambda x: x["score"], reverse=True)[:10]

    return jsonify({
        "results": results,
        "errors": errors
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
