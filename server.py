import os
import time
from flask import Flask, Response, jsonify, render_template_string, request

app = Flask(__name__)

ADMIN_ID = os.environ.get("ADMIN_ID", "Kira")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "Kali")

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
        "Disallow: /admin\n"
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


@app.route("/api/auth/admin", methods=["POST"])
def auth_admin():
    data = request.get_json(force=True, silent=True) or {}
    if data.get("username") == ADMIN_ID and data.get("password") == ADMIN_PASS:
        return jsonify({"ok": True, "message": "Admin authenticated"})
    return jsonify({"ok": False, "message": "Invalid Admin ID or Password"}), 401


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


@app.route("/api/admin/users", methods=["POST"])
def admin_users():
    data = request.get_json(force=True, silent=True) or {}
    if data.get("username") != ADMIN_ID or data.get("password") != ADMIN_PASS:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    now = time.time()
    result = []
    for ip, u in users_db.items():
        item = dict(u)
        item["online"] = (now - u["last_seen"]) < 15
        result.append(item)
    return jsonify({"ok": True, "users": result})


@app.route("/api/admin/control", methods=["POST"])
def admin_control():
    data = request.get_json(force=True, silent=True) or {}
    if data.get("username") != ADMIN_ID or data.get("password") != ADMIN_PASS:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    target_ip = data.get("ip")
    action = data.get("action")
    if target_ip in users_db and action in ("PAUSE", "RESUME"):
        users_db[target_ip]["remote_command"] = action
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Invalid IP or action"}), 400


ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Focus Master — Admin Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 24px; }
    h1 { color: #38bdf8; }
    .login-box { max-width: 360px; background: #1e293b; padding: 20px; border-radius: 8px; }
    input, button { width: 100%; padding: 8px; margin: 6px 0; border-radius: 4px; border: none; }
    button { background: #0284c7; color: white; font-weight: bold; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; background: #1e293b; }
    th, td { border: 1px solid #334155; padding: 10px; text-align: left; vertical-align: top; }
    th { background: #0f172a; color: #7dd3fc; }
    .pill { padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
    .studying { background: #166534; color: #bbf7d0; }
    .paused { background: #854d0e; color: #fef08a; }
    .cooked { color: #f87171; font-weight: bold; }
  </style>
</head>
<body>
  <h1>Focus Master — Admin Telemetry</h1>
  <div id="login" class="login-box">
    <h3>Admin Sign In</h3>
    <input id="uid" placeholder="Admin ID" />
    <input id="pwd" type="password" placeholder="Password" />
    <button onclick="login()">Login</button>
  </div>
  <div id="dash" style="display:none;">
    <button style="width:auto;padding:8px 16px;" onclick="loadUsers()">Refresh Now</button>
    <table>
      <thead>
        <tr>
          <th>IP Address</th>
          <th>State</th>
          <th>Study Time</th>
          <th>Break Time</th>
          <th>Allowed Sites</th>
          <th>Cooked (Blocked) Sites</th>
          <th>Remote Control</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <script>
    let creds = {};
    function fmt(sec) {
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = sec % 60;
      return `${h}h ${m}m ${s}s`;
    }
    async function login() {
      creds = { username: document.getElementById("uid").value, password: document.getElementById("pwd").value };
      const res = await fetch("/api/auth/admin", { method: "POST", body: JSON.stringify(creds) });
      if (res.ok) {
        document.getElementById("login").style.display = "none";
        document.getElementById("dash").style.display = "block";
        loadUsers();
        setInterval(loadUsers, 3000);
      } else {
        alert("Invalid credentials");
      }
    }
    async function sendCmd(ip, action) {
      await fetch("/api/admin/control", {
        method: "POST",
        body: JSON.stringify({ ...creds, ip, action })
      });
      loadUsers();
    }
    async function loadUsers() {
      const res = await fetch("/api/admin/users", { method: "POST", body: JSON.stringify(creds) });
      const data = await res.json();
      const tbody = document.getElementById("rows");
      tbody.innerHTML = "";
      (data.users || []).forEach(u => {
        const cookedStr = (u.cooked_sites || []).map(c => `${c.domain} (${c.count})`).join(", ") || "None";
        const allowedStr = (u.allowed_sites || []).join(", ") || "None";
        tbody.innerHTML += `
          <tr>
            <td><b>${u.ip}</b> ${u.online ? "🟢" : "⚪"}</td>
            <td><span class="pill ${u.status === "STUDYING" ? "studying" : "paused"}">${u.status}</span></td>
            <td>${fmt(u.study_seconds)}</td>
            <td>${fmt(u.break_seconds)}</td>
            <td>${allowedStr}</td>
            <td class="cooked">${cookedStr}</td>
            <td>
              <button style="width:auto;padding:4px 10px;background:#d97706;" onclick="sendCmd('${u.ip}','PAUSE')">Pause</button>
              <button style="width:auto;padding:4px 10px;background:#16a34a;" onclick="sendCmd('${u.ip}','RESUME')">Work/Resume</button>
            </td>
          </tr>`;
      });
    }
  </script>
</body>
</html>
"""


@app.route("/admin")
def admin_page():
    return render_template_string(ADMIN_HTML)


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
      <li><b>Network Info:</b> IP address used for session sync and remote pause/resume commands.</li>
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
      <a href="/admin">Admin Dashboard →</a>
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
