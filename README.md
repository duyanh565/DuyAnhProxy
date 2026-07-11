# 🔬 Đồ Án Khoa Học – mitmproxy File Replacer

Proxy server dùng **mitmproxy** để thay file trong game Free Fire / Free Fire Max.

---

## 📱 Hướng dẫn cài đặt trên iPhone

> Trang web proxy (Railway) hiển thị đầy đủ IP, port và nút tải cert.
> Mở Safari trên iPhone → vào `https://<cert_host>/`

### Bước 1 — Cài Certificate (fix lỗi "Không thể truy xuất cấu hình")

1. Tải **mitmproxy.mobileconfig** từ trang web
2. **Cài đặt → Thông báo đã tải hồ sơ → Cài đặt** → nhập PIN → Cài đặt → Xong
3. **Cài đặt → Cài đặt chung → Giới thiệu → Cài đặt tin cậy chứng chỉ**
   → Bật toggle cạnh **mitmproxy CA Cert**

> ⚠️ Bước 3 bắt buộc — thiếu bước này game vẫn báo lỗi SSL.

### Bước 2 — Cài proxy vào WiFi

1. **Cài đặt → WiFi → tên mạng → ⓘ**
2. Cuộn xuống → **Cấu hình Proxy → Thủ công**
3. Nhập:
   - **Máy chủ:** `<proxy_host từ config.yaml>`
   - **Cổng:** `<external_port từ config.yaml>`
4. Bấm **Lưu** → mở game ✅

---

## 🚀 Deploy lên Railway

### Bước 1 — Push lên GitHub
```bash
git init && git add . && git commit -m "init"
git remote add origin https://github.com/USER/REPO.git
git push -u origin main
```

### Bước 2 — Tạo project Railway
[railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**

### Bước 3 — Thêm TCP Proxy
Settings → Networking → **Add TCP Proxy** → Port nội bộ: `3636`

Railway sẽ cấp hostname + port, ví dụ:
- Host: `hayabusa.proxy.rlwy.net`
- Port: `56020`

### Bước 4 — Cập nhật `config.yaml`
```yaml
port: 3636
cert_host: "ten-service.up.railway.app"
proxy_host: "hayabusa.proxy.rlwy.net"
external_port: 56020
```

Push lại → Railway tự redeploy.

---

## 📁 Cấu trúc thư mục

```
├── addon.py          # mitmproxy addon — xử lý thay file
├── cert_http.py      # HTTP server — trang hướng dẫn + tải cert
├── config.yaml       # Cấu hình chính
├── run.py            # Entry point
├── replacements/     # Đặt file thay thế vào đây
├── certs/            # CA cert cố định của mitmproxy
└── requirements.txt
```

---

## 📝 Thêm rule thay file

```yaml
# config.yaml
rules:
  - match: "tên_file_cần_bắt"
    replace_with: "tên_file_trong_replacements"
    app: "Tên app"
```

Đặt file thay vào `replacements/` → push → Railway tự deploy lại.

---

## 🔄 Sơ đồ hoạt động

```
iPhone (WiFi proxy thủ công)
  └─ TCP → Railway TCP Proxy :56020
               └─ Forward → mitmproxy :3636
                               ├─ Khớp rule → trả file từ replacements/
                               └─ Không khớp → chuyển tiếp bình thường

Safari trên iPhone → https://<cert_host>/
  ├─ /                       → Trang hướng dẫn (hiện IP, port, nút tải cert)
  ├─ /mitmproxy.mobileconfig → Chỉ cài CA cert (fix lỗi SSL)
  ├─ /cert.cer               → Cert dự phòng iOS
  └─ /health                 → Railway health-check
```
