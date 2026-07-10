"""
TCP router — lắng nghe port 8080 (Railway expose):
  • Request trực tiếp (GET /, GET /cert.cer, ...)  → phục vụ trang tải cert
  • Request proxy  (CONNECT / GET http://...)       → chuyển sang mitmproxy:8081
"""

import asyncio
import os

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding

MITM_HOST = "127.0.0.1"
MITM_PORT = 8081          # mitmproxy lắng nghe nội bộ
CERT_PEM   = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem")

# ── helpers ──────────────────────────────────────────────────────────────────

def _pem_to_der() -> bytes:
    with open(CERT_PEM, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    return cert.public_bytes(Encoding.DER)


def _http_response(status: int, reason: str, content_type: str,
                   body: bytes, extra_headers: dict | None = None) -> bytes:
    headers = [
        f"HTTP/1.1 {status} {reason}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body)}",
        "Connection: close",
    ]
    if extra_headers:
        for k, v in extra_headers.items():
            headers.append(f"{k}: {v}")
    return "\r\n".join(headers).encode() + b"\r\n\r\n" + body


# ── cert page HTML ────────────────────────────────────────────────────────────

def _cert_html(cert_host: str, proxy_port: int) -> bytes:
    url = f"http://{cert_host}:{proxy_port}"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tải Certificate</title>
<style>
body{{font-family:-apple-system,sans-serif;padding:24px;max-width:480px;margin:auto;background:#f2f2f7}}
h2{{color:#1c1c1e;font-size:20px}}
a.btn{{display:block;padding:16px;margin:12px 0;border-radius:14px;
text-decoration:none;color:#fff;font-size:17px;font-weight:600;text-align:center}}
.green{{background:#34c759}}.blue{{background:#007aff}}
.card{{background:#fff;border-radius:14px;padding:16px;margin:16px 0}}
p,li{{color:#3a3a3c;font-size:14px;line-height:1.8}}
code{{background:#e5e5ea;padding:2px 6px;border-radius:6px;font-size:13px}}
</style></head>
<body>
<h2>✅ Proxy đang chạy</h2>
<div class="card">
  <a href="{url}/cert.cer" class="btn green">📥 Tải Certificate (.cer) — iOS</a>
  <a href="{url}/cert.pem" class="btn blue">Tải Certificate (.pem)</a>
</div>
<div class="card">
  <p><b>Cách cài trên iPhone:</b></p>
  <ol>
    <li>Bấm <b>Tải Certificate (.cer)</b> → bấm <b>Cho phép</b></li>
    <li><b>Cài đặt</b> → <b>VPN và Quản lý thiết bị</b> → bấm <b>mitmproxy</b> → <b>Cài đặt</b></li>
    <li><b>Cài đặt</b> → <b>Cài đặt chung</b> → <b>Giới thiệu</b> → <b>Tin cậy chứng chỉ</b> → bật <b>mitmproxy</b></li>
  </ol>
  <p><b>Sau đó cài proxy WiFi:</b><br>
  Máy chủ: <code>{cert_host}</code><br>
  Cổng: <code>{proxy_port}</code></p>
</div>
</body></html>"""
    return html.encode("utf-8")


# ── pipe helper ───────────────────────────────────────────────────────────────

async def _pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
    try:
        while True:
            chunk = await src.read(65536)
            if not chunk:
                break
            dst.write(chunk)
            await dst.drain()
    except Exception:
        pass
    finally:
        try:
            dst.close()
        except Exception:
            pass


# ── direct-request handler (cert page) ───────────────────────────────────────

async def _serve_direct(first_line: bytes, reader: asyncio.StreamReader,
                        writer: asyncio.StreamWriter,
                        cert_host: str, proxy_port: int):
    # Đọc hết headers (bỏ body vì GET không có body)
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break

    # Parse path từ request line  (ví dụ: GET /cert.cer HTTP/1.1)
    try:
        path = first_line.decode("utf-8", errors="replace").split(" ")[1]
        path = path.split("?")[0]
    except (IndexError, ValueError):
        path = "/"

    if path in ("/", "/index.html"):
        body = _cert_html(cert_host, proxy_port)
        resp = _http_response(200, "OK", "text/html; charset=utf-8", body)

    elif path == "/cert.pem":
        if os.path.exists(CERT_PEM):
            with open(CERT_PEM, "rb") as f:
                body = f.read()
            resp = _http_response(200, "OK", "application/x-pem-file", body,
                                  {"Content-Disposition": "attachment; filename=mitmproxy-ca.pem"})
        else:
            resp = _http_response(503, "Service Unavailable", "text/plain",
                                  b"Cert chua san sang, thu lai sau 10 giay")

    elif path == "/cert.cer":
        if os.path.exists(CERT_PEM):
            try:
                body = _pem_to_der()
                resp = _http_response(200, "OK", "application/pkix-cert", body,
                                      {"Content-Disposition": "attachment; filename=mitmproxy-ca.cer"})
            except Exception as e:
                resp = _http_response(500, "Internal Server Error", "text/plain",
                                      f"Loi: {e}".encode())
        else:
            resp = _http_response(503, "Service Unavailable", "text/plain",
                                  b"Cert chua san sang, thu lai sau 10 giay")

    else:
        resp = _http_response(404, "Not Found", "text/plain", b"Not found")

    try:
        writer.write(resp)
        await writer.drain()
    finally:
        writer.close()


# ── forward to mitmproxy ──────────────────────────────────────────────────────

async def _forward_to_mitm(first_line: bytes, reader: asyncio.StreamReader,
                            writer: asyncio.StreamWriter):
    try:
        mitm_r, mitm_w = await asyncio.open_connection(MITM_HOST, MITM_PORT)
    except Exception as e:
        print(f"[router] Không kết nối được mitmproxy: {e}")
        writer.close()
        return

    # Gửi lại dòng đầu tiên đã đọc trước đó
    mitm_w.write(first_line)
    await mitm_w.drain()

    # Pipe hai chiều song song
    await asyncio.gather(
        _pipe(reader, mitm_w),
        _pipe(mitm_r, writer),
    )


# ── main handler ──────────────────────────────────────────────────────────────

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                        cert_host: str, proxy_port: int):
    try:
        first_line = await asyncio.wait_for(reader.readline(), timeout=10)
    except (asyncio.TimeoutError, Exception):
        writer.close()
        return

    if not first_line:
        writer.close()
        return

    line_str = first_line.decode("utf-8", errors="replace").strip()
    parts    = line_str.split(" ")
    method   = parts[0].upper() if parts else ""
    uri      = parts[1] if len(parts) >= 2 else ""

    # Proxy request: CONNECT hoặc URI tuyệt đối (http://... / https://...)
    is_proxy = method == "CONNECT" or uri.startswith("http://") or uri.startswith("https://")

    if is_proxy:
        await _forward_to_mitm(first_line, reader, writer)
    else:
        await _serve_direct(first_line, reader, writer, cert_host, proxy_port)


# ── start ─────────────────────────────────────────────────────────────────────

async def start_router(host: str, port: int, cert_host: str, proxy_port: int):
    def client_connected(reader, writer):
        asyncio.create_task(handle_client(reader, writer, cert_host, proxy_port))

    server = await asyncio.start_server(client_connected, host, port)
    print(f"[router] Lắng nghe {host}:{port}")
    print(f"[router] Tải cert: http://{cert_host}:{proxy_port}/")
    async with server:
        await server.serve_forever()
