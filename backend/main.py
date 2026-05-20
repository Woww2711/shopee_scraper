import time
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from collections import defaultdict

from backend.database import get_cached_results, set_cached_results, clear_expired_cache
from backend.scraper import fetch_shopee_products
from backend.scorer import filter_and_score_items
from backend.ai_ranker import rank_products_with_gemini

load_dotenv()

app = FastAPI(
    title="Shopee Top 10 Search Tool API",
    description="Backend API phục vụ tìm kiếm, chấm điểm và xếp hạng sản phẩm Shopee nổi bật bằng AI.",
    version="1.3.0"
)

# Cấu hình CORS để Streamlit (hoặc các UI khác) gọi API không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Giới hạn tần suất gọi API đơn giản lưu trong bộ nhớ
CALL_HISTORY = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # Cửa sổ thời gian tính bằng giây (1 phút)
MAX_CALLS_PER_MINUTE = 5  # Tối đa 5 lượt tìm kiếm/phút cho mỗi IP

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    # Loại bỏ các mốc thời gian ngoài cửa sổ 1 phút
    CALL_HISTORY[ip] = [t for t in CALL_HISTORY[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(CALL_HISTORY[ip]) >= MAX_CALLS_PER_MINUTE:
        return True
    CALL_HISTORY[ip].append(now)
    return False

class SearchRequest(BaseModel):
    keyword: str = Field(..., example="tai nghe bluetooth", description="Từ khóa tìm kiếm sản phẩm")
    country: str = Field("VN", example="VN", description="Mã quốc gia Shopee (VN, BR, SG, MY, ID, PH, TH)")
    sort_mode: str = Field("default", example="default", description="Chế độ sắp xếp: default, best_selling, best_rating, opportunity")
    max_items: int = Field(40, ge=10, le=100, description="Số lượng sản phẩm tải về từ Shopee tối đa")

@app.post("/api/search")
async def search_and_analyze(request: SearchRequest, http_req: Request):
    """
    Tìm kiếm sản phẩm trên Shopee qua Apify, lọc thô, chấm điểm và xếp hạng Top 10 qua Gemini API.
    Có tích hợp Cache SQLite tự động và Rate Limiting theo IP.
    """
    # 0. Kiểm tra Rate Limit
    client_ip = http_req.headers.get("x-forwarded-for") or http_req.client.host
    if is_rate_limited(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Bạn đã vượt quá giới hạn lượt tìm kiếm cho phép (tối đa 5 lần/phút). Vui lòng thử lại sau ít phút."
        )

    keyword = request.keyword.lower().strip()
    country = request.country.upper().strip()
    sort_mode = request.sort_mode.lower().strip()
    max_items = request.max_items

    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword cannot be empty")

    start_time = time.time()
    
    # 1. Kiểm tra SQLite cache trước
    ttl = int(os.getenv("CACHE_TTL_SECONDS", 3600))
    cached_data = get_cached_results(keyword, country, sort_mode, ttl_seconds=ttl)
    
    if cached_data:
        duration = round(time.time() - start_time, 2)
        return {
            "keyword": keyword,
            "country": country,
            "sort_mode": sort_mode,
            "cached": True,
            "duration_seconds": duration,
            **cached_data
        }

    # 2. Cache Miss: Gọi Apify để cào sản phẩm mới
    print(f"Cache miss for '{keyword}' ({country}, {sort_mode}). Fetching from Apify...")
    raw_products = fetch_shopee_products(keyword, country, max_items=max_items)
    
    if not raw_products:
        duration = round(time.time() - start_time, 2)
        return {
            "keyword": keyword,
            "country": country,
            "sort_mode": sort_mode,
            "cached": False,
            "duration_seconds": duration,
            "top10": [],
            "market_summary": f"Không tìm thấy sản phẩm nào trên Shopee với từ khóa '{keyword}' tại quốc gia {country}."
        }

    # 3. Lọc thô và tính toán điểm số thuật toán
    filtered_and_scored = filter_and_score_items(raw_products, sort_mode)
    
    if not filtered_and_scored:
        duration = round(time.time() - start_time, 2)
        return {
            "keyword": keyword,
            "country": country,
            "sort_mode": sort_mode,
            "cached": False,
            "duration_seconds": duration,
            "top10": [],
            "market_summary": f"Tất cả sản phẩm tìm thấy đều không đạt tiêu chuẩn lọc tối thiểu."
        }

    # 4. Gửi sang Gemini API để xếp hạng Top 10 và lấy lý do, tóm tắt thị trường
    ai_result = rank_products_with_gemini(keyword, filtered_and_scored, sort_mode)
    
    # 5. Map lại kết quả phân tích AI với toàn bộ dữ liệu gốc của sản phẩm
    ai_top10 = ai_result.get("top10", [])
    mapped_top10 = []
    
    product_map = {item["itemId"]: item for item in filtered_and_scored}
    
    for rank_item in ai_top10:
        item_id = rank_item.get("itemId")
        original_item = product_map.get(item_id)
        
        if original_item:
            mapped_item = {
                "rank": rank_item.get("rank"),
                "reason": rank_item.get("reason"),
                "itemId": original_item.get("itemId"),
                "shopId": original_item.get("shopId"),
                "name": original_item.get("name"),
                "price": original_item.get("price"),
                "rating": original_item.get("rating"),
                "ratingCount": original_item.get("ratingCount"),
                "shopName": original_item.get("shopName"),
                "brand": original_item.get("brand"),
                "location": original_item.get("location"),
                "images": original_item.get("images", []),
                "url": original_item.get("url"),
                "calculated_score": original_item.get("calculated_score")
            }
            mapped_top10.append(mapped_item)
            
    # Dự phòng: Nếu Gemini không map đúng ID hoặc có lỗi, lấy top 10 từ danh sách đã sắp xếp của scorer
    if not mapped_top10:
        for idx, item in enumerate(filtered_and_scored[:10]):
            mapped_top10.append({
                "rank": idx + 1,
                "reason": f"Sản phẩm đạt điểm chất lượng và độ phổ biến cao ({item.get('ratingCount')} đánh giá).",
                **item
            })

    final_result = {
        "top10": mapped_top10,
        "market_summary": ai_result.get("market_summary", "")
    }

    # 6. Lưu kết quả vào Cache SQLite
    set_cached_results(keyword, country, sort_mode, final_result)
    
    # Xóa bớt cache hết hạn định kỳ
    try:
        clear_expired_cache(ttl_seconds=ttl)
    except Exception:
        pass

    duration = round(time.time() - start_time, 2)
    return {
        "keyword": keyword,
        "country": country,
        "sort_mode": sort_mode,
        "cached": False,
        "duration_seconds": duration,
        **final_result
    }

@app.get("/health")
def health_check():
    """Endpoint kiểm tra sức khỏe hệ thống."""
    return {"status": "ok", "time": time.time()}
