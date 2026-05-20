# Shopee Top 10 Product Analyzer

Ứng dụng tinh gọn giúp tìm kiếm, phân tích và xếp hạng **Top 10 sản phẩm Shopee tốt nhất** theo thời gian thực. Hệ thống tự động thu thập dữ liệu sản phẩm, xếp hạng bằng mô hình **Gemini AI**, tích hợp sẵn **Rate Limiting (IP)** và lưu trữ đệm **SQLite Cache**.

🌐 **Trải nghiệm trực tuyến tại:** [https://shopeescraper.streamlit.app/](https://shopeescraper.streamlit.app/)

Ứng dụng được thiết kế theo cấu trúc nguyên khối phân tầng (Monolith), cho phép deploy trực tiếp và chạy độc lập chỉ với 1 lệnh duy nhất (thích hợp hoàn hảo cho **Streamlit Community Cloud**).

---

## 🚀 Tính Năng Chính

1. **Giao diện tối giản**: Ô tìm kiếm trung tâm tập trung vào trải nghiệm người dùng, lược bỏ các cấu hình rườm rà.
2. **Xếp hạng thông minh**: Sử dụng **Gemini 3.1 Flash Lite** (Structured Output) để đánh giá và đưa ra lý do lựa chọn sản phẩm khách quan.
3. **Bộ đệm thông minh (Cache SQLite)**: Tự động lưu trữ kết quả trong 1 giờ giúp phản hồi ngay lập tức cho các truy vấn trùng lặp và tiết kiệm chi phí gọi API.
4. **Hạn chế spam (Rate Limiting)**: Giới hạn tần suất tối đa 5 lượt tìm kiếm/phút cho mỗi IP client để bảo vệ tài nguyên API.
5. **Hỗ trợ đa thị trường**: VN, BR, SG, MY, ID, PH, TH.

---

## ⚙️ Cài Đặt & Khởi Chạy Local

### 1. Cài đặt thư viện
Đồng bộ môi trường ảo và cài đặt thư viện phụ thuộc bằng **`uv`**:
```bash
uv sync
```

### 2. Cấu hình biến môi trường
Tạo file `.env` ở thư mục gốc của dự án:
```env
APIFY_API_TOKEN=your_apify_api_token
GEMINI_API_KEY=your_gemini_api_key
```
> 💡 *Nếu chưa cấu hình `GEMINI_API_KEY`, ứng dụng sẽ tự động chuyển sang chế độ giả lập (Mock Analyzer) để chạy thử nghiệm offline.*

### 3. Chạy Dashboard
Chỉ cần chạy lệnh sau để mở Dashboard Streamlit:
```bash
uv run streamlit run frontend/app.py --server.port 8501
```
*(Giao diện hiển thị tại: `http://localhost:8501`)*

*(Lưu ý: Bạn cũng có thể khởi chạy server FastAPI độc lập qua `uv run uvicorn backend.main:app` nếu muốn đóng gói API để sử dụng cho các ứng dụng khác).*

---

## 🌐 Hướng Dẫn Deploy Lên Streamlit Cloud

1. Đẩy mã nguồn của bạn lên một repository **GitHub** (file `.env` đã được tự động bỏ qua nhờ `.gitignore`).
2. Truy cập [Streamlit Community Cloud](https://share.streamlit.io/) và tạo một app mới trỏ tới repo GitHub của bạn.
3. Đi vào **App Settings** -> **Secrets** trên Dashboard của Streamlit Cloud và dán cấu hình TOML:
   ```toml
   APIFY_API_TOKEN = "token_apify_của_bạn"
   GEMINI_API_KEY = "khóa_api_gemini_của_bạn"
   ```
4. Nhấn **Save** và hệ thống sẽ tự động khởi chạy và chạy độc lập một cách an toàn mà không bị lộ API keys.

---

## 📁 Cấu Trúc Thư Mục

```text
shopee-search-tool/
├── backend/
│   ├── scraper.py            # Thu thập dữ liệu Shopee qua Apify
│   ├── scorer.py             # Lọc thô & chấm điểm chất lượng sơ bộ
│   ├── ai_ranker.py          # Gọi Gemini API xếp hạng & phân tích
│   ├── database.py           # Quản lý SQLite cache cục bộ
│   └── main.py               # (Tùy chọn) FastAPI Server độc lập
├── frontend/
│   └── app.py                # Giao diện Streamlit Dashboard & Rate Limiter
├── pyproject.toml            # Khai báo dependencies dự án
└── README.md                 # Hướng dẫn này
```
