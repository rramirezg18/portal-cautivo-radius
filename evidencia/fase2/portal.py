#!/usr/bin/env python3
"""
Portal cautivo - Fase 2
Login local (sin RADIUS todavía).
Autoriza clientes agregándolos a un set de nftables.
"""
import subprocess
import time
import threading
from flask import Flask, request, render_template, redirect

app = Flask(__name__)

# Usuarios locales (Fase 2). En Fase 4 esto lo sustituye RADIUS.
USUARIOS = {
    "guest1":   {"password": "guest123",   "role": "guest",   "timeout": 1800},
    "student1": {"password": "student123", "role": "student", "timeout": 3600},
    "teacher1": {"password": "teacher123", "role": "teacher", "timeout": 7200},
}

# Sesiones activas: ip -> {user, role, mac, start, timeout}
sessions = {}


def get_mac(ip):
    """Obtiene la MAC del cliente a partir de su IP en la tabla ARP."""
    try:
        out = subprocess.check_output(["ip", "neigh", "show", ip]).decode()
        for token in out.split():
            if ":" in token and len(token) == 17:
                return token
    except Exception:
        pass
    return None


def allow_client(ip, timeout):
    """Agrega la IP al set de autorizados en nftables."""
    subprocess.run(
        ["nft", "add", "element", "ip", "portal_nat", "allowed_ip",
         f"{{ {ip} timeout {timeout}s }}"],
        check=False
    )


def deny_client(ip):
    """Quita la IP del set de autorizados."""
    subprocess.run(
        ["nft", "delete", "element", "ip", "portal_nat", "allowed_ip",
         f"{{ {ip} }}"],
        check=False
    )


def session_expiry_watcher(ip):
    """Cierra la sesión cuando expira el timeout."""
    sess = sessions.get(ip)
    if not sess:
        return
    time.sleep(sess["timeout"])
    if ip in sessions:
        deny_client(ip)
        sessions.pop(ip, None)
        print(f"[SESSION] Expirada para {ip}")


@app.route("/", methods=["GET"])
def index():
    ip = request.remote_addr
    if ip in sessions:
        return redirect("/landing")
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    ip = request.remote_addr
    user = request.form.get("username", "").strip()
    pwd = request.form.get("password", "").strip()
    mac = get_mac(ip)

    print(f"[LOGIN] Intento: user={user}, ip={ip}, mac={mac}")

    if user not in USUARIOS or USUARIOS[user]["password"] != pwd:
        return render_template("login.html", error="Credenciales inválidas")

    info = USUARIOS[user]
    sessions[ip] = {
        "user": user,
        "role": info["role"],
        "mac": mac,
        "start": time.time(),
        "timeout": info["timeout"],
    }
    allow_client(ip, info["timeout"])
    threading.Thread(target=session_expiry_watcher, args=(ip,), daemon=True).start()

    print(f"[LOGIN] OK: {user} ({info['role']}) desde {ip}")
    return redirect("/landing")


@app.route("/landing")
def landing():
    ip = request.remote_addr
    sess = sessions.get(ip)
    if not sess:
        return redirect("/")
    remaining = int(sess["timeout"] - (time.time() - sess["start"]))
    return render_template(
        "landing.html",
        user=sess["user"],
        role=sess["role"],
        remaining=remaining,
    )


# Endpoints que iOS/Android/Windows consultan para detectar portal cautivo.
# Al responder con un redirect a /, el sistema abre automáticamente la CNA.
@app.route("/generate_204")
@app.route("/gen_204")
@app.route("/hotspot-detect.html")
@app.route("/library/test/success.html")
@app.route("/ncsi.txt")
@app.route("/connecttest.txt")
def cna():
    return redirect("/")


# Catch-all: cualquier otra ruta también redirige al login
@app.route("/<path:path>")
def catch_all(path):
    return redirect("/")


if __name__ == "__main__":
    app.run(host="10.10.0.1", port=80, debug=False)
