import math
from typing import List, Dict, Any

def compute_score(item: Dict[str, Any], sort_mode: str = "default") -> float:
    """
    Tính điểm số cho một sản phẩm Shopee dựa theo chất lượng và mức độ phổ biến.
    """
    rating = item.get("rating", 0) or 0
    review_count = item.get("ratingCount", 0) or 0
    
    # Chuyển số lượng đánh giá sang log scale để tránh các shop khổng lồ áp đảo hoàn toàn
    review_score = math.log1p(review_count)

    # Thay đổi trọng số dựa trên sort_mode
    if sort_mode == "best_selling":
        # Ưu tiên lượt mua/đánh giá cao
        return review_score * 0.80 + rating * 0.20
        
    elif sort_mode == "best_rating":
        # Ưu tiên chất lượng sản phẩm (rating cao)
        return rating * 0.80 + review_score * 0.20
        
    else:  # default / opportunity
        # Chế độ mặc định cân bằng tổng hợp
        normalized_review = min(review_score / 10.0, 1.0)
        normalized_rating = rating / 5.0
        return (normalized_rating * 0.50 + normalized_review * 0.50) * 100

def filter_and_score_items(items: List[Dict[str, Any]], sort_mode: str = "default") -> List[Dict[str, Any]]:
    """
    1. Lọc thô các sản phẩm rác hoặc thiếu thông tin cơ bản.
    2. Tính toán điểm số chất lượng & độ hot rồi sắp xếp.
    """
    filtered_items = []
    
    for item in items:
        # Kiểm tra dữ liệu bắt buộc
        if not item.get("name") or not item.get("itemId"):
            continue
            
        rating = item.get("rating")
        review_count = item.get("ratingCount")
        images = item.get("images", [])
        
        # Lọc cứng tối thiểu:
        # - Rating dưới 4.0 → loại (chất lượng kém)
        # - Lượt đánh giá dưới 5 → loại (chưa được thị trường kiểm chứng)
        # - Không có hình ảnh sản phẩm → loại
        if rating is not None and rating < 4.0:
            continue
        if review_count is not None and review_count < 5:
            continue
        if not images or len(images) == 0:
            continue
            
        # Tính toán điểm số
        score = compute_score(item, sort_mode)
        
        # Đính kèm điểm số vào item
        item_with_score = item.copy()
        item_with_score["calculated_score"] = round(score, 2)
        filtered_items.append(item_with_score)
        
    # Sắp xếp giảm dần theo điểm số tính toán
    filtered_items.sort(key=lambda x: x["calculated_score"], reverse=True)
    
    return filtered_items
