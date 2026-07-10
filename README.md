# 🔬 Đồ Án Khoa Học – mitmproxy File Replacer

Proxy server dùng **mitmproxy** để tự động thay thế file trong ứng dụng di động (iOS/Android) khi thiết bị kết nối qua proxy.

---

## 📁 Cấu trúc thư mục

```
proxy-project/
├── addon.py          # Script mitmproxy chính (xử lý thay file)
├── cert_http.py      # HTTP server phục vụ trang tải cert & cấu hình proxy
├── config.yaml       # Danh sách rule: file nào thay bằng file nào
├── replacements/     # Thư mục chứa các file thay thế
│   └── (đặt file thay thế vào đây)
├── certs/            # Chứng chỉ CA cố định của mitmproxy
├── requirements.txt  # Python dependencies
├── railway.toml      # Cấu hình Railway deployment
├── start.sh          # Script khởi động
└── README.md
```

---

## ⚙️ Cài đặt và chạy local

### Yêu cầu
- Python 3.11+
- pip

### Cài đặt

```bash
pip install -r requirements.txt
```

### Chạy proxy

```bash
bash start.sh
# hoặc chạy trực tiếp:
python3 run.py
```

Proxy sẽ lắng nghe tại `0.0.0.0:3636` (theo `config.yaml`).

---

## 📱 Cấu hình iOS — Cách nhanh nhất (1 file duy nhất)

Sau khi deploy lên Railway, mở **Safari** trên iPhone và truy cập:

```
https://<domain-railway>/
```

### ⭐ Cài đặt nhanh — chỉ cần 1 file

1. Bấm **"Tải mitmproxy.mobileconfig"**
2. Bấm **Cho phép** → vào **Cài đặt → VPN và Quản lý thiết bị → mitmproxy → Cài đặt**
3. Vào **Cài đặt → Cài đặt chung → Giới thiệu → Tin cậy chứng chỉ** → bật **mitmproxy**

> File `.mobileconfig` gộp luôn **Certificate mitmproxy CA** và **cấu hình Proxy** — không cần làm riêng từng bước, không cần nhập tay IP và port.  
> Bước 3 (Tin cậy chứng chỉ) là bắt buộc do chính sách bảo mật của iOS — không thể bỏ qua.

### Cài riêng từng bước (dự phòng)

Nếu file `.mobileconfig` không hoạt động:

1. Tải **Certificate (.cer)** → cài và tin cậy theo hướng dẫn trên trang
2. Vào **Cài đặt → WiFi → [Tên mạng] → Cấu hình Proxy → Thủ công**  
   Máy chủ: `<host Railway TCP>` · Cổng: `<port Railway TCP>`

---

## 📝 Thêm file thay thế

### Bước 1 – Đặt file vào thư mục `replacements/`

```
replacements/
├── cache_res.CfnFf59sr1SbsqQ6JqTKsEusjKs~3D
└── assetindexer.H5ak1JM1Eck~2FxRcJrEp~2FMzeuqmY~3D
```

### Bước 2 – Kiểm tra `config.yaml`

File `config.yaml` đã có sẵn rule cho 2 file này:

```yaml
rules:
  - match: "cache_res.CfnFf59sr1SbsqQ6JqTKsEusjKs~3D"
    replace_with: "cache_res.CfnFf59sr1SbsqQ6JqTKsEusjKs~3D"

  - match: "assetindexer.H5ak1JM1Eck~2FxRcJrEp~2FMzeuqmY~3D"
    replace_with: "assetindexer.H5ak1JM1Eck~2FxRcJrEp~2FMzeuqmY~3D"
```

---

## 🚀 Deploy lên Railway

### Bước 1 – Push lên GitHub

```bash
git init
git add .
git commit -m "Initial commit - mitmproxy file replacer"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Bước 2 – Tạo project trên Railway

1. Vào [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
2. Chọn repo vừa push.
3. Railway sẽ tự build và deploy.

### Bước 3 – Lấy IP và cổng từ Railway TCP Proxy

Để iPhone nhập đúng dạng **IP : cổng**, bạn cần bật **TCP Proxy** trên Railway:

1. Vào project Railway → chọn service → tab **Settings**.
2. Kéo xuống mục **Networking** → nhấn **Add TCP Proxy**.
3. Nhập **Port nội bộ**: `3636` → nhấn **Create**.
4. Railway sẽ cấp cho bạn một địa chỉ dạng:
   ```
   Host: containers.railway.app
   Port: 56020   ← số cổng ngẫu nhiên, cố định sau khi tạo
   ```
5. Cập nhật `cert_host` trong `config.yaml` với host Railway TCP này.

### Bước 4 – Cập nhật `config.yaml`

```yaml
port: 3636              # port nội bộ mitmproxy
cert_host: "containers.railway.app"   # host Railway TCP (để hiển thị trên trang web)
```

Push lại lên GitHub → Railway tự động redeploy.

### Bước 5 – Cấu hình iOS

Mở trình duyệt trên iPhone → truy cập **https://\<domain-HTTP-Railway\>/** và làm theo hướng dẫn 2 bước.

Nếu muốn cài tay:

| Trường  | Giá trị                          |
|---------|----------------------------------|
| Chế độ  | Thủ công                         |
| Server  | `containers.railway.app` (host Railway TCP) |
| Cổng    | `56020` (cổng Railway TCP cấp)   |

---

## 🔄 Cách hoạt động

```
iPhone
  │  (HTTP/HTTPS request đến game server)
  ▼
Railway TCP Proxy (port 56020)
  │
  ▼
mitmproxy (port 3636 nội bộ)
  │  Kiểm tra tên file trong URL có khớp rule trong config.yaml?
  ├─ Có → Thay body response bằng file trong replacements/
  └─ Không → Chuyển tiếp response gốc
  │
  ▼
iPhone nhận response (đã bị thay file nếu khớp)
```

Ngoài ra, Railway còn chạy một **HTTP server** (`cert_http.py`) trên `$PORT`:

```
iPhone (Safari)
  │  https://<domain-railway>/
  ▼
cert_http.py
  ├─ /            → Trang hướng dẫn cài đặt
  ├─ /cert.cer    → Tải Certificate iOS
  ├─ /cert.pem    → Tải Certificate Android/PC
  ├─ /proxy.mobileconfig → Tải cấu hình proxy tự động (iOS)
  └─ /health      → Railway health-check
```

---

## 🛠 Chạy thủ công (không dùng run.py)

```bash
# BUG FIX: flag đúng cho mitmproxy 10.x là --set ssl_insecure=true
mitmdump \
  --listen-host 0.0.0.0 \
  --listen-port 3636 \
  -s addon.py \
  --set block_global=false \
  --set ssl_insecure=true
```

---

## ⚠️ Lưu ý

- Chỉ hoạt động với HTTPS sau khi cài và tin cậy chứng chỉ mitmproxy trên thiết bị.
- File thay thế phải có đúng format mà ứng dụng mong đợi.
- Dùng cho mục đích nghiên cứu và học tập.
