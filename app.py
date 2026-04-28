from flask import Flask, jsonify, render_template_string
import yfinance as yf
import time

app = Flask(__name__)

symbols = [
    ("1146422.TA", "זהב"),
    ("1159093.TA", "Nasdaq"),
    ("1159028.TA", "S&P"),
    ("1142009.TA", 'ת"א 125'),
    ("1159515.TA", "פי3 Nasdaq"),
]

def analyze(df):
    if df is None or df.empty or "Close" not in df:
        return None

    close = df["Close"].dropna()

    if len(close) < 65:
        return None

    last = float(close.iloc[-1])
    month = (last / float(close.iloc[-21]) - 1) * 100
    q3 = (last / float(close.iloc[-63]) - 1) * 100

    score = month * 0.4 + q3 * 0.6

    return {
        "month": round(month, 1),
        "q3": round(q3, 1),
        "score": round(score, 1)
    }

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
body{direction:rtl;font-family:Arial;padding:16px;background:#f7f7f7}
h2{text-align:center}
button{width:100%;padding:14px;font-size:20px;border-radius:10px;border:0;background:#1976d2;color:white}
#loading{text-align:center;font-size:18px;margin:14px;color:#333}
table{width:100%;border-collapse:collapse;background:white;margin-top:12px}
th,td{border:1px solid #ddd;padding:9px;text-align:center}
th{background:#eee}
.buy{color:green;font-weight:bold}
.mid{color:orange;font-weight:bold}
.bad{color:red;font-weight:bold}
</style>
</head>
<body>

<h2>📊 סורק השקעות</h2>
<button onclick="run()">🔵 סריקה</button>

<div id="loading"></div>
<table id="t"></table>

<script>
async function run(){
    const loading = document.getElementById("loading");
    const table = document.getElementById("t");

    loading.innerText = "⏳ מבצע סריקה... זה יכול לקחת עד דקה";
    table.innerHTML = "";

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 90000);

        let r = await fetch('/scan', { signal: controller.signal });
        clearTimeout(timeoutId);

        let d = await r.json();

        if (!d.results || d.results.length === 0) {
            loading.innerText = "⚠️ לא התקבלו נתונים כרגע. נסה שוב בעוד כמה דקות.";
            return;
        }

        let html = "<tr><th>#</th><th>נייר</th><th>חודש</th><th>3 חודשים</th><th>ציון</th><th>פעולה</th></tr>";

        d.results.forEach((x,i)=>{
            let action = "🔴 להימנע";
            let cls = "bad";
            if (x.score >= 5) { action = "🟢 קנייה"; cls = "buy"; }
            else if (x.score >= 1) { action = "🟡 מעקב"; cls = "mid"; }

            html += `<tr>
                <td>${i+1}</td>
                <td>${x.name}</td>
                <td>${x.month}%</td>
                <td>${x.q3}%</td>
                <td>${x.score}</td>
                <td class="${cls}">${action}</td>
            </tr>`;
        });

        table.innerHTML = html;
        loading.innerText = "✅ הסריקה הסתיימה";

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

    for symbol, name in symbols:
        try:
            df = yf.download(
                symbol,
                period="6mo",
                interval="1d",
                progress=False,
                threads=False,
                timeout=10
            )

            res = analyze(df)

            if res:
                results.append({
                    "symbol": symbol,
                    "name": name,
                    **res
                })
            else:
                errors.append(name)

            time.sleep(1.2)

        except Exception as e:
            errors.append(name)
            continue

    results = sorted(results, key=lambda x: x["score"], reverse=True)[:10]

    return jsonify({
        "results": results,
        "errors": errors
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
