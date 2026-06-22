"""
OGGI S3 Connector — Ingests real data from OGGI's AWS S3 data lake.

Connects to the OGGI lakehouse S3 bucket and reads Parquet files from the
Medallion Architecture layers (silver/gold). Handles snapshot-based
partitioning, MFA session tokens, and OGGI-specific data validation.

S3 Bucket: oggi-lakehouse-landing-276483282865-us-east-2
Region: us-east-2
"""

import io
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator

import pandas as pd

from src.ingestion.base_connector import BaseConnector, IngestionConfig

logger = logging.getLogger(__name__)


# OGGI Company IDs for validation
VALID_COMPANY_IDS = {
    "OGGI_MAYOREO", "OGGI_JUNIOR", "OGGI_TEZIUTLAN",
    "SOF", "BLUSTER", "DYCLASS", "BUYING", "JUNIOR_NOMINA",
}

# OGGI Company Groups
VALID_COMPANY_GROUPS = {"OGGI", "SOF", "BLUSTER", "DYCLASS", "BUYING", "JUNIOR_NOMINA"}

# OGGI S3 bucket configuration
OGGI_BUCKET = "oggi-lakehouse-landing-276483282865-us-east-2"
OGGI_REGION = "us-east-2"

# Available datasets by layer
SILVER_DATASETS = {
    "facturas", "pagos", "pedidos", "customer", "company", "item", "vendor",
    "aspel-coi", "aspel-noi", "location", "warehouse", "carrier",
    "receipt_header", "receipt_detail", "receipt_container",
    "shipment_header", "shipment_detail", "shipping_address", "shipping_load",
    "location_inventory", "location_inventory_attributes",
    "process_history", "transaction_history", "labor_management_detail",
    "productos-sku", "item_unit_of_measure", "presupuesto-ventas", "zone",
    "CAT", "VTA", "PED", "INV",
}

GOLD_DATASETS = {
    "dim_company", "dim_articulo", "fct_sell_in", "fct_bom_intensity",
    "fct_production_order", "fct_inventory", "fct_maquila_cost",
    "fct_maquila_assignment", "fct_maquila_scorecard", "fct_maquila_quality",
    "fct_garment_defect", "fct_mrp_requirements",
    "pnl_canonical", "rentabilidad_cliente", "maquila_plan_optimo",
    "g_crosswalk_style", "g_dim_ean", "g_sell_out_coppel",
    "g_sell_out_suburbia", "sell_out_sears", "mart_sell_through",
    "forecast",
}


@dataclass
class OGGIDatasetConfig:
    """Configuration for an OGGI dataset to ingest."""
    layer: str                    # "silver" or "gold"
    dataset_name: str             # e.g., "facturas", "dim_company"
    snapshot: str | None = None   # e.g., "2026-06-19" (None = latest)
    s3_prefix: str = ""           # Custom S3 prefix override
    local_cache_dir: str = ""     # Local directory for downloaded files
    max_files: int = 10           # Max files to download per dataset


class OGGIS3Connector(BaseConnector):
    """
    Connector for OGGI's S3-based data lake.

    Reads Parquet files from the OGGI lakehouse bucket, supporting both
    silver and gold layer datasets with snapshot-based partitioning.

    Features:
    - Reads directly from S3 or from locally cached Parquet files
    - Supports snapshot-based partitioning (snapshot=YYYY-MM-DD)
    - dt-based partitioning for silver layer (dt=YYYY-MM-DD)
    - Validates OGGI-specific business rules (company IDs, amounts)
    - Handles MFA session tokens for AWS authentication
    - Bronze data is IMMUTABLE — this connector is READ-ONLY

    Usage:
        config = IngestionConfig(
            source_name="oggi_lake",
            source_type="s3_parquet",
        )
        dataset = OGGIDatasetConfig(
            layer="gold",
            dataset_name="dim_company",
            snapshot="2026-06-19",
        )
        connector = OGGIS3Connector(config, dataset)
        df = connector.ingest()
    """

    def __init__(
        self,
        config: IngestionConfig,
        dataset: OGGIDatasetConfig,
        aws_profile: str | None = None,
        local_path: str | Path | None = None,
    ):
        super().__init__(config)
        self.dataset = dataset
        self.aws_profile = aws_profile
        self.local_path = Path(local_path) if local_path else None
        self._dataframes: list[pd.DataFrame] = []
        self._s3_client = None
        self._use_local = local_path is not None

        # Build S3 prefix
        if dataset.s3_prefix:
            self._s3_prefix = dataset.s3_prefix
        elif dataset.layer == "gold":
            self._s3_prefix = f"gold/gm3s_envio/{dataset.dataset_name}/"
        elif dataset.layer == "silver":
            self._s3_prefix = f"silver/gm3s_envio/{dataset.dataset_name}/"
        else:
            self._s3_prefix = f"{dataset.layer}/{dataset.dataset_name}/"

    def connect(self) -> None:
        """
        Establish connection to OGGI S3 bucket or local cache.

        If local_path is provided, reads from local Parquet files.
        Otherwise, connects to S3 using boto3 with MFA session support.
        """
        if self._use_local:
            if not self.local_path or not self.local_path.exists():
                raise FileNotFoundError(
                    f"Local cache directory not found: {self.local_path}"
                )
            self._load_local_parquet()
        else:
            self._connect_s3()

        self.logger.info(
            f"Connected to OGGI {self.dataset.layer}/{self.dataset.dataset_name} "
            f"— loaded {len(self._dataframes)} file(s)"
        )

    def _load_local_parquet(self) -> None:
        """Load Parquet files from local cache directory."""
        assert self.local_path is not None

        parquet_files = list(self.local_path.rglob("*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(
                f"No Parquet files found in {self.local_path}"
            )

        # If snapshot is specified, filter to that snapshot
        if self.dataset.snapshot:
            snapshot_dir = f"snapshot={self.dataset.snapshot}"
            parquet_files = [
                f for f in parquet_files
                if snapshot_dir in str(f)
            ]
            if not parquet_files:
                # Try dt-based partitioning (silver layer)
                dt_dir = f"dt={self.dataset.snapshot}"
                parquet_files = [
                    f for f in self.local_path.rglob("*.parquet")
                    if dt_dir in str(f)
                ]

        for pf in parquet_files[:self.dataset.max_files]:
            try:
                df = pd.read_parquet(pf)
                # Extract partition info from path
                parts = str(pf).split(os.sep)
                for part in parts:
                    if part.startswith("snapshot="):
                        df["_snapshot"] = part.split("=")[1]
                    elif part.startswith("dt="):
                        df["_dt"] = part.split("=")[1]
                self._dataframes.append(df)
                self.logger.debug(f"Loaded {len(df)} rows from {pf.name}")
            except Exception as e:
                self.logger.warning(f"Failed to read {pf}: {e}")

    def _connect_s3(self) -> None:
        """Connect to S3 and download Parquet files."""
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 access. Install with: pip install boto3"
            )

        session_kwargs: dict[str, Any] = {"region_name": OGGI_REGION}
        if self.aws_profile:
            session_kwargs["profile_name"] = self.aws_profile

        session = boto3.Session(**session_kwargs)
        self._s3_client = session.client("s3")

        # Build the full prefix with snapshot filter
        prefix = self._s3_prefix
        if self.dataset.snapshot:
            if self.dataset.layer == "gold":
                prefix = f"{self._s3_prefix}snapshot={self.dataset.snapshot}/"
            elif self.dataset.layer == "silver":
                prefix = f"{self._s3_prefix}dt={self.dataset.snapshot}/"

        # List objects in the prefix
        self.logger.info(f"Listing S3 objects: s3://{OGGI_BUCKET}/{prefix}")
        response = self._s3_client.list_objects_v2(
            Bucket=OGGI_BUCKET,
            Prefix=prefix,
            MaxKeys=self.dataset.max_files * 2,
        )

        contents = response.get("Contents", [])
        parquet_keys = [
            obj["Key"] for obj in contents
            if obj["Key"].endswith(".parquet")
        ]

        if not parquet_keys:
            self.logger.warning(f"No Parquet files found at s3://{OGGI_BUCKET}/{prefix}")
            # Try listing JSON files as fallback
            json_keys = [obj["Key"] for obj in contents if obj["Key"].endswith(".json")]
            if json_keys:
                for key in json_keys[:self.dataset.max_files]:
                    self._download_json_from_s3(key)
            return

        for key in parquet_keys[:self.dataset.max_files]:
            self._download_parquet_from_s3(key)

    def _download_parquet_from_s3(self, key: str) -> None:
        """Download and parse a single Parquet file from S3."""
        self.logger.debug(f"Downloading s3://{OGGI_BUCKET}/{key}")
        response = self._s3_client.get_object(Bucket=OGGI_BUCKET, Key=key)
        body = response["Body"].read()

        df = pd.read_parquet(io.BytesIO(body))

        # Extract partition info from key
        parts = key.split("/")
        for part in parts:
            if part.startswith("snapshot="):
                df["_snapshot"] = part.split("=")[1]
            elif part.startswith("dt="):
                df["_dt"] = part.split("=")[1]

        self._dataframes.append(df)
        self.logger.debug(f"Downloaded {len(df)} rows from {key}")

    def _download_json_from_s3(self, key: str) -> None:
        """Download and parse a JSON file from S3."""
        self.logger.debug(f"Downloading JSON s3://{OGGI_BUCKET}/{key}")
        response = self._s3_client.get_object(Bucket=OGGI_BUCKET, Key=key)
        body = response["Body"].read()

        df = pd.read_json(io.BytesIO(body), lines=True)
        self._dataframes.append(df)

    def extract(self) -> Generator[list[dict[str, Any]], None, None]:
        """
        Extract OGGI records in batches from loaded Parquet files.

        Yields lists of records (dicts) in batch_size chunks.
        """
        for df in self._dataframes:
            records = df.to_dict(orient="records")
            batch: list[dict[str, Any]] = []

            for record in records:
                batch.append(record)

                if len(batch) >= self.config.batch_size:
                    yield batch
                    batch = []

            if batch:
                yield batch

    def validate_record(self, record: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate an OGGI record based on dataset-specific rules.

        Validation depends on the dataset type:
        - dim_company: company_id must be valid
        - facturas/factura_line: amounts must be non-negative
        - All: no completely null records
        """
        errors: list[str] = []

        # Universal check: record should not be all nulls
        non_null_count = sum(
            1 for v in record.values()
            if v is not None and str(v).strip() != "" and str(v) != "nan"
        )
        if non_null_count == 0:
            errors.append("All fields are null/empty")

        # Dataset-specific validation
        dataset = self.dataset.dataset_name

        if dataset == "dim_company":
            company_id = record.get("company_id", "")
            if company_id and company_id not in VALID_COMPANY_IDS:
                errors.append(f"Unknown company_id: {company_id}")

        elif dataset in ("g_factura_line", "fct_sell_in"):
            # Validate amounts
            for amount_field in ("gross_amount", "precio_unit", "costo_unit", "qty"):
                value = record.get(amount_field)
                if value is not None:
                    try:
                        float_val = float(value)
                        # qty can be negative for returns
                        if amount_field != "qty" and float_val < 0:
                            errors.append(f"Negative {amount_field}: {float_val}")
                    except (ValueError, TypeError):
                        errors.append(f"Invalid {amount_field}: {value}")

            # Validate company_id if present
            company_id = record.get("company_id", "")
            if company_id and company_id not in VALID_COMPANY_IDS:
                errors.append(f"Unknown company_id: {company_id}")

        elif dataset == "pnl_canonical":
            # P&L should have company reference
            pass  # Minimal validation for P&L

        elif dataset == "rentabilidad_cliente":
            # Client profitability should have client reference
            cliente_rfc = record.get("cliente_rfc", "")
            if not cliente_rfc or str(cliente_rfc).strip() == "":
                # RFC can be empty for some internal transactions
                pass

        if errors:
            return False, "; ".join(errors)
        return True, None

    def disconnect(self) -> None:
        """Clean up S3 connection resources."""
        self._dataframes = []
        self._s3_client = None
        super().disconnect()

    def get_available_snapshots(self) -> list[str]:
        """
        List available snapshots for the configured dataset.

        Returns list of snapshot dates (e.g., ['2026-06-10', '2026-06-11', ...])
        """
        if self._use_local and self.local_path:
            snapshots = []
            for d in self.local_path.iterdir():
                if d.is_dir():
                    name = d.name
                    if name.startswith("snapshot="):
                        snapshots.append(name.split("=")[1])
                    elif name.startswith("dt="):
                        snapshots.append(name.split("=")[1])
            return sorted(snapshots)

        # For S3, list prefixes
        if not self._s3_client:
            return []

        response = self._s3_client.list_objects_v2(
            Bucket=OGGI_BUCKET,
            Prefix=self._s3_prefix,
            Delimiter="/",
        )
        snapshots = []
        for prefix_info in response.get("CommonPrefixes", []):
            prefix = prefix_info["Prefix"]
            parts = prefix.rstrip("/").split("/")
            last = parts[-1]
            if last.startswith("snapshot=") or last.startswith("dt="):
                snapshots.append(last.split("=")[1])
        return sorted(snapshots)


def create_oggi_connector(
    dataset_name: str,
    layer: str = "gold",
    snapshot: str | None = None,
    local_path: str | Path | None = None,
    batch_size: int = 1000,
) -> OGGIS3Connector:
    """
    Factory function to create an OGGI connector with sensible defaults.

    Args:
        dataset_name: Name of the dataset (e.g., 'dim_company', 'pnl_canonical')
        layer: Medallion layer ('silver' or 'gold')
        snapshot: Snapshot date (e.g., '2026-06-19'), None for latest
        local_path: Path to locally cached Parquet files (optional)
        batch_size: Number of records per batch

    Returns:
        Configured OGGIS3Connector ready to .ingest()

    Example:
        # From local cache
        connector = create_oggi_connector(
            'dim_company', layer='gold', snapshot='2026-06-19',
            local_path='oggi-samples/dim_company'
        )
        df = connector.ingest()

        # From S3 (requires MFA session)
        connector = create_oggi_connector('pnl_canonical', layer='gold')
        df = connector.ingest()
    """
    config = IngestionConfig(
        source_name=f"oggi_{layer}_{dataset_name}",
        source_type="s3_parquet",
        batch_size=batch_size,
        max_retries=3,
        retry_delay_seconds=2.0,
        target_path=f"{layer}/{dataset_name}/",
    )

    dataset_config = OGGIDatasetConfig(
        layer=layer,
        dataset_name=dataset_name,
        snapshot=snapshot,
    )

    return OGGIS3Connector(
        config=config,
        dataset=dataset_config,
        local_path=local_path,
    )
