import json
import os
import platform
import socket
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import psutil
import requests

SERVER_URL = "http://127.0.0.1:5000"  # Change to your hosted server URL
CONFIG_FILE = "focus_master_config.json"
STATS_FILE = "focus_master_stats.json"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8899

ADMIN_ID = "Kira"
ADMIN_PASS = "Kali"

SYSTEM_SAFE_PROCESSES = {
    "system", "idle", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "svchost.exe", "winlogon.exe", "explorer.exe", "dwm.exe",
    "taskhostw.exe", "runtimebroker.exe", "shellexperiencehost.exe",
    "searchhost.exe", "startmenuexperiencehost.exe", "ctfmon.exe",
    "conhost.exe", "python.exe", "pythonw.exe", "python3", "systemd",
    "gnome-shell", "xorg", "wayland", "pulseaudio", "pipewire", "dbus-daemon",
    "bash", "zsh", "sh", "windowsterminal.exe"
}

DEFAULT_CONFIG = {
    "allowed_sites": [
        "pw.live",
        "penpencil.co",
        "cloudfront.net",
        "youtube-nocookie.com",
        "googlevideo.com"
    ],
    "allowed_apps": [
        "chrome.exe",
        "msedge.exe",
        "brave.exe",
        "firefox.exe",
        "firefox",
        "google-chrome",
        "acrobat.exe",
        "sumatrapdf.exe",
        "notepad.exe"
    ]
}


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class LocalEnforcer:
    def __init__(self, on_cooked_callback):
        self.enforcing = False
        self.allowed_sites = []
        self.allowed_apps = set()
        self.on_cooked_callback = on_cooked_callback
        self.server_socket = None

    def set_rules(self, sites, apps):
        self.allowed_sites = [s.lower().strip() for s in sites if s.strip()]
        self.allowed_apps = {a.lower().strip() for a in apps if a.strip()}

    def is_site_allowed(self, host: str) -> bool:
        host = host.split(":")[0].lower().strip()
        return any(host == d or host.endswith("." + d) for d in self.allowed_sites)

    def _pipe(self, src, dst):
        try:
            while self.enforcing:
                data = src.recv(4096)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                src.close()
                dst.close()
            except Exception:
                pass

    def _handle_client(self, client_sock):
        try:
            req = client_sock.recv(4096)
            if not req:
                client_sock.close()
                return

            first_line = req.split(b"\r\n")[0].decode("utf-8", errors="ignore")
            parts = first_line.split(" ")
            if len(parts) < 2:
                client_sock.close()
                return

            method, target = parts[0], parts[1]
            if method == "CONNECT":
                host, _, port_str = target.partition(":")
                port = int(port_str) if port_str else 443
            else:
                url = target.replace("http://", "")
                host_port = url.split("/")[0]
                host, _, port_str = host_port.partition(":")
                port = int(port_str) if port_str else 80

            clean_host = host.split(":")[0].lower().strip()
            if not self.is_site_allowed(clean_host):
                if clean_host and self.on_cooked_callback:
                    self.on_cooked_callback(clean_host)
                client_sock.sendall(
                    b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\n\r\n"
                    b"<h1>Cooked / Blocked Site</h1><p>This website is not allowed during study.</p>"
                )
                client_sock.close()
                return

            remote_sock = socket.create_connection((host, port), timeout=10)
            if method == "CONNECT":
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            else:
                remote_sock.sendall(req)

            threading.Thread(target=self._pipe, args=(client_sock, remote_sock), daemon=True).start()
            threading.Thread(target=self._pipe, args=(remote_sock, client_sock), daemon=True).start()
        except Exception:
            try:
                client_sock.close()
            except Exception:
                pass

    def _proxy_loop(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((PROXY_HOST, PROXY_PORT))
        self.server_socket.listen(120)
        self.server_socket.settimeout(1.0)

        while self.enforcing:
            try:
                client_sock, _ = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break
        try:
            self.server_socket.close()
        except Exception:
            pass

    def _watchdog_loop(self):
        my_pid = os.getpid()
        try:
            current_user = psutil.Process(my_pid).username()
        except Exception:
            current_user = None

        while self.enforcing:
            for proc in psutil.process_iter(["pid", "name", "username", "exe"]):
                try:
                    if proc.info["pid"] == my_pid:
                        continue
                    if current_user and proc.info["username"] != current_user:
                        continue
                    pname = (proc.info["name"] or "").lower()
                    exe_path = (proc.info["exe"] or "").lower()
                    if not pname or pname in SYSTEM_SAFE_PROCESSES:
                        continue
                    if "\\windows\\system32" in exe_path:
                        continue
                    if pname not in self.allowed_apps:
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            time.sleep(1.5)

    def set_system_proxy(self, enable: bool):
        os_name = platform.system()
        if os_name == "Windows":
            reg = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            if enable:
                subprocess.run(["reg", "add", reg, "/v", "ProxyEnable", "/t", "REG_DWORD", "/d", "1", "/f"], check=False)
                subprocess.run(["reg", "add", reg, "/v", "ProxyServer", "/t", "REG_SZ", "/d", f"{PROXY_HOST}:{PROXY_PORT}", "/f"], check=False)
            else:
                subprocess.run(["reg", "add", reg, "/v", "ProxyEnable", "/t", "REG_DWORD", "/d", "0", "/f"], check=False)
        elif os_name == "Linux":
            mode = "manual" if enable else "none"
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", mode], check=False)
            if enable:
                subprocess.run(["gsettings", "set", "org.gnome.system.proxy.http", "host", PROXY_HOST], check=False)
                subprocess.run(["gsettings", "set", "org.gnome.system.proxy.http", "port", str(PROXY_PORT)], check=False)
                subprocess.run(["gsettings", "set", "org.gnome.system.proxy.https", "host", PROXY_HOST], check=False)
                subprocess.run(["gsettings", "set", "org.gnome.system.proxy.https", "port", str(PROXY_PORT)], check=False)

    def start(self):
        if self.enforcing:
            return
        self.enforcing = True
        self.set_system_proxy(True)
        threading.Thread(target=self._proxy_loop, daemon=True).start()
        threading.Thread(target=self._watchdog_loop, daemon=True).start()

    def stop(self):
        self.enforcing = False
        self.set_system_proxy(False)


class FocusMasterApp:
    def __init__(self, root, role, admin_creds=None):
        self.root = root
        self.role = role  # "USER" or "ADMIN"
        self.admin_creds = admin_creds
        self.ip = get_local_ip()

        self.root.title(f"Focus Master ({role}) — IP: {self.ip}")
        self.root.geometry("760x580")
        self.root.configure(bg="#0f172a")

        self.config = self.load_json(CONFIG_FILE, DEFAULT_CONFIG)
        self.stats = self.load_json(STATS_FILE, {
            "study_seconds": 0,
            "break_seconds": 0,
            "cooked_sites": []
        })

        # Stopwatch state starting from 0 (no fixed target timer required)
        # state: "IDLE" | "STUDYING" | "PAUSED"
        self.state = "IDLE"
        self.session_study_secs = 0
        self.session_break_secs = 0

        self.enforcer = LocalEnforcer(self.record_cooked_site)
        self.enforcer.set_rules(self.config["allowed_sites"], self.config["allowed_apps"])

        self.build_ui()
        self.refresh_lists()
        self.update_labels()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        self.root.after(1000, self._ticker)

    def load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in default.items():
                        data.setdefault(k, v)
                    return data
            except Exception:
                pass
        return json.loads(json.dumps(default))

    def save_json(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def fmt_hms(self, secs):
        h, rem = divmod(int(secs), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def fmt_hm(self, secs):
        h, rem = divmod(int(secs), 3600)
        m, _ = divmod(rem, 60)
        return f"{h}h {m}m"

    def build_ui(self):
        top = tk.Frame(self.root, bg="#1e293b", pady=10, padx=14)
        top.pack(fill=tk.X)
        tk.Label(top, text="FOCUS MASTER", font=("Segoe UI", 15, "bold"), bg="#1e293b", fg="#38bdf8").pack(side=tk.LEFT)
        tk.Label(top, text=f"Role: {self.role}  |  Your IP: {self.ip}", font=("Segoe UI", 10, "bold"), bg="#1e293b", fg="#a5f3fc").pack(side=tk.RIGHT)

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tab_work = tk.Frame(nb, bg="#0f172a")
        tab_rules = tk.Frame(nb, bg="#0f172a")
        nb.add(tab_work, text="⏱ Work & Pause")
        nb.add(tab_rules, text="🛡 Sites & Apps")

        self.build_work_tab(tab_work)
        self.build_rules_tab(tab_rules)

        if self.role == "ADMIN":
            tab_admin = tk.Frame(nb, bg="#0f172a")
            nb.add(tab_admin, text="👑 Admin Console")
            self.build_admin_tab(tab_admin)

    def build_work_tab(self, parent):
        self.status_lbl = tk.Label(parent, text="STATUS: IDLE", font=("Segoe UI", 13, "bold"), bg="#0f172a", fg="#94a3b8")
        self.status_lbl.pack(pady=(16, 4))

        self.study_clock_lbl = tk.Label(parent, text="00:00:00", font=("Consolas", 42, "bold"), bg="#0f172a", fg="#4ade80")
        self.study_clock_lbl.pack(pady=6)
        tk.Label(parent, text="Study Stopwatch (Starts from 0)", font=("Segoe UI", 9), bg="#0f172a", fg="#94a3b8").pack()

        self.break_clock_lbl = tk.Label(parent, text="Break / Pause Time: 00:00:00", font=("Consolas", 14, "bold"), bg="#0f172a", fg="#facc15")
        self.break_clock_lbl.pack(pady=10)

        btns = tk.Frame(parent, bg="#0f172a")
        btns.pack(pady=10)

        self.work_btn = tk.Button(btns, text="▶ START / WORK", font=("Segoe UI", 11, "bold"), bg="#16a34a", fg="white", padx=18, pady=8, borderwidth=0, command=self.start_work)
        self.work_btn.grid(row=0, column=0, padx=6)

        self.pause_btn = tk.Button(btns, text="⏸ PAUSE (URGENT TASK)", font=("Segoe UI", 11, "bold"), bg="#d97706", fg="white", padx=18, pady=8, borderwidth=0, command=self.pause_work)
        self.pause_btn.grid(row=0, column=1, padx=6)

        self.stop_btn = tk.Button(btns, text="⏹ STOP & UNLOCK", font=("Segoe UI", 11, "bold"), bg="#dc2626", fg="white", padx=18, pady=8, borderwidth=0, command=self.stop_session)
        self.stop_btn.grid(row=0, column=2, padx=6)

        self.totals_lbl = tk.Label(parent, text="", font=("Segoe UI", 11, "bold"), bg="#0f172a", fg="#e2e8f0")
        self.totals_lbl.pack(pady=12)

        self.cooked_box_lbl = tk.Label(parent, text="Cooked (Blocked) Sites This Session: None", font=("Segoe UI", 10), bg="#0f172a", fg="#f87171", wraplength=700)
        self.cooked_box_lbl.pack(pady=4)

    def build_rules_tab(self, parent):
        cols = tk.Frame(parent, bg="#0f172a")
        cols.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = tk.Frame(cols, bg="#1e293b", padx=10, pady=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(left, text="Allowed Websites", font=("Segoe UI", 11, "bold"), bg="#1e293b", fg="#38bdf8").pack(anchor="w")
        self.site_lb = tk.Listbox(left, bg="#0f172a", fg="white", font=("Consolas", 10), borderwidth=0)
        self.site_lb.pack(fill=tk.BOTH, expand=True, pady=6)
        sf = tk.Frame(left, bg="#1e293b")
        sf.pack(fill=tk.X)
        self.site_entry = tk.Entry(sf)
        self.site_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Button(sf, text="Add", bg="#0284c7", fg="white", borderwidth=0, padx=8, command=self.add_site).pack(side=tk.LEFT)
        tk.Button(sf, text="Del", bg="#dc2626", fg="white", borderwidth=0, padx=8, command=self.del_site).pack(side=tk.LEFT, padx=(4, 0))

        right = tk.Frame(cols, bg="#1e293b", padx=10, pady=10)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
        tk.Label(right, text="Allowed PC Apps", font=("Segoe UI", 11, "bold"), bg="#1e293b", fg="#fbbf24").pack(anchor="w")
        self.app_lb = tk.Listbox(right, bg="#0f172a", fg="white", font=("Consolas", 10), borderwidth=0)
        self.app_lb.pack(fill=tk.BOTH, expand=True, pady=6)
        af = tk.Frame(right, bg="#1e293b")
        af.pack(fill=tk.X)
        self.app_entry = tk.Entry(af)
        self.app_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Button(af, text="Add", bg="#0284c7", fg="white", borderwidth=0, padx=8, command=self.add_app).pack(side=tk.LEFT)
        tk.Button(af, text="Del", bg="#dc2626", fg="white", borderwidth=0, padx=8, command=self.del_app).pack(side=tk.LEFT, padx=(4, 0))

    def build_admin_tab(self, parent):
        bar = tk.Frame(parent, bg="#0f172a")
        bar.pack(fill=tk.X, padx=10, pady=8)
        tk.Button(bar, text="🔄 Refresh Connected Users", bg="#0284c7", fg="white", borderwidth=0, padx=12, pady=5, command=self.refresh_admin_view).pack(side=tk.LEFT)
        tk.Button(bar, text="⏸ Pause Selected IP", bg="#d97706", fg="white", borderwidth=0, padx=12, pady=5, command=lambda: self.admin_remote_cmd("PAUSE")).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="▶ Resume Selected IP", bg="#16a34a", fg="white", borderwidth=0, padx=12, pady=5, command=lambda: self.admin_remote_cmd("RESUME")).pack(side=tk.LEFT)

        self.admin_lb = tk.Listbox(parent, bg="#1e293b", fg="#e2e8f0", font=("Consolas", 9), borderwidth=0)
        self.admin_lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        self.admin_detail = tk.Text(parent, height=7, bg="#1e293b", fg="#f87171", font=("Consolas", 9), borderwidth=0)
        self.admin_detail.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.refresh_admin_view()

    def refresh_lists(self):
        self.site_lb.delete(0, tk.END)
        for s in self.config["allowed_sites"]:
            self.site_lb.insert(tk.END, s)
        self.app_lb.delete(0, tk.END)
        for a in self.config["allowed_apps"]:
            self.app_lb.insert(tk.END, a)

    def add_site(self):
        s = self.site_entry.get().strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
        if s and s not in self.config["allowed_sites"]:
            self.config["allowed_sites"].append(s)
            self.save_json(CONFIG_FILE, self.config)
            self.enforcer.set_rules(self.config["allowed_sites"], self.config["allowed_apps"])
            self.refresh_lists()
            self.site_entry.delete(0, tk.END)

    def del_site(self):
        sel = self.site_lb.curselection()
        if sel:
            self.config["allowed_sites"].remove(self.site_lb.get(sel[0]))
            self.save_json(CONFIG_FILE, self.config)
            self.enforcer.set_rules(self.config["allowed_sites"], self.config["allowed_apps"])
            self.refresh_lists()

    def add_app(self):
        a = self.app_entry.get().strip().lower()
        if a and a not in self.config["allowed_apps"]:
            self.config["allowed_apps"].append(a)
            self.save_json(CONFIG_FILE, self.config)
            self.enforcer.set_rules(self.config["allowed_sites"], self.config["allowed_apps"])
            self.refresh_lists()
            self.app_entry.delete(0, tk.END)

    def del_app(self):
        sel = self.app_lb.curselection()
        if sel:
            self.config["allowed_apps"].remove(self.app_lb.get(sel[0]))
            self.save_json(CONFIG_FILE, self.config)
            self.enforcer.set_rules(self.config["allowed_sites"], self.config["allowed_apps"])
            self.refresh_lists()

    def record_cooked_site(self, domain):
        if domain not in self.stats["cooked_sites"]:
            self.stats["cooked_sites"].append(domain)
            self.save_json(STATS_FILE, self.stats)
        try:
            requests.post(f"{SERVER_URL}/api/cooked", json={"ip": self.ip, "domain": domain}, timeout=2)
        except Exception:
            pass

    def start_work(self):
        self.state = "STUDYING"
        self.enforcer.set_rules(self.config["allowed_sites"], self.config["allowed_apps"])
        self.enforcer.start()
        self.status_lbl.config(text="STATUS: STUDYING (STRICT LOCK ACTIVE)", fg="#4ade80")

    def pause_work(self):
        self.state = "PAUSED"
        self.enforcer.stop()
        self.status_lbl.config(text="STATUS: PAUSED (URGENT TASK / BREAK TRACKING)", fg="#facc15")

    def stop_session(self):
        self.state = "IDLE"
        self.enforcer.stop()
        self.save_json(STATS_FILE, self.stats)
        self.status_lbl.config(text="STATUS: IDLE (UNLOCKED)", fg="#94a3b8")

    def _ticker(self):
        if self.state == "STUDYING":
            self.session_study_secs += 1
            self.stats["study_seconds"] += 1
        elif self.state == "PAUSED":
            self.session_break_secs += 1
            self.stats["break_seconds"] += 1

        self.update_labels()
        self.root.after(1000, self._ticker)

    def update_labels(self):
        self.study_clock_lbl.config(text=self.fmt_hms(self.session_study_secs))
        self.break_clock_lbl.config(text=f"Break / Pause Time: {self.fmt_hms(self.session_break_secs)}")
        self.totals_lbl.config(
            text=f"Total Tracked Study: {self.fmt_hm(self.stats['study_seconds'])}  |  Total Break/Pause: {self.fmt_hm(self.stats['break_seconds'])}"
        )
        cooked = ", ".join(self.stats["cooked_sites"]) if self.stats["cooked_sites"] else "None"
        self.cooked_box_lbl.config(text=f"Cooked (Blocked) Sites: {cooked}")

    def _heartbeat_loop(self):
        while True:
            try:
                res = requests.post(f"{SERVER_URL}/api/heartbeat", json={
                    "ip": self.ip,
                    "status": self.state,
                    "study_seconds": self.stats["study_seconds"],
                    "break_seconds": self.stats["break_seconds"],
                    "allowed_sites": self.config["allowed_sites"],
                    "allowed_apps": self.config["allowed_apps"],
                }, timeout=3)
                if res.ok:
                    data = res.json()
                    cmd = data.get("command")
                    if cmd == "PAUSE":
                        self.root.after(0, self.pause_work)
                    elif cmd == "RESUME":
                        self.root.after(0, self.start_work)
            except Exception:
                pass
            time.sleep(3)

    def refresh_admin_view(self):
        if self.role != "ADMIN" or not self.admin_creds:
            return
        try:
            res = requests.post(f"{SERVER_URL}/api/admin/users", json=self.admin_creds, timeout=3)
            if not res.ok:
                return
            users = res.json().get("users", [])
            self.admin_lb.delete(0, tk.END)
            self.admin_detail.delete("1.0", tk.END)
            for u in users:
                line = f"{u['ip']} | {u['status']} | Study: {self.fmt_hm(u['study_seconds'])} | Break: {self.fmt_hm(u['break_seconds'])}"
                self.admin_lb.insert(tk.END, line)
                cooked_list = [f"{c['domain']} (x{c['count']})" for c in u.get("cooked_sites", [])]
                self.admin_detail.insert(
                    tk.END,
                    f"IP {u['ip']} -> Allowed: {', '.join(u.get('allowed_sites', []))} | Cooked: {', '.join(cooked_list) or 'None'}\n"
                )
        except Exception:
            pass

    def admin_remote_cmd(self, action):
        sel = self.admin_lb.curselection()
        if not sel or not self.admin_creds:
            return
        line = self.admin_lb.get(sel[0])
        target_ip = line.split("|")[0].strip()
        try:
            requests.post(f"{SERVER_URL}/api/admin/control", json={
                **self.admin_creds,
                "ip": target_ip,
                "action": action
            }, timeout=3)
            self.refresh_admin_view()
        except Exception:
            pass

    def on_close(self):
        self.enforcer.stop()
        self.save_json(STATS_FILE, self.stats)
        self.root.destroy()


def prompt_role_and_launch():
    root = tk.Tk()
    root.withdraw()

    choice = messagebox.askquestion(
        "Focus Master — Select Mode",
        "Are you logging in as ADMIN?\n\nClick 'Yes' for Admin (ID: Kira)\nClick 'No' for Normal User"
    )

    if choice == "yes":
        uid = simpledialog.askstring("Admin Login", "Enter Admin ID:", initialvalue="Kira", parent=root)
        pwd = simpledialog.askstring("Admin Login", "Enter Admin Password:", show="*", parent=root)
        if uid == ADMIN_ID and pwd == ADMIN_PASS:
            # Verify against server if reachable, otherwise allow local match
            try:
                r = requests.post(f"{SERVER_URL}/api/auth/admin", json={"username": uid, "password": pwd}, timeout=2)
                if r.status_code == 401:
                    messagebox.showerror("Access Denied", "Invalid Admin ID or Password.")
                    root.destroy()
                    return
            except Exception:
                pass
            root.deiconify()
            FocusMasterApp(root, role="ADMIN", admin_creds={"username": uid, "password": pwd})
            root.mainloop()
        else:
            messagebox.showerror("Access Denied", "Invalid Admin ID or Password.")
            root.destroy()
    else:
        root.deiconify()
        FocusMasterApp(root, role="USER")
        root.mainloop()


if __name__ == "__main__":
    prompt_role_and_launch()