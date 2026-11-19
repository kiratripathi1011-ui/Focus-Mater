import time
from flask import Flask, Response, jsonify, render_template_string, request

app = Flask(__name__)

DOWNLOAD_URL = (
    "https://github.com/kiratripathi1011-ui/Focus-Mater/releases/download/v1.0.0/FocusMaster.exe"
)

users_db = {}


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def ensure_user(ip):
    if ip not in users_db:
        users_db[ip] = {
            "ip": ip,
            "status": "PAUSED",
            "study_seconds": 0,
            "break_seconds": 0,
            "last_seen": time.time(),
            "allowed_sites": ["pw.live", "penpencil.co", "cloudfront.net"],
            "allowed_apps": [
                "chrome.exe",
                "msedge.exe",
                "code.exe",
                "firefox",
                "google-chrome",
            ],
            "cooked_sites": [],
            "remote_command": None,
        }
    users_db[ip]["last_seen"] = time.time()
    return users_db[ip]


@app.route("/google088ad576209b6a72.html")
def google_verification():
    return (
        "google-site-verification: google088ad576209b6a72.html",
        200,
        {"Content-Type": "text/html; charset=UTF-8"},
    )


@app.route("/robots.txt")
def robots_txt():
    base_url = request.url_root.rstrip("/")
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    base_url = request.url_root.rstrip("/")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{base_url}/</loc>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "</urlset>\n"
    )
    return Response(xml, mimetype="application/xml")


@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip") or get_client_ip()
    user = ensure_user(ip)

    if "status" in data:
        user["status"] = data["status"]
    if "study_seconds" in data:
        user["study_seconds"] = max(user["study_seconds"], int(data["study_seconds"]))
    if "break_seconds" in data:
        user["break_seconds"] = max(user["break_seconds"], int(data["break_seconds"]))
    if "allowed_sites" in data and isinstance(data["allowed_sites"], list):
        user["allowed_sites"] = data["allowed_sites"]
    if "allowed_apps" in data and isinstance(data["allowed_apps"], list):
        user["allowed_apps"] = data["allowed_apps"]

    cmd = user.get("remote_command")
    user["remote_command"] = None

    return jsonify(
        {
            "ok": True,
            "ip": ip,
            "command": cmd,
            "allowed_sites": user["allowed_sites"],
            "allowed_apps": user["allowed_apps"],
        }
    )


@app.route("/api/cooked", methods=["POST"])
def report_cooked_site():
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip") or get_client_ip()
    domain = (data.get("domain") or "").strip().lower()
    user = ensure_user(ip)

    if domain:
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        existing = next((x for x in user["cooked_sites"] if x["domain"] == domain), None)
        if existing:
            existing["count"] += 1
            existing["last_time"] = now_str
        else:
            user["cooked_sites"].append({"domain": domain, "count": 1, "last_time": now_str})

    return jsonify({"ok": True})


PRIVACY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Privacy Policy — Focus Master</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 32px; line-height: 1.6; }
    .box { max-width: 720px; margin: 0 auto; background: #1e293b; padding: 28px; border-radius: 12px; }
    h1, h2 { color: #38bdf8; }
    a { color: #38bdf8; }
  </style>
</head>
<body>
  <div class="box">
    <h1>Privacy Policy — Focus Master</h1>
    <p><b>Last updated:</b> November 19, 2026</p>
    <p>Focus Master is a study focus and distraction-blocking app for Windows.</p>
    <h2>1. Information We Collect</h2>
    <ul>
      <li><b>Session &amp; Focus Telemetry:</b> Study time, break time, current state, and allowlists.</li>
      <li><b>Blocked Site Logs:</b> Distracting domains blocked during sessions and attempt counts.</li>
      <li><b>Network Info:</b> IP address used for session sync and focus telemetry.</li>
    </ul>
    <h2>2. How We Use Information</h2>
    <p>Used only to run focus timers, enforce distraction limits, and show live session telemetry.</p>
    <h2>3. Data Sharing</h2>
    <p>We do not sell user data to third parties.</p>
    <h2>4. Contact</h2>
    <p>GitHub: <a href="https://github.com/kiratripathi1011-ui/Focus-Mater">github.com/kiratripathi1011-ui/Focus-Mater</a></p>
    <p><a href="/">← Back to Home</a></p>
  </div>
</body>
</html>
"""


@app.route("/privacy")
def privacy_page():
    return render_template_string(PRIVACY_HTML)


HOME_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="Focus Master PC — Study lockdown app for Windows that blocks distracting websites and apps while tracking real study hours." />
  <title>Focus Master — Study Lockdown & Focus Tracker</title>
  <style>
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      background: #0f172a;
      color: #f1f5f9;
      margin: 0;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }}
    .card {{
      background: #1e293b;
      max-width: 560px;
      width: 90%;
      padding: 36px;
      border-radius: 14px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.4);
      text-align: center;
    }}
    h1 {{ color: #38bdf8; margin-bottom: 8px; font-size: 2rem; }}
    p.sub {{ color: #94a3b8; margin-bottom: 24px; line-height: 1.5; }}
    .features {{
      text-align: left;
      background: #0f172a;
      padding: 16px 20px;
      border-radius: 8px;
      margin-bottom: 26px;
      font-size: 0.95rem;
      line-height: 1.7;
    }}
    .btn {{
      display: inline-block;
      background: #16a34a;
      color: white;
      text-decoration: none;
      font-weight: bold;
      font-size: 1.1rem;
      padding: 14px 28px;
      border-radius: 8px;
      transition: background 0.2s;
    }}
    .btn:hover {{ background: #15803d; }}
    .note {{
      margin-top: 18px;
      font-size: 0.82rem;
      color: #94a3b8;
    }}
    .links {{
      margin-top: 22px;
      font-size: 0.9rem;
    }}
    .links a {{
      color: #38bdf8;
      text-decoration: none;
      margin: 0 10px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Focus Master PC</h1>
    <p class="sub">Block distracting sites and apps automatically while tracking your real study hours.</p>
    <div class="features">
      ✅ <b>Strict Allowlist Mode:</b> Only approved websites (like pw.live) and study apps stay open.<br/>
      ⏱ <b>Live Stopwatch & Pause:</b> Tracks study hours from 00:00:00 with an urgent-task Pause button.<br/>
      📊 <b>Real-Time Sync:</b> Automatically logs study time, break time, and blocked attempts.
    </div>
    <a class="btn" href="{DOWNLOAD_URL}">⬇ Download FocusMaster.exe (Windows)</a>
    <div class="note">
      <b>First-time Windows tip:</b> If Windows SmartScreen appears, click <i>More info → Run anyway</i>.
    </div>
    <div class="links">
      <a href="/privacy">Privacy Policy</a>
    </div>
  </div>
</body>
</html>
"""


@app.route("/")
def home_page():
    return render_template_string(HOME_HTML)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
