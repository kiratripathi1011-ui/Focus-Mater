import time
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

ADMIN_ID = "Kira"
ADMIN_PASS = "Kali"

# In-memory store keyed by client IP address
# Structure: ip -> dict of telemetry & rules
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
            "status": "PAUSED",          # STUDYING | PAUSED | BREAK
            "study_seconds": 0,
            "break_seconds": 0,
            "last_seen": time.time(),
            "allowed_sites": ["pw.live", "penpencil.co", "cloudfront.net"],
            "allowed_apps": ["chrome.exe", "msedge.exe", "code.exe", "firefox", "google-chrome"],
            "cooked_sites": [],          # list of {domain, count, last_time}
            "remote_command": None,      # None | "PAUSE" | "RESUME"
        }
    users_db[ip]["last_seen"] = time.time()
    return users_db[ip]


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
    user["remote_command"] = None  # consume once delivered

    return jsonify({
        "ok": True,
        "ip": ip,
        "command": cmd,
        "allowed_sites": user["allowed_sites"],
        "allowed_apps": user["allowed_apps"],
    })


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
    action = data.get("action")  # "PAUSE" or "RESUME"
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
    <input id="uid" placeholder="Admin ID" value="Kira" />
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)