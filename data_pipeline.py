"""
CYCLONEX — Traceable Multi-Source Data Ingestion & Normalization Pipeline
Problem Statement: SIH 26070

Architectural Stages:
1. Source Discovery: Catalog discovery for ISRO MOSDAC, NASA GIBS, Open-Meteo, IBTrACS/CMA/IMD.
2. Data Retrieval: Resilient network fetching with timeout & error handling.
3. File Validation: Format validation, file signatures, and Content-Type inspection.
4. Product Decoding: Metadata parsing and variable extraction.
5. Variable Normalization: Unit standardization (km/h, hPa, °C) while preserving original values.
6. Quality Control: Out-of-bounds checks, missing-data flags (NO fabrication of missing values).
7. Provenance & Storage: Explicit data lineage, agency attribution, observation timestamps.
8. Data Delivery: Structured distribution to frontend workstations and predictive models.
"""

import os
import re
import json
import time
import math
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict

# =============================================================================
# DATA QUALITY FLAGS & ENUMS
# =============================================================================
class QualityFlag:
    VALID_VERIFIED = "QC_PASSED_VERIFIED"
    SUSPECT_CLIPPED = "QC_SUSPECT_OUT_OF_RANGE"
    MISSING_VALUE = "QC_MISSING_VALUE"
    UNAUTHENTICATED = "QC_ACCESS_UNAUTHORIZED"
    SYNOPTIC_ESTIMATE = "QC_MODEL_ASSISTED_ESTIMATE"

# =============================================================================
# OBSERVATION PROVENANCE SCHEMA
# =============================================================================
@dataclass
class ObservationProvenance:
    source_agency: str               # e.g., "ISRO Space Applications Centre", "NASA EOSDIS", "IMD RSMC New Delhi"
    satellite_or_system: str         # e.g., "INSAT-3DR", "EOS Terra MODIS", "Synoptic Marine Station"
    sensor_payload: str              # e.g., "Imager TIR-1", "MODIS Radiometer", "Surface Barometer"
    product_identifier: str          # e.g., "3RIMG_L2B_SST", "MODIS_Terra_TrueColor", "ERA5/Open-Meteo"
    observation_timestamp_utc: str   # ISO-8601 UTC timestamp of genuine observation
    ingestion_timestamp_utc: str     # ISO-8601 UTC timestamp of ingestion into CYCLONEX
    data_tier: str                   # "DIRECT_SATELLITE_MEASUREMENT", "REANALYSIS_ESTIMATE", "BEST_TRACK_VERIFIED"
    terms_attribution: str           # Open citation or access license terms
    is_live_observation: bool        # True only if genuine near-real-time pass, False if historical archive

@dataclass
class NormalizedVariable:
    canonical_name: str              # e.g., "surface_wind_speed", "central_pressure", "sea_surface_temp"
    original_name: str               # e.g., "wind_speed_10m", "min_pressure_hpa", "SST"
    normalized_value: Optional[float]# Converted numerical value
    normalized_units: str            # e.g., "km/h", "hPa", "degC"
    original_value: Optional[float]  # Unaltered value from source
    original_units: str              # e.g., "m/s", "knots", "Kelvin"
    quality_flag: str                # QualityFlag enum value
    is_missing: bool = False
    missing_reason: Optional[str] = None

# =============================================================================
# CORE DATA PIPELINE ENGINE
# =============================================================================
class CyclonexDataPipeline:
    """
    Unified, repeatable pipeline for searching, validating, processing,
    and delivering multi-source meteorological and satellite observations.
    """

    # Physical valid ranges for quality control checks
    PHYSICAL_LIMITS = {
        "wind_speed_kmh": (0.0, 380.0),          # Earth tropical record: ~315 km/h (Patricia)
        "pressure_hpa": (850.0, 1050.0),         # Earth lowest: 870 hPa (Tip)
        "sea_surface_temp_c": (10.0, 36.0),      # Ocean surface water range
        "cloud_top_temp_c": (-110.0, 40.0),      # Tropical convective cloud-top to sea level
        "latitude": (-90.0, 90.0),
        "longitude": (-180.0, 180.0)
    }

    # -------------------------------------------------------------------------
    # STAGE 1 & 2: SOURCE DISCOVERY & RETRIEVAL
    # -------------------------------------------------------------------------
    @staticmethod
    def discover_mosdac_products(
        dataset_id: str = "3RIMG_L2B_SST",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: int = 10
    ) -> Dict[str, Any]:
        """Queries ISRO MOSDAC OpenSearch gateway for genuine archived files."""
        from mosdac_client import MosdacClient
        client = MosdacClient()
        return client.search_datasets(
            dataset_id=dataset_id,
            start_time=start_date,
            end_time=end_date,
            count=count
        )

    # -------------------------------------------------------------------------
    # STAGE 3: FILE & FORMAT VALIDATION
    # -------------------------------------------------------------------------
    @staticmethod
    def validate_file_signature(file_bytes: bytes, expected_format: str) -> Tuple[bool, str]:
        """
        Validates binary file signature (magic number) to prevent corrupt files.
        """
        if not file_bytes:
            return False, "File buffer is empty (0 bytes)"

        expected_upper = expected_format.upper()
        if expected_upper in ("HDF5", "H5"):
            if file_bytes.startswith(b"\x89HDF\r\n\x1a\n"):
                return True, "Valid HDF5 magic number signature detected"
            return False, "Invalid file signature: Missing HDF5 magic bytes"

        elif expected_upper in ("JPEG", "JPG"):
            if file_bytes.startswith(b"\xff\xd8\xff"):
                return True, "Valid JPEG magic number signature detected"
            return False, "Invalid file signature: Missing JPEG SOI marker"

        elif expected_upper in ("NETCDF", "NC"):
            if file_bytes.startswith(b"CDF") or file_bytes.startswith(b"\x89HDF"):
                return True, "Valid NetCDF/CDF magic number signature detected"
            return False, "Invalid file signature: Missing NetCDF header"

        elif expected_upper == "JSON":
            try:
                json.loads(file_bytes.decode("utf-8"))
                return True, "Valid JSON payload structure parsed"
            except Exception as e:
                return False, f"Malformed JSON: {e}"

        return True, "Unspecified format: Passed basic non-empty check"

    # -------------------------------------------------------------------------
    # STAGE 4 & 5: PRODUCT DECODING & VARIABLE NORMALIZATION
    # -------------------------------------------------------------------------
    @classmethod
    def normalize_wind_speed(
        cls,
        raw_val: Any,
        raw_units: str = "km/h"
    ) -> NormalizedVariable:
        """
        Normalizes wind speed into km/h while preserving original values.
        Handles knots, m/s, and km/h. Flags missing/unrealistic values.
        """
        orig_u = raw_units.strip().lower()
        if raw_val is None or raw_val == -999 or raw_val == 9999 or (isinstance(raw_val, float) and math.isnan(raw_val)):
            return NormalizedVariable(
                canonical_name="surface_wind_speed",
                original_name="wind_speed",
                normalized_value=None,
                normalized_units="km/h",
                original_value=raw_val,
                original_units=raw_units,
                quality_flag=QualityFlag.MISSING_VALUE,
                is_missing=True,
                missing_reason="Source value flagged as null/missing code"
            )

        try:
            val_f = float(raw_val)
        except (ValueError, TypeError):
            return NormalizedVariable(
                canonical_name="surface_wind_speed",
                original_name="wind_speed",
                normalized_value=None,
                normalized_units="km/h",
                original_value=raw_val,
                original_units=raw_units,
                quality_flag=QualityFlag.MISSING_VALUE,
                is_missing=True,
                missing_reason="Value could not be parsed as float"
            )

        # Convert to km/h
        if orig_u in ("kt", "kts", "knot", "knots"):
            conv_kmh = round(val_f * 1.852, 1)
        elif orig_u in ("m/s", "mps", "ms-1"):
            conv_kmh = round(val_f * 3.6, 1)
        else:
            conv_kmh = round(val_f, 1)

        # Quality Control range check
        min_w, max_w = cls.PHYSICAL_LIMITS["wind_speed_kmh"]
        if conv_kmh < min_w or conv_kmh > max_w:
            qf = QualityFlag.SUSPECT_CLIPPED
        else:
            qf = QualityFlag.VALID_VERIFIED

        return NormalizedVariable(
            canonical_name="surface_wind_speed",
            original_name="wind_speed",
            normalized_value=conv_kmh,
            normalized_units="km/h",
            original_value=val_f,
            original_units=raw_units,
            quality_flag=qf,
            is_missing=False
        )

    @classmethod
    def normalize_pressure(
        cls,
        raw_val: Any,
        raw_units: str = "hPa"
    ) -> NormalizedVariable:
        """
        Normalizes barometric pressure into hPa (hectopascals/millibars).
        """
        orig_u = raw_units.strip().lower()
        if raw_val is None or raw_val in (-999, 9999) or (isinstance(raw_val, float) and math.isnan(raw_val)):
            return NormalizedVariable(
                canonical_name="central_pressure",
                original_name="pressure",
                normalized_value=None,
                normalized_units="hPa",
                original_value=raw_val,
                original_units=raw_units,
                quality_flag=QualityFlag.MISSING_VALUE,
                is_missing=True,
                missing_reason="Source value is null or missing"
            )

        try:
            val_f = float(raw_val)
        except (ValueError, TypeError):
            return NormalizedVariable(
                canonical_name="central_pressure",
                original_name="pressure",
                normalized_value=None,
                normalized_units="hPa",
                original_value=raw_val,
                original_units=raw_units,
                quality_flag=QualityFlag.MISSING_VALUE,
                is_missing=True,
                missing_reason="Pressure cannot be parsed as float"
            )

        # In Pa -> hPa
        if orig_u in ("pa", "pascal"):
            conv_hpa = round(val_f / 100.0, 1)
        else:
            conv_hpa = round(val_f, 1)

        min_p, max_p = cls.PHYSICAL_LIMITS["pressure_hpa"]
        qf = QualityFlag.SUSPECT_CLIPPED if (conv_hpa < min_p or conv_hpa > max_p) else QualityFlag.VALID_VERIFIED

        return NormalizedVariable(
            canonical_name="central_pressure",
            original_name="pressure",
            normalized_value=conv_hpa,
            normalized_units="hPa",
            original_value=val_f,
            original_units=raw_units,
            quality_flag=qf,
            is_missing=False
        )

    @classmethod
    def normalize_sst(
        cls,
        raw_val: Any,
        raw_units: str = "degC"
    ) -> NormalizedVariable:
        """
        Normalizes Sea Surface Temperature into degrees Celsius.
        Explicitly notes: SST represents oceanic thermodynamic potential,
        NOT proof of cyclogenesis on its own.
        """
        orig_u = raw_units.strip().lower()
        if raw_val is None or raw_val in (-999, 9999) or (isinstance(raw_val, float) and math.isnan(raw_val)):
            return NormalizedVariable(
                canonical_name="sea_surface_temperature",
                original_name="SST",
                normalized_value=None,
                normalized_units="degC",
                original_value=raw_val,
                original_units=raw_units,
                quality_flag=QualityFlag.MISSING_VALUE,
                is_missing=True,
                missing_reason="SST measurement obscured by cloud cover or null"
            )

        try:
            val_f = float(raw_val)
        except (ValueError, TypeError):
            return NormalizedVariable(
                canonical_name="sea_surface_temperature",
                original_name="SST",
                normalized_value=None,
                normalized_units="degC",
                original_value=raw_val,
                original_units=raw_units,
                quality_flag=QualityFlag.MISSING_VALUE,
                is_missing=True,
                missing_reason="Cannot parse SST value"
            )

        if orig_u in ("k", "kelvin"):
            conv_c = round(val_f - 273.15, 2)
        else:
            conv_c = round(val_f, 2)

        min_s, max_s = cls.PHYSICAL_LIMITS["sea_surface_temp_c"]
        qf = QualityFlag.SUSPECT_CLIPPED if (conv_c < min_s or conv_c > max_s) else QualityFlag.VALID_VERIFIED

        return NormalizedVariable(
            canonical_name="sea_surface_temperature",
            original_name="SST",
            normalized_value=conv_c,
            normalized_units="degC",
            original_value=val_f,
            original_units=raw_units,
            quality_flag=qf,
            is_missing=False
        )

    # -------------------------------------------------------------------------
    # STAGE 6: COORDINATE VALIDATION
    # -------------------------------------------------------------------------
    @classmethod
    def validate_coordinates(cls, lat: Any, lon: Any) -> Tuple[bool, Optional[float], Optional[float], str]:
        """
        Enforces geographic coordinate bounds (-90 <= lat <= 90, -180 <= lon <= 180).
        """
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (ValueError, TypeError):
            return False, None, None, "Coordinates must be real numbers"

        min_lat, max_lat = cls.PHYSICAL_LIMITS["latitude"]
        min_lon, max_lon = cls.PHYSICAL_LIMITS["longitude"]

        if not (min_lat <= lat_f <= max_lat):
            return False, lat_f, lon_f, f"Latitude {lat_f} out of bounds [{min_lat}, {max_lat}]"
        if not (min_lon <= lon_f <= max_lon):
            return False, lat_f, lon_f, f"Longitude {lon_f} out of bounds [{min_lon}, {max_lon}]"

        return True, round(lat_f, 4), round(lon_f, 4), "Valid geographic coordinates"

    # -------------------------------------------------------------------------
    # STAGE 7 & 8: PROVENANCE, STORAGE & DELIVERY
    # -------------------------------------------------------------------------
    @classmethod
    def build_normalized_observation(
        cls,
        lat: float,
        lon: float,
        observation_time_utc: str,
        wind_speed_raw: Any,
        wind_units: str = "km/h",
        pressure_raw: Optional[Any] = None,
        pressure_units: str = "hPa",
        sst_raw: Optional[Any] = None,
        sst_units: str = "degC",
        source_agency: str = "IMD RSMC New Delhi",
        satellite_or_system: str = "Verified In Situ / Best Track",
        sensor_payload: str = "Anemometer / Barometer",
        product_identifier: str = "BEST_TRACK_WAYPOINT",
        data_tier: str = "BEST_TRACK_VERIFIED",
        is_live: bool = False
    ) -> Dict[str, Any]:
        """
        Builds a fully traceable, standardized observation packet.
        """
        valid_coords, clean_lat, clean_lon, coord_msg = cls.validate_coordinates(lat, lon)
        norm_wind = cls.normalize_wind_speed(wind_speed_raw, wind_units)
        norm_pres = cls.normalize_pressure(pressure_raw, pressure_units) if pressure_raw is not None else None
        norm_sst = cls.normalize_sst(sst_raw, sst_units) if sst_raw is not None else None

        provenance = ObservationProvenance(
            source_agency=source_agency,
            satellite_or_system=satellite_or_system,
            sensor_payload=sensor_payload,
            product_identifier=product_identifier,
            observation_timestamp_utc=observation_time_utc,
            ingestion_timestamp_utc=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            data_tier=data_tier,
            terms_attribution="WMO / RSMC Operational Meteorological Ingestion License",
            is_live_observation=is_live
        )

        variables = {
            "wind_speed": asdict(norm_wind)
        }
        if norm_pres:
            variables["pressure"] = asdict(norm_pres)
        if norm_sst:
            variables["sea_surface_temp"] = asdict(norm_sst)

        return {
            "status": "VALID_OBSERVATION" if valid_coords and not norm_wind.is_missing else "PARTIAL_OR_FLAGGED",
            "coordinates": {
                "latitude": clean_lat,
                "longitude": clean_lon,
                "is_valid": valid_coords,
                "validation_message": coord_msg
            },
            "provenance": asdict(provenance),
            "variables": variables,
            "scientific_disclaimer": "SST indicates ocean thermal potential; surface winds reflect 10m boundary layer only."
        }
