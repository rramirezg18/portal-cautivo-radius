#!/bin/bash
# Detiene el portal cautivo y restaura el estado normal del sistema.

echo "[*] Deteniendo servicios del portal..."
sudo pkill -f "python3.*portal.py" 2>/dev/null || true
sudo pkill hostapd 2>/dev/null || true
sudo pkill dnsmasq 2>/dev/null || true

echo "[*] Flush de nftables..."
sudo nft flush ruleset

echo "[*] Devolviendo wlp2s0 a NetworkManager..."
sudo nmcli device set wlp2s0 managed yes 2>/dev/null || true

echo "[*] Reiniciando contenedor pg_proxy..."
sudo docker start pg_proxy 2>/dev/null || true

echo "[✓] Portal detenido."
