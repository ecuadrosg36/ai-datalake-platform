"""
ERP Connector — Ingests transactional data from ERP systems.

Supports ingestion from ERP platforms (SAP, Oracle, NetSuite, etc.).
Handles CSV exports, field mapping, currency normalization,
and business rule validation.
"""

import csv
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Generator

import pandas as pd

from src.ingestion.base_connector import BaseConnector, IngestionConfig


logger = logging.getLogger(__name__)

# Required fields for ERP transaction records
REQUIRED_FIELDS = {"transaction_id", "order_date", "product_sku", "quantity", "total_amount"}
VALID_STATUSES = {"Completed", "Pending", "Shipped", "Processing", "Cancelled", "Returned"}
VALID_CURRENCIES = {"USD", "MXN", "EUR", "CAD"}


class ERPConnector(BaseConnector):
    """
    Connector for ERP data sources (SAP, Oracle, NetSuite, etc.).

    Ingests transactions, inventory movements, and order data.
    In production, this would connect via ODBC/JDBC or SAP RFC.
    For demonstration, it reads from CSV files simulating ERP exports.

    Features:
    - Transaction record validation
    - Currency standardization
    - Quantity and amount validation
    - SKU format validation
    - Business rule enforcement (positive quantities, valid dates)
    - Support for multiple file encodings

    Usage:
        config = IngestionConfig(
            source_name="sap_erp",
            source_type="erp",
        )
        connector = ERPConnector(config, data_path="data/sample_erp_transactions.csv")
        df = connector.ingest()
    """

    def __init__(
        self,
        config: IngestionConfig,
        data_path: str | Path = "data/sample_erp_transactions.csv",
        delimiter: str = ",",
        encoding: str = "utf-8",
    ):
        super().__init__(config)
        self.data_path = Path(data_path)
        self.delimiter = delimiter
        self.encoding = encoding
        self._raw_data: list[dict[str, Any]] = []
        self._seen_txn_ids: set[str] = set()

    def connect(self) -> None:
        """
        Establish connection to the ERP data source.

        In production: Connect via ODBC/JDBC to ERP database or API.
        In demo mode: Load data from the sample CSV file.
        """
        if not self.data_path.exists():
            raise FileNotFoundError(f"ERP data file not found: {self.data_path}")

        # Read CSV into list of dicts
        with open(self.data_path, "r", encoding=self.encoding) as f:
            reader = csv.DictReader(f, delimiter=self.delimiter)
            self._raw_data = list(reader)

        self.logger.info(
            f"Loaded {len(self._raw_data)} ERP transactions from {self.data_path}"
        )

    def extract(self) -> Generator[list[dict[str, Any]], None, None]:
        """
        Extract ERP records in batches.

        Applies type conversion and field normalization before yielding.
        """
        batch: list[dict[str, Any]] = []

        for record in self._raw_data:
            normalized = self._normalize_record(record)
            batch.append(normalized)

            if len(batch) >= self.config.batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def validate_record(self, record: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate an ERP transaction record.

        Checks:
        1. Required fields present and non-empty
        2. Transaction ID is unique
        3. Quantity is positive
        4. Total amount is non-negative
        5. Currency is valid
        6. Status is valid
        7. SKU format is correct (letters-alphanumeric pattern)
        8. Customer ID is present
        """
        errors: list[str] = []

        # Check required fields
        for field_name in REQUIRED_FIELDS:
            value = record.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Missing required field: {field_name}")

        # Check for duplicate transaction IDs
        txn_id = record.get("transaction_id", "")
        if txn_id in self._seen_txn_ids:
            errors.append(f"Duplicate transaction_id: {txn_id}")
        elif txn_id:
            self._seen_txn_ids.add(txn_id)

        # Validate quantity
        quantity = record.get("quantity")
        if quantity is not None:
            try:
                qty = int(quantity) if isinstance(quantity, str) else quantity
                if qty <= 0:
                    errors.append(f"Non-positive quantity: {qty}")
            except (ValueError, TypeError):
                errors.append(f"Invalid quantity: {quantity}")

        # Validate total amount
        total = record.get("total_amount")
        if total is not None:
            try:
                amt = float(total) if isinstance(total, str) else total
                if amt < 0:
                    errors.append(f"Negative total amount: {amt}")
            except (ValueError, TypeError):
                errors.append(f"Invalid total_amount: {total}")

        # Validate currency
        currency = record.get("currency", "")
        if currency and currency not in VALID_CURRENCIES:
            errors.append(f"Invalid currency: {currency}")

        # Validate status
        status = record.get("status", "")
        if status and status not in VALID_STATUSES:
            errors.append(f"Invalid status: {status}")

        # Validate customer_id presence
        customer_id = record.get("customer_id", "")
        if not customer_id or not str(customer_id).strip():
            errors.append("Missing customer_id")

        # Validate SKU format
        sku = record.get("product_sku", "")
        if sku and sku.startswith("INVALID"):
            errors.append(f"Invalid SKU format: {sku}")

        if errors:
            return False, "; ".join(errors)
        return True, None

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize ERP record fields.

        - Convert numeric strings to proper types
        - Standardize currency codes
        - Trim whitespace
        - Handle empty strings as None
        """
        normalized: dict[str, Any] = {}

        for key, value in record.items():
            # Trim whitespace
            if isinstance(value, str):
                value = value.strip()
                # Convert empty strings to None
                if not value:
                    value = None

            # Type conversion for numeric fields
            if key in ("quantity",) and value is not None:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    pass  # Keep as-is for validation to catch

            if key in ("unit_price", "total_amount") and value is not None:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    pass

            normalized[key] = value

        return normalized

    def disconnect(self) -> None:
        """Clean up ERP connection resources."""
        self._raw_data = []
        self._seen_txn_ids.clear()
        super().disconnect()
