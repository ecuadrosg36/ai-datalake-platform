"""
Tests for OGGI S3 Connector — using real downloaded Parquet data.

Tests the connector against the actual dim_company data downloaded
from s3://oggi-lakehouse-landing-276483282865-us-east-2/gold/gm3s_envio/dim_company/
"""

import os
import sys
from pathlib import Path

import pytest
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ingestion.oggi_s3_connector import (
    OGGIS3Connector,
    OGGIDatasetConfig,
    create_oggi_connector,
    VALID_COMPANY_IDS,
    VALID_COMPANY_GROUPS,
    OGGI_BUCKET,
    OGGI_REGION,
    SILVER_DATASETS,
    GOLD_DATASETS,
)
from src.ingestion.base_connector import IngestionConfig, IngestionStatus


# Path to downloaded sample data
SAMPLES_DIR = Path(os.environ.get(
    "OGGI_SAMPLES_DIR",
    str(Path(__file__).parent.parent.parent.parent / "oggi-samples")
))
DIM_COMPANY_DIR = SAMPLES_DIR / "dim_company"


class TestOGGIConstants:
    """Test OGGI-specific constants and configuration."""

    def test_bucket_name_format(self):
        """Bucket name should include account ID and region."""
        assert "276483282865" in OGGI_BUCKET
        assert "us-east-2" in OGGI_BUCKET

    def test_region_is_us_east_2(self):
        assert OGGI_REGION == "us-east-2"

    def test_valid_company_ids(self):
        """Should include all known OGGI entities."""
        assert "OGGI_MAYOREO" in VALID_COMPANY_IDS
        assert "OGGI_JUNIOR" in VALID_COMPANY_IDS
        assert "OGGI_TEZIUTLAN" in VALID_COMPANY_IDS
        assert "SOF" in VALID_COMPANY_IDS
        assert "BUYING" in VALID_COMPANY_IDS
        assert "DYCLASS" in VALID_COMPANY_IDS

    def test_silver_datasets_not_empty(self):
        assert len(SILVER_DATASETS) > 20

    def test_gold_datasets_not_empty(self):
        assert len(GOLD_DATASETS) > 10

    def test_key_datasets_present(self):
        """Critical business datasets should be listed."""
        assert "facturas" in SILVER_DATASETS
        assert "pagos" in SILVER_DATASETS
        assert "dim_company" in GOLD_DATASETS
        assert "pnl_canonical" in GOLD_DATASETS
        assert "rentabilidad_cliente" in GOLD_DATASETS


class TestOGGIDatasetConfig:
    """Test dataset configuration."""

    def test_default_config(self):
        cfg = OGGIDatasetConfig(layer="gold", dataset_name="dim_company")
        assert cfg.layer == "gold"
        assert cfg.dataset_name == "dim_company"
        assert cfg.snapshot is None
        assert cfg.max_files == 10

    def test_config_with_snapshot(self):
        cfg = OGGIDatasetConfig(
            layer="gold", dataset_name="pnl_canonical",
            snapshot="2026-06-19"
        )
        assert cfg.snapshot == "2026-06-19"


class TestCreateOGGIConnector:
    """Test the factory function."""

    def test_factory_creates_connector(self):
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            local_path=str(DIM_COMPANY_DIR) if DIM_COMPANY_DIR.exists() else None
        )
        assert isinstance(connector, OGGIS3Connector)
        assert connector.dataset.dataset_name == "dim_company"
        assert connector.dataset.layer == "gold"

    def test_factory_sets_source_name(self):
        connector = create_oggi_connector("pnl_canonical", layer="gold")
        assert connector.config.source_name == "oggi_gold_pnl_canonical"

    def test_factory_silver_layer(self):
        connector = create_oggi_connector("facturas", layer="silver")
        assert connector.config.source_name == "oggi_silver_facturas"


@pytest.mark.skipif(
    not DIM_COMPANY_DIR.exists(),
    reason="OGGI sample data not downloaded. Run: aws s3 cp s3://oggi-lakehouse-landing-276483282865-us-east-2/gold/gm3s_envio/dim_company/ oggi-samples/dim_company/ --recursive"
)
class TestOGGIConnectorWithRealData:
    """
    Integration tests using real OGGI dim_company data.

    These tests run against actual Parquet files downloaded from S3.
    Skip if the sample data directory doesn't exist.
    """

    def test_connect_local_parquet(self):
        """Should successfully connect and load local Parquet files."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            local_path=str(DIM_COMPANY_DIR)
        )
        connector.connect()
        assert len(connector._dataframes) > 0

    def test_ingest_dim_company(self):
        """Should ingest dim_company data and return valid DataFrame."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            local_path=str(DIM_COMPANY_DIR)
        )
        df = connector.ingest()

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "company_id" in df.columns
        assert "company_name" in df.columns
        assert "is_revenue_company" in df.columns

    def test_ingest_with_snapshot_filter(self):
        """Should filter to a specific snapshot."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            snapshot="2026-06-19",
            local_path=str(DIM_COMPANY_DIR)
        )
        df = connector.ingest()

        assert len(df) > 0
        # Should have snapshot metadata
        assert "_snapshot" in df.columns or "_source_system" in df.columns

    def test_company_data_structure(self):
        """Verify the structure of OGGI company data matches expectations."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            snapshot="2026-06-19",
            local_path=str(DIM_COMPANY_DIR)
        )
        df = connector.ingest()

        # Expected columns
        expected_cols = {
            "company_id", "company_name", "role",
            "is_revenue_company", "is_cogs_source", "is_overhead_only",
            "company_group",
        }
        assert expected_cols.issubset(set(df.columns))

    def test_company_count(self):
        """OGGI should have exactly 9 company entities."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            snapshot="2026-06-19",
            local_path=str(DIM_COMPANY_DIR)
        )
        df = connector.ingest()

        assert len(df) == 9

    def test_revenue_companies(self):
        """Should have the correct revenue-generating companies."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            snapshot="2026-06-19",
            local_path=str(DIM_COMPANY_DIR)
        )
        df = connector.ingest()

        revenue_cos = df[df["is_revenue_company"] == True]["company_id"].tolist()
        assert "OGGI_MAYOREO" in revenue_cos
        assert "OGGI_JUNIOR" in revenue_cos

    def test_cogs_source_company(self):
        """BUYING should be the COGS source."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            snapshot="2026-06-19",
            local_path=str(DIM_COMPANY_DIR)
        )
        df = connector.ingest()

        cogs_cos = df[df["is_cogs_source"] == True]["company_id"].tolist()
        assert "BUYING" in cogs_cos

    def test_ingestion_status_success(self):
        """Ingestion of clean data should return SUCCESS status."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            snapshot="2026-06-19",
            local_path=str(DIM_COMPANY_DIR)
        )
        connector.ingest()

        assert connector.metrics.status == IngestionStatus.SUCCESS
        assert connector.metrics.records_rejected == 0
        assert connector.metrics.records_accepted == 9

    def test_metadata_enrichment(self):
        """Ingested records should have metadata columns."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            snapshot="2026-06-19",
            local_path=str(DIM_COMPANY_DIR)
        )
        df = connector.ingest()

        assert "_ingested_at" in df.columns
        assert "_source_system" in df.columns
        assert "_run_id" in df.columns
        assert df["_source_system"].iloc[0] == "oggi_gold_dim_company"

    def test_available_snapshots(self):
        """Should list available snapshot dates."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            local_path=str(DIM_COMPANY_DIR)
        )
        connector.connect()

        snapshots = connector.get_available_snapshots()
        assert len(snapshots) > 0
        assert all(s.startswith("2026-06-") for s in snapshots)

    def test_ingestion_metrics(self):
        """Metrics should track records correctly."""
        connector = create_oggi_connector(
            "dim_company", layer="gold",
            snapshot="2026-06-19",
            local_path=str(DIM_COMPANY_DIR)
        )
        connector.ingest()

        metrics = connector.metrics.to_dict()
        assert metrics["records_read"] == 9
        assert metrics["records_accepted"] == 9
        assert metrics["records_rejected"] == 0
        assert metrics["rejection_rate_pct"] == 0.0
        assert metrics["status"] == "success"
        assert metrics["duration_seconds"] > 0


class TestOGGIS3Prefix:
    """Test S3 prefix building logic."""

    def test_gold_prefix(self):
        connector = create_oggi_connector("dim_company", layer="gold")
        assert connector._s3_prefix == "gold/gm3s_envio/dim_company/"

    def test_silver_prefix(self):
        connector = create_oggi_connector("facturas", layer="silver")
        assert connector._s3_prefix == "silver/gm3s_envio/facturas/"

    def test_custom_prefix(self):
        config = IngestionConfig(source_name="test", source_type="s3_parquet")
        dataset = OGGIDatasetConfig(
            layer="gold", dataset_name="test",
            s3_prefix="custom/path/"
        )
        connector = OGGIS3Connector(config, dataset)
        assert connector._s3_prefix == "custom/path/"


class TestOGGIValidation:
    """Test OGGI-specific validation rules."""

    def test_valid_company_record(self):
        connector = create_oggi_connector("dim_company", layer="gold")
        record = {
            "company_id": "OGGI_MAYOREO",
            "company_name": "OGGI Mayoreo",
            "is_revenue_company": True,
        }
        is_valid, error = connector.validate_record(record)
        assert is_valid
        assert error is None

    def test_invalid_company_id(self):
        connector = create_oggi_connector("dim_company", layer="gold")
        record = {
            "company_id": "FAKE_COMPANY",
            "company_name": "Fake Corp",
        }
        is_valid, error = connector.validate_record(record)
        assert not is_valid
        assert "Unknown company_id" in error

    def test_all_null_record_rejected(self):
        connector = create_oggi_connector("dim_company", layer="gold")
        record = {"company_id": None, "company_name": None}
        is_valid, error = connector.validate_record(record)
        assert not is_valid
        assert "null/empty" in error

    def test_factura_negative_amount(self):
        connector = create_oggi_connector("g_factura_line", layer="gold")
        record = {
            "factura_id": 1,
            "gross_amount": -100.0,
            "company_id": "OGGI_MAYOREO",
        }
        is_valid, error = connector.validate_record(record)
        assert not is_valid
        assert "Negative gross_amount" in error

    def test_factura_valid_record(self):
        connector = create_oggi_connector("g_factura_line", layer="gold")
        record = {
            "factura_id": 1,
            "sku_id": 12345,
            "qty": 10.0,
            "precio_unit": 150.0,
            "costo_unit": 80.0,
            "gross_amount": 1500.0,
            "company_id": "OGGI_MAYOREO",
        }
        is_valid, error = connector.validate_record(record)
        assert is_valid

    def test_negative_qty_allowed_for_returns(self):
        """Negative quantity is allowed (returns/credits)."""
        connector = create_oggi_connector("g_factura_line", layer="gold")
        record = {
            "factura_id": 1,
            "qty": -5.0,
            "gross_amount": 100.0,
            "company_id": "OGGI_JUNIOR",
        }
        is_valid, error = connector.validate_record(record)
        assert is_valid
