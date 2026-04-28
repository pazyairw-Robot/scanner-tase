from flask import Flask, jsonify, render_template_string
import requests
import os
import time

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")

symbols = [
    ("TA35", "ת״א 35"),
    ("TA125", "ת״א 125"),
    ("USD/ILS", "דולר"),
    ("XAU/USD", "זהב"),
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft")
]

def get_price(symbol):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize=70&apikey={API_KEY}"
        r = requests.get(url, timeout=10).json()

        if "values" not in r:
            return None

        prices = [float(x["close"]) for x in r["values"]]
        prices.reverse()

        if len(prices) < 65:
            return None

        month = (prices[-1] / prices[-21] - 1) * 100
        q3 = (prices[-1] / prices[-63] - 1) * 100

        score = month * 0.4 + q3 * 0.6

        return {
            "month": round(month,1),
            "q3": round(q3,1),
            "score": round(score,1)
        }

    except:
        return None

@app.route("/")
def home():
    return render_template_string("""
<html>
<body style='direction:rtl;font-family:Arial;padding:20px'>

<h2>📊 סורק השקעות</h2>

<button onclick="run()" style="padding:12px;font-size:20px;width:100%">
🔵 סריקה
</button>

<p id="loading"></p>
<table id="t" border="1" style="width:100%;margin-top:10px"></table>

<script>
async function run(){
    document.getElementById("loading").innerText = "⏳ סורק נתונים...";
    document.getElementById("t").innerHTML = "";

    let r = await fetch('/scan');
    let d = await r.json();

    if(d.length === 0){
        document.getElementById("loading").innerText = "⚠️ אין נתונים כרגע";
        return;
    }

    let html = "<tr><th>#</th><th>נייר</th><th>חודש</th><th>3ח׳</th><th>ציון</th></tr>";

    d.forEach((x,i)=>{
        html += `<tr>
        <td>${i+1}</td>
        <td>${x.name}</td>
        <td>${x.month}%</td>
        <td>${x.q3}%</td>
        <td>${x.score}</td>
        </tr>`;
    });

    document.getElementById("t").innerHTML = html;
    document.getElementById("loading").innerText = "✅ סיום";
}
</script>

</body>
</html>
""")

@app.route("/scan")
def scan():
    results = []

    for symbol, name in symbols:
        data = get_price(symbol)
        if data:
            results.append({
                "name": name,
                **data
            })
        time.sleep(1)

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
