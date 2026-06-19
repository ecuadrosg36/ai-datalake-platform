"""
Tests for the MCP Server.
"""

import json
import pytest

from src.mcp_server.server import (
    DATA_CATALOG,
    QUALITY_REPORTS,
    handle_query_dataset,
    handle_get_schema,
    handle_check_quality,
    handle_list_datasets,
    handle_run_pipeline,
    handle_generate_insight,
)


class TestMCPTools:
    """Tests for MCP tool handlers."""

    def test_query_dataset(self):
        """Test query_dataset tool."""
        result = handle_query_dataset({
            "query": "SELECT * FROM erp_transactions_clean LIMIT 10",
            "layer": "silver",
        })
        assert result["status"] == "success"
        assert "available_tables" in result

    def test_get_schema_existing(self):
        """Test get_schema for an existing table."""
        result = handle_get_schema({
            "table_name": "crm_contacts_raw",
            "layer": "bronze",
        })
        assert "schema" in result
        assert result["table_name"] == "crm_contacts_raw"

    def test_get_schema_not_found(self):
        """Test get_schema for a non-existent table."""
        result = handle_get_schema({
            "table_name": "nonexistent",
            "layer": "bronze",
        })
        assert "error" in result

    def test_check_quality_existing(self):
        """Test check_quality for an existing dataset."""
        result = handle_check_quality({
            "dataset_name": "erp_transactions_clean",
        })
        assert "overall_score" in result
        assert result["overall_score"] == 0.94

    def test_check_quality_not_found(self):
        """Test check_quality for a non-existent dataset."""
        result = handle_check_quality({
            "dataset_name": "nonexistent",
        })
        assert "error" in result

    def test_list_datasets_all(self):
        """Test listing all datasets."""
        result = handle_list_datasets({"layer": "all"})
        assert "bronze" in result
        assert "silver" in result
        assert "gold" in result

    def test_list_datasets_specific_layer(self):
        """Test listing datasets for a specific layer."""
        result = handle_list_datasets({"layer": "gold"})
        assert "daily_business_metrics" in result

    def test_run_pipeline(self):
        """Test pipeline trigger."""
        result = handle_run_pipeline({
            "layer": "silver",
            "dry_run": True,
        })
        assert result["status"] == "accepted"
        assert result["dry_run"] is True

    def test_run_pipeline_full(self):
        """Test full pipeline trigger."""
        result = handle_run_pipeline({"layer": "full"})
        assert result["status"] == "accepted"

    def test_generate_insight(self):
        """Test insight generation."""
        result = handle_generate_insight({
            "dataset_name": "daily_business_metrics",
            "focus_area": "revenue trends",
        })
        assert result["status"] == "success"
        assert "sample_insights" in result
        assert len(result["sample_insights"]) > 0


class TestDataCatalog:
    """Tests for the in-memory data catalog."""

    def test_catalog_has_three_layers(self):
        """Test catalog contains all three medallion layers."""
        assert "bronze" in DATA_CATALOG
        assert "silver" in DATA_CATALOG
        assert "gold" in DATA_CATALOG

    def test_bronze_has_datasets(self):
        """Test Bronze layer has expected datasets."""
        assert "crm_contacts_raw" in DATA_CATALOG["bronze"]
        assert "erp_transactions_raw" in DATA_CATALOG["bronze"]

    def test_dataset_has_metadata(self):
        """Test datasets have required metadata."""
        dataset = DATA_CATALOG["bronze"]["crm_contacts_raw"]
        assert "description" in dataset
        assert "format" in dataset
        assert "row_count" in dataset

    def test_quality_reports_exist(self):
        """Test quality reports are available."""
        assert len(QUALITY_REPORTS) > 0
        for name, report in QUALITY_REPORTS.items():
            assert "overall_score" in report
            assert "dimension_scores" in report
