# 🔬 Đồ Án Khoa Học – mitmproxy File Replacer

Proxy server dùng **mitmproxy** để tự động thay thế file trong ứng dụng di động (iOS/Android) khi thiết bị kết nối qua proxy.

---

## 📁 Cấu trúc thư mục

```
proxy-project/
├── addon.py          # Script mitmproxy chính (xử lý thay file)
├── config.yaml       # Danh sách rule: file nào thay bằng file nào
├── replacements/     # Thư mục chứa các file thay thế
│   └── (đặt file thay thế vào đây)
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
# hoặc
mitmdump --listen-host 0.0.0.0 --listen-port 8080 --scripts addon.py --set block_global=false --ssl-insecure
```

Proxy sẽ lắng nghe tại `0.0.0.0:8080`.

---

## 📱 Cấu hình iOS

1. **Kết nối WiFi** cùng mạng với proxy (hoặc dùng IP public của Railway).
2. Vào **Cài đặt → WiFi → [Tên mạng] → Cấu hình Proxy**:
   - Chế độ: **Thủ công**
   - Server: `IP hoặc domain Railway`
   - Port: `8080` (hoặc port Railway cấp)
3. Mở Safari và truy cập **http://mitm.it** → tải và cài chứng chỉ mitmproxy.
4. Vào **Cài đặt → Cài đặt chung → VPN và Quản lý thiết bị** → Tin cậy chứng chỉ mitmproxy.
5. Vào **Cài đặt → Cài đặt chung → Giới thiệu → Tin cậy chứng chỉ** → Bật mitmproxy.

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

Để iOS nhập đúng dạng **IP : cổng**, bạn cần bật **TCP Proxy** trên Railway:

1. Vào project Railway → chọn service → tab **Settings**.
2. Kéo xuống mục **Networking** → nhấn **Add TCP Proxy**.
3. Nhập **Port nội bộ**: `8080` → nhấn **Create**.
4. Railway sẽ cấp cho bạn một địa chỉ dạng:
   ```
   Host: containers.railway.app
   Port: 12345   ← số cổng ngẫu nhiên, cố định sau khi tạo
   ```
5. Dùng đúng `Host` và `Port` này để nhập vào iOS.

### Bước 4 – Cấu hình iOS

Vào **Cài đặt → WiFi → [Tên mạng WiFi] → Cấu hình Proxy**:

| Trường  | Giá trị                          |
|---------|----------------------------------|
| Chế độ  | Thủ công                         |
| Server  | `containers.railway.app` (host Railway TCP) |
| Cổng    | `12345` (cổng Railway TCP cấp)   |

---

## 🔄 Cách hoạt động

```
iOS Device
   │  (HTTP/HTTPS request đến game server)
   ▼
Railway (mitmproxy đang chạy)
   │  Kiểm tra tên file trong URL có khớp rule trong config.yaml?
   ├─ Có → Thay body response bằng file trong replacements/
   └─ Không → Chuyển tiếp response gốc
   │
   ▼
iOS Device nhận response (đã bị thay file nếu khớp)
```

---

## ⚠️ Lưu ý

- Chỉ hoạt động với HTTPS sau khi cài và tin cậy chứng chỉ mitmproxy trên thiết bị.
- File thay thế phải có đúng format mà ứng dụng mong đợi.
- Dùng cho mục đích nghiên cứu và học tập.
