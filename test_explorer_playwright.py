import asyncio
from playwright.async_api import async_playwright

async def test_explorer():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            
            resp = await page.goto("http://127.0.0.1:8000/data-explorer.html")
            print("Page status:", resp.status)
            await page.wait_for_timeout(2000)
            
            title = await page.title()
            print("Title:", title)
            
            # Check platform select
            sat_select = await page.query_selector("#selSatPlatform")
            print("Platform Select present:", sat_select is not None)
            
            # Initial Image src
            img = await page.query_selector("#primarySatelliteDisplay")
            src = await img.get_attribute("src") if img else None
            print("Initial Image src:", src)
            
            # Test switching platform to Himawari
            await page.select_option("#selSatPlatform", "himawari")
            await page.wait_for_timeout(1000)
            src_h = await img.get_attribute("src")
            print("Himawari Image src:", src_h)
            
            # Test switching platform to NASA GIBS
            await page.select_option("#selSatPlatform", "nasa_gibs")
            await page.wait_for_timeout(1000)
            src_g = await img.get_attribute("src")
            print("NASA GIBS Image src:", src_g)
            
            # Test Compare mode toggle
            compare_btn = await page.query_selector("#btnViewCompare")
            if compare_btn:
                await compare_btn.click()
                await page.wait_for_timeout(1000)
                comp_container = await page.query_selector("#compareImageryContainer")
                is_visible = await comp_container.is_visible()
                print("Compare container visible:", is_visible)
            
            # Verify detect button
            detect_btn = await page.query_selector("#btnSendToDetection")
            print("Detect button present:", detect_btn is not None)
            
            print("Page errors logged:", errors)
            await browser.close()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_explorer())
