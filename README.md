# Portal Cautivo Naruto-WiFi

Portal cautivo funcional con autenticación **RADIUS (CHAP)** y accounting, publicado desde una laptop Ubuntu como punto de acceso WiFi real.


## Stack

- `hostapd` — Punto de acceso WiFi
- `dnsmasq` — DHCP y DNS
- `nftables` — NAT e intercept de tráfico HTTP no autenticado
- `FreeRADIUS 3.2` — Servidor AAA
- `Flask + pyrad` — Portal web e integración con RADIUS

## Arquitectura

```
[Celular cliente] --WiFi--> [wlp2s0: 10.10.0.1] --NAT--> [usb0: uplink] --> Internet
                                    |
                                    +-- hostapd
                                    +-- dnsmasq
                                    +-- nftables
                                    +-- FreeRADIUS
                                    +-- Flask portal
```

- Red del AP: `10.10.0.0/24`
- Gateway: `10.10.0.1`
- Uplink: tethering USB (`usb0`)

## Requisitos

- Ubuntu 24.04
- Tarjeta WiFi con soporte de modo AP (`iw list` debe mostrar `* AP`)
- Celular Android/iPhone para uplink por tethering USB
- Uno o más celulares como clientes de prueba

## Instalación

```bash
sudo apt update
sudo apt install -y hostapd dnsmasq nftables freeradius freeradius-utils \
    python3-flask python3-pyrad iw tcpdump
```

## Configuración

Copiar los archivos de configuración:

```bash
sudo cp configs/hostapd.conf         /etc/hostapd/hostapd.conf
sudo cp configs/dnsmasq.conf         /etc/dnsmasq.conf
sudo cp configs/nftables-portal.nft  /etc/nftables-portal.nft
sudo cp configs/freeradius-users.example /etc/freeradius/3.0/mods-config/files/authorize
```

Editar `/etc/freeradius/3.0/clients.conf` en los bloques `client localhost` y `client localhost_ipv6`:

```
secret = TU_SECRET_AQUI
require_message_authenticator = no
```

Reiniciar FreeRADIUS:

```bash
sudo systemctl restart freeradius
```

## Uso

Levantar toda la infraestructura del portal:

```bash
sudo bash scripts/iniciar-portal.sh
```

Correr el portal Flask (en primer plano):

```bash
sudo RADIUS_SECRET="TU_SECRET_AQUI" python3 portal/portal.py
```

Detener todo y restaurar el sistema:

```bash
sudo bash scripts/detener-portal.sh
```

## Roles disponibles

El portal reconoce 4 roles diferenciados. Cada uno recibe una landing y un
tiempo de sesión distinto.

| Rol         | Timeout de sesión | Landing                                      |
|-------------|-------------------|----------------------------------------------|
| invitado    | 30 min            | Tips de seguridad para WiFi pública          |
| estudiante  | 1 h               | Micro-quiz de la clase                       |
| docente     | 2 h               | Enlaces a recursos académicos simulados      |
| staff       | 4 h               | Panel administrativo simulado                |

Las credenciales de prueba están definidas en el archivo de usuarios de
FreeRADIUS (`configs/freeradius-users.example`).

## Flujo end-to-end

1. Cliente conecta al SSID `Naruto-WiFi` (red abierta).
2. Recibe IP `10.10.0.X` por DHCP.
3. Android/iOS hace su prueba HTTP de conectividad → nftables la redirige al portal.
4. Cliente ve el login del portal.
5. Ingresa credenciales → portal envía Access-Request (CHAP) a FreeRADIUS.
6. FreeRADIUS responde `Access-Accept` con `Reply-Message` (rol) y `Session-Timeout`.
7. Portal agrega la IP del cliente al set `allowed_ip` de nftables → ya tiene Internet.
8. Portal envía `Accounting-Start` a FreeRADIUS.
9. Al expirar el `Session-Timeout` → portal quita la IP y envía `Accounting-Stop`.


## Seguridad

- El SSID es abierto (WPA deshabilitado). La autenticación ocurre en capa 7 (portal).
- Los secrets RADIUS se manejan vía variable de entorno, nunca hardcoded.
- El AP debe usarse solo en entornos controlados de laboratorio.
- Los usuarios de prueba son ficticios.

## Autor

**Roberto Ramírez** — 7690-22-12700