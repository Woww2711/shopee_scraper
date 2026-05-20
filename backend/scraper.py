import os
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

# Lấy token và actor ID từ file cấu hình .env
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "Qi1dxd9QYcPE9YrUS")

def fetch_shopee_products(keyword: str, country: str = "VN", max_items: int = 40) -> list:
    """
    Sử dụng Apify Shopee Scraper actor để lấy thông tin sản phẩm từ Shopee.
    """
    if not APIFY_API_TOKEN:
        raise ValueError("APIFY_API_TOKEN is missing in the environment variables.")
        
    client = ApifyClient(APIFY_API_TOKEN)
    
    run_input = {
        "keyword": keyword,
        "maxItems": max_items,
        "country": country.upper(),  # VN, BR, SG, v.v.
        "cookieHeader": "",
    }
    
    try:
        # Gọi Actor Apify và đợi kết quả hoàn thành (timeout 120 giây)
        run = client.actor(APIFY_ACTOR_ID).call(timeout_secs=120, run_input=run_input)
        
        # Lấy dữ liệu từ dataset mặc định của run
        products = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            products.append(item)
            
        return products
    except Exception as e:
        print(f"Error fetching data from Apify: {e}")
        # Trả về mảng rỗng nếu có lỗi xảy ra để tránh crash hệ thống
        return []
