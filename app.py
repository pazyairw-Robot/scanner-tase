from flask import Flask, jsonify, render_template_string
import requests
import os
import time
import statistics

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")

FUNDS = [
    {"buy_name": "קרן סל ישראלית עוקבת Nasdaq 100", "proxy": "QQQ", "risk": "רגיל"},
    {"buy_name": "קרן ממונפת פי 3 Nasdaq / איילון אקסטרים Nasdaq", "proxy": "QQQ", "risk": "ממונף פי 3"},
    {"buy_name": "קרן ממונפת פי 2 Nasdaq", "proxy": "QQQ", "risk": "ממונף פי 2"},

    {"buy_name": "קרן סל ישראלית עוקבת S&P 500", "proxy": "SPY", "risk": "רגיל"},
    {"buy_name": "קרן ממונפת פי 3 S&P 500 / איילון אקסטרים S&P", "proxy": "SPY", "risk": "ממונף פי 3"},
    {"buy_name": "קרן ממונפת פי 2 S&P 500", "proxy": "SPY", "risk": "ממונף פי 2"},

    {"buy_name": "קרן סל ישראלית עוקבת MSCI World", "proxy": "ACWI", "risk": "רגיל"},
    {"buy_name": "קרן סל ישראלית עוקבת שווקים מתעוררים", "proxy": "EEM", "risk": "רגיל"},

    {"buy_name": "קרן סל ישראלית עוקבת טאיוואן / מזרח אסיה", "proxy": "EWT", "risk": "רגיל"},
    {"buy_name": "קרן סל ישראלית עוקבת קוריאה / מזרח אסיה", "proxy": "EWY", "risk": "רגיל"},
    {"buy_name": "קרן סל ישראלית עוקבת יפן", "proxy": "EWJ", "risk": "רגיל"},
    {"buy_name": "קרן סל ישראלית עוקבת הודו", "proxy": "INDA", "risk": "רגיל"},
    {"buy_name": "קרן סל ישראלית עוקבת סין", "proxy": "FXI", "risk": "רגיל"},

    {"buy_name": "קרן סל ישראלית עוקבת שבבים / Semiconductors", "proxy": "SMH", "risk": "רגיל"},
    {"buy_name": "קרן סל ישראלית עוקבת טכנולוגיה", "proxy": "XLK", "risk": "רגיל"},
    {"buy_name": "קרן סל ישראלית עוקבת אנרגיה", "proxy": "XLE", "risk": "רגיל"},
    {"buy_name": "קרן סל ישראלית עוקבת פיננסים / בנקים", "proxy": "XLF", "risk": "רגיל"},

    {"buy_name": "קרן סל ישראלית עוקבת זהב / קסם זהב", "proxy": "GLD", "risk": "סחורה"},
    {"buy_name": "קרן סל ישראלית עוקבת כסף", "proxy": "SLV", "risk": "סחורה"},
    {"buy_name": "קרן סל ישראלית עוקבת נפט", "proxy": "USO", "risk": "סחורה"},
    {"buy_name": "קרן דולר / חשיפה לדולר", "proxy": "UUP", "risk": "מטבע"},
]

def fetch_prices(symbol):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 260,
        "apikey": API_KEY
    }

    r = requests.get(url, params=params, timeout=20)
    data = r.json()

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

def calc(prices, risk):
    last = prices[-1]

    week = (last / prices[-5] - 1) * 100
    month = (last / prices[-21] - 1) * 100
    q3 = (last / prices[-63] - 1) * 100
    half = (last / prices[-126] - 1) * 100 if len(prices) >= 126 else q3
    year = (last / prices[-252] - 1) * 100 if len(prices) >= 252 else half

    daily = []
    for i in range(1, len(prices)):
        daily.append((prices[i] / prices[i-1] - 1) * 100)

    vol = statistics.mean([abs(x) for x in daily[-60:]]) if daily else 0

    score = (
        0.10 * week +
        0.20 * month +
        0.30 * q3 +
        0.25 * half +
        0.15 * year -
        0.70 * vol
    )

    if "פי 3" in risk:
        score = score * 1.25 - 2
    elif "פי 2" in risk:
        score = score * 1.15 - 1

    return {
        "week": round(week, 1),
        "month": round(month, 1),
        "q3": round(q3, 1),
        "half": round(half, 1),
        "year": round(year, 1),
        "vol": round(vol, 1),
        "score": round(score, 1)
    }

def reco(score, risk):
    if "פי 3" in risk:
        if score >= 8:
            return "🟢 קנייה אגרסיבית"
        if score >= 3:
            return "🟡 מעקב בלבד"
        return "🔴 להימנע"

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
<title>סורק השקעות</title>
<style>
body{direction:rtl;font-family:Arial;padding:16px;background:#f6f7fb}
h2{text-align:center}
button{width:100%;padding:16px;font-size:22px;border-radius:12px;border:0;background:#1976d2;color:white}
#loading{text-align:center;font-size:20px;margin:18px}
.spinner{font-size:38px;animation:flip 1s infinite}
@keyframes flip{0%{transform:rotate(0deg)}50%{transform:rotate(180deg)}100%{transform:rotate(360deg)}}
table{width:100%;border-collapse:collapse;background:white;margin-top:12px;font-size:14px}
th,td{border:1px solid #ddd;padding:8px;text-align:center}
th{background:#e9eef5}
.buy{color:green;font-weight:bold}
.mid{color:#b36b00;font-weight:bold}
.bad{color:red;font-weight:bold}
.small{font-size:12px;color:#555;text-align:center;margin-top:10px}
</style>
</head>
<body>

<h2>📊 סורק קרנות/סל לרכישה בישראל</h2>

<button onclick="run()">🔵 סריקה</button>

<div id="loading"></div>
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
            <div style="font-size:14px;color:#555">זה יכול לקחת עד כמה דקות</div>
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
    startClock();

    try{
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 240000);

        let r = await fetch('/scan', {signal: controller.signal});
        clearTimeout(timeoutId);

        let d = await r.json();

        if(!d.results || d.results.length === 0){
            stopClock("⚠️ לא התקבלו נתונים. נסה שוב מאוחר יותר.");
            if(d.errors){document.getElementById("errors").innerHTML = "נכשלו: " + d.errors.join(", ");}
            return;
        }

        let html = "<tr><th>#</th><th>שם לרכישה בבנק/ברוקר</th><th>בסיס ניתוח</th><th>סיכון</th><th>חודש</th><th>3ח׳</th><th>חצי שנה</th><th>ציון</th><th>המלצה</th></tr>";

        d.results.forEach((x,i)=>{
            let cls = "bad";
            if(x.reco.includes("קנייה")) cls = "buy";
            else if(x.reco.includes("מעקב")) cls = "mid";

            html += `<tr>
                <td>${i+1}</td>
                <td>${x.buy_name}</td>
                <td>${x.proxy}</td>
                <td>${x.risk}</td>
                <td>${x.month}%</td>
                <td>${x.q3}%</td>
                <td>${x.half}%</td>
                <td>${x.score}</td>
                <td class="${cls}">${x.reco}</td>
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

    cache = {}

    for fund in FUNDS:
        try:
            proxy = fund["proxy"]

            if proxy not in cache:
                prices = fetch_prices(proxy)
                cache[proxy] = prices
                time.sleep(1.2)
            else:
                prices = cache[proxy]

            if not prices:
                errors.append(fund["buy_name"])
                continue

            data = calc(prices, fund["risk"])

            results.append({
                "buy_name": fund["buy_name"],
                "proxy": fund["proxy"],
                "risk": fund["risk"],
                **data,
                "reco": reco(data["score"], fund["risk"])
            })

        except Exception:
            errors.append(fund["buy_name"])

    results = sorted(results, key=lambda x: x["score"], reverse=True)[:10]

    return jsonify({
        "results": results,
        "errors": errors
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
