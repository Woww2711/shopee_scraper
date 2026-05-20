import os
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

# Lấy token và actor ID từ file cấu hình .env
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "Qi1dxd9QYcPE9YrUS")

def fetch_shopee_products(keyword: str, country: str = "VN", max_items: int = 40, status_callback=None) -> list:
    """
    Sử dụng Apify Shopee Scraper actor để lấy thông tin sản phẩm từ Shopee.
    Có hỗ trợ callback để cập nhật tiến trình chạy bất đồng bộ.
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
        if status_callback:
            status_callback("🚀 Đang khởi tạo container cào dữ liệu trên Apify...")
            
        # Gọi Actor Apify bất đồng bộ (không block)
        run = client.actor(APIFY_ACTOR_ID).start(run_input=run_input)
        run_id = run["id"]
        
        # Vòng lặp thăm dò trạng thái (polling loop)
        import time
        last_status = None
        status_map = {
            "READY": "📦 Khởi tạo container cào dữ liệu...",
            "RUNNING": "🌐 Đang kết nối Shopee và cào sản phẩm...",
            "SUCCEEDED": "✅ Hoàn tất thu thập dữ liệu Shopee!",
            "FAILED": "❌ Gặp lỗi trong quá trình cào dữ liệu Shopee.",
            "TIMED-OUT": "⏱️ Quá thời gian cào dữ liệu (Timeout).",
            "ABORTED": "🚫 Tiến trình cào dữ liệu bị hủy bỏ."
        }
        
        printed_log_bytes = 0
        while True:
            run_info = client.run(run_id).get()
            status = run_info.get("status")
            
            if status != last_status:
                last_status = status
                if status_callback:
                    msg = status_map.get(status, f"Trạng thái Apify: {status}")
                    status_callback(msg)
                    
            # Lấy log của Actor và in ra stdout của terminal
            try:
                log_text = client.log(run_id).get()
                if log_text:
                    new_log = log_text[printed_log_bytes:]
                    if new_log:
                        import sys
                        sys.stdout.write(new_log)
                        sys.stdout.flush()
                        printed_log_bytes = len(log_text)
            except Exception:
                pass
                
            if status in ["SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"]:
                break
                
            time.sleep(2.5)
            
        # In nốt log còn lại sau khi tiến trình kết thúc
        try:
            log_text = client.log(run_id).get()
            if log_text:
                new_log = log_text[printed_log_bytes:]
                if new_log:
                    import sys
                    sys.stdout.write(new_log)
                    sys.stdout.flush()
        except Exception:
            pass
            
        if last_status == "SUCCEEDED":
            # Lấy dữ liệu từ dataset mặc định của run
            products = []
            for item in client.dataset(run_info["defaultDatasetId"]).iterate_items():
                products.append(item)
            return products
        else:
            return []
            
    except Exception as e:
        print(f"Error fetching data from Apify: {e}")
        if status_callback:
            status_callback(f"❌ Lỗi kết nối Apify: {e}")
        # Trả về mảng rỗng nếu có lỗi xảy ra để tránh crash hệ thống
        return []
