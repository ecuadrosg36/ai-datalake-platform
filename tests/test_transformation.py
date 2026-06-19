"""
Tests for the Silver Layer — Transformation, Quality, and Deduplication.
"""

import pandas as pd
import pytest

from src.transformation.spark_processor import SparkProcessor
from src.transformation.data_quality import DataQualityChecker
from src.transformation.deduplication import (
    DeduplicationEngine,
    DeduplicationStrategy,
    KeepStrategy,
)
from src.transformation.schema_enforcer import (
    SchemaEnforcer,
    SchemaMode,
    CRM_SCHEMA,
    ERP_SCHEMA,
)


# =============================================================================
# SparkProcessor Tests
# =============================================================================

class TestSparkProcessor:
    """Tests for PySpark/Pandas data transformations."""

    def test_standardize_columns(self, sample_erp_df):
        """Test column name standardization to snake_case."""
        df = sample_erp_df.rename(columns={"product_sku": "ProductSKU"})
        processor = SparkProcessor(use_spark=False)
        result = processor._standardize_columns(df)
        assert "product_sku" in result.columns

    def test_handle_nulls(self):
        """Test null handling replaces common null strings."""
        df = pd.DataFrame({
            "name": ["Carlos", "N/A", "", "NULL", "Maria"],
            "value": [100, None, 200, 300, None],
        })
        processor = SparkProcessor(use_spark=False)
        result = processor._handle_nulls(df)
        assert result["name"].iloc[1] is None
        assert result["name"].iloc[2] is None
        assert result["name"].iloc[3] is None

    def test_normalize_emails(self):
        """Test email normalization to lowercase."""
        df = pd.DataFrame({"email": ["Carlos@Test.COM", "MARIA@corp.mx"]})
        processor = SparkProcessor(use_spark=False)
        result = processor._normalize_strings(df)
        assert result["email"].iloc[0] == "carlos@test.com"

    def test_add_partition_columns(self, sample_erp_df):
        """Test partition column generation."""
        processor = SparkProcessor(use_spark=False)
        result = processor._add_partition_columns(sample_erp_df)
        assert "_partition_year" in result.columns
        assert "_partition_month" in result.columns
        assert "_partition_day" in result.columns

    def test_full_transform(self, sample_erp_df):
        """Test full transformation pipeline."""
        processor = SparkProcessor(use_spark=False)
        result = processor.transform(sample_erp_df, source_type="erp")
        assert "_processed_at" in result.columns
        assert "_layer" in result.columns
        assert result["_layer"].iloc[0] == "silver"

    def test_transform_empty_df(self):
        """Test transformation of empty DataFrame."""
        processor = SparkProcessor(use_spark=False)
        result = processor.transform(pd.DataFrame(), source_type="erp")
        assert result.empty


# =============================================================================
# DataQualityChecker Tests
# =============================================================================

class TestDataQualityChecker:
    """Tests for data quality validation."""

    def test_completeness_check(self, sample_erp_df):
        """Test completeness rule."""
        checker = DataQualityChecker()
        checker.add_completeness_rule("customer_id", threshold=0.95)
        report = checker.check(sample_erp_df, "test_data")
        assert report.overall_score > 0
        assert len(report.results) == 1

    def test_accuracy_check_range(self, sample_erp_df):
        """Test accuracy rule with range validation."""
        checker = DataQualityChecker()
        checker.add_accuracy_rule("quantity", min_value=0, max_value=10000)
        report = checker.check(sample_erp_df, "test_data")
        result = report.results[0]
        assert result.passed  # All quantities are valid

    def test_uniqueness_check(self, sample_erp_df):
        """Test uniqueness rule."""
        checker = DataQualityChecker()
        checker.add_uniqueness_rule(["transaction_id"])
        report = checker.check(sample_erp_df, "test_data")
        result = report.results[0]
        assert result.score == 1.0  # No duplicates

    def test_uniqueness_finds_duplicates(self, sample_erp_with_issues):
        """Test uniqueness rule detects duplicates."""
        checker = DataQualityChecker()
        checker.add_uniqueness_rule(["transaction_id"])
        report = checker.check(sample_erp_with_issues, "test_data")
        result = report.results[0]
        assert result.score < 1.0  # Should find TXN-001 duplicate

    def test_quality_report_structure(self, sample_erp_df):
        """Test quality report structure."""
        checker = DataQualityChecker()
        checker.add_completeness_rule("customer_id")
        checker.add_accuracy_rule("quantity", min_value=0)
        checker.add_uniqueness_rule(["transaction_id"])

        report = checker.check(sample_erp_df, "erp_test", layer="silver")
        report_dict = report.to_dict()

        assert "dataset_name" in report_dict
        assert "overall_score" in report_dict
        assert "dimension_scores" in report_dict
        assert "results" in report_dict

    def test_dimension_scores(self, sample_erp_df):
        """Test dimension score calculation."""
        checker = DataQualityChecker()
        checker.add_completeness_rule("customer_id")
        checker.add_accuracy_rule("quantity", min_value=0)

        report = checker.check(sample_erp_df, "test_data")
        dimensions = report.dimension_scores

        assert "completeness" in dimensions
        assert "accuracy" in dimensions


# =============================================================================
# DeduplicationEngine Tests
# =============================================================================

class TestDeduplicationEngine:
    """Tests for data deduplication."""

    def test_exact_dedup(self, sample_erp_with_issues):
        """Test exact deduplication removes duplicates."""
        engine = DeduplicationEngine(
            strategy=DeduplicationStrategy.EXACT,
            key_columns=["transaction_id"],
        )
        df_out, result = engine.deduplicate(sample_erp_with_issues)
        assert result.duplicates_removed > 0
        assert len(df_out) < len(sample_erp_with_issues)

    def test_keep_first(self):
        """Test keeping first occurrence."""
        df = pd.DataFrame({
            "id": ["A", "A", "B"],
            "value": [1, 2, 3],
        })
        engine = DeduplicationEngine(
            strategy=DeduplicationStrategy.EXACT,
            key_columns=["id"],
            keep=KeepStrategy.FIRST,
        )
        df_out, _ = engine.deduplicate(df)
        assert len(df_out) == 2
        assert df_out[df_out["id"] == "A"]["value"].iloc[0] == 1

    def test_keep_last(self):
        """Test keeping last occurrence."""
        df = pd.DataFrame({
            "id": ["A", "A", "B"],
            "value": [1, 2, 3],
        })
        engine = DeduplicationEngine(
            strategy=DeduplicationStrategy.EXACT,
            key_columns=["id"],
            keep=KeepStrategy.LAST,
        )
        df_out, _ = engine.deduplicate(df)
        assert len(df_out) == 2
        assert df_out[df_out["id"] == "A"]["value"].iloc[0] == 2

    def test_dedup_result_metrics(self, sample_erp_with_issues):
        """Test deduplication result metrics."""
        engine = DeduplicationEngine(
            strategy=DeduplicationStrategy.EXACT,
            key_columns=["transaction_id"],
        )
        _, result = engine.deduplicate(sample_erp_with_issues)
        assert result.total_input == len(sample_erp_with_issues)
        assert result.total_output <= result.total_input
        assert result.dedup_rate >= 0

    def test_empty_df_dedup(self):
        """Test deduplication of empty DataFrame."""
        engine = DeduplicationEngine(strategy=DeduplicationStrategy.EXACT)
        df_out, result = engine.deduplicate(pd.DataFrame())
        assert result.total_input == 0
        assert result.duplicates_removed == 0


# =============================================================================
# SchemaEnforcer Tests
# =============================================================================

class TestSchemaEnforcer:
    """Tests for schema validation."""

    def test_register_schema(self):
        """Test schema registration."""
        enforcer = SchemaEnforcer()
        enforcer.register_schema(CRM_SCHEMA)
        enforcer.register_schema(ERP_SCHEMA)
        assert len(enforcer.schemas) == 2

    def test_permissive_mode(self, sample_erp_df):
        """Test permissive mode keeps all rows."""
        enforcer = SchemaEnforcer(mode=SchemaMode.PERMISSIVE)
        enforcer.register_schema(ERP_SCHEMA)
        df_out, violations = enforcer.enforce(sample_erp_df, "erp_transactions")
        assert len(df_out) == len(sample_erp_df)

    def test_list_schemas(self):
        """Test schema listing."""
        enforcer = SchemaEnforcer()
        enforcer.register_schema(CRM_SCHEMA)
        schemas = enforcer.list_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "crm_contacts"
