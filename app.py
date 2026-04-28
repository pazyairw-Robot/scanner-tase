from flask import Flask, jsonify, render_template_string
import yfinance as yf

app = Flask(__name__)

symbols = [
("1146422.TA","זהב"),
("1159093.TA","Nasdaq"),
("1159028.TA","S&P"),
("1142009.TA","ת\"א125"),
("1159515.TA","פי3 Nasdaq"),
("1159531.TA","פי3 S&P"),
("1159614.TA","פי3 ת\"א"),
("1159267.TA","טכנולוגיה"),
("1159234.TA","בנקים"),
("1159275.TA","אנרגיה")
]

def analyze(df):
    close = df["Close"]
    if len(close) < 70:
        return None
    month = (close[-1]/close[-21]-1)*100
    q3 = (close[-1]/close[-63]-1)*100
    return month*0.4 + q3*0.6

@app.route("/")
def home():
    return render_template_string("""
    <html>
    <body style='direction:rtl;font-family:Arial;padding:20px'>
    
    <h2>📊 סורק השקעות</h2>

    <button onclick="run()" style="padding:10px;font-size:18px">
    🔵 סריקה
    </button>

    <p id="loading"></p>

    <table id='t' border="1" style="margin-top:10px;width:100%"></table>

    <script>
    async function run(){
      document.getElementById("loading").innerText = "⏳ טוען נתונים...";

      let r = await fetch('/scan');
      let d = await r.json();

      let html = "<tr><th>#</th><th>נייר</th><th>ציון</th></tr>";

      d.forEach((x,i)=>{
        html+=`<tr><td>${i+1}</td><td>${x.name}</td><td>${x.score}</td></tr>`;
      });

      document.getElementById("t").innerHTML = html;
      document.getElementById("loading").innerText = "";
    }
    </script>

    </body>
    </html>
    """)

@app.route("/scan")
def scan():
    results = []
    for s,n in symbols:
        try:
            df = yf.download(s, period="6mo", progress=False)
            score = analyze(df)
            if score:
                results.append({"name":n,"score":round(score,1)})
        except:
            pass
    results = sorted(results, key=lambda x:x["score"], reverse=True)[:10]
    return jsonify(results)

app.run(host="0.0.0.0", port=10000)
