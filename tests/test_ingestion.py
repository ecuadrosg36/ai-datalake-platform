"""
Tests for the Bronze Layer — Data Ingestion Connectors.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.base_connector import IngestionConfig, IngestionStatus
from src.ingestion.crm_connector import CRMConnector
from src.ingestion.erp_connector import ERPConnector
from src.ingestion.csv_ingestion import CSVIngestor
from src.ingestion.api_connector import APIConnector


# =============================================================================
# CRM Connector Tests
# =============================================================================

class TestCRMConnector:
    """Tests for CRM data ingestion."""

    def test_ingest_valid_contacts(self, tmp_path, sample_crm_data):
        """Test ingestion of valid CRM contacts."""
        data_file = tmp_path / "crm_data.json"
        data_file.write_text(json.dumps(sample_crm_data))

        config = IngestionConfig(source_name="test_crm", source_type="crm")
        connector = CRMConnector(config, data_path=str(data_file))
        df = connector.ingest()

        assert not df.empty
        assert connector.metrics.status in (IngestionStatus.SUCCESS, IngestionStatus.PARTIAL)
        assert connector.metrics.records_accepted > 0

    def test_reject_invalid_email(self, tmp_path):
        """Test that records with invalid emails are rejected."""
        data = [
            {
                "contact_id": "CRM-BAD",
                "email": "not-an-email",
                "company": "Test",
                "first_name": "Test",
            }
        ]
        data_file = tmp_path / "bad_crm.json"
        data_file.write_text(json.dumps(data))

        config = IngestionConfig(source_name="test_crm", source_type="crm")
        connector = CRMConnector(config, data_path=str(data_file))
        df = connector.ingest()

        assert connector.metrics.records_rejected > 0

    def test_reject_duplicates(self, tmp_path):
        """Test that duplicate contact_ids are detected."""
        data = [
            {"contact_id": "CRM-001", "email": "a@test.com", "company": "A"},
            {"contact_id": "CRM-001", "email": "b@test.com", "company": "B"},
        ]
        data_file = tmp_path / "dup_crm.json"
        data_file.write_text(json.dumps(data))

        config = IngestionConfig(source_name="test_crm", source_type="crm")
        connector = CRMConnector(config, data_path=str(data_file))
        df = connector.ingest()

        assert connector.metrics.records_rejected >= 1

    def test_flatten_custom_fields(self, tmp_path):
        """Test that custom_fields are flattened correctly."""
        data = [
            {
                "contact_id": "CRM-001",
                "email": "test@test.com",
                "company": "Test",
                "custom_fields": {"annual_revenue": 1000000, "tier": "Gold"},
            }
        ]
        data_file = tmp_path / "cf_crm.json"
        data_file.write_text(json.dumps(data))

        config = IngestionConfig(source_name="test_crm", source_type="crm")
        connector = CRMConnector(config, data_path=str(data_file))
        df = connector.ingest()

        assert "cf_annual_revenue" in df.columns
        assert "cf_tier" in df.columns

    def test_metrics_tracking(self, tmp_path, sample_crm_data):
        """Test that ingestion metrics are properly tracked."""
        data_file = tmp_path / "crm.json"
        data_file.write_text(json.dumps(sample_crm_data))

        config = IngestionConfig(source_name="test_crm", source_type="crm")
        connector = CRMConnector(config, data_path=str(data_file))
        connector.ingest()

        metrics = connector.metrics.to_dict()
        assert metrics["source_name"] == "test_crm"
        assert metrics["records_read"] > 0
        assert metrics["duration_seconds"] >= 0


# =============================================================================
# ERP Connector Tests
# =============================================================================

class TestERPConnector:
    """Tests for ERP data ingestion."""

    def test_ingest_valid_transactions(self):
        """Test ingestion from sample ERP CSV."""
        data_path = Path("data/sample_erp_transactions.csv")
        if not data_path.exists():
            pytest.skip("Sample data not available")

        config = IngestionConfig(source_name="test_erp", source_type="erp")
        connector = ERPConnector(config, data_path=data_path)
        df = connector.ingest()

        assert not df.empty
        assert connector.metrics.records_accepted > 0

    def test_reject_negative_quantity(self, tmp_path):
        """Test that negative quantities are rejected."""
        csv_content = (
            "transaction_id,order_date,customer_id,product_sku,quantity,"
            "total_amount,currency,status\n"
            "TXN-001,2025-06-01,CUST-100,SKU-A1,-5,100,USD,Completed\n"
        )
        data_file = tmp_path / "bad_erp.csv"
        data_file.write_text(csv_content)

        config = IngestionConfig(source_name="test_erp", source_type="erp")
        connector = ERPConnector(config, data_path=str(data_file))
        df = connector.ingest()

        assert connector.metrics.records_rejected > 0

    def test_reject_missing_customer_id(self, tmp_path):
        """Test that missing customer_id is rejected."""
        csv_content = (
            "transaction_id,order_date,customer_id,product_sku,quantity,"
            "total_amount,currency,status\n"
            "TXN-001,2025-06-01,,SKU-A1,5,100,USD,Completed\n"
        )
        data_file = tmp_path / "no_cust.csv"
        data_file.write_text(csv_content)

        config = IngestionConfig(source_name="test_erp", source_type="erp")
        connector = ERPConnector(config, data_path=str(data_file))
        df = connector.ingest()

        assert connector.metrics.records_rejected > 0


# =============================================================================
# CSV Ingestor Tests
# =============================================================================

class TestCSVIngestor:
    """Tests for generic CSV ingestion."""

    def test_auto_delimiter_detection(self, tmp_path):
        """Test automatic delimiter detection."""
        csv_content = "name;age;city\nCarlos;30;Monterrey\nMaria;25;CDMX\n"
        data_file = tmp_path / "semicolon.csv"
        data_file.write_text(csv_content)

        config = IngestionConfig(source_name="test_csv", source_type="csv")
        ingestor = CSVIngestor(config, file_path=str(data_file))
        df = ingestor.ingest()

        assert not df.empty
        assert "name" in df.columns

    def test_type_inference(self, tmp_path):
        """Test automatic type inference."""
        csv_content = "name,age,active,score\nCarlos,30,true,95.5\nMaria,25,false,88.0\n"
        data_file = tmp_path / "typed.csv"
        data_file.write_text(csv_content)

        config = IngestionConfig(source_name="test_csv", source_type="csv")
        ingestor = CSVIngestor(config, file_path=str(data_file))
        df = ingestor.ingest()

        assert df["age"].iloc[0] == 30  # Should be int
        assert df["score"].iloc[0] == 95.5  # Should be float

    def test_schema_info(self, tmp_path):
        """Test schema info generation."""
        csv_content = "id,name,value\n1,Carlos,100\n2,Maria,200\n"
        data_file = tmp_path / "schema.csv"
        data_file.write_text(csv_content)

        config = IngestionConfig(source_name="test_csv", source_type="csv")
        ingestor = CSVIngestor(config, file_path=str(data_file))
        ingestor.connect()

        schema = ingestor.get_schema_info()
        assert schema["row_count"] == 2
        assert len(schema["columns"]) == 3


# =============================================================================
# API Connector Tests
# =============================================================================

class TestAPIConnector:
    """Tests for API data ingestion."""

    def test_ingest_api_data(self):
        """Test ingestion from sample API response."""
        data_path = Path("data/sample_api_response.json")
        if not data_path.exists():
            pytest.skip("Sample data not available")

        config = IngestionConfig(source_name="test_api", source_type="api")
        connector = APIConnector(config, data_path=data_path, data_key="data")
        df = connector.ingest()

        assert not df.empty
        assert connector.metrics.records_accepted > 0

    def test_flatten_nested_json(self, tmp_path):
        """Test flattening of nested JSON structures."""
        data = {
            "data": [
                {
                    "event_id": "EVT-001",
                    "timestamp": "2025-06-15T08:30:00Z",
                    "metadata": {
                        "agent_id": "AGT-01",
                        "geo": {"country": "Mexico", "city": "CDMX"},
                    },
                }
            ]
        }
        data_file = tmp_path / "nested.json"
        data_file.write_text(json.dumps(data))

        config = IngestionConfig(source_name="test_api", source_type="api")
        connector = APIConnector(config, data_path=str(data_file), data_key="data")
        df = connector.ingest()

        assert "metadata_agent_id" in df.columns
        assert "metadata_geo_country" in df.columns
