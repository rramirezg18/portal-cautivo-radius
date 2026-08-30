#!/usr/bin/env python3
"""
Portal cautivo - Fase 4 (CHAP)
Login validado contra FreeRADIUS usando CHAP (evita bug de pyrad 2.4 con PAP).
Autoriza clientes agregándolos a un set de nftables.
Envía Accounting-Start / Accounting-Stop.
"""
import subprocess
import time
import threading
import uuid
import os
import hashlib
from flask import Flask, request, render_template, redirect

from pyrad.client import Client
from pyrad.dictionary import Dictionary
import pyrad.packet as pkt

# ---------- Config RADIUS ----------
RADIUS_SERVER = "127.0.0.1"
RADIUS_SECRET = os.environ.get("RADIUS_SECRET", "CHANGE_ME_SECRET").encode()
NAS_IDENTIFIER = "portal-naruto"
DICT_PATH = "/home/robertin/portal-cautivo/portal/dict/dictionary"

app = Flask(__name__)

# Sesiones activas
sessions = {}


def radius_client():
    c = Client(server=RADIUS_SERVER, secret=RADIUS_SECRET,
               dict=Dictionary(DICT_PATH))
    c.AuthPort = 1812
    c.AcctPort = 1813
    c.timeout = 5
    c.retries = 2
    return c


def get_mac(ip):
    try:
        out = subprocess.check_output(["ip", "neigh", "show", ip]).decode()
        for token in out.split():
            if ":" in token and len(token) == 17:
                return token
    except Exception:
        pass
    return None


def allow_client(ip, timeout):
    subprocess.run(
        ["nft", "add", "element", "ip", "portal_nat", "allowed_ip",
         f"{{ {ip} timeout {timeout}s }}"],
        check=False,
    )


def deny_client(ip):
    subprocess.run(
        ["nft", "delete", "element", "ip", "portal_nat", "allowed_ip",
         f"{{ {ip} }}"],
        check=False,
    )


def send_accounting(status_type, sess):
    try:
        c = radius_client()
        req = c.CreateAcctPacket(User_Name=sess["user"])
        req["Acct-Status-Type"] = status_type
        req["Acct-Session-Id"] = sess["session_id"]
        req["Framed-IP-Address"] = sess["ip"]
        req["NAS-Identifier"] = NAS_IDENTIFIER
        req["Calling-Station-Id"] = sess["mac"] or "unknown"
        if status_type == "Stop":
            req["Acct-Session-Time"] = int(time.time() - sess["start"])
            req["Acct-Terminate-Cause"] = "Session-Timeout"
        c.SendPacket(req)
        print(f"[ACCT] {status_type} enviado: user={sess['user']} ip={sess['ip']}")
    except Exception as e:
        print(f"[ACCT] Error enviando {status_type}: {e}")


def session_expiry_watcher(ip):
    sess = sessions.get(ip)
    if not sess:
        return
    time.sleep(sess["timeout"])
    if ip in sessions:
        deny_client(ip)
        send_accounting("Stop", sess)
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

    try:
        c = radius_client()
        req = c.CreateAuthPacket(code=pkt.AccessRequest, User_Name=user)

        # CHAP: MD5(chap_id + password + challenge)
        challenge = os.urandom(16)
        chap_id = os.urandom(1)
        chap_response = chap_id + hashlib.md5(chap_id + pwd.encode() + challenge).digest()

        req["CHAP-Password"] = chap_response
        req["CHAP-Challenge"] = challenge
        req["NAS-Identifier"] = NAS_IDENTIFIER
        req["NAS-IP-Address"] = "127.0.0.1"
        req["Calling-Station-Id"] = mac or "unknown"
        req["Framed-IP-Address"] = ip

        reply = c.SendPacket(req)
    except Exception as e:
        print(f"[LOGIN] Error RADIUS: {type(e).__name__}: {e}")
        return render_template("login.html", error=f"Error RADIUS: {e}")

    if reply.code != pkt.AccessAccept:
        print(f"[LOGIN] RECHAZADO: {user}")
        return render_template("login.html", error="Credenciales inválidas")

    role = "guest"
    if "Reply-Message" in reply:
        role = reply["Reply-Message"][0]
    timeout = 1800
    if "Session-Timeout" in reply:
        timeout = int(reply["Session-Timeout"][0])

    session_id = uuid.uuid4().hex[:16]
    sessions[ip] = {
        "user": user,
        "role": role,
        "mac": mac,
        "ip": ip,
        "start": time.time(),
        "timeout": timeout,
        "session_id": session_id,
    }
    allow_client(ip, timeout)
    send_accounting("Start", sessions[ip])
    threading.Thread(
        target=session_expiry_watcher, args=(ip,), daemon=True
    ).start()

    print(f"[LOGIN] OK: {user} ({role}) desde {ip}, timeout={timeout}s")
    # Renderizar landing directamente (no redirigir) para que la CNA la muestre antes de cerrar
    return render_template(f"landing_{role}.html", user=user, role=role, remaining=timeout)


@app.route("/landing")
def landing():
    ip = request.remote_addr
    sess = sessions.get(ip)
    if not sess:
        return redirect("/")
    remaining = int(sess["timeout"] - (time.time() - sess["start"]))
    return render_template(
        f"landing_{sess['role']}.html",
        user=sess["user"],
        role=sess["role"],
        remaining=remaining,
    )


@app.route("/generate_204")
@app.route("/gen_204")
@app.route("/hotspot-detect.html")
@app.route("/library/test/success.html")
@app.route("/ncsi.txt")
@app.route("/connecttest.txt")
def cna():
    return redirect("/")


@app.route("/<path:path>")
def catch_all(path):
    return redirect("/")


if __name__ == "__main__":
    app.run(host="10.10.0.1", port=80, debug=False)
