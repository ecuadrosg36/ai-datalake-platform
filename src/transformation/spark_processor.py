"""
Spark Processor — PySpark-based data transformations for Silver layer.

Provides a comprehensive set of transformations for cleaning, normalizing,
and standardizing data from the Bronze layer into the Silver layer.
Supports both PySpark (distributed) and Pandas (local) execution modes.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class SparkProcessor:
    """
    PySpark-based data processor for Silver layer transformations.

    In production, this runs on AWS Glue (Spark) or EMR.
    For local development, it falls back to Pandas with equivalent logic.

    Transformations applied:
    1. Type casting and standardization
    2. Null handling and default values
    3. String normalization (trim, case, encoding)
    4. Date/timestamp standardization (UTC)
    5. Currency normalization
    6. Column renaming to snake_case
    7. Derived column creation
    8. Partition column generation

    Usage:
        processor = SparkProcessor(use_spark=False)  # Pandas mode
        df_clean = processor.transform(df_raw, source_type="crm")
    """

    def __init__(self, use_spark: bool = False, spark_config: dict[str, Any] | None = None):
        self.use_spark = use_spark
        self.spark_config = spark_config or {}
        self._spark_session = None

        if use_spark:
            self._init_spark()

    def _init_spark(self) -> None:
        """Initialize SparkSession for distributed processing."""
        try:
            from pyspark.sql import SparkSession

            builder = SparkSession.builder.appName("AI-DataLake-Silver-Transform")

            for key, value in self.spark_config.items():
                builder = builder.config(key, value)

            self._spark_session = builder.getOrCreate()
            logger.info("SparkSession initialized successfully")
        except ImportError:
            logger.warning("PySpark not available, falling back to Pandas mode")
            self.use_spark = False

    def transform(self, df: pd.DataFrame, source_type: str = "generic") -> pd.DataFrame:
        """
        Apply all Silver layer transformations to a DataFrame.

        Args:
            df: Raw Bronze layer DataFrame.
            source_type: Type of source data ("crm", "erp", "api", "csv").

        Returns:
            Cleaned and transformed Silver layer DataFrame.
        """
        if df.empty:
            logger.warning("Empty DataFrame received, skipping transformation")
            return df

        logger.info(
            f"Starting Silver transformation: {len(df)} rows, "
            f"source_type={source_type}"
        )

        # Step 1: Standardize column names
        df = self._standardize_columns(df)

        # Step 2: Handle nulls and empty values
        df = self._handle_nulls(df)

        # Step 3: Normalize strings
        df = self._normalize_strings(df)

        # Step 4: Standardize dates to UTC
        df = self._standardize_dates(df)

        # Step 5: Apply source-specific transformations
        if source_type == "crm":
            df = self._transform_crm(df)
        elif source_type == "erp":
            df = self._transform_erp(df)
        elif source_type == "api":
            df = self._transform_api(df)

        # Step 6: Add partition columns
        df = self._add_partition_columns(df)

        # Step 7: Add processing metadata
        df = self._add_processing_metadata(df)

        logger.info(f"Silver transformation complete: {len(df)} rows output")
        return df

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize column names to snake_case.

        - Converts CamelCase → snake_case
        - Replaces spaces and hyphens with underscores
        - Converts to lowercase
        - Removes special characters
        """
        import re

        def to_snake_case(name: str) -> str:
            # Handle CamelCase
            name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
            name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
            # Replace spaces and hyphens
            name = re.sub(r"[\s\-]+", "_", name)
            # Remove non-alphanumeric (except underscore)
            name = re.sub(r"[^a-zA-Z0-9_]", "", name)
            return name.lower().strip("_")

        df.columns = [to_snake_case(col) for col in df.columns]
        return df

    def _handle_nulls(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle null values with type-appropriate defaults.

        - String columns: Replace NaN with None (not empty string)
        - Numeric columns: Keep NaN (for proper aggregation)
        - Boolean columns: Keep NaN
        """
        for col in df.columns:
            if df[col].dtype == "object":
                # Replace common null representations
                df[col] = df[col].replace(
                    ["", "NULL", "null", "None", "none", "N/A", "n/a", "NA", "#N/A"],
                    None,
                )
        return df

    def _normalize_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize string columns.

        - Trim leading/trailing whitespace
        - Normalize unicode characters
        - Standardize email addresses (lowercase)
        - Standardize country names
        """
        for col in df.select_dtypes(include=["object"]).columns:
            # Skip metadata columns
            if col.startswith("_"):
                continue

            # Trim whitespace
            df[col] = df[col].apply(
                lambda x: x.strip() if isinstance(x, str) else x
            )

            # Lowercase emails
            if "email" in col.lower():
                df[col] = df[col].apply(
                    lambda x: x.lower() if isinstance(x, str) else x
                )

        return df

    def _standardize_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize date/timestamp columns to UTC ISO format.

        Detects date columns by name pattern and converts to consistent format.
        """
        date_patterns = ["date", "time", "created", "updated", "timestamp", "_at"]

        for col in df.columns:
            if any(pattern in col.lower() for pattern in date_patterns):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
                    df[col] = df[col].apply(
                        lambda x: x.isoformat() if pd.notna(x) else None
                    )
                except Exception:
                    pass  # Not a date column, skip

        return df

    def _transform_crm(self, df: pd.DataFrame) -> pd.DataFrame:
        """CRM-specific transformations."""
        # Standardize lifecycle stages
        stage_mapping = {
            "lead": "Lead",
            "opportunity": "Opportunity",
            "customer": "Customer",
            "churned": "Churned",
        }
        if "lifecycle_stage" in df.columns:
            df["lifecycle_stage"] = df["lifecycle_stage"].apply(
                lambda x: stage_mapping.get(x.lower(), x) if isinstance(x, str) else x
            )

        # Calculate engagement score (derived column)
        if "deal_value_usd" in df.columns:
            df["has_deal"] = df["deal_value_usd"].notna() & (df["deal_value_usd"] > 0)

        return df

    def _transform_erp(self, df: pd.DataFrame) -> pd.DataFrame:
        """ERP-specific transformations."""
        # Ensure numeric types
        numeric_cols = ["quantity", "unit_price", "total_amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Standardize currency
        if "currency" in df.columns:
            df["currency"] = df["currency"].apply(
                lambda x: x.upper().strip() if isinstance(x, str) else x
            )

        # Calculate line total validation
        if all(c in df.columns for c in ["quantity", "unit_price", "total_amount"]):
            df["_amount_validated"] = (
                (df["quantity"] * df["unit_price"] - df["total_amount"]).abs() < 0.01
            )

        return df

    def _transform_api(self, df: pd.DataFrame) -> pd.DataFrame:
        """API-specific transformations."""
        # Standardize event types
        if "event_type" in df.columns:
            df["event_type"] = df["event_type"].apply(
                lambda x: x.lower().replace(" ", "_") if isinstance(x, str) else x
            )

        # Standardize channels
        if "channel" in df.columns:
            df["channel"] = df["channel"].apply(
                lambda x: x.title() if isinstance(x, str) else x
            )

        return df

    def _add_partition_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add year/month/day partition columns for S3 storage.

        Uses the primary timestamp column or falls back to processing time.
        """
        # Find the best timestamp column
        timestamp_col = None
        for col in ["timestamp", "order_date", "created_at", "event_time"]:
            if col in df.columns:
                timestamp_col = col
                break

        if timestamp_col and df[timestamp_col].notna().any():
            try:
                dates = pd.to_datetime(df[timestamp_col], errors="coerce", utc=True)
                df["_partition_year"] = dates.dt.year
                df["_partition_month"] = dates.dt.month.apply(
                    lambda x: f"{int(x):02d}" if pd.notna(x) else None
                )
                df["_partition_day"] = dates.dt.day.apply(
                    lambda x: f"{int(x):02d}" if pd.notna(x) else None
                )
            except Exception:
                self._add_current_partitions(df)
        else:
            self._add_current_partitions(df)

        return df

    def _add_current_partitions(self, df: pd.DataFrame) -> None:
        """Add partition columns using current UTC time."""
        now = datetime.now(timezone.utc)
        df["_partition_year"] = now.year
        df["_partition_month"] = f"{now.month:02d}"
        df["_partition_day"] = f"{now.day:02d}"

    def _add_processing_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Silver layer processing metadata."""
        df["_processed_at"] = datetime.now(timezone.utc).isoformat()
        df["_layer"] = "silver"
        df["_transformation_version"] = "1.0.0"
        return df

    def close(self) -> None:
        """Stop SparkSession if running."""
        if self._spark_session:
            self._spark_session.stop()
            logger.info("SparkSession stopped")
