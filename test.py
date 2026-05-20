import asyncio
from playwright.async_api import async_playwright
import json

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False để thấy browser
        page = await browser.new_page()
        
        await page.goto("https://shopee.vn/search?keyword=tai+nghe")
        await page.wait_for_timeout(3000)  # chờ load
        
        # Intercept API response
        results = []
        
        async def handle_response(response):
            if "search_items" in response.url:
                try:
                    data = await response.json()
                    if "items" in data:
                        results.extend(data["items"])
                        print(f"✅ Bắt được {len(data['items'])} sản phẩm!")
                except:
                    pass
        
        page.on("response", handle_response)
        
        await page.goto("https://shopee.vn/search?keyword=tai+nghe")
        await page.wait_for_timeout(5000)
        
        if results:
            item = results[0]["item_basic"]
            print(f"Sản phẩm: {item['name'][:50]}")
            print(f"Đã bán: {item.get('sold', 0)}")
        
        await browser.close()

asyncio.run(test())