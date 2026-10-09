"""
CYCLONEX — NASA Scientific Data Ingestion & Integration Client
Integrates:
1. NASA POWER API (Hourly/Daily Atmospheric Climatology & Meteorology)
2. NASA Earthdata CMR (Common Metadata Repository Discovery for AIRS, CYGNSS, MODIS)
Provides resilient querying, rate-limit/timeout handling, schema validation, and unit normalization.
"""

import os
import time
import httpx
from typing import Dict, Any, Optional, List

NASA_POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal"
NASA_CMR_BASE_URL = "https://cmr.earthdata.nasa.gov/search"

# Cache memory with TTL (15 minutes)
_NASA_POWER_CACHE: Dict[str, Dict[str, Any]] = {}
_NASA_CMR_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 900

class NasaClient:
    """Client for NASA open scientific data APIs (POWER and Earthdata CMR)."""

    def __init__(self):
        self.power_base_url = NASA_POWER_BASE_URL
        self.cmr_base_url = NASA_CMR_BASE_URL
        self.earthdata_user = os.environ.get("EARTHDATA_USERNAME", "")
        self.earthdata_pass = os.environ.get("EARTHDATA_PASSWORD", "")
        self.earthdata_token = os.environ.get("EARTHDATA_BEARER_TOKEN", "")

    def get_auth_status(self) -> Dict[str, Any]:
        """Reports Earthdata authentication configuration without revealing secrets."""
        has_token = bool(self.earthdata_token and self.earthdata_token != "your_earthdata_token_here")
        has_creds = bool(self.earthdata_user and self.earthdata_pass)
        return {
            "has_bearer_token": has_token,
            "has_user_credentials": has_creds,
            "auth_configured": has_token or has_creds,
            "auth_provider": "NASA Earthdata Login (URS)",
            "public_services_available": True,
            "protected_granule_download_available": has_token or has_creds,
            "documentation_url": "https://urs.earthdata.nasa.gov"
        }

    # -------------------------------------------------------------------------
    # 1. NASA POWER API (Atmospheric & Meteorological Observations)
    # -------------------------------------------------------------------------
    async def fetch_power_point_meteorology(
        self,
        latitude: float,
        longitude: float,
        date_str: str,
        temporal: str = "hourly"
    ) -> Dict[str, Any]:
        """
        Retrieves real atmospheric parameters from NASA POWER API:
        - T2M: 2-meter air temperature (°C)
        - RH2M: 2-meter relative humidity (%)
        - PS: Surface barometric pressure (kPa, converted to hPa)
        - WS10M: 10-meter wind speed (m/s, converted to km/h)
        - WS50M: 50-meter wind speed (m/s, converted to km/h)
        """
        # Validate coordinates
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            return {
                "status": "INVALID_COORDINATES",
                "message": f"Coordinates out of bounds: lat={latitude}, lon={longitude}"
            }

        # Format date for NASA POWER (YYYYMMDD)
        clean_date = date_str.replace("-", "").strip()[:8]
        cache_key = f"power_{latitude:.2f}_{longitude:.2f}_{clean_date}_{temporal}"

        now = time.time()
        if cache_key in _NASA_POWER_CACHE:
            entry = _NASA_POWER_CACHE[cache_key]
            if now - entry["cached_at"] < CACHE_TTL_SECONDS:
                cached_data = dict(entry["data"])
                cached_data["cache_hit"] = True
                return cached_data

        url = f"{self.power_base_url}/{temporal}/point"
        params = {
            "parameters": "T2M,RH2M,PS,WS10M,WS50M",
            "community": "RE",
            "longitude": f"{longitude:.4f}",
            "latitude": f"{latitude:.4f}",
            "start": clean_date,
            "end": clean_date,
            "format": "JSON"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, params=params)
                if res.status_code != 200:
                    return {
                        "status": "NASA_POWER_ERROR",
                        "http_status": res.status_code,
                        "message": f"NASA POWER API returned HTTP {res.status_code}",
                        "error_detail": res.text[:200]
                    }

                payload = res.json()
                props = payload.get("properties", {})
                param_data = props.get("parameter", {})

                # Extract time series
                t2m_dict = param_data.get("T2M", {})
                rh2m_dict = param_data.get("RH2M", {})
                ps_dict = param_data.get("PS", {})
                ws10m_dict = param_data.get("WS10M", {})
                ws50m_dict = param_data.get("WS50M", {})

                # Build parsed observation readings
                readings = []
                for ts_key in sorted(t2m_dict.keys()):
                    t2m = t2m_dict.get(ts_key)
                    rh = rh2m_dict.get(ts_key)
                    ps_kpa = ps_dict.get(ts_key)
                    ws10_ms = ws10m_dict.get(ts_key)
                    ws50_ms = ws50m_dict.get(ts_key)

                    # Handle fill values (-999 or -9999)
                    if t2m in (-999, -9999, None): t2m = None
                    if rh in (-999, -9999, None): rh = None
                    if ps_kpa in (-999, -9999, None): ps_hpa = None
                    else: ps_hpa = round(ps_kpa * 10.0, 1)  # 1 kPa = 10 hPa

                    if ws10_ms in (-999, -9999, None): ws10_kmh = None
                    else: ws10_kmh = round(ws10_ms * 3.6, 1)  # 1 m/s = 3.6 km/h

                    if ws50_ms in (-999, -9999, None): ws50_kmh = None
                    else: ws50_kmh = round(ws50_ms * 3.6, 1)

                    readings.append({
                        "hour_utc": ts_key[-2:] if len(ts_key) >= 10 else ts_key,
                        "timestamp_raw": ts_key,
                        "temperature_2m_c": t2m,
                        "relative_humidity_percent": rh,
                        "surface_pressure_hpa": ps_hpa,
                        "wind_speed_10m_kmh": ws10_kmh,
                        "wind_speed_50m_kmh": ws50_kmh
                    })

                # Compute representative mean values (excluding missing values)
                valid_winds = [r["wind_speed_10m_kmh"] for r in readings if r["wind_speed_10m_kmh"] is not None]
                valid_press = [r["surface_pressure_hpa"] for r in readings if r["surface_pressure_hpa"] is not None]
                valid_temps = [r["temperature_2m_c"] for r in readings if r["temperature_2m_c"] is not None]
                valid_rhs = [r["relative_humidity_percent"] for r in readings if r["relative_humidity_percent"] is not None]

                summary = {
                    "mean_wind_speed_10m_kmh": round(sum(valid_winds) / len(valid_winds), 1) if valid_winds else None,
                    "max_wind_speed_10m_kmh": max(valid_winds) if valid_winds else None,
                    "min_surface_pressure_hpa": min(valid_press) if valid_press else None,
                    "mean_temperature_2m_c": round(sum(valid_temps) / len(valid_temps), 1) if valid_temps else None,
                    "mean_relative_humidity_percent": round(sum(valid_rhs) / len(valid_rhs), 1) if valid_rhs else None,
                    "total_valid_hours": len(valid_winds)
                }

                result = {
                    "status": "SUCCESS",
                    "provenance": {
                        "source_agency": "NASA Langley Research Center",
                        "product_name": "NASA POWER Agroclimatology & Meteorology API",
                        "temporal_resolution": temporal.upper(),
                        "model_reanalysis_base": "MERRA-2 / GEOS FP-IT Assimilation",
                        "scientific_attribution": "NASA POWER Project (Prediction Of Worldwide Energy Resources)",
                        "retrieval_timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                        "latitude": latitude,
                        "longitude": longitude,
                        "query_date": date_str
                    },
                    "summary": summary,
                    "hourly_readings": readings,
                    "cache_hit": False
                }

                _NASA_POWER_CACHE[cache_key] = {"cached_at": now, "data": result}
                return result

        except Exception as e:
            return {
                "status": "NASA_POWER_UNAVAILABLE",
                "message": f"Network exception communicating with NASA POWER API: {str(e)}",
                "retrieval_timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }

    # -------------------------------------------------------------------------
    # 2. NASA Earthdata CMR Discovery API (AIRS, CYGNSS, MODIS)
    # -------------------------------------------------------------------------
    async def search_cmr_collections(
        self,
        keyword: str = "cyclone",
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Discovers NASA Earthdata collections via the Common Metadata Repository (CMR).
        """
        cache_key = f"cmr_col_{keyword}_{page_size}"
        now = time.time()
        if cache_key in _NASA_CMR_CACHE:
            entry = _NASA_CMR_CACHE[cache_key]
            if now - entry["cached_at"] < CACHE_TTL_SECONDS:
                c = dict(entry["data"])
                c["cache_hit"] = True
                return c

        url = f"{self.cmr_base_url}/collections.json"
        params = {
            "keyword": keyword,
            "page_size": min(50, page_size)
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, params=params)
                if res.status_code != 200:
                    return {
                        "status": "CMR_ERROR",
                        "http_status": res.status_code,
                        "message": f"NASA CMR API returned HTTP {res.status_code}"
                    }

                data = res.json()
                feed = data.get("feed", {})
                entries = feed.get("entry", [])

                collections = []
                for e in entries:
                    collections.append({
                        "id": e.get("id"),
                        "title": e.get("title"),
                        "short_name": e.get("short_name"),
                        "version_id": e.get("version_id"),
                        "data_center": e.get("data_center"),
                        "time_start": e.get("time_start"),
                        "time_end": e.get("time_end"),
                        "summary": (e.get("summary") or "")[:240] + "..." if e.get("summary") else ""
                    })

                result = {
                    "status": "SUCCESS",
                    "provenance": {
                        "source_agency": "NASA EOSDIS",
                        "catalog_service": "Common Metadata Repository (CMR) OpenSearch",
                        "keyword_filter": keyword,
                        "retrieval_timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                    },
                    "total_returned": len(collections),
                    "collections": collections,
                    "cache_hit": False
                }

                _NASA_CMR_CACHE[cache_key] = {"cached_at": now, "data": result}
                return result

        except Exception as e:
            return {
                "status": "CMR_UNAVAILABLE",
                "message": f"Network exception communicating with NASA CMR: {str(e)}",
                "retrieval_timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }

    async def search_cmr_granules(
        self,
        collection_id: str,
        start_date: str,
        end_date: str,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Discovers specific scientific observation granules for a given NASA collection and timeframe.
        """
        cache_key = f"cmr_gran_{collection_id}_{start_date}_{end_date}_{page_size}"
        now = time.time()
        if cache_key in _NASA_CMR_CACHE:
            entry = _NASA_CMR_CACHE[cache_key]
            if now - entry["cached_at"] < CACHE_TTL_SECONDS:
                c = dict(entry["data"])
                c["cache_hit"] = True
                return c

        url = f"{self.cmr_base_url}/granules.json"
        temporal = f"{start_date}T00:00:00Z,{end_date}T23:59:59Z"
        params = {
            "collection_concept_id": collection_id,
            "temporal": temporal,
            "page_size": min(50, page_size)
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, params=params)
                if res.status_code != 200:
                    return {
                        "status": "CMR_ERROR",
                        "http_status": res.status_code,
                        "message": f"NASA CMR API returned HTTP {res.status_code}"
                    }

                data = res.json()
                entries = data.get("feed", {}).get("entry", [])

                granules = []
                for e in entries:
                    links = e.get("links", [])
                    data_link = None
                    for l in links:
                        if l.get("rel", "").endswith("/data#"):
                            data_link = l.get("href")
                            break

                    granules.append({
                        "id": e.get("id"),
                        "title": e.get("title"),
                        "granule_size_mb": round(float(e.get("granule_size", 0.0)), 2),
                        "time_start": e.get("time_start"),
                        "time_end": e.get("time_end"),
                        "download_url": data_link,
                        "requires_earthdata_auth": True if data_link and "urs.earthdata.nasa.gov" in data_link else False
                    })

                result = {
                    "status": "SUCCESS",
                    "provenance": {
                        "source_agency": "NASA EOSDIS",
                        "collection_id": collection_id,
                        "temporal_query": temporal,
                        "retrieval_timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                    },
                    "total_returned": len(granules),
                    "granules": granules,
                    "auth_status": self.get_auth_status(),
                    "cache_hit": False
                }

                _NASA_CMR_CACHE[cache_key] = {"cached_at": now, "data": result}
                return result

        except Exception as e:
            return {
                "status": "CMR_UNAVAILABLE",
                "message": f"Network exception searching granules: {str(e)}",
                "retrieval_timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }

nasa_client_instance = NasaClient()
