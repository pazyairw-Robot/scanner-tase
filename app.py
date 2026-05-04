from flask import Flask, render_template_string
import requests
import statistics
from datetime import datetime

app = Flask(__name__)

TWELVE_API_KEY = "YOUR_TWELVE_DATA_API_KEY"

# =========================
# רשימת קרנות/סקטורים לסריקה
# =========================
FUNDS = [
    {
        "name": "שבבים ארה״ב",
        "proxy": "SOXX",
        "sector": "semiconductors",
        "fx": True
    },
    {
        "name": "נאסד״ק 100",
        "proxy": "QQQ",
        "sector": "technology",
        "fx": True
    },
    {
        "name": "S&P 500",
        "proxy": "SPY",
        "sector": "sp500",
        "fx": True
    },
    {
        "name": "מתכות וכרייה",
        "proxy": "XME",
        "sector": "metals",
        "fx": True
    },
    {
        "name": "זהב",
        "proxy": "GLD",
        "sector": "gold",
        "fx": True
    },
    {
        "name": "אנרגיה / נפט",
        "proxy": "XLE",
        "sector": "energy",
        "fx": True
    },
    {
        "name": "פיננסים ארה״ב",
        "proxy": "XLF",
        "sector": "financials",
        "fx": True
    },
    {
        "name": "קוריאה",
        "proxy": "EWY",
        "sector": "korea",
        "fx": True
    },
    {
        "name": "סין",
        "proxy": "FXI",
        "sector": "china",
        "fx": True
    },
    {
        "name": "אירופה",
        "proxy": "VGK",
        "sector": "europe",
        "fx": True
    },
    {
        "name": "ראסל 2000",
        "proxy": "IWM",
        "sector": "small_caps",
        "fx": True
    },
    {
        "name": "בריאות ארה״ב",
        "proxy": "XLV",
        "sector": "healthcare",
        "fx": True
    },
]


# =========================
# Twelve Data
# =========================
def get_daily_closes(symbol, outputsize=90):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": outputsize,
        "apikey": TWELVE_API_KEY,
    }

    try:
        data = requests.get(url, params=params, timeout=12).json()
        if "values" not in data:
            return []
        values = list(reversed(data["values"]))
        return [float(v["close"]) for v in values]
    except Exception:
        return []


def percent_change(closes, days):
    if len(closes) <= days:
        return None
    old = closes[-days - 1]
    new = closes[-1]
    if old == 0:
        return None
    return (new - old) / old * 100


def calc_volatility(closes, days=20):
    if len(closes) < days + 1:
        return None

    recent = closes[-days:]
    returns = []
    for i in range(1, len(recent)):
        if recent[i - 1] != 0:
            returns.append((recent[i] - recent[i - 1]) / recent[i - 1] * 100)

    if len(returns) < 2:
        return None

    return statistics.stdev(returns)


# =========================
# מט"ח
# =========================
def get_usd_ils_change():
    closes = get_daily_closes("USD/ILS", 10)
    if len(closes) < 6:
        return 0
    return percent_change(closes, 5) or 0


# =========================
# אקטואליה קדימה - לפי סקטור
# =========================
def forward_news_text(sector, weekly, monthly, usd_change):
    weekly = weekly or 0
    monthly = monthly or 0

    trend_positive = weekly > 0 and monthly > 0
    trend_weak = weekly < 0 and monthly > 0
    trend_negative = weekly < 0 and monthly < 0

    fx_text = ""
    if usd_change > 0.6:
        fx_text = "הדולר מתחזק ולכן הוא עשוי לתמוך בקרנות חשופות מט״ח, אך ללחוץ על סחורות."
    elif usd_change < -0.6:
        fx_text = "הדולר נחלש ולכן הוא עלול לפגוע בתשואה שקלית של קרנות חו״ל."
    else:
        fx_text = "השפעת המט״ח כרגע מתונה."

    if sector == "semiconductors":
        base = "שבבים עדיין נהנים מרוח גבית של AI וביקוש למחשוב מתקדם."
        risk = "אחרי עליות חדות הסקטור רגיש למימושים."
    elif sector == "technology":
        base = "טכנולוגיה ממשיכה להוביל כאשר נאסד״ק חזק וציפיות הריבית אינן מתדרדרות."
        risk = "הסיכון המרכזי הוא מימושים במדדי צמיחה ועלייה בתשואות אג״ח."
    elif sector == "sp500":
        base = "S&P 500 משקף את מצב השוק האמריקאי הרחב."
        risk = "כאשר המדד קרוב לשיאים, כל נתון ריבית/אינפלציה שלילי יכול לגרום לתיקון."
    elif sector == "metals":
        base = "מתכות וכרייה תלויות בביקוש תעשייתי, בעיקר מסין ובמחירי מתכות."
        risk = "אם סין חלשה או הדולר מתחזק, הסקטור עלול להמשיך להיות תנודתי."
    elif sector == "gold":
        base = "זהב נתמך כאשר יש חשש שוק, ירידת תשואות או ביקוש לנכס הגנתי."
        risk = "דולר חזק או עליית תשואות יכולים ללחוץ את הזהב מטה."
    elif sector == "energy":
        base = "אנרגיה תלויה במחירי נפט, מלאים וציפיות ביקוש עולמי."
        risk = "אם יש צפי להאטה או ירידת מחירי נפט, המומנטום יכול להתהפך מהר."
    elif sector == "financials":
        base = "פיננסים נהנים מסביבת ריבית גבוהה ומרווחי אשראי."
        risk = "הסיכון הוא חשש להאטה, גידול בהפרשות אשראי או ירידה בציפיות הריבית."
    elif sector == "china":
        base = "סין תלויה בצעדי תמרוץ, נדל״ן וביקוש צרכני/תעשייתי."
        risk = "הסקטור תנודתי מאוד וכל נתון מאקרו חלש יכול לשנות כיוון במהירות."
    elif sector == "korea":
        base = "קוריאה מושפעת מאוד מטכנולוגיה, שבבים ויצוא."
        risk = "אם שבבים או סחר עולמי נחלשים, המדד יכול להיחלש מהר."
    elif sector == "small_caps":
        base = "מניות קטנות נהנות כאשר השוק מצפה להורדת ריבית וצמיחה מקומית."
        risk = "הן רגישות מאוד לריבית גבוהה ולחשש מהאטה."
    elif sector == "healthcare":
        base = "בריאות נחשבת סקטור יציב יחסית ומתגונן."
        risk = "היא פחות נהנית מטרנדים חדים, ולכן יכולה לפגר אחרי שוק טכנולוגי חזק."
    else:
        base = "הקרן מושפעת ממגמת השוק הרחבה."
        risk = "יש לעקוב אחרי שינוי במומנטום ובמט״ח."

    if trend_positive:
        conclusion = "המומנטום תומך בהמשך החזקה/קנייה זהירה, כל עוד אין שבירה יומית חדה."
        bias = "חיובי זהיר"
    elif trend_weak:
        conclusion = "יש חולשה קצרה אחרי מגמה חיובית; מתאים למעקב ולא לקנייה אגרסיבית."
        bias = "מעקב"
    elif trend_negative:
        conclusion = "גם השבוע וגם החודש חלשים; אין כרגע הצדקה להגדלת חשיפה."
        bias = "שלילי"
    else:
        conclusion = "המגמה אינה חד-משמעית; עדיף להמתין לאישור כיוון."
        bias = "ניטרלי"

    text = f"{base} {risk} {fx_text} {conclusion}"
    return bias, text


# =========================
# חישוב ציון
# =========================
def score_fund(weekly, monthly, quarterly, volatility, usd_change, fx):
    weekly = weekly or 0
    monthly = monthly or 0
    quarterly = quarterly or 0
    volatility = volatility or 0

    score = 50

    score += weekly * 1.8
    score += monthly * 1.3
    score += quarterly * 0.7

    # קנס תנודתיות
    score -= volatility * 1.8

    # מט"ח
    if fx:
        score += usd_change * 0.8

    return round(max(0, min(100, score)), 1)


def decision_from_score(score, bias):
    if score >= 75 and bias in ["חיובי זהיר", "חיובי"]:
        return "קנייה זהירה / החזקה"
    if score >= 65:
        return "החזקה / מעקב חיובי"
    if score >= 55:
        return "מעקב בלבד"
    if score >= 45:
        return "לא לקנות כרגע"
    return "להימנע / לשקול יציאה"


# =========================
# סריקה
# =========================
def scan_funds():
    usd_change = get_usd_ils_change()
    results = []

    for fund in FUNDS:
        closes = get_daily_closes(fund["proxy"], 100)

        if len(closes) < 30:
            results.append({
                "name": fund["name"],
                "proxy": fund["proxy"],
                "weekly": None,
                "monthly": None,
                "quarterly": None,
                "volatility": None,
                "usd": usd_change,
                "score": 0,
                "bias": "אין נתונים",
                "forward": "לא התקבלו מספיק נתונים מ־Twelve Data.",
                "decision": "אין החלטה",
            })
            continue

        weekly = percent_change(closes, 5)
        monthly = percent_change(closes, 22)
        quarterly = percent_change(closes, 66)
        volatility = calc_volatility(closes, 20)

        bias, forward = forward_news_text(
            fund["sector"],
            weekly,
            monthly,
            usd_change
        )

        score = score_fund(
            weekly,
            monthly,
            quarterly,
            volatility,
            usd_change,
            fund["fx"]
        )

        decision = decision_from_score(score, bias)

        results.append({
            "name": fund["name"],
            "proxy": fund["proxy"],
            "weekly": weekly,
            "monthly": monthly,
            "quarterly": quarterly,
            "volatility": volatility,
            "usd": usd_change,
            "score": score,
            "bias": bias,
            "forward": forward,
            "decision": decision,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10], usd_change


# =========================
# HTML
# =========================
HTML = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>סורק קרנות וסל</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f3f4f6;
            margin: 0;
            padding: 30px;
            color: #111827;
        }
        h1 {
            margin-bottom: 5px;
        }
        .subtitle {
            color: #6b7280;
            margin-bottom: 25px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        }
        th {
            background: #111827;
            color: white;
            padding: 12px;
            font-size: 14px;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
            vertical-align: top;
            font-size: 14px;
        }
        tr:hover {
            background: #f9fafb;
        }
        .score {
            font-weight: bold;
            font-size: 18px;
        }
        .small {
            color: #6b7280;
            font-size: 12px;
        }
        .forward {
            max-width: 420px;
            line-height: 1.45;
        }
        .button {
            display: inline-block;
            background: #2563eb;
            color: white;
            padding: 12px 18px;
            border-radius: 10px;
            text-decoration: none;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>

<h1>סורק קרנות וסל — TOP 10</h1>
<div class="subtitle">
    כולל מומנטום, תנודתיות, השפעת דולר/שקל ואקטואליה קדימה.
    <br>
    עודכן: {{ now }} | שינוי דולר/שקל שבועי: {{ usd_change|round(2) }}%
</div>

<a class="button" href="/">סרוק מחדש</a>

<table>
    <thead>
        <tr>
            <th>דירוג</th>
            <th>קרן / תחום</th>
            <th>ETF ייחוס</th>
            <th>שבוע</th>
            <th>חודש</th>
            <th>3 חודשים</th>
            <th>תנודתיות</th>
            <th>ציון</th>
            <th>כיוון</th>
            <th>אקטואליה קדימה — למה?</th>
            <th>החלטה</th>
        </tr>
    </thead>
    <tbody>
    {% for r in results %}
        <tr>
            <td>{{ loop.index }}</td>
            <td><b>{{ r.name }}</b></td>
            <td>{{ r.proxy }}</td>
            <td>{{ "%.2f"|format(r.weekly or 0) }}%</td>
            <td>{{ "%.2f"|format(r.monthly or 0) }}%</td>
            <td>{{ "%.2f"|format(r.quarterly or 0) }}%</td>
            <td>{{ "%.2f"|format(r.volatility or 0) }}%</td>
            <td class="score">{{ r.score }}</td>
            <td>{{ r.bias }}</td>
            <td class="forward">{{ r.forward }}</td>
            <td><b>{{ r.decision }}</b></td>
        </tr>
    {% endfor %}
    </tbody>
</table>

<p class="small">
הערה: הסורק אינו ייעוץ השקעות. הוא משתמש ב־ETF ייחוס ובמט״ח כדי להעריך כיוון, ולא בשער המדויק של הקרן הישראלית.
</p>

</body>
</html>
"""


@app.route("/")
def index():
    results, usd_change = scan_funds()
    return render_template_string(
        HTML,
        results=results,
        usd_change=usd_change,
        now=datetime.now().strftime("%d/%m/%Y %H:%M")
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
