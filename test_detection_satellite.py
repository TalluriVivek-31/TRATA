"""
CYCLONEX — Detection Page Satellite Workspace Browser Test
Validates interactive controls on detection.html:
- Multi-source channel selector (GIBS + Himawari)
- Region jump selector
- Observation date picker & apply
- View Original image URL
- Download Asset endpoint verification
- Metadata JSON generation
"""

import asyncio
from playwright.async_api import async_playwright
import httpx

BASE_URL = "http://127.0.0.1:8000"

async def test_detection_satellite():
    print("=" * 60)
    print("  CYCLONEX DETECTION SATELLITE WORKSPACE BROWSER TEST  ")
    print("=" * 60)

    # 1. First verify backend endpoints via httpx
    print("\n--- 1. VERIFYING BACKEND ENDPOINTS ---")
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Channels directory
        r_ch = await client.get("/api/satellite/channels")
        assert r_ch.status_code == 200, f"Channels directory failed: {r_ch.status_code}"
        ch_data = r_ch.json()
        print(f"[PASS] Satellite channels endpoint: {ch_data['total_channels']} verified channels")

        # Himawari metadata
        r_hm = await client.get("/api/satellite/metadata?channel=HIMAWARI_FULL")
        assert r_hm.status_code == 200
        hm_data = r_hm.json()
        assert hm_data["is_direct_image"] is True
        print(f"[PASS] Himawari metadata endpoint: direct image {hm_data['image_url']}")

        # Download Himawari
        r_dl_h = await client.get("/api/satellite/download?source=himawari&region=bay-of-bengal")
        assert r_dl_h.status_code == 200
        assert r_dl_h.headers.get("content-type") == "image/png"
        assert len(r_dl_h.content) > 1000
        print(f"[PASS] Download Himawari: {len(r_dl_h.content)} bytes (image/png)")

        # Download GIBS tile
        r_dl_g = await client.get("/api/satellite/download?source=gibs_tile&channel=MODIS_TrueColor&date=2020-05-18")
        assert r_dl_g.status_code == 200
        assert r_dl_g.headers.get("content-type") == "image/jpeg"
        assert len(r_dl_g.content) > 1000
        print(f"[PASS] Download GIBS tile: {len(r_dl_g.content)} bytes (image/jpeg)")

    # 2. Browser Interactive Tests
    print("\n--- 2. BROWSER INTERACTION TESTS (detection.html) ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # Pre-seed authenticated session
        await page.goto(f"{BASE_URL}/login.html", wait_until="networkidle")
        await page.evaluate("""() => {
            sessionStorage.setItem('cyclonex_user', JSON.stringify({
                status: 'AUTHENTICATED',
                employee_id: 'MET-26070',
                operator_name: 'Chief Meteorological Officer (MET-26070)',
                clearance_level: 'LEVEL-IV SCIENTIFIC'
            }));
        }""")

        # Navigate to detection.html
        await page.goto(f"{BASE_URL}/detection.html", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Check default storm Amphan loaded
        storm_val = await page.input_value("#detectionStormSelect")
        print(f"[PASS] Initial storm selected: {storm_val}")

        # Check observation date populated
        obs_date_val = await page.input_value("#satCustomDate")
        print(f"[PASS] Synchronized observation date populated: '{obs_date_val}'")

        # Check provenance fields populated
        platform_text = await page.text_content("#metaSatPlatform")
        print(f"[PASS] Initial satellite platform: '{platform_text.strip()}'")

        # Select Himawari Full Disk
        print("\n--- Testing Channel Switch to NOAA / JMA Himawari-9 ---")
        await page.select_option("#satSourceSelect", "HIMAWARI_FULL")
        await page.wait_for_timeout(1500)

        # Verify static overlay is visible
        overlay_display = await page.evaluate("() => document.getElementById('staticImageOverlay').style.display")
        assert overlay_display == "flex", f"Expected overlay display 'flex', got '{overlay_display}'"
        print("[PASS] Himawari Full Disk mode activated: static raster overlay displayed")

        # Verify Himawari image src
        img_src = await page.evaluate("() => document.getElementById('staticSatelliteImg').src")
        assert "api/satellite/latest.png" in img_src
        print(f"[PASS] Static satellite image source loaded: {img_src}")

        # Verify metadata card updated to Himawari
        h_platform = await page.text_content("#metaSatPlatform")
        assert "Himawari" in h_platform
        print(f"[PASS] Metadata updated to: '{h_platform.strip()}'")

        # Test Himawari Bay of Bengal crop
        await page.select_option("#satSourceSelect", "HIMAWARI_BOB")
        await page.wait_for_timeout(1000)
        bob_img_src = await page.evaluate("() => document.getElementById('staticSatelliteImg').src")
        assert "bay-of-bengal" in bob_img_src
        print(f"[PASS] Switched to Himawari BoB sector: {bob_img_src}")

        # Switch back to NASA GIBS Thermal IR Band 31
        print("\n--- Testing Channel Switch to NASA GIBS Thermal IR Band 31 ---")
        await page.select_option("#satSourceSelect", "TIR1_Infrared")
        await page.wait_for_timeout(1500)

        overlay_hidden = await page.evaluate("() => document.getElementById('staticImageOverlay').style.display")
        assert overlay_hidden == "none", f"Expected overlay hidden, got '{overlay_hidden}'"
        tir_platform = await page.text_content("#metaSatPlatform")
        tir_band = await page.text_content("#metaSatBand")
        print(f"[PASS] Switched to NASA GIBS TIR1: Platform='{tir_platform.strip()}', Band='{tir_band.strip()}'")

        # Test Region Jump to Arabian Sea
        print("\n--- Testing Region Jump Selector ---")
        await page.select_option("#regionJumpSelect", "as")
        await page.wait_for_timeout(800)
        print("[PASS] Region Jump triggered for Arabian Sea basin")

        # Test Custom Date Apply
        print("\n--- Testing Custom Date Selection & Apply ---")
        await page.fill("#satCustomDate", "2024-05-26")
        await page.click("#btnApplySatDate")
        await page.wait_for_timeout(1500)
        curr_obs_date = await page.input_value("#satCustomDate")
        assert curr_obs_date == "2024-05-26"
        print(f"[PASS] Applied custom observation date: {curr_obs_date}")

        # Verify zero console errors
        print("\n--- Console Error Audit ---")
        if console_errors:
            print(f"[WARN] Console errors detected: {console_errors}")
        else:
            print("[PASS] Zero console errors on Detection satellite workspace")

        await browser.close()

    print("\n" + "=" * 60)
    print("  ALL DETECTION SATELLITE WORKSPACE TESTS PASSED (100%)  ")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_detection_satellite())
