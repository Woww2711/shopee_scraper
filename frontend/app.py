import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
import altair as alt
import time
from collections import defaultdict
from dotenv import load_dotenv
import html
import importlib

# Import trực tiếp các logic backend để chạy ứng dụng độc lập trên Streamlit Cloud
import backend.database
import backend.scraper
import backend.scorer
import backend.ai_ranker

importlib.reload(backend.database)
importlib.reload(backend.scraper)
importlib.reload(backend.scorer)
importlib.reload(backend.ai_ranker)

from backend.database import get_cached_results, set_cached_results, clear_expired_cache, get_recent_keywords
from backend.scraper import fetch_shopee_products
from backend.scorer import filter_and_score_items
from backend.ai_ranker import rank_products_with_gemini

load_dotenv()

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="Shopee Top 10 Product Analyzer",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Nhúng Custom CSS để làm UI trông cực kỳ hiện đại, premium (Glassmorphism & Gradients)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    /* Giao diện font chữ chung */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Title Gradient */
    .title-gradient {
        background: linear-gradient(135deg, #FF4B4B 0%, #FF8C00 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3rem;
        margin-top: 2rem;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    
    .subtitle-text {
        font-size: 1.15rem;
        color: #888888;
        margin-bottom: 3rem;
        text-align: center;
    }
    
    /* Card sản phẩm hiệu ứng Glassmorphism */
    .product-row {
        background: rgba(255, 75, 75, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        display: flex;
        flex-direction: row;
        gap: 20px;
    }
    
    .product-row:hover {
        transform: translateY(-4px);
        border-color: rgba(255, 75, 75, 0.4);
        box-shadow: 0 12px 24px rgba(255, 75, 75, 0.08);
        background: rgba(255, 75, 75, 0.06);
    }
    
    /* Rank badge */
    .rank-badge {
        background: linear-gradient(135deg, #FF4B4B 0%, #FF8C00 100%);
        color: white;
        font-weight: 700;
        font-size: 1.2rem;
        width: 38px;
        height: 38px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 10px rgba(255, 75, 75, 0.3);
    }
    
    /* Lý do AI nổi bật */
    .ai-reason-box {
        background: rgba(255, 140, 0, 0.08);
        border-left: 4px solid #FF8C00;
        padding: 10px 15px;
        border-radius: 4px 12px 12px 4px;
        margin-top: 10px;
        font-size: 0.95rem;
        font-style: italic;
    }
    
    /* Stats badge */
    .stat-badge {
        background: rgba(255, 255, 255, 0.05);
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.85rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-right: 8px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Khởi tạo bộ giới hạn rate limit lưu trữ toàn cục trong Streamlit
@st.cache_resource
def get_rate_limiter():
    return defaultdict(list)

def check_rate_limit(ip: str) -> bool:
    limiter = get_rate_limiter()
    now = time.time()
    # Giữ lại các lượt gọi trong 60 giây gần nhất
    limiter[ip] = [t for t in limiter[ip] if now - t < 60]
    if len(limiter[ip]) >= 5:  # Tối đa 5 lượt / phút / IP
        return False
    limiter[ip].append(now)
    return True

# Tiêu đề chính dạng Hero Section
st.markdown('<div class="title-gradient">🛍️ Shopee Top 10 Product Analyzer</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">Tìm kiếm, xếp hạng và đánh giá Top 10 sản phẩm Shopee tốt nhất bằng AI</div>', unsafe_allow_html=True)

# Khởi tạo st.session_state nếu chưa có
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = "tai nghe bluetooth"
if "search_country" not in st.session_state:
    st.session_state.search_country = "VN"
if "search_sort_mode" not in st.session_state:
    st.session_state.search_sort_mode = "Mặc định (Cân bằng)"
if "trigger_search" not in st.session_state:
    st.session_state.trigger_search = False

# Thanh tìm kiếm tối giản
col_space_left, col_search, col_space_right = st.columns([1, 10, 1])

with col_search:
    col_kw, col_ct, col_sm, col_btn = st.columns([4.8, 1.2, 2.2, 1.8])
    with col_kw:
        keyword_input = st.text_input(
            "Từ khóa sản phẩm:",
            value=st.session_state.search_keyword,
            placeholder="Nhập tên sản phẩm cần tìm kiếm...",
            label_visibility="collapsed"
        )
    with col_ct:
        countries = ["VN", "BR", "SG", "MY", "ID", "PH", "TH"]
        country_index = countries.index(st.session_state.search_country) if st.session_state.search_country in countries else 0
        country_input = st.selectbox(
            "Thị trường:",
            options=countries,
            index=country_index,
            label_visibility="collapsed"
        )
    with col_sm:
        sort_modes = [
            "Mặc định (Cân bằng)",
            "Bán chạy nhất",
            "Đánh giá tốt nhất",
            "Sản phẩm tiềm năng"
        ]
        sort_mode_index = sort_modes.index(st.session_state.search_sort_mode) if st.session_state.search_sort_mode in sort_modes else 0
        sort_mode_label = st.selectbox(
            "Sắp xếp:",
            options=sort_modes,
            index=sort_mode_index,
            label_visibility="collapsed"
        )
        sort_mode_map = {
            "Mặc định (Cân bằng)": "default",
            "Bán chạy nhất": "best_selling",
            "Đánh giá tốt nhất": "best_rating",
            "Sản phẩm tiềm năng": "opportunity"
        }
    with col_btn:
        search_clicked = st.button("🔍 Phân tích", type="primary", use_container_width=True)

    # Hiển thị lịch sử tìm kiếm gần đây dạng tag ngang
    try:
        recent_queries = get_recent_keywords(limit=5)
    except Exception:
        recent_queries = []

    if recent_queries:
        st.markdown("<div style='margin-top: 10px; margin-bottom: 5px; font-size: 0.85rem; color: #888;'>🔍 Tìm kiếm gần đây:</div>", unsafe_allow_html=True)
        
        sm_display_map = {
            "default": "Cân bằng",
            "best_selling": "Bán chạy",
            "best_rating": "Đánh giá tốt",
            "opportunity": "Tiềm năng"
        }
        
        num_tags = len(recent_queries)
        ratios = [1.6] * num_tags + [10 - (1.6 * num_tags)]
        cols_recent = st.columns(ratios)
        
        for i, (kw, ct, sm) in enumerate(recent_queries):
            display_sm = sm_display_map.get(sm, "Cân bằng")
            btn_label = f"{kw} ({ct} | {display_sm})"
            if cols_recent[i].button(btn_label, key=f"recent_btn_{i}", use_container_width=True):
                st.session_state.search_keyword = kw
                st.session_state.search_country = ct
                st.session_state.search_sort_mode = {
                    "default": "Mặc định (Cân bằng)",
                    "best_selling": "Bán chạy nhất",
                    "best_rating": "Đánh giá tốt nhất",
                    "opportunity": "Sản phẩm tiềm năng"
                }.get(sm, "Mặc định (Cân bằng)")
                st.session_state.trigger_search = True
                st.rerun()

# Logic tìm kiếm trực tiếp (không thông qua API HTTP)
if search_clicked or st.session_state.trigger_search:
    # Reset trigger
    st.session_state.trigger_search = False
    
    raw_keyword = keyword_input.strip() if search_clicked else st.session_state.search_keyword
    raw_country = country_input.strip() if search_clicked else st.session_state.search_country
    
    if search_clicked:
        sort_mode = sort_mode_map.get(sort_mode_label, "default")
    else:
        sort_mode_rev_map = {
            "Mặc định (Cân bằng)": "default",
            "Bán chạy nhất": "best_selling",
            "Đánh giá tốt nhất": "best_rating",
            "Sản phẩm tiềm năng": "opportunity"
        }
        sort_mode = sort_mode_rev_map.get(st.session_state.search_sort_mode, "default")

    if not raw_keyword:
        st.warning("⚠️ Vui lòng nhập từ khóa tìm kiếm!")
    else:
        # Đồng bộ session_state
        st.session_state.search_keyword = raw_keyword
        st.session_state.search_country = raw_country
        st.session_state.search_sort_mode = {
            "default": "Mặc định (Cân bằng)",
            "best_selling": "Bán chạy nhất",
            "best_rating": "Đánh giá tốt nhất",
            "opportunity": "Sản phẩm tiềm năng"
        }.get(sort_mode, "Mặc định (Cân bằng)")

        # Lấy IP client từ Streamlit headers
        try:
            client_ip = st.context.headers.get("x-forwarded-for", "127.0.0.1").split(",")[0].strip()
        except Exception:
            client_ip = "127.0.0.1"

        if not check_rate_limit(client_ip):
            st.error("❌ Bạn đã vượt quá giới hạn lượt tìm kiếm cho phép (tối đa 5 lần/phút). Vui lòng thử lại sau ít phút.")
        else:
            # Sử dụng st.status để tạo UI cập nhật động premium
            with st.status("🚀 Đang chuẩn bị phân tích dữ liệu...", expanded=True) as status_box:
                start_time = time.time()
                
                keyword = raw_keyword.lower().strip()
                country = raw_country.upper().strip()
                ttl = int(os.getenv("CACHE_TTL_SECONDS", 3600))
                
                # 1. Kiểm tra cache SQLite
                status_box.write("🔍 Đang kiểm tra bộ nhớ đệm (Cache)...")
                cached_data = get_cached_results(keyword, country, sort_mode, ttl_seconds=ttl)
                
                final_data = None
                is_cached = False
                
                if cached_data:
                    status_box.write("⚡ Phát hiện kết quả phù hợp trong bộ nhớ đệm (Cache hit).")
                    final_data = cached_data
                    is_cached = True
                    status_box.update(label="✅ Đã tải kết quả từ Cache!", state="complete")
                else:
                    # Cache miss: chạy các module backend
                    status_box.write("🌐 Bộ nhớ đệm trống. Đang gửi yêu cầu cào dữ liệu đến Apify...")
                    
                    # Định nghĩa callback để cập nhật tiến trình từ Apify Scraper vào Streamlit status_box
                    def apify_callback(msg):
                        status_box.write(msg)
                        
                    raw_products = fetch_shopee_products(keyword, country, max_items=40, status_callback=apify_callback)
                    
                    if not raw_products:
                        status_box.update(label="⚠️ Không tìm thấy sản phẩm trên Shopee!", state="error")
                        st.warning(f"Không tìm thấy sản phẩm nào trên Shopee với từ khóa '{keyword}' tại quốc gia {country}.")
                    else:
                        status_box.write(f"📊 Thu thập được {len(raw_products)} sản phẩm. Đang chạy thuật toán lọc chất lượng & chấm điểm...")
                        filtered_and_scored = filter_and_score_items(raw_products, sort_mode)
                        
                        if not filtered_and_scored:
                            status_box.update(label="⚠️ Không có sản phẩm đạt chất lượng tối thiểu!", state="error")
                            st.warning("Tất cả sản phẩm tìm thấy đều không đạt tiêu chuẩn lọc tối thiểu.")
                        else:
                            status_box.write("🧠 Đang gọi AI Gemini để phân tích bối cảnh thị trường và xếp hạng Top 10...")
                            ai_result = rank_products_with_gemini(keyword, filtered_and_scored, sort_mode)
                            
                            # Map dữ liệu gốc với kết quả AI
                            ai_top10 = ai_result.get("top10", [])
                            mapped_top10 = []
                            product_map = {item["itemId"]: item for item in filtered_and_scored}
                            
                            for rank_item in ai_top10:
                                item_id = rank_item.get("itemId")
                                original_item = product_map.get(item_id)
                                
                                if original_item:
                                    mapped_top10.append({
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
                                    })
                                    
                            if not mapped_top10:
                                for idx, item in enumerate(filtered_and_scored[:10]):
                                    mapped_top10.append({
                                        "rank": idx + 1,
                                        "reason": f"Sản phẩm đạt điểm chất lượng và độ phổ biến cao ({item.get('ratingCount')} đánh giá).",
                                        **item
                                    })
                                    
                            final_data = {
                                "top10": mapped_top10,
                                "market_summary": ai_result.get("market_summary", "")
                            }
                            
                            # Lưu vào Cache
                            status_box.write("💾 Đang cập nhật dữ liệu phân tích vào SQLite Cache...")
                            set_cached_results(keyword, country, sort_mode, final_data)
                            try:
                                clear_expired_cache(ttl_seconds=ttl)
                            except Exception:
                                pass
                                
                            status_box.update(label="✅ Phân tích thành công!", state="complete")
                
                duration = round(time.time() - start_time, 2)
                
                # 2. Hiển thị kết quả ra màn hình
                if final_data:
                    st.success("✅ Phân tích thành công!")
                    
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        st.metric(label="Nguồn dữ liệu", value="Cơ sở dữ liệu (Cache)" if is_cached else "Dữ liệu mới (Live)")
                    with col_m2:
                        st.metric(label="Thời gian xử lý", value=f"{duration} giây")
                    with col_m3:
                        st.metric(label="Số sản phẩm phân tích", value=f"{len(final_data.get('top10', []))} sản phẩm")

                    # Tóm tắt thị trường từ AI
                    st.markdown("### 📊 Phân tích xu hướng thị trường (AI Market Insight)")
                    st.info(final_data.get("market_summary", "Không có tóm tắt thị trường."))
                    
                    # Danh sách Top 10
                    top10_list = final_data.get("top10", [])
                    st.markdown("### 🏆 Top 10 Sản phẩm Nổi bật nhất")
                    
                    chart_data = []
                    for item in top10_list:
                        rank = item.get("rank")
                        name = item.get("name")
                        price_formatted = item.get("price", {}).get("formatted", "0 ₫")
                        price_val = item.get("price", {}).get("value", 0)
                        rating = item.get("rating", 0)
                        rating_count = item.get("ratingCount", 0)
                        shop_name = item.get("shopName", "N/A")
                        location = item.get("location", "N/A")
                        images = item.get("images", [])
                        url = item.get("url", "#")
                        reason = item.get("reason", "")
                        
                        chart_data.append({
                            "Sản phẩm": f"#{rank} - {name[:25]}...",
                            "Giá trị (₫)": price_val,
                            "Số lượt đánh giá": rating_count,
                            "Rating": rating
                        })
                        
                        # Render HTML card
                        image_url = images[0] if images else "https://via.placeholder.com/150"
                        if not image_url.startswith(("http://", "https://")):
                            image_url = "https://via.placeholder.com/150"
                        
                        if not url.startswith(("http://", "https://")):
                            url_cleaned = "#"
                        else:
                            url_cleaned = url

                        # Escape dynamic values to prevent XSS
                        name_esc = html.escape(name or "")
                        url_esc = html.escape(url_cleaned or "#")
                        image_url_esc = html.escape(image_url or "")
                        price_formatted_esc = html.escape(price_formatted or "")
                        shop_name_esc = html.escape(shop_name or "")
                        location_esc = html.escape(location or "")
                        reason_esc = html.escape(reason or "")

                        html_content = f"""
                        <div class="product-row">
                            <div style="display: flex; align-items: center;">
                                <div class="rank-badge">#{rank}</div>
                            </div>
                            <img src="{image_url_esc}" style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px;" />
                            <div style="flex: 1;">
                                <h4 style="margin: 0 0 8px 0;"><a href="{url_esc}" target="_blank" style="color: #FF4B4B; text-decoration: none;">{name_esc}</a></h4>
                                <div style="margin-bottom: 8px;">
                                    <span class="stat-badge">💰 Giá bán: {price_formatted_esc}</span>
                                    <span class="stat-badge">⭐ Đánh giá: {rating}/5.0</span>
                                    <span class="stat-badge">💬 Phản hồi: {rating_count:,} lượt</span>
                                </div>
                                <div style="font-size: 0.85rem; color: #777;">
                                    🏪 Shop: <strong>{shop_name_esc}</strong> | 📍 Khu vực: <strong>{location_esc}</strong>
                                </div>
                                <div class="ai-reason-box">
                                    💡 <strong>Lý do AI khuyên chọn:</strong> {reason_esc}
                                </div>
                            </div>
                        </div>
                        """
                        st.markdown(html_content, unsafe_allow_html=True)
                    
                    # Biểu đồ so sánh
                    st.markdown("### 📈 Biểu đồ so sánh sản phẩm Top 10")
                    df = pd.DataFrame(chart_data)
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        st.subheader("So sánh giá bán")
                        bar_chart = alt.Chart(df).mark_bar(color='#FF4B4B').encode(
                            x=alt.X('Giá trị (₫):Q', title='Giá bán (VND)'),
                            y=alt.Y('Sản phẩm:N', sort=None, title='Sản phẩm')
                        ).properties(height=350)
                        st.altair_chart(bar_chart, width="stretch")
                        
                    with col_chart2:
                        st.subheader("Số lượt đánh giá")
                        point_chart = alt.Chart(df).mark_bar(color='#FF8C00').encode(
                            x=alt.X('Số lượt đánh giá:Q', title='Lượt đánh giá (review_count)'),
                            y=alt.Y('Sản phẩm:N', sort=None, title='Sản phẩm')
                        ).properties(height=350)
                        st.altair_chart(point_chart, width="stretch")

                    # Export CSV
                    st.markdown("### 💾 Xuất dữ liệu")
                    export_data = []
                    for item in top10_list:
                        export_data.append({
                            "Rank": item.get("rank"),
                            "Name": item.get("name"),
                            "Price": item.get("price", {}).get("value"),
                            "Rating": item.get("rating"),
                            "Rating Count": item.get("ratingCount"),
                            "Shop Name": item.get("shopName"),
                            "Location": item.get("location"),
                            "AI Reason": item.get("reason"),
                            "Shopee URL": item.get("url")
                        })
                    export_df = pd.DataFrame(export_data)
                    csv_data = export_df.to_csv(index=False).encode('utf-8-sig')
                    
                    st.download_button(
                        label="📥 Tải Báo Cáo CSV (Excel-ready)",
                        data=csv_data,
                        file_name=f"shopee_analysis_{keyword_input.replace(' ', '_')}.csv",
                        mime="text/csv",
                    )
