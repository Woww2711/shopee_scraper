import sqlite3
import json
import os
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.db")

def init_db():
    """Khởi tạo database cache SQLite nếu chưa tồn tại"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Kiểm tra cấu trúc bảng cũ để dọn dẹp nếu có cột persona cũ
    try:
        cursor.execute("SELECT persona FROM search_cache LIMIT 1;")
        has_persona = True
    except sqlite3.OperationalError:
        has_persona = False
        
    if has_persona:
        # Xóa bảng cũ nếu chứa cột persona cũ để đồng bộ hóa đơn giản
        cursor.execute("DROP TABLE IF EXISTS search_cache;")
        
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_cache (
            keyword TEXT,
            country TEXT,
            sort_mode TEXT,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (keyword, country, sort_mode)
        )
    """)
    conn.commit()
    conn.close()

def get_cached_results(keyword: str, country: str, sort_mode: str, ttl_seconds: int = 3600):
    """Lấy dữ liệu từ cache theo keyword, country, sort_mode nếu chưa hết hạn"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT data, created_at FROM search_cache 
        WHERE keyword = ? AND country = ? AND sort_mode = ?
    """, (keyword.lower().strip(), country.upper(), sort_mode.lower()))
    
    row = cursor.fetchone()
    conn.close()

    if row:
        data_str, created_at_str = row
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            try:
                created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
                
        age = datetime.now(timezone.utc).replace(tzinfo=None) - created_at
        if age.total_seconds() < ttl_seconds:
            return json.loads(data_str)
            
    return None

def set_cached_results(keyword: str, country: str, sort_mode: str, data: dict):
    """Lưu dữ liệu kết quả phân tích vào cache theo keyword, country, sort_mode"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    data_str = json.dumps(data, ensure_ascii=False)
    
    cursor.execute("""
        INSERT OR REPLACE INTO search_cache (keyword, country, sort_mode, data, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (keyword.lower().strip(), country.upper(), sort_mode.lower(), data_str, now_str))
    
    conn.commit()
    conn.close()

def clear_expired_cache(ttl_seconds: int = 3600):
    """Xóa các bản ghi cache đã hết hạn"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    threshold = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=ttl_seconds)).isoformat()
    cursor.execute("DELETE FROM search_cache WHERE created_at < ?", (threshold,))
    conn.commit()
    conn.close()

def get_recent_keywords(limit: int = 5):
    """Lấy danh sách các từ khóa tìm kiếm gần đây từ cache"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT keyword, country, sort_mode FROM search_cache 
        GROUP BY keyword, country, sort_mode
        ORDER BY max(created_at) DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows
