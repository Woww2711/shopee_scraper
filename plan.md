# Shopee Top 10 Search Tool — Project Spec

## Mục tiêu
Tool nhận keyword từ người dùng, scrape Shopee qua Apify, dùng Gemini API để re-rank và trả về **Top 10 sản phẩm nổi bật nhất** kèm lý do chi tiết cho seller và tóm tắt thị trường.

**Target user:** Seller/reseller TMĐT cần nghiên cứu thị trường nhanh trước khi nhập hàng.

**"Nổi bật" = market opportunity signal** — không phải sản phẩm tốt nhất cho người mua, mà là sản phẩm có nhu cầu (demand) đã được xác thực, chất lượng ổn, giá cả nằm trong phân khúc đại chúng mà reseller có thể tham gia cạnh tranh.

---

## Tech Stack Đề Xuất (Tối Ưu Cho Interview & Production)

- **Backend: FastAPI (Python)**
  - RESTful API sạch, tự động sinh tài liệu Swagger UI (`/docs`) thuận tiện cho việc test và tích hợp.
  - Tách biệt logic xử lý dữ liệu (Apify, scoring, AI) khỏi giao diện hiển thị.
  - Hỗ trợ bất đồng bộ (async/await) giúp xử lý đồng thời tốt hơn.
- **Frontend: Streamlit**
  - Xây dựng giao diện phân tích dữ liệu chuyên nghiệp và trực quan cực nhanh bằng Python.
  - Hỗ trợ hiển thị bảng dữ liệu, biểu đồ so sánh giá/rating, hình ảnh sản phẩm và các metric nổi bật.
- **Scraper: Apify**
  - Sử dụng Actor Shopee Scraper để cào thông tin sản phẩm (chọn lọc theo thị trường VN, BR, SG,...).
- **AI Engine: Gemini API** (`gemini-2.5-flash` hoặc `gemini-1.5-flash`)
  - **Tối ưu chi phí:** Rẻ hơn Claude 3.5 Sonnet khoảng 40 lần, có free tier rất hào phóng phù hợp làm bài test.
  - **Structured Outputs:** Gemini hỗ trợ định nghĩa schema đầu ra bằng Pydantic hoặc JSON Schema. Điều này giúp đảm bảo 100% kết quả trả về đúng định dạng JSON để parse mà không lo LLM trả về thừa chữ hay sai cấu trúc.
  - **Tốc độ:** Latency cực thấp so với các dòng mô hình lớn khác.

---

## Data từ Apify

Apify trả về các fields sau:

```json
{
  "itemId": "string",
  "shopId": "string",
  "name": "string",
  "price": { "value": 135000, "formatted": "135.000 ₫" },
  "priceMax": { "value": 135000, "formatted": "135.000 ₫" },
  "rating": 4.89,
  "ratingCount": 8359,
  "shopName": "string",
  "brand": "string",
  "location": "string",
  "images": ["url1", "url2"],
  "url": "https://shopee.vn/..."
}
```

> ⚠️ `sold` (đã bán) và `stock` (kho hàng) thường bị Shopee ẩn.
> ✅ Dùng `ratingCount` làm proxy thay thế: lượng đánh giá phản ánh lượng giao dịch thực tế đã thành công và khách hàng đủ tương tác để nhận xét.

---

## Architecture & Flow (FastAPI + Streamlit)

```
┌────────────────┐      (HTTP POST /api/search)      ┌─────────────────┐
│                │ ────────────────────────────────> │                 │
│   Streamlit    │                                   │   FastAPI API   │
│   Frontend     │ <──────────────────────────────── │     Backend     │
└────────────────┘       (JSON: Top 10 + Insights)   └─────────────────┘
                                                              │
                                            ┌─────────────────┼─────────────────┐
                                            ▼                 ▼                 ▼
                                      ┌───────────┐     ┌───────────┐     ┌───────────┐
                                      │  SQLite   │     │   Apify   │     │  Gemini   │
                                      │   Cache   │     │  Scraper  │     │Structured │
                                      │ (TTL: 1h) │     │ (Shopee)  │     │  Output   │
                                      └───────────┘     └───────────┘     └───────────┘
```

1. **User** nhập keyword, chọn quốc gia và phân loại sort trên **Streamlit**.
2. Streamlit gửi request tới **FastAPI backend** endpoint `/api/search`.
3. FastAPI kiểm tra **SQLite cache**:
   - Nếu *Cache Hit* (dưới 1 giờ): Trả về ngay lập tức.
   - Nếu *Cache Miss*:
     - Gọi **Apify** lấy 40-60 sản phẩm.
     - **Python Scorer** thực hiện lọc thô (loại rating thấp, review quá ít) và chấm điểm sơ bộ.
     - Gửi danh sách đã lọc + prompt sang **Gemini API** sử dụng cơ chế **Structured Outputs** để chọn ra Top 10 và viết tóm tắt thị trường.
     - Lưu kết quả vào **SQLite cache**.
4. FastAPI trả về dữ liệu chuẩn JSON. Giao diện Streamlit render biểu đồ so sánh giá, danh sách dạng card kèm ảnh và lý do nổi bật của từng sản phẩm.

---

## Scoring Logic (Python — Lọc thô trước khi gọi AI)

```python
import math

def compute_score(item):
    rating = item.get("rating", 0) or 0
    review_count = item.get("ratingCount", 0) or 0
    price = item.get("price", {}).get("value", 0) or 0

    review_score = math.log1p(review_count)  # log scale tránh các shop quá khủng làm lệch hệ thống

    # Price score: Ưu tiên tầm giá dễ bán cho reseller (50k - 400k VND)
    if 50000 <= price <= 400000:
        price_score = 1.0
    elif price < 50000:
        price_score = 0.5   # biên lợi nhuận thấp, cạnh tranh khốc liệt
    else:
        price_score = 0.7   # phân khúc cao cấp, vốn lớn, khó scale nhanh

    return (
        rating * 0.35 +
        review_score * 0.45 +
        price_score * 0.20
    )
```

---

## Gemini API — Prompt & Structured Output

Sử dụng thư viện `google-genai` của Google để truyền cấu trúc Pydantic mong muốn.

### 1. Schema Định Nghĩa Bằng Pydantic
```python
from pydantic import BaseModel, Field
from typing import List

class TopProduct(BaseModel):
    itemId: str = Field(description="ID của sản phẩm")
    rank: int = Field(description="Thứ hạng từ 1 đến 10")
    reason: str = Field(description="Lý do ngắn gọn tại sao sản phẩm này nổi bật đối với seller (1 câu, tiếng Việt)")

class MarketAnalysis(BaseModel):
    top10: List[TopProduct] = Field(description="Danh sách top 10 sản phẩm nổi bật nhất")
    market_summary: str = Field(description="Tóm tắt thị trường: đối thủ thống trị, tầm giá phổ biến, cơ hội kinh doanh (2-3 câu, tiếng Việt)")
```

### 2. Prompt Thiết Lập
```python
SYSTEM_PROMPT = """
Bạn là một chuyên gia phân tích thị trường Thương mại điện tử (Shopee) dành cho các nhà bán hàng (seller/reseller).
Nhiệm vụ của bạn là nhận danh sách các sản phẩm đã được lọc thô từ kết quả tìm kiếm Shopee, chọn ra 10 sản phẩm nổi bật nhất đại diện cho cơ hội kinh doanh tốt nhất.

Tiêu chí lựa chọn:
1. Nhu cầu lớn (ratingCount cao chứng minh sản phẩm bán chạy).
2. Chất lượng tốt và ổn định (rating trung bình từ 4.5 trở lên).
3. Tầm giá phù hợp với reseller (ưu tiên 50k-400k VND để tối ưu xoay vòng vốn và biên lợi nhuận).
4. Shop hoặc Brand uy tín (tránh rủi ro về nguồn hàng giả/kém chất lượng).
"""
```

---

## Cấu Trúc Thư Mục Dự Án (Project Structure)

```
shopee-search-tool/
├── backend/
│   ├── main.py               # FastAPI app (Endpoints: /api/search, /health)
│   ├── scraper.py            # Tích hợp Apify Client cào dữ liệu Shopee
│   ├── scorer.py             # Lọc cứng + Chấm điểm thuật toán sơ bộ
│   ├── ai_ranker.py          # Gemini API + Pydantic Structured Output
│   └── database.py           # SQLite cache (lưu trữ và TTL kết quả tìm kiếm)
├── frontend/
│   └── app.py                # Streamlit UI (nhập liệu, render bảng, card, charts)
├── .env                      # API Keys (GEMINI_API_KEY, APIFY_API_TOKEN)
├── pyproject.toml            # Cấu hình dự án PEP 621 và khai báo thư viện
└── README.md                 # Hướng dẫn cài đặt và chạy ứng dụng
```

---

## API Endpoints (FastAPI)

- **`POST /api/search`**
  - **Body**: `{ "keyword": "tai nghe", "country": "VN", "sort_mode": "default" }`
  - **Response**: Trả về object chứa `keyword`, `top10` (đã map đầy đủ data hình ảnh, giá, link gốc), `market_summary`, `cached_status`.
- **`GET /health`**
  - **Response**: `{ "status": "ok" }`

---

## Ưu Điểm Của Đề Xuất (FastAPI + Streamlit + Gemini)

1. **Structured Output Tuyệt Đối**: Loại bỏ hoàn toàn lỗi cú pháp JSON khi gọi LLM nhờ tính năng schema định sẵn của Gemini API.
2. **Chi Phí Gần Như Bằng 0**: Gemini Flash cực rẻ, có thể chạy demo hàng nghìn lần mà không tốn quá $1 tiền API.
3. **SQLite làm Cache**: Thay vì Redis (phức tạp khi cài đặt local), sử dụng SQLite có sẵn trong Python để làm local cache. Vừa chứng minh được tư duy tối ưu chi phí và chống spam hệ thống cho giám khảo bài test, vừa không cần setup hạ tầng phức tạp.
4. **Trực Quan Hóa Dữ Liệu**: Streamlit cho phép hiển thị hình ảnh sản phẩm ngay lập tức, so sánh giá cả bằng biểu đồ cột hoặc biểu đồ tròn trực quan hơn nhiều so với giao diện HTML/JS thuần.

---

## Hướng Mở Rộng & Giới Hạn (Ghi vào PDF báo cáo)

- **Giới hạn**:
  - Thời gian phản hồi phụ thuộc vào Apify (~10-15 giây). Đã khắc phục bằng cách thiết kế trạng thái Loading trên Streamlit và cơ chế SQLite cache.
  - Số lượng bán thực tế bị ẩn, giải quyết bằng cách dùng `ratingCount` làm biến đại diện (proxy variable).
- **Hướng mở rộng**:
  - Hỗ trợ đa quốc gia khu vực Đông Nam Á để phân tích xu hướng bán hàng chéo biên giới.
  - Tích hợp biểu đồ phân tích biến động giá để phát hiện thời điểm xả hàng hoặc nâng giá ảo của đối thủ.