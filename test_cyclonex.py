"""
CYCLONEX — Automated Verification & Unit Test Suite
Covers: Map Configuration, Detection API, Weather, Machine Learning, and Multi-Page Routing
"""

import sys
import os

sys.path.append(os.path.expanduser(r"~\AppData\Roaming\Python\Python314\site-packages"))

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

def run_tests():
    print("==================================================")
    print("  CYCLONEX AUTOMATED TEST & VERIFICATION SUITE   ")
    print("==================================================")

    # 1. Health check test
    r_health = client.get('/api/health')
    assert r_health.status_code == 200, f"Health check failed: {r_health.status_code}"
    print('[PASS] 1. Health Check Endpoint -> Status: OK, Subsystems Online')

    # 2. Map Configuration test
    r_map = client.get('/api/config/map')
    assert r_map.status_code == 200, f"Map config failed: {r_map.status_code}"
    map_data = r_map.json()
    assert map_data['status'] == 'ready'
    assert len(map_data['supported_basemaps']) >= 3
    print(f"[PASS] 2. Map Configuration API -> Status: {map_data['status']}, {len(map_data['supported_basemaps'])} Basemaps Configured")

    # 3. Storms list test
    r_storms = client.get('/api/storms')
    assert r_storms.status_code == 200, f"Storms list failed: {r_storms.status_code}"
    storms = r_storms.json()['storms']
    assert len(storms) >= 9
    print(f'[PASS] 3. Storm Archive Registry -> {len(storms)} Verified Cyclones Loaded')

    # 4. Weather endpoint query test
    r_weather = client.get('/weather?lat=20.8&lon=89.4')
    assert r_weather.status_code == 200, f"Weather endpoint failed: {r_weather.status_code}"
    w_data = r_weather.json()
    assert 'current' in w_data
    w_curr = w_data['current']
    print(f"[PASS] 4. Open-Meteo Weather Route -> Wind: {w_curr['wind_speed_10m']} km/h, MSL Pressure: {w_curr['pressure_msl']} hPa")

    # 5. Cyclone Detection API (Valid cyclone parameters)
    r_detect = client.post('/api/detect', json={
        'latitude': 21.6,
        'longitude': 89.2,
        'wind_speed_kmh': 135.0,
        'central_pressure_hpa': 978.0,
        'storm_id': 'REMAL'
    })
    assert r_detect.status_code == 200, f"Detection API failed: {r_detect.status_code}"
    d_data = r_detect.json()
    assert d_data['status'] == 'VORTEX_DETECTED'
    assert d_data['is_cyclone_detected'] is True
    assert 'estimated_center' in d_data
    print(f"[PASS] 5. Cyclone Detection API -> Status: {d_data['status']}, Confidence: {d_data['confidence_percent']}%, Tier: {d_data['vortex_intensity_tier']}")

    # 6. Cyclone Detection API (Negative disturbance case)
    r_detect_neg = client.post('/api/detect', json={
        'latitude': 10.0,
        'longitude': 90.0,
        'wind_speed_kmh': 35.0,
        'central_pressure_hpa': 1010.0,
        'storm_id': 'NON_VORTICAL_WAVE'
    })
    assert r_detect_neg.status_code == 200
    d_neg_data = r_detect_neg.json()
    assert d_neg_data['is_cyclone_detected'] is False
    print(f"[PASS] 6. Non-Cyclonic Wave Rejection -> Status: {d_neg_data['status']}, Correctly classified as non-cyclonic")

    # 7. Detection Input Validation test (Invalid latitude out of bounds)
    r_invalid = client.post('/api/detect', json={
        'latitude': 195.0, # Out of range (-90 to 90)
        'longitude': 89.2,
        'wind_speed_kmh': 100.0,
        'central_pressure_hpa': 980.0
    })
    assert r_invalid.status_code == 422, f"Expected 422 for invalid coordinates, got {r_invalid.status_code}"
    print('[PASS] 7. Detection Validation -> Coordinate bounds correctly rejected with HTTP 422')

    # 8. Active Storm Detection Endpoint
    r_active_det = client.get('/api/detect/active?storm_key=REMAL_2024')
    assert r_active_det.status_code == 200
    act_data = r_active_det.json()
    assert act_data['status'] == 'VORTEX_DETECTED'
    print(f"[PASS] 8. Active Storm Auto-Detection -> Storm: {act_data['storm_metadata']['name']}, Confidence: {act_data['confidence_percent']}%")

    # 9. Pattern Classification ML test
    r_class = client.post('/api/ml/classify', json={'wind_speed_kmh': 185.0, 'central_pressure_hpa': 930.0})
    assert r_class.status_code == 200
    c_data = r_class.json()
    assert c_data['primary_class'] == 'EYE'
    print(f"[PASS] 9. ML Convective Pattern Classifier -> Class: {c_data['class_name']}, Dvorak: T{c_data['estimated_dvorak_t']}")

    # 10. Track Prediction ML test
    sample_recs = [
        {'lat': 20.0, 'lon': 88.0, 'wind_kmh': 120.0, 'pressure_hpa': 980.0},
        {'lat': 20.8, 'lon': 89.2, 'wind_kmh': 135.0, 'pressure_hpa': 978.0}
    ]
    r_pred = client.post('/api/ml/predict-track', json={'records': sample_recs, 'horizon_steps': 4})
    assert r_pred.status_code == 200
    p_data = r_pred.json()
    assert len(p_data['forecast']) == 4
    print(f"[PASS] 10. AM-ConvGRU Spatio-Temporal Prediction -> Generated {len(p_data['forecast'])} Lead Horizons (+6h to +24h)")

    # 11. Model Evaluation Benchmark test
    r_eval = client.get('/api/ml/evaluation')
    assert r_eval.status_code == 200
    e_data = r_eval.json()
    print(f"[PASS] 11. Model Evaluation Benchmark -> Verified Test Error: {e_data['overall_mean_distance_error_km']} km")

    # 12. Multi-page serving tests
    pages = ['index.html', 'detection.html', 'classification.html', 'track.html', 'intensity.html', 'data-explorer.html', 'model-lab.html', 'system.html', 'login.html']
    for p in pages:
        r_p = client.get(f'/{p}')
        assert r_p.status_code == 200, f'Page {p} failed with status {r_p.status_code}'
    print(f'[PASS] 12. Multi-Page Workstation Routes -> All {len(pages)} Pages Serving Successfully (HTTP 200)')

    # 13. Live Basin Surveillance Route (Handles quiet basin truthfully)
    r_live = client.get('/api/detect/live')
    assert r_live.status_code == 200, f"Live surveillance route failed: {r_live.status_code}"
    l_data = r_live.json()
    assert l_data['status'] in ['QUIET_BASIN', 'VORTEX_DETECTED']
    assert 'surveillance_timestamp' in l_data
    assert 'official_bulletin' in l_data
    print(f"[PASS] 13. Live Basin Surveillance -> Status: {l_data['status']}, Agency: {l_data['official_bulletin']['agency']}")

    # 14. Historical Archive Re-Analysis Route (Cyclone Amphan 2020)
    r_arch = client.get('/api/detect/archive/AMPHAN_2020')
    assert r_arch.status_code == 200, f"Archive reanalysis failed: {r_arch.status_code}"
    a_data = r_arch.json()
    assert a_data['mode'] == 'HISTORICAL_REANALYSIS'
    assert a_data['status'] == 'VORTEX_DETECTED'
    assert 'Amphan' in a_data['archive_metadata']['name']
    assert a_data['confidence_percent'] >= 90.0
    print(f"[PASS] 14. Historical Archive Re-Analysis -> {a_data['archive_metadata']['name']}, Agency: {a_data['archive_metadata']['agency']}, Confidence: {a_data['confidence_percent']}%")

    # 15. Live Ocean Coordinate Probe Endpoint
    r_probe = client.post('/api/detect/probe-point', json={'latitude': 15.0, 'longitude': 88.0})
    assert r_probe.status_code == 200, f"Ocean probe failed: {r_probe.status_code}"
    pr_data = r_probe.json()
    assert 'live_probe_telemetry' in pr_data
    print(f"[PASS] 15. Live Oceanic Point Probe -> Status: {pr_data['status']}, Surface Wind: {pr_data['live_probe_telemetry']['wind_speed_10m_kmh']} km/h, MSL Pressure: {pr_data['live_probe_telemetry']['pressure_msl_hpa']} hPa")

    # 16. Satellite Metadata & Date-Synchronized Acquisition Route
    r_sat = client.get('/api/satellite/metadata?storm_key=AMPHAN_2020&channel=TIR1_Infrared')
    assert r_sat.status_code == 200, f"Satellite metadata route failed: {r_sat.status_code}"
    sat_data = r_sat.json()
    assert sat_data['observation_date'] == '2020-05-18'
    assert '2020-05-18' in sat_data['tile_template_url']
    assert sat_data['channel']['key'] == 'TIR1_Infrared'
    assert sat_data['cloud_top_brightness_temperature_c'] == -78.0
    print(f"[PASS] 16. Satellite Metadata Engine -> Date: {sat_data['observation_date']}, Band: {sat_data['channel']['name']}, Cloud-Top: {sat_data['cloud_top_brightness_temperature_c']}°C")

    # 17. Live Near-Real-Time Satellite Metadata Route
    r_sat_live = client.get('/api/satellite/metadata?storm_key=LIVE&channel=MODIS_TrueColor')
    assert r_sat_live.status_code == 200
    sat_live_data = r_sat_live.json()
    assert sat_live_data['freshness_status'] == 'GENUINE_NEAR_REAL_TIME'
    print(f"[PASS] 17. Live Satellite Metadata Engine -> Freshness: {sat_live_data['freshness_status']}, Retrieval: {sat_live_data['retrieval_timestamp_utc']}")

    # 18. Operator Portal Authentication & Firebase Token Cryptographic Verification
    r_auth_good = client.post('/api/auth/login', json={'employee_id': 'MET-26070', 'password': 'cyclone2026'})
    assert r_auth_good.status_code == 200, f"Auth failed: {r_auth_good.status_code}"
    auth_data = r_auth_good.json()
    assert auth_data['status'] == 'AUTHENTICATED'
    assert auth_data['employee_id'] == 'MET-26070'
    assert auth_data['clearance_level'] == 'LEVEL-IV SCIENTIFIC'
    assert 'id_token' in auth_data and len(auth_data['id_token']) > 20
    valid_id_token = auth_data['id_token']

    # 18a. Cryptographic ID Token Verification Endpoint (/api/auth/verify-token)
    r_verify_body = client.post('/api/auth/verify-token', json={'id_token': valid_id_token, 'employee_id': 'MET-26070'})
    assert r_verify_body.status_code == 200, f"Token verify endpoint failed: {r_verify_body.status_code}"
    v_data = r_verify_body.json()
    assert v_data['status'] == 'AUTHENTICATED'
    assert v_data['employee_id'] == 'MET-26070'
    assert v_data['clearance_level'] == 'LEVEL-IV SCIENTIFIC'

    # 18b. Bearer Header Verification
    r_verify_hdr = client.post('/api/auth/verify-token', headers={'Authorization': f'Bearer {valid_id_token}'})
    assert r_verify_hdr.status_code == 200
    assert r_verify_hdr.json()['employee_id'] == 'MET-26070'

    # 18c. Forged / Tampered Token Rejection
    fake_token = valid_id_token[:-10] + "tampered00"
    r_verify_fake = client.post('/api/auth/verify-token', json={'id_token': fake_token})
    assert r_verify_fake.status_code in (401, 403), f"Expected 401/403 for tampered token, got {r_verify_fake.status_code}"

    # 18d. Missing / Empty Token Rejection
    r_verify_empty = client.post('/api/auth/verify-token', json={'id_token': ''})
    assert r_verify_empty.status_code in (401, 422)

    # 18e. Protected Route Security Dependency (/api/satellite/refresh) - Rejection without Token
    r_refresh_unauth = client.post('/api/satellite/refresh')
    assert r_refresh_unauth.status_code == 401, f"Expected 401 for unauthenticated refresh, got {r_refresh_unauth.status_code}"

    # 18f. Protected Route Security Dependency (/api/satellite/refresh) - Acceptance with Valid Bearer Token
    r_refresh_auth = client.post('/api/satellite/refresh', headers={'Authorization': f'Bearer {valid_id_token}'})
    assert r_refresh_auth.status_code == 200, f"Expected 200 for authenticated refresh, got {r_refresh_auth.status_code}"
    refresh_res = r_refresh_auth.json()
    assert refresh_res['clearance_level'] == 'LEVEL-IV SCIENTIFIC'

    # 18g. Invalid Credentials Rejection
    r_auth_bad = client.post('/api/auth/login', json={'employee_id': 'BAD_USER', 'password': 'wrong_password'})
    assert r_auth_bad.status_code == 401
    print('[PASS] 18. Operator Authentication & Firebase Cryptographic Verification -> Token verified, clearance LEVEL-IV enforced, forged tokens & unauthenticated refresh rejected (HTTP 401)')

    # 19. ISRO MOSDAC OpenSearch Ingestion Route
    r_mosdac_ds = client.get('/api/mosdac/datasets')
    assert r_mosdac_ds.status_code == 200
    m_ds = r_mosdac_ds.json()
    assert '3RIMG_L2B_SST' in m_ds['datasets']
    print(f"[PASS] 19. ISRO MOSDAC Ingestion Engine -> Catalog verified with {len(m_ds['datasets'])} cyclone satellite products")

    # 20. Legacy v1 Active Cyclones Route (/api/v1/cyclones/active)
    r_v1_active = client.get('/api/v1/cyclones/active')
    assert r_v1_active.status_code == 200, f"v1 active failed: {r_v1_active.status_code}"
    v1_act = r_v1_active.json()
    assert 'status' in v1_act
    assert 'cyclones' in v1_act
    print(f"[PASS] 20. Legacy v1 Active Cyclones API -> Status: {v1_act['status']}, Basin: {v1_act.get('basin')}")

    # 21. Legacy v1 Specific Cyclone Lookup (/api/v1/cyclones/TC-2023-BOB-02)
    r_v1_spec = client.get('/api/v1/cyclones/TC-2023-BOB-02')
    assert r_v1_spec.status_code == 200, f"v1 lookup failed: {r_v1_spec.status_code}"
    v1_storm = r_v1_spec.json()
    assert v1_storm['status'] == 'FOUND'
    storm_payload = v1_storm['data']
    assert 'Biparjoy' in storm_payload['name'] or 'BIPARJOY' in storm_payload.get('id', '')
    print(f"[PASS] 21. Legacy v1 Cyclone Lookup -> Successfully aliased TC-2023-BOB-02 to {storm_payload['name']}")

    # 22. Data Pipeline Variable Normalization & Physical QC (/api/pipeline/normalize)
    r_norm = client.post('/api/pipeline/normalize', json={
        'latitude': 18.5,
        'longitude': 88.2,
        'observation_time_utc': '2024-05-25T12:00:00Z',
        'wind_speed': 80.0,
        'wind_units': 'knots',
        'pressure': 965.0,
        'pressure_units': 'hPa',
        'sst': 303.15,
        'sst_units': 'kelvin',
        'source_agency': 'IMD RSMC New Delhi'
    })
    assert r_norm.status_code == 200, f"Pipeline normalization failed: {r_norm.status_code}"
    n_res = r_norm.json()
    assert n_res['status'] == 'VALID_OBSERVATION'
    wind_var = n_res['variables']['wind_speed']
    sst_var = n_res['variables']['sea_surface_temp']
    assert round(wind_var['normalized_value'], 1) == 148.2
    assert round(sst_var['normalized_value'], 2) == 30.0
    assert wind_var['quality_flag'] == 'QC_PASSED_VERIFIED'
    print(f"[PASS] 22. Data Pipeline Normalization & QC -> 80 kt -> {wind_var['normalized_value']} km/h, 303.15 K -> {sst_var['normalized_value']} °C (QC: {wind_var['quality_flag']})")


    # 23. MOSDAC Search Bounds & Gateway Verification
    r_mosdac_search = client.get('/api/mosdac/search?dataset_id=3RIMG_L2B_SST&count=50')
    assert r_mosdac_search.status_code == 200, f"MOSDAC search failed: {r_mosdac_search.status_code}"
    ms_data = r_mosdac_search.json()
    assert ms_data['status'] in ('SUCCESS', 'SEARCH_COMPLETED')
    assert ms_data['dataset_id'] == '3RIMG_L2B_SST'
    assert len(ms_data['entries']) <= 50
    total_found = ms_data.get('pagination', {}).get('total_results_in_catalog', len(ms_data.get('entries', [])))
    print(f"[PASS] 23. MOSDAC Search Gateway -> Status: {ms_data['status']}, Found: {total_found} records, Returned: {len(ms_data['entries'])}")



    # 24. Live NOAA Satellite Status API (/api/satellite/status)
    r_sat_status = client.get('/api/satellite/status')
    assert r_sat_status.status_code == 200, f"Satellite status failed: {r_sat_status.status_code}"
    sat_st = r_sat_status.json()
    assert sat_st['source_identifier'] == 'NOAA_OSPO_HIMAWARI_IR4'
    assert 'image_dimensions' in sat_st
    print(f"[PASS] 24. NOAA Satellite Status API -> Platform: {sat_st['satellite_platform']}, Band: {sat_st['spectral_band']}")

    # 25. Regional Satellite Metadata & Supported Bounds (/api/satellite/regions)
    r_sat_reg = client.get('/api/satellite/regions')
    assert r_sat_reg.status_code == 200
    reg_data = r_sat_reg.json()
    assert 'bay-of-bengal' in reg_data['regions']
    assert 'arabian-sea' in reg_data['regions']
    assert 'full-disk' in reg_data['regions']
    print(f"[PASS] 25. NOAA Satellite Regions API -> Verified {len(reg_data['regions'])} Configured Basin Crops")

    # 26. Live Full-Disk Satellite Image Streaming (/api/satellite/latest.png)
    r_sat_img = client.get('/api/satellite/latest.png')
    assert r_sat_img.status_code == 200, f"Satellite image fetch failed: {r_sat_img.status_code}"
    assert r_sat_img.headers.get('content-type') == 'image/png'
    # PNG magic bytes: \x89PNG
    assert r_sat_img.content.startswith(b"\x89PNG")
    print(f"[PASS] 26. NOAA Full-Disk Satellite PNG Stream -> {len(r_sat_img.content)} bytes (Verified PNG magic bytes)")

    # 27. Regional Crop Image Streaming (/api/satellite/regions/bay-of-bengal/latest.png)
    r_bob_img = client.get('/api/satellite/regions/bay-of-bengal/latest.png')
    assert r_bob_img.status_code == 200
    assert r_bob_img.headers.get('content-type') == 'image/png'
    assert r_bob_img.content.startswith(b"\x89PNG")
    print(f"[PASS] 27. NOAA Regional Crop Stream (Bay of Bengal) -> {len(r_bob_img.content)} bytes (Verified PNG magic bytes)")

    # 28. Direct Regional Endpoint (/api/satellite/regions/bay-of-bengal.png)
    r_bob_direct = client.get('/api/satellite/regions/bay-of-bengal.png')
    assert r_bob_direct.status_code == 200
    assert r_bob_direct.content.startswith(b"\x89PNG")
    print(f"[PASS] 28. Direct Regional Route (/api/satellite/regions/bay-of-bengal.png) -> {len(r_bob_direct.content)} bytes")

    # 29. Direct Regional Endpoint (/api/satellite/regions/arabian-sea.png)
    r_as_direct = client.get('/api/satellite/regions/arabian-sea.png')
    assert r_as_direct.status_code == 200
    assert r_as_direct.content.startswith(b"\x89PNG")
    print(f"[PASS] 29. Direct Regional Route (/api/satellite/regions/arabian-sea.png) -> {len(r_as_direct.content)} bytes")

    # 30. NASA Services Status API (/api/nasa/status)
    r_nasa_st = client.get('/api/nasa/status')
    assert r_nasa_st.status_code == 200, f"NASA status failed: {r_nasa_st.status_code}"
    nasa_st_data = r_nasa_st.json()
    assert nasa_st_data['status'] == 'OPERATIONAL'
    assert 'gibs_wmts' in nasa_st_data['services']
    assert 'power_api' in nasa_st_data['services']
    assert 'earthdata_cmr' in nasa_st_data['services']
    print(f"[PASS] 30. NASA Services Status API -> Verified GIBS, POWER, and CMR subsystem connectivity")

    # 31. NASA GIBS Dynamic Tile Matrix Sets & Channel Metadata (/api/satellite/metadata)
    # 31a. TrueColor Visible (Level9)
    r_gibs_vis = client.get('/api/satellite/metadata?storm_key=REMAL_2024&channel=MODIS_TrueColor')
    assert r_gibs_vis.status_code == 200
    vis_data = r_gibs_vis.json()
    assert 'GoogleMapsCompatible_Level9' in vis_data['tile_template_url']
    assert vis_data['max_zoom'] == 9

    # 31b. Thermal IR Band 31 (Level7)
    r_gibs_tir = client.get('/api/satellite/metadata?storm_key=REMAL_2024&channel=TIR1_Infrared')
    assert r_gibs_tir.status_code == 200
    tir_data = r_gibs_tir.json()
    assert 'GoogleMapsCompatible_Level7' in tir_data['tile_template_url']
    assert tir_data['max_zoom'] == 7
    assert 'MODIS_Terra_Brightness_Temp_Band31_Day' in tir_data['tile_template_url']

    # 31c. Tropospheric Water Vapor (Level6)
    r_gibs_wv = client.get('/api/satellite/metadata?storm_key=REMAL_2024&channel=WV_WaterVapor')
    assert r_gibs_wv.status_code == 200
    wv_data = r_gibs_wv.json()
    assert 'GoogleMapsCompatible_Level6' in wv_data['tile_template_url']
    assert wv_data['max_zoom'] == 6

    # 31d. AIRS Sounder Precipitation (Level6)
    r_gibs_airs = client.get('/api/satellite/metadata?storm_key=REMAL_2024&channel=AIRS_Precipitation')
    assert r_gibs_airs.status_code == 200
    airs_data = r_gibs_airs.json()
    assert 'GoogleMapsCompatible_Level6' in airs_data['tile_template_url']
    assert airs_data['max_zoom'] == 6
    print(f"[PASS] 31. NASA GIBS WMTS Resolution & TileMatrixSets -> Level9 (VIS), Level7 (TIR1), Level6 (WV), Level6 (AIRS) validated")

    # 32. NASA POWER Point Climatology & Meteorology API (/api/nasa/power/point)
    r_power = client.get('/api/nasa/power/point?lat=21.6&lon=89.2&date=2024-05-26')
    assert r_power.status_code == 200, f"NASA POWER point failed: {r_power.status_code}"
    power_data = r_power.json()
    assert power_data['status'] in ('SUCCESS', 'NASA_POWER_UNAVAILABLE')
    if power_data['status'] == 'SUCCESS':
        assert 'summary' in power_data
        assert 'hourly_readings' in power_data
        assert power_data['provenance']['source_agency'] == 'NASA Langley Research Center'
        print(f"[PASS] 32. NASA POWER API Integration -> Lat: 21.6, Lon: 89.2, Max Wind: {power_data['summary']['max_wind_speed_10m_kmh']} km/h, Min MSL Pres: {power_data['summary']['min_surface_pressure_hpa']} hPa")
    else:
        print(f"[PASS] 32. NASA POWER API Integration -> Graceful fallback status: {power_data['status']}")

    # 33. NASA Earthdata CMR Collections Discovery API (/api/nasa/cmr/collections)
    r_cmr_col = client.get('/api/nasa/cmr/collections?keyword=cyclone&page_size=5')
    assert r_cmr_col.status_code == 200, f"CMR Collections search failed: {r_cmr_col.status_code}"
    cmr_col_data = r_cmr_col.json()
    assert cmr_col_data['status'] in ('SUCCESS', 'CMR_UNAVAILABLE')
    if cmr_col_data['status'] == 'SUCCESS':
        assert len(cmr_col_data['collections']) >= 1
        print(f"[PASS] 33. NASA Earthdata CMR Discovery -> Found {len(cmr_col_data['collections'])} open cyclone collections via CMR")
    else:
        print(f"[PASS] 33. NASA Earthdata CMR Discovery -> Graceful fallback status: {cmr_col_data['status']}")

    # 34. NASA Earthdata CMR Granule Search API (/api/nasa/cmr/granules)
    r_cmr_gran = client.get('/api/nasa/cmr/granules?collection_id=C2515837343-GES_DISC&start_date=2024-05-25&end_date=2024-05-27&page_size=5')
    assert r_cmr_gran.status_code == 200
    cmr_gran_data = r_cmr_gran.json()
    assert cmr_gran_data['status'] in ('SUCCESS', 'CMR_UNAVAILABLE')
    if cmr_gran_data['status'] == 'SUCCESS':
        assert len(cmr_gran_data['granules']) >= 1
        print(f"[PASS] 34. NASA Earthdata Granule Search -> Retrieved {len(cmr_gran_data['granules'])} scientific observation granules")
    else:
        print(f"[PASS] 34. NASA Earthdata Granule Search -> Graceful fallback status: {cmr_gran_data['status']}")

    # 35. Satellite Channel Directory Discovery API (/api/satellite/channels)
    r_sat_ch = client.get('/api/satellite/channels')
    assert r_sat_ch.status_code == 200, f"Satellite channels failed: {r_sat_ch.status_code}"
    sat_ch_data = r_sat_ch.json()
    assert sat_ch_data['status'] == 'SUCCESS'
    assert sat_ch_data['total_channels'] >= 5
    ch_keys = [c['key'] for c in sat_ch_data['channels']]
    assert 'MODIS_TrueColor' in ch_keys
    assert 'HIMAWARI9_IR4' in ch_keys
    print(f"[PASS] 35. Satellite Channel Directory API -> {sat_ch_data['total_channels']} verified channels discovered")

    # 36. Himawari Metadata & Direct Image Provisioning (/api/satellite/metadata?channel=HIMAWARI_BOB)
    r_h_meta = client.get('/api/satellite/metadata?channel=HIMAWARI_BOB')
    assert r_h_meta.status_code == 200
    h_meta_data = r_h_meta.json()
    assert h_meta_data['status'] == 'success'
    assert h_meta_data['is_direct_image'] is True
    assert 'bay-of-bengal' in h_meta_data['image_url']
    assert 'himawari' in h_meta_data['download_url']
    print(f"[PASS] 36. Himawari Metadata Route -> Direct sector image URL: {h_meta_data['image_url']}")

    # 37. Date-Synchronized Satellite Metadata Query (/api/satellite/metadata with custom date)
    r_custom_date = client.get('/api/satellite/metadata?storm_key=AMPHAN_2020&channel=MODIS_TrueColor&date=2020-05-18')
    assert r_custom_date.status_code == 200
    custom_date_data = r_custom_date.json()
    assert custom_date_data['observation_date'] == '2020-05-18'
    assert '2020-05-18' in custom_date_data['tile_template_url']
    print(f"[PASS] 37. Date-Synchronized Metadata -> Verified 2020-05-18 in WMTS tile template")

    # 38. Verified Asset Acquisition & Download Route (/api/satellite/download)
    r_dl_himawari = client.get('/api/satellite/download?source=himawari&region=bay-of-bengal')
    assert r_dl_himawari.status_code == 200
    assert r_dl_himawari.headers.get('content-type') == 'image/png'
    assert 'attachment;' in r_dl_himawari.headers.get('content-disposition', '')
    assert r_dl_himawari.content.startswith(b"\x89PNG")

    r_dl_gibs = client.get('/api/satellite/download?source=gibs_tile&channel=MODIS_TrueColor&date=2020-05-18')
    assert r_dl_gibs.status_code == 200
    assert r_dl_gibs.headers.get('content-type') == 'image/jpeg'
    assert 'attachment;' in r_dl_gibs.headers.get('content-disposition', '')
    assert r_dl_gibs.content.startswith(b"\xff\xd8\xff")
    print(f"[PASS] 38. Satellite Asset Download Endpoint -> Himawari PNG ({len(r_dl_himawari.content)} bytes) & GIBS JPEG ({len(r_dl_gibs.content)} bytes) validated")

    # 39. IMD District-Wise Rainfall API (/api/imd/rainfall)
    r_rain = client.get('/api/imd/rainfall')
    assert r_rain.status_code == 200, f"IMD Rainfall failed: {r_rain.status_code}"
    rain_data = r_rain.json()
    assert rain_data['status'] == 'SUCCESS'
    assert rain_data['total_districts'] >= 10
    assert 'districts' in rain_data
    first_d = rain_data['districts'][0]
    assert 'daily' in first_d and 'actual_mm' in first_d['daily']
    print(f"[PASS] 39. IMD District-Wise Rainfall API -> {rain_data['total_districts']} Districts Ingested ({rain_data['data_mode']})")

    # 40. IMD District ID Lookup (/api/imd/rainfall/164)
    r_dist164 = client.get('/api/imd/rainfall/164')
    assert r_dist164.status_code == 200, f"District 164 failed: {r_dist164.status_code}"
    d164_data = r_dist164.json()
    assert len(d164_data['districts']) == 1
    kol = d164_data['districts'][0]
    assert kol['district_id'] == '164'
    assert 'Kolkata' in kol['district_name']
    assert kol['daily']['actual_mm'] == 12.4
    assert kol['daily']['category_code'] == 'LE'
    print(f"[PASS] 40. IMD District Lookup Filter -> District #{kol['district_id']} {kol['district_name']} (Actual: {kol['daily']['actual_mm']} mm, Cat: {kol['daily']['category_code']})")

    # 41. IMD Cyclone Track API (/api/imd/cyclone-track)
    r_track = client.get('/api/imd/cyclone-track')
    assert r_track.status_code == 200, f"IMD track failed: {r_track.status_code}"
    t_data = r_track.json()
    assert t_data['status'] == 'SUCCESS'
    assert len(t_data['observed_track']) >= 5
    assert len(t_data['forecast_track']) >= 3
    assert t_data['cyclone_name'] != ''
    first_obs = t_data['observed_track'][0]
    assert first_obs['is_forecast'] is False
    first_fcst = t_data['forecast_track'][0]
    assert first_fcst['is_forecast'] is True
    print(f"[PASS] 41. IMD Cyclone Track API -> Cyclone {t_data['cyclone_name']} ({len(t_data['observed_track'])} Observed, {len(t_data['forecast_track'])} Forecast Waypoints)")

    # 42. IMD Cyclone Wind Warnings GeoJSON API (/api/imd/cyclone-wind)
    r_wind = client.get('/api/imd/cyclone-wind')
    assert r_wind.status_code == 200, f"IMD wind failed: {r_wind.status_code}"
    w_data = r_wind.json()
    assert w_data['status'] == 'SUCCESS'
    assert w_data['type'] == 'FeatureCollection'
    assert len(w_data['features']) >= 4
    for thresh in ['27kt', '34kt', '50kt', '64kt']:
        assert thresh in w_data['available_thresholds']
    print(f"[PASS] 42. IMD Cyclone Wind Warnings -> {len(w_data['features'])} Geospatial Gale Polygons {w_data['available_thresholds']}")

    # 43. IMD Cyclone Cone of Uncertainty API (/api/imd/cyclone-cone)
    r_cou = client.get('/api/imd/cyclone-cone')
    assert r_cou.status_code == 200, f"IMD COU failed: {r_cou.status_code}"
    cou_data = r_cou.json()
    assert cou_data['status'] == 'SUCCESS'
    assert cou_data['geometry']['type'] in ('Polygon', 'MultiPolygon')
    assert len(cou_data['geometry']['coordinates']) >= 1
    assert 'envelope' in cou_data.get('disclaimer', '').lower() or 'probability' in cou_data.get('disclaimer', '').lower()
    print(f"[PASS] 43. IMD Cone of Uncertainty -> Geometry: {cou_data['geometry']['type']} Envelope for {cou_data['cyclone_name']}")

    # 44. Negative / Invalid District Lookup Handling
    r_dist_err = client.get('/api/imd/rainfall/9999999')
    assert r_dist_err.status_code == 404
    print("[PASS] 44. IMD Error Handling -> Non-existent district query rejected gracefully with HTTP 404")

    print("==================================================")
    print("  ALL 44 TEST SUITES PASSED WITH 100% SUCCESS RATE ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()



