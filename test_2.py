import os
from dotenv import load_dotenv
from apify_client import ApifyClient
import streamlit as st

load_dotenv()

# Khởi tạo client với API Token từ môi trường
client = ApifyClient(os.getenv("APIFY_API_TOKEN"))

def fetch_shopee_via_apify(keyword, max_items=40, country="BR"):
    # Cấu hình request gửi tới Apify Shopee Scraper
    run_input = {
        "keyword": keyword,
        "maxItems": max_items,
        "country": country,
        "cookieHeader": "",
    }
    
    # Chạy actor và đợi kết quả
    run = client.actor("Qi1dxd9QYcPE9YrUS").call(timeout_secs=120, run_input=run_input)
    
    # Lấy dữ liệu từ dataset của Apify
    products = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        products.append(item)
    return products

# Streamlit UI
st.set_page_config(page_title="Shopee Product Search", page_icon="🛍️", layout="wide")
st.title("🛍️ Shopee Product Search (via Apify - Qi1dxd9QYcPE9YrUS)")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    keyword = st.text_input("Nhập từ khóa tìm kiếm:", value="tai nghe")
with col2:
    country = st.selectbox("Quốc gia:", options=["VN", "BR", "SG", "MY", "ID", "PH", "TH"], index=0)
with col3:
    max_items = st.number_input("Số lượng tối đa:", min_value=1, max_value=100, value=10)

if st.button("Tìm kiếm", type="primary"):
    if not keyword.strip():
        st.warning("Vui lòng nhập từ khóa!")
    else:
        with st.spinner("Đang tìm kiếm trên Shopee qua Apify Scraper..."):
            try:
                products = fetch_shopee_via_apify(keyword, max_items=max_items, country=country)
                if products:
                    st.success(f"Tìm thấy {len(products)} sản phẩm:")
                    st.dataframe(products, width='stretch')
                else:
                    st.info("Không tìm thấy sản phẩm nào.")
            except Exception as e:
                st.error(f"Đã xảy ra lỗi: {e}")