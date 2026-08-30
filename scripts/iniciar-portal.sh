#!/bin/bash
# Levanta el portal cautivo Naruto-WiFi completo.
# Requiere: hostapd, dnsmasq, freeradius, nftables ya instalados y configurados.

set -e

USB_IFACE="usb0"
WIFI_IFACE="wlp2s0"
WIFI_IP="10.10.0.1/24"

echo "[*] Verificando uplink en $USB_IFACE..."
if ! ip link show "$USB_IFACE" &>/dev/null; then
  echo "[!] No existe $USB_IFACE. Activa el tethering USB del celular antes de continuar."
  exit 1
fi

echo "[*] Deteniendo contenedor Docker pg_proxy si está usando el puerto 80..."
sudo docker stop pg_proxy 2>/dev/null || true

echo "[*] Sacando $WIFI_IFACE de NetworkManager..."
sudo nmcli device set "$WIFI_IFACE" managed no 2>/dev/null || true
sudo nmcli device disconnect "$WIFI_IFACE" 2>/dev/null || true
sudo rfkill unblock wifi

echo "[*] Configurando IP en $WIFI_IFACE..."
sudo ip addr flush dev "$WIFI_IFACE"
sudo ip addr add "$WIFI_IP" dev "$WIFI_IFACE"
sudo ip link set "$WIFI_IFACE" up

echo "[*] Habilitando IP forwarding..."
sudo sysctl -w net.ipv4.ip_forward=1

echo "[*] Cargando reglas nftables..."
sudo nft -f /etc/nftables-portal.nft
sudo nft flush set ip portal_nat allowed_ip 2>/dev/null || true

echo "[*] Iniciando FreeRADIUS..."
sudo systemctl restart freeradius

echo "[*] Iniciando hostapd (AP WiFi)..."
sudo pkill hostapd 2>/dev/null || true
sleep 1
sudo hostapd -B /etc/hostapd/hostapd.conf

echo "[*] Iniciando dnsmasq (DHCP/DNS)..."
sudo systemctl stop dnsmasq 2>/dev/null || true
sudo pkill dnsmasq 2>/dev/null || true
sleep 1
sudo dnsmasq -C /etc/dnsmasq.conf

echo ""
echo "[✓] Portal listo. Ahora ejecuta el portal Flask en primer plano:"
echo "    sudo RADIUS_SECRET="TU_SECRET" python3 ~/portal-cautivo/portal/portal.py"
echo ""
echo "SSID: Naruto-WiFi (abierto)"
echo "Gateway del cliente: 10.10.0.1"
