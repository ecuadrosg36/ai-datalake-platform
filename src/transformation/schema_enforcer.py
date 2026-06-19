"""
Schema Enforcer — Schema validation and evolution handling.

Validates data against defined schemas and supports backward-compatible
schema evolution. Ensures data consistency across the data lake.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class SchemaMode(Enum):
    """How to handle schema violations."""
    STRICT = "strict"          # Reject records that don't match schema
    PERMISSIVE = "permissive"  # Accept but tag non-conforming records
    DROP = "drop"              # Silently drop non-conforming columns


class ColumnType(Enum):
    """Supported column data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ColumnSchema:
    """Schema definition for a single column."""
    name: str
    type: ColumnType
    required: bool = False
    nullable: bool = True
    description: str = ""
    default: Any = None


@dataclass
class TableSchema:
    """Schema definition for a dataset/table."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    columns: list[ColumnSchema] = field(default_factory=list)
    partition_columns: list[str] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def get_column(self, name: str) -> ColumnSchema | None:
        """Get a column schema by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    @property
    def required_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.required]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "columns": [
                {
                    "name": c.name,
                    "type": c.type.value,
                    "required": c.required,
                    "nullable": c.nullable,
                    "description": c.description,
                }
                for c in self.columns
            ],
            "partition_columns": self.partition_columns,
            "primary_key": self.primary_key,
            "created_at": self.created_at,
        }


# --- Predefined Schemas for the Data Lake ---

CRM_SCHEMA = TableSchema(
    name="crm_contacts",
    version="1.0.0",
    description="CRM contact records from various CRM platforms",
    columns=[
        ColumnSchema("contact_id", ColumnType.STRING, required=True, nullable=False,
                      description="Unique contact identifier"),
        ColumnSchema("first_name", ColumnType.STRING, required=False,
                      description="Contact first name"),
        ColumnSchema("last_name", ColumnType.STRING, required=False,
                      description="Contact last name"),
        ColumnSchema("email", ColumnType.STRING, required=True, nullable=False,
                      description="Contact email address"),
        ColumnSchema("company", ColumnType.STRING, required=True,
                      description="Company name"),
        ColumnSchema("industry", ColumnType.STRING, required=False,
                      description="Industry sector"),
        ColumnSchema("country", ColumnType.STRING, required=False,
                      description="Country code or name"),
        ColumnSchema("city", ColumnType.STRING, required=False,
                      description="City name"),
        ColumnSchema("lifecycle_stage", ColumnType.STRING, required=False,
                      description="CRM lifecycle stage"),
        ColumnSchema("deal_value_usd", ColumnType.FLOAT, required=False,
                      description="Deal value in USD"),
        ColumnSchema("created_at", ColumnType.TIMESTAMP, required=False,
                      description="Record creation timestamp"),
        ColumnSchema("last_interaction", ColumnType.TIMESTAMP, required=False,
                      description="Last customer interaction timestamp"),
        ColumnSchema("tags", ColumnType.STRING, required=False,
                      description="Comma-separated tags"),
    ],
    primary_key=["contact_id"],
    partition_columns=["_partition_year", "_partition_month", "_partition_day"],
)

ERP_SCHEMA = TableSchema(
    name="erp_transactions",
    version="1.0.0",
    description="ERP transaction records from various ERP systems",
    columns=[
        ColumnSchema("transaction_id", ColumnType.STRING, required=True, nullable=False,
                      description="Unique transaction identifier"),
        ColumnSchema("order_date", ColumnType.DATE, required=True,
                      description="Order date"),
        ColumnSchema("customer_id", ColumnType.STRING, required=True,
                      description="Customer identifier"),
        ColumnSchema("product_sku", ColumnType.STRING, required=True,
                      description="Product SKU code"),
        ColumnSchema("product_name", ColumnType.STRING, required=False,
                      description="Product name"),
        ColumnSchema("category", ColumnType.STRING, required=False,
                      description="Product category"),
        ColumnSchema("quantity", ColumnType.INTEGER, required=True,
                      description="Quantity ordered"),
        ColumnSchema("unit_price", ColumnType.FLOAT, required=False,
                      description="Unit price"),
        ColumnSchema("total_amount", ColumnType.FLOAT, required=True,
                      description="Total transaction amount"),
        ColumnSchema("currency", ColumnType.STRING, required=False,
                      description="Currency code (USD, MXN, etc.)"),
        ColumnSchema("status", ColumnType.STRING, required=False,
                      description="Transaction status"),
        ColumnSchema("country", ColumnType.STRING, required=False,
                      description="Country"),
        ColumnSchema("region", ColumnType.STRING, required=False,
                      description="Geographic region"),
    ],
    primary_key=["transaction_id"],
    partition_columns=["_partition_year", "_partition_month", "_partition_day"],
)


class SchemaEnforcer:
    """
    Schema validation and evolution engine.

    Validates DataFrames against defined schemas and handles schema evolution
    (adding new columns, relaxing constraints) while maintaining backward
    compatibility.

    Usage:
        enforcer = SchemaEnforcer(mode=SchemaMode.STRICT)

        # Register schemas
        enforcer.register_schema(CRM_SCHEMA)
        enforcer.register_schema(ERP_SCHEMA)

        # Validate
        df_valid, violations = enforcer.enforce(df, schema_name="crm_contacts")
    """

    def __init__(self, mode: SchemaMode = SchemaMode.STRICT):
        self.mode = mode
        self.schemas: dict[str, TableSchema] = {}

    def register_schema(self, schema: TableSchema) -> None:
        """Register a table schema."""
        self.schemas[schema.name] = schema
        logger.info(
            f"Schema registered: {schema.name} v{schema.version} "
            f"({len(schema.columns)} columns)"
        )

    def get_schema(self, name: str) -> TableSchema | None:
        """Get a registered schema by name."""
        return self.schemas.get(name)

    def enforce(
        self, df: pd.DataFrame, schema_name: str
    ) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        """
        Enforce schema on a DataFrame.

        Args:
            df: The DataFrame to validate.
            schema_name: Name of the registered schema to enforce.

        Returns:
            Tuple of (validated_df, violations_list).
            In STRICT mode, invalid rows are removed from the DataFrame.
            In PERMISSIVE mode, all rows are kept but tagged.
            In DROP mode, non-conforming columns are dropped.
        """
        schema = self.schemas.get(schema_name)
        if schema is None:
            raise ValueError(f"Schema '{schema_name}' not registered")

        violations: list[dict[str, Any]] = []
        valid_mask = pd.Series([True] * len(df), index=df.index)

        # Check required columns exist
        for col_schema in schema.columns:
            if col_schema.required and col_schema.name not in df.columns:
                violations.append({
                    "type": "missing_required_column",
                    "column": col_schema.name,
                    "message": f"Required column '{col_schema.name}' is missing",
                })
                if self.mode == SchemaMode.STRICT:
                    logger.error(f"Required column missing: {col_schema.name}")
                    return pd.DataFrame(), violations

        # Validate each column
        for col_schema in schema.columns:
            if col_schema.name not in df.columns:
                continue

            # Check nullable
            if not col_schema.nullable:
                null_mask = df[col_schema.name].isna()
                if null_mask.any():
                    null_count = null_mask.sum()
                    violations.append({
                        "type": "null_violation",
                        "column": col_schema.name,
                        "count": int(null_count),
                        "message": f"Non-nullable column '{col_schema.name}' has {null_count} null values",
                    })
                    if self.mode == SchemaMode.STRICT:
                        valid_mask &= ~null_mask

            # Type validation
            type_violations = self._validate_types(df, col_schema)
            if type_violations:
                violations.extend(type_violations)
                if self.mode == SchemaMode.STRICT:
                    for v in type_violations:
                        if "invalid_indices" in v:
                            valid_mask.iloc[v["invalid_indices"]] = False

        # Handle extra columns not in schema
        schema_cols = set(schema.column_names)
        # Include metadata columns (starting with _)
        extra_cols = [
            c for c in df.columns
            if c not in schema_cols and not c.startswith("_")
        ]
        if extra_cols:
            if self.mode == SchemaMode.DROP:
                df = df.drop(columns=extra_cols)
                violations.append({
                    "type": "extra_columns_dropped",
                    "columns": extra_cols,
                    "message": f"Dropped {len(extra_cols)} extra columns: {extra_cols}",
                })
            elif self.mode == SchemaMode.PERMISSIVE:
                violations.append({
                    "type": "extra_columns_kept",
                    "columns": extra_cols,
                    "message": f"{len(extra_cols)} extra columns found and kept: {extra_cols}",
                })

        # Apply mask in strict mode
        if self.mode == SchemaMode.STRICT:
            removed = (~valid_mask).sum()
            if removed > 0:
                logger.warning(f"Removed {removed} invalid rows (STRICT mode)")
                df = df[valid_mask].reset_index(drop=True)

        logger.info(
            f"Schema enforcement complete: {len(violations)} violations, "
            f"mode={self.mode.value}, {len(df)} rows remaining"
        )

        return df, violations

    def _validate_types(
        self, df: pd.DataFrame, col_schema: ColumnSchema
    ) -> list[dict[str, Any]]:
        """Validate data types for a column."""
        violations: list[dict[str, Any]] = []
        col = col_schema.name

        if col not in df.columns:
            return violations

        if col_schema.type == ColumnType.INTEGER:
            numeric = pd.to_numeric(df[col], errors="coerce")
            invalid = df[col].notna() & numeric.isna()
            if invalid.any():
                violations.append({
                    "type": "type_mismatch",
                    "column": col,
                    "expected_type": "integer",
                    "count": int(invalid.sum()),
                    "message": f"Column '{col}': {invalid.sum()} non-integer values",
                })

        elif col_schema.type == ColumnType.FLOAT:
            numeric = pd.to_numeric(df[col], errors="coerce")
            invalid = df[col].notna() & numeric.isna()
            if invalid.any():
                violations.append({
                    "type": "type_mismatch",
                    "column": col,
                    "expected_type": "float",
                    "count": int(invalid.sum()),
                    "message": f"Column '{col}': {invalid.sum()} non-numeric values",
                })

        elif col_schema.type in (ColumnType.TIMESTAMP, ColumnType.DATE):
            dates = pd.to_datetime(df[col], errors="coerce")
            invalid = df[col].notna() & dates.isna()
            if invalid.any():
                violations.append({
                    "type": "type_mismatch",
                    "column": col,
                    "expected_type": col_schema.type.value,
                    "count": int(invalid.sum()),
                    "message": f"Column '{col}': {invalid.sum()} invalid date values",
                })

        return violations

    def list_schemas(self) -> list[dict[str, Any]]:
        """List all registered schemas."""
        return [
            {
                "name": s.name,
                "version": s.version,
                "description": s.description,
                "columns": len(s.columns),
                "required_columns": s.required_columns,
            }
            for s in self.schemas.values()
        ]
