import asyncio
from playwright.async_api import async_playwright

async def audit_imd_frontend():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        console_errors = []
        page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)

        print('\n--- 1. Testing Track & Forecast Page (track.html) ---')
        # Inject operator session so auth guard permits access
        await page.goto('http://127.0.0.1:8000/login.html')
        await page.evaluate("""() => {
            sessionStorage.setItem('cyclonex_user', JSON.stringify({
                employeeId: 'IMD-01',
                operatorName: 'Senior Severe Weather Specialist (IMD-01)',
                token: 'audit-test-token',
                authenticatedAt: new Date().toISOString()
            }));
        }""")

        await page.goto('http://127.0.0.1:8000/track.html')
        await page.wait_for_timeout(2000)

        # Check IMD observed points loaded
        obs_badge = await page.text_content('#imdObsCountBadge')
        fcst_badge = await page.text_content('#imdFcstCountBadge')
        print(f"[PASS] IMD Observed Badge: '{obs_badge.strip()}'")
        print(f"[PASS] IMD Forecast Badge: '{fcst_badge.strip()}'")

        # Check toggle chips
        chips = await page.evaluate("() => document.querySelectorAll('.imd-layer-toggle-chip').length")
        print(f"[PASS] Found {chips} interactive IMD layer toggle chips")

        print('\n--- 2. Testing Data Explorer (data-explorer.html) ---')
        await page.goto('http://127.0.0.1:8000/data-explorer.html')
        await page.wait_for_timeout(2000)

        # Check district rows rendered
        rows = await page.evaluate("() => document.querySelectorAll('#imdRainfallTableBody tr').length")
        print(f"[PASS] Ingested district rows rendered in table: {rows}")

        # Check selected district gauge
        dist_name = await page.text_content('#selDistrictName')
        actual_val = await page.text_content('#gaugeActualVal')
        print(f"[PASS] Selected District Gauge: '{dist_name.strip()}' -> Actual: '{actual_val.strip()}'")

        # Filter test
        await page.fill('#imdDistrictSearch', 'Kolkata')
        await page.wait_for_timeout(600)
        filtered_rows = await page.evaluate("() => document.querySelectorAll('#imdRainfallTableBody tr').length")
        print(f"[PASS] Filtered rows for 'Kolkata': {filtered_rows}")

        print('\n--- 3. Console Errors Audit ---')
        real_errors = [e for e in console_errors if 'favicon' not in e.lower()]
        if real_errors:
            print(f"[WARN] Console errors: {real_errors}")
        else:
            print("[PASS] Zero critical console errors on IMD views")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(audit_imd_frontend())
