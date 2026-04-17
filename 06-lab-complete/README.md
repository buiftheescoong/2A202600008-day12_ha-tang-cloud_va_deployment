# Smart Travel Assistant - Production AI Agent

Hệ thống AI Agent hỗ trợ du lịch thông minh được thiết kế theo tiêu chuẩn Production, hỗ trợ lưu trữ trạng thái (Stateful), giới hạn lưu lượng (Rate Limiting), và quản lý ngân sách (Cost Guard).

## 🚀 Tính năng chính
- **AI Orchestration**: Sử dụng LangGraph để xây dựng luồng xử lý Agent phức tạp.
- **Persistence**: Lưu trữ lịch sử hội thoại vào Redis Stack (Stateless API).
- **Security**: Xác thực bằng API Key qua Header `X-API-Key`.
- **Reliability**: Hỗ trợ Health Check, Ready Check và Graceful Shutdown.
- **Scaling**: Sẵn sàng triển khai trên Docker và Cloud (Railway/Render).

---

## 🛠️ Yêu cầu hệ thống
- Python 3.10+
- Docker & Docker Compose
- Redis Stack (nếu chạy local mà không dùng Docker)

---

## 💻 Cài đặt Local (Development)

### 1. Chuẩn bị môi trường
```bash
# Tạo môi trường ảo
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Cài đặt thư viện
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường
Sao chép file mẫu và điền các API Key của bạn:
```bash
cp .env.example .env
```
*Lưu ý: Đảm bảo điền ít nhất `GEMINI_API_KEY` và `AGENT_API_KEY`.*

### 3. Chạy ứng dụng
```bash
uvicorn app.main:app --reload --port 8000
```

---

## 🐳 Triển khai với Docker Compose

Đây là cách tốt nhất để giả lập môi trường Production (bao gồm cả Agent, Redis và Nginx Load Balancer).

```bash
# Build và khởi chạy 3 instance của Agent
docker-compose up --build --scale agent=3
```

---

## ☁️ Triển khai lên Railway

1. Di chuyển ra thư mục gốc (Root): `cd ..`
2. Cài đặt Railway CLI: `npm i -g @railway/cli`
3. Đăng nhập: `railway login`
4. Liên kết dự án: `railway link`
5. Deploy: `railway up`

---

## 🧪 Kiểm tra hệ thống (Testing)

Bạn có thể sử dụng script tự động chấm điểm để kiểm tra toàn bộ tiêu chí:
```bash
python grade.py . "https://smartagent-production-2cdd.up.railway.app" "lab-secret-key-123"
```

Hoặc dùng `curl`:
```bash
# Kiểm tra sức khỏe
curl http://localhost:8000/health

# Gửi câu hỏi (kèm Auth)
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: lab-secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Suggest a trip to Japan", "session_id": "user_1"}'
```

```text
. (Project Root)
├── railway.toml            # Cấu hình Railway (Deploy từ đây)
├── MISSION_ANSWERS.md      # Bài làm lý thuyết & Screenshot
├── DEPLOYMENT.md           # Thông tin Public URL & Test thực tế
└── 06-lab-complete/        # Thư mục bài làm chính
    ├── app/                # Mã nguồn Python (Agent, API, Logic)
    ├── Dockerfile          # Container config
    ├── docker-compose.yml  # Local infrastructure config
    ├── requirements.txt    # Danh sách thư viện
    └── README.md           # Hướng dẫn này
```
