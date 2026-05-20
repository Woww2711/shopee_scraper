import os
import json
from typing import List, Dict, Any
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Cấu hình Pydantic Schema cho Structured Output
class TopProductSchema(BaseModel):
    itemId: str = Field(description="ID của sản phẩm Shopee (itemId)")
    rank: int = Field(description="Thứ hạng nổi bật từ 1 đến 10")
    reason: str = Field(description="Lý do ngắn gọn tại sao sản phẩm này nổi bật (1 câu, viết bằng tiếng Việt)")

class MarketAnalysisSchema(BaseModel):
    top10: List[TopProductSchema] = Field(description="Danh sách 10 sản phẩm nổi bật nhất")
    market_summary: str = Field(description="Tóm tắt bối cảnh thị trường của từ khóa: xu hướng chung, phân khúc giá phổ biến, lời khuyên mua sắm/resell (2-3 câu, viết bằng tiếng Việt)")

# Khởi tạo Gemini client
def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def get_system_prompt(sort_mode: str) -> str:
    """
    Tạo system prompt động dựa trên chế độ sắp xếp.
    """
    base_prompt = """Bạn là một chuyên gia phân tích thị trường Thương mại điện tử (Shopee).
Nhiệm vụ của bạn là nhận danh sách các sản phẩm đã được lọc thô và sắp xếp sơ bộ bằng thuật toán, sau đó chọn ra Top 10 sản phẩm nổi bật nhất.

Tiêu chí lựa chọn:
1. Nhu cầu lớn (lượt đánh giá ratingCount lớn chứng minh sản phẩm được mua nhiều).
2. Chất lượng sản phẩm cao (rating tốt, ít phản hồi tiêu cực từ người mua).
3. Đáng giá tiền (mức giá hợp lý so với giá trị thực tế sản phẩm đem lại).
4. Shop hoặc Brand có độ uy tín để đảm bảo trải nghiệm nhận hàng tốt.
"""

    if sort_mode == "best_selling":
        extra = "\nĐẶC BIỆT CHÚ Ý: Chế độ 'Bán chạy nhất'. Hãy ưu tiên chọn các sản phẩm đang dẫn đầu xu hướng thị trường, có lượt mua/đánh giá (ratingCount) khổng lồ."
    elif sort_mode == "best_rating":
        extra = "\nĐẶC BIỆT CHÚ Ý: Chế độ 'Đánh giá tốt nhất'. Hãy ưu tiên chọn các sản phẩm có chất lượng vượt trội, rating tiệm cận 5.0 và nhận được phản hồi cực kỳ hài lòng từ người dùng."
    elif sort_mode == "opportunity":
        extra = "\nĐẶC BIỆT CHÚ Ý: Chế độ 'Sản phẩm tiềm năng'. Hãy tìm các sản phẩm nổi bật có chất lượng cao (rating tốt) và mức giá cực kỳ cạnh tranh, hấp dẫn so với mặt bằng chung."
    else:
        extra = "\nCHẾ ĐỘ TỔNG HỢP: Hãy cân bằng hài hòa giữa chất lượng (rating), độ phổ biến (reviews) và giá cả."

    format_instruction = """
Hãy viết lý do vì sao lựa chọn sản phẩm đó một cách khách quan và ngắn gọn (1 câu, viết bằng tiếng Việt). Ví dụ: 'Sản phẩm bán chạy nhất phân khúc dưới 100k, đánh giá cực cao' hoặc 'Thương hiệu chính hãng uy tín, rating 4.9 hoàn hảo đảm bảo chất lượng'.
"""
    return base_prompt + extra + format_instruction

def rank_products_with_gemini(keyword: str, items: List[Dict[str, Any]], sort_mode: str = "default") -> Dict[str, Any]:
    """
    Sử dụng Gemini API với tính năng Structured Output để chọn và phân tích Top 10 sản phẩm Shopee.
    """
    client = get_gemini_client()
    if not client:
        print("⚠️ CẢNH BÁO: GEMINI_API_KEY chưa được cấu hình. Sử dụng kết quả phân tích mô phỏng!")
        return get_mock_ranking_results(keyword, items, sort_mode)

    # Chỉ gửi các trường thông tin cần thiết đến AI để tiết kiệm tokens
    simplified_items = []
    for idx, item in enumerate(items[:30]):  # Gửi tối đa 30 sản phẩm hàng đầu sau khi đã lọc & chấm điểm
        simplified_items.append({
            "itemId": item.get("itemId"),
            "name": item.get("name"),
            "price": item.get("price", {}).get("formatted"),
            "price_value": item.get("price", {}).get("value"),
            "rating": item.get("rating"),
            "ratingCount": item.get("ratingCount"),
            "shopName": item.get("shopName"),
            "brand": item.get("brand"),
            "location": item.get("location"),
            "calculated_score": item.get("calculated_score")
        })

    user_prompt = f"""
Từ khóa tìm kiếm (Keyword): {keyword}
Chế độ lọc/sắp xếp: {sort_mode}
Danh sách các sản phẩm Shopee đã được lọc và sắp xếp sơ bộ bằng thuật toán:
{json.dumps(simplified_items, ensure_ascii=False, indent=2)}
"""

    system_instruction = get_system_prompt(sort_mode)

    try:
        # Gọi Gemini API sử dụng gemini-3.1-flash-lite để nhanh và tiết kiệm chi phí
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=MarketAnalysisSchema,
                temperature=0.2
            )
        )
        
        result = json.loads(response.text)
        return result
        
    except Exception as e:
        print(f"Lỗi khi gọi Gemini API: {e}")
        return get_mock_ranking_results(keyword, items, sort_mode)

def get_mock_ranking_results(keyword: str, items: List[Dict[str, Any]], sort_mode: str = "default") -> Dict[str, Any]:
    """
    Trả về dữ liệu phân tích mô phỏng nếu API Key chưa được cài đặt hoặc xảy ra lỗi kết nối.
    """
    top10 = []
    for idx, item in enumerate(items[:10]):
        if sort_mode == "best_selling":
            reason = f"Sản phẩm bán chạy nổi bật với {item.get('ratingCount')} lượt đánh giá từ khách hàng."
        elif sort_mode == "best_rating":
            reason = f"Điểm đánh giá gần như tuyệt đối ({item.get('rating')}/5.0), phản ánh mức độ hài lòng khách hàng rất cao."
        elif sort_mode == "opportunity":
            reason = f"Sản phẩm tiềm năng với mức giá {item.get('price', {}).get('formatted')} cực kỳ cạnh tranh và chất lượng tốt."
        else:
            reason = f"Đạt điểm đánh giá cao ({item.get('rating')}/5.0) cùng mức giá hợp lý trong phân khúc."

        top10.append({
            "itemId": item.get("itemId", ""),
            "rank": idx + 1,
            "reason": reason
        })
        
    if sort_mode == "best_selling":
        summary = f"Thị trường sản phẩm '{keyword}' đang có lượt tiêu thụ rất lớn, tập trung chủ yếu ở phân khúc phổ thông."
    elif sort_mode == "best_rating":
        summary = f"Phần lớn khách hàng tìm kiếm '{keyword}' cực kỳ quan tâm tới chất lượng sản phẩm. Các shop có rating trên 4.8 đang nắm giữ lợi thế."
    elif sort_mode == "opportunity":
        summary = f"Nhiều sản phẩm tiềm năng với giá cả cạnh tranh đang xuất hiện trên thị trường, thích hợp cho người mua tìm deal hời."
    else:
        summary = f"Tổng quan thị trường sản phẩm '{keyword}' đang hoạt động sôi động với đa dạng phân khúc giá và chất lượng để lựa chọn."

    return {
        "top10": top10,
        "market_summary": summary
    }
