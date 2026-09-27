# Zona Orsay LAN URL Server v0.5.3
# Python 3, standard library only.
# Automatically selects the home LAN IPv4 address and ignores VPN-style addresses.

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import socket
import os
import json
import ipaddress
import subprocess
import re

HOST = "0.0.0.0"
PORT = 8765
current_url = ""

# If your home network is always 192.168.88.0/24, this gets highest priority.
# It can be overridden without editing the file:
#   Windows: set ZONA_LAN_PREFIX=192.168.88.
#   Linux:   export ZONA_LAN_PREFIX=192.168.88.
LAN_PREFIX = os.environ.get("ZONA_LAN_PREFIX", "192.168.88.")

HTML = r'''<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zona Orsay - Send URL to TV</title>
<style>
body{font-family:Arial,sans-serif;max-width:760px;margin:30px auto;padding:0 16px;background:#17171d;color:#eee}
h1{font-size:24px} input{width:100%;box-sizing:border-box;padding:14px;font-size:16px;border-radius:8px;border:1px solid #555;background:#25252d;color:#fff}
button{margin-top:12px;padding:13px 20px;font-size:17px;border:0;border-radius:8px;cursor:pointer}
#msg{margin-top:18px;padding:12px;background:#25252d;border-radius:8px;word-break:break-all}
small{color:#aaa}.box{background:#202027;padding:18px;border-radius:12px;margin-top:16px}
</style></head><body>
<h1>Zona Orsay — отправить URL на TV</h1>
<div class="box">
<form method="POST" action="/set">
<input name="url" id="url" placeholder="https://example.com/video.mp4" autocomplete="off">
<button type="submit">SEND TO TV</button>
</form>
<p><small>Вставь прямую ссылку на MP4/M3U8. Телевизор проверяет сервер каждые 2 секунды.</small></p>
<div id="msg">Текущий URL: CURRENT</div>
</div>
</body></html>'''


def _is_private_ipv4(ip):
    try:
        addr = ipaddress.ip_address(ip)
        return addr.version == 4 and addr.is_private and not addr.is_loopback and not addr.is_link_local
    except ValueError:
        return False


def _get_hostname_ips():
    result = []
    try:
        hn = socket.gethostname()
        for info in socket.getaddrinfo(hn, None, socket.AF_INET):
            ip = info[4][0]
            if _is_private_ipv4(ip) and ip not in result:
                result.append(ip)
    except Exception:
        pass
    return result


def _get_ipconfig_ips():
    """Get IPv4 addresses on Windows without requiring third-party modules."""
    result = []
    try:
        if os.name != "nt":
            return result
        out = subprocess.check_output(["ipconfig"], stderr=subprocess.DEVNULL,
                                      text=True, encoding="mbcs", errors="ignore")
        for line in out.splitlines():
            # Windows can display this as "IPv4 Address" or localized
            # equivalents such as "IPv4-адрес". Only inspect lines that
            # identify an IPv4 address, so gateway/DNS addresses are ignored.
            if "IPv4" not in line and "ipv4" not in line:
                continue
            for match in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line):
                if _is_private_ipv4(match) and match not in result:
                    result.append(match)
    except Exception:
        pass
    return result


def _get_route_ip():
    """Ask the OS which source address it would use for an Internet route."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if _is_private_ipv4(ip):
            return ip
    except Exception:
        pass
    return None


def local_ips():
    """Return local IPv4s in preference order, with home LAN first and VPN last."""
    candidates = []
    for ip in _get_ipconfig_ips() + _get_hostname_ips():
        if ip not in candidates:
            candidates.append(ip)
    route_ip = _get_route_ip()
    if route_ip and route_ip not in candidates:
        candidates.append(route_ip)

    def score(ip):
        # Highest priority: user's home LAN 192.168.88.x.
        if LAN_PREFIX and ip.startswith(LAN_PREFIX):
            return 0
        # Other common home LANs.
        if ip.startswith("192.168."):
            return 10
        # 10/8 and 172.16/12 are common LANs, but also frequently used by VPNs.
        if ip.startswith("10."):
            return 30
        try:
            second = int(ip.split(".")[1])
            if ip.startswith("172.") and 16 <= second <= 31:
                return 40
        except Exception:
            pass
        return 100

    candidates.sort(key=score)
    return candidates


def preferred_lan_ip():
    ips = local_ips()
    return ips[0] if ips else None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.address_string(), fmt % args))

    def _send_headers(self, content_type="text/plain; charset=utf-8"):
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")

    def do_GET(self):
        global current_url
        p = urlparse(self.path)
        if p.path == "/api/ping":
            self.send_response(200); self._send_headers("application/json; charset=utf-8"); self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "service": "zona-orsay", "version": "0.5.3"}).encode("utf-8")); return
        if p.path == "/api/status":
            data = json.dumps({"url": current_url, "lan_ip": preferred_lan_ip()}, ensure_ascii=False)
            self.send_response(200); self._send_headers("application/json; charset=utf-8"); self.end_headers()
            self.wfile.write(data.encode("utf-8")); return
        if p.path == "/api/url":
            data = current_url
            self.send_response(200); self._send_headers(); self.end_headers()
            self.wfile.write(data.encode("utf-8")); return
        if p.path == "/api/clear":
            current_url = ""
            self.send_response(200); self._send_headers(); self.end_headers()
            self.wfile.write(b"OK"); return
        if p.path == "/api/network":
            data = json.dumps({"lan_ip": preferred_lan_ip(), "all_private_ips": local_ips(), "port": PORT}, ensure_ascii=False)
            self.send_response(200); self._send_headers("application/json; charset=utf-8"); self.end_headers()
            self.wfile.write(data.encode("utf-8")); return
        if p.path == "/":
            body = HTML.replace("CURRENT", current_url.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            self.send_response(200); self._send_headers("text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(body.encode("utf-8")); return
        self.send_response(404); self._send_headers(); self.end_headers(); self.wfile.write(b"Not found")

    def do_POST(self):
        global current_url
        p = urlparse(self.path)
        if p.path not in ("/set", "/api/set", "/api/clear"):
            self.send_response(404); self._send_headers(); self.end_headers(); return

        if p.path == "/api/clear":
            current_url = ""
            self.send_response(200); self._send_headers(); self.end_headers()
            self.wfile.write(b"OK"); return

        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n).decode("utf-8", "replace")
        form = parse_qs(body)
        current_url = form.get("url", [""])[0].strip()
        if p.path == "/api/set":
            self.send_response(200); self._send_headers(); self.end_headers()
            self.wfile.write(b"OK"); return
        self.send_response(303); self.send_header("Location", "/"); self.end_headers()


if __name__ == "__main__":
    lan_ip = preferred_lan_ip()
    print("=" * 58)
    print(" Zona Orsay Telegram Server v0.5.3")
    print("=" * 58)
    if lan_ip:
        print("LAN IP     : %s" % lan_ip)
        print("TV API     : http://%s:%d/api/url" % (lan_ip, PORT))
        print("LAN WEB    : http://%s:%d/" % (lan_ip, PORT))
    else:
        print("LAN IP     : NOT FOUND")
        print("TV API     : http://<LAN-IP>:%d/api/url" % PORT)
    all_ips = local_ips()
    print("Local IPv4 : %s" % (", ".join(all_ips) if all_ips else "none"))
    print("LAN prefix : %s (highest priority)" % LAN_PREFIX)
    print("VPN note   : VPN/private IPs are lower priority than 192.168.88.x")
    print("Port       : %d" % PORT)
    print("=" * 58)

    try:
        from telegram_bot import start as start_telegram
        start_telegram()
    except Exception as e:
        print("[Telegram] failed to start:", e)

    # Listen on all interfaces so the service remains reachable even if Windows
    # changes interface metrics. The advertised TV address is the selected LAN IP.
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
