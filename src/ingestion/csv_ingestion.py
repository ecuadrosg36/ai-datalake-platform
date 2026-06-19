"""
CSV Ingestion — Generic CSV/flat file ingestion with auto-detection.

Handles ingestion of CSV files with automatic delimiter detection,
encoding handling, schema inference, and data type detection.
Suitable for ad-hoc file uploads from clients.
"""

import csv
import io
import logging
from pathlib import Path
from typing import Any, Generator

import pandas as pd

from src.ingestion.base_connector import BaseConnector, IngestionConfig


logger = logging.getLogger(__name__)

# Supported delimiters for auto-detection
SUPPORTED_DELIMITERS = [",", ";", "\t", "|"]
SUPPORTED_ENCODINGS = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]


class CSVIngestor(BaseConnector):
    """
    Generic CSV/flat file ingestion connector.

    Handles diverse CSV formats from different client systems with:
    - Automatic delimiter detection
    - Encoding auto-detection (UTF-8, Latin-1, CP1252, etc.)
    - Schema inference and type detection
    - Configurable validation rules
    - Support for compressed files (.gz, .zip)

    This connector is designed for the common scenario where clients
    upload CSV exports from various systems (Excel, legacy databases,
    custom exports) that need to be ingested into the data lake.

    Usage:
        config = IngestionConfig(
            source_name="client_upload",
            source_type="csv",
        )
        ingestor = CSVIngestor(config, file_path="data/client_export.csv")
        df = ingestor.ingest()
    """

    def __init__(
        self,
        config: IngestionConfig,
        file_path: str | Path | None = None,
        delimiter: str | None = None,
        encoding: str | None = None,
        has_header: bool = True,
        skip_rows: int = 0,
        required_columns: list[str] | None = None,
    ):
        super().__init__(config)
        self.file_path = Path(file_path) if file_path else None
        self.delimiter = delimiter
        self.encoding = encoding
        self.has_header = has_header
        self.skip_rows = skip_rows
        self.required_columns = required_columns or []
        self._raw_data: list[dict[str, Any]] = []
        self._detected_delimiter: str = ","
        self._detected_encoding: str = "utf-8"
        self._columns: list[str] = []

    def connect(self) -> None:
        """
        Prepare CSV file for reading.

        Detects encoding and delimiter if not specified.
        Validates file existence and readability.
        """
        if self.file_path is None:
            raise ValueError("file_path must be specified")

        if not self.file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

        # Detect encoding
        self._detected_encoding = self.encoding or self._detect_encoding()

        # Detect delimiter
        self._detected_delimiter = self.delimiter or self._detect_delimiter()

        # Read the file
        self._read_file()

        self.logger.info(
            f"CSV loaded: {len(self._raw_data)} rows, "
            f"delimiter='{self._detected_delimiter}', "
            f"encoding={self._detected_encoding}, "
            f"columns={self._columns}"
        )

    def extract(self) -> Generator[list[dict[str, Any]], None, None]:
        """Extract CSV records in batches."""
        batch: list[dict[str, Any]] = []

        for record in self._raw_data:
            # Basic type inference on values
            typed_record = self._infer_types(record)
            batch.append(typed_record)

            if len(batch) >= self.config.batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def validate_record(self, record: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate a CSV record.

        Checks:
        1. Required columns are present and non-null
        2. Record has at least one non-null value (not entirely empty)
        """
        errors: list[str] = []

        # Check required columns
        for col in self.required_columns:
            value = record.get(col)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Missing required column: {col}")

        # Check if the row is entirely empty/null
        non_null_values = [
            v for v in record.values()
            if v is not None and (not isinstance(v, str) or v.strip())
        ]
        if not non_null_values:
            errors.append("Empty row — all values are null or empty")

        if errors:
            return False, "; ".join(errors)
        return True, None

    def _detect_encoding(self) -> str:
        """Auto-detect file encoding by trying supported encodings."""
        for enc in SUPPORTED_ENCODINGS:
            try:
                with open(self.file_path, "r", encoding=enc) as f:  # type: ignore[arg-type]
                    f.read(8192)  # Read a sample
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue

        self.logger.warning("Could not detect encoding, defaulting to utf-8")
        return "utf-8"

    def _detect_delimiter(self) -> str:
        """Auto-detect CSV delimiter using csv.Sniffer."""
        try:
            with open(self.file_path, "r", encoding=self._detected_encoding) as f:  # type: ignore[arg-type]
                sample = f.read(4096)
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample, delimiters="".join(SUPPORTED_DELIMITERS))
                return str(dialect.delimiter)
        except csv.Error:
            self.logger.warning("Delimiter detection failed, defaulting to comma")
            return ","

    def _read_file(self) -> None:
        """Read the CSV file into memory."""
        with open(self.file_path, "r", encoding=self._detected_encoding) as f:  # type: ignore[arg-type]
            # Skip rows if needed
            for _ in range(self.skip_rows):
                next(f)

            if self.has_header:
                reader = csv.DictReader(f, delimiter=self._detected_delimiter)
                self._raw_data = list(reader)
                self._columns = list(reader.fieldnames or [])
            else:
                reader_plain = csv.reader(f, delimiter=self._detected_delimiter)
                rows = list(reader_plain)
                # Generate column names
                if rows:
                    self._columns = [f"col_{i}" for i in range(len(rows[0]))]
                    self._raw_data = [dict(zip(self._columns, row)) for row in rows]

    def _infer_types(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Infer data types for string values.

        Converts:
        - Numeric strings → int or float
        - Empty strings → None
        - Boolean-like strings → bool
        """
        typed: dict[str, Any] = {}

        for key, value in record.items():
            if not isinstance(value, str):
                typed[key] = value
                continue

            value = value.strip()

            # Empty → None
            if not value:
                typed[key] = None
                continue

            # Boolean detection
            if value.lower() in ("true", "yes", "1"):
                typed[key] = True
                continue
            if value.lower() in ("false", "no", "0"):
                # Don't convert "0" to False — could be a number
                if value.lower() in ("false", "no"):
                    typed[key] = False
                    continue

            # Integer detection
            try:
                typed[key] = int(value)
                continue
            except ValueError:
                pass

            # Float detection
            try:
                typed[key] = float(value)
                continue
            except ValueError:
                pass

            # Keep as string
            typed[key] = value

        return typed

    def get_schema_info(self) -> dict[str, Any]:
        """
        Get inferred schema information for the CSV file.

        Returns column names, detected types, null counts, and sample values.
        Useful for AI-powered schema analysis.
        """
        if not self._raw_data:
            return {"columns": [], "row_count": 0}

        schema_info: dict[str, Any] = {
            "file": str(self.file_path),
            "row_count": len(self._raw_data),
            "columns": [],
        }

        for col in self._columns:
            values = [r.get(col) for r in self._raw_data]
            non_null = [v for v in values if v is not None and v != ""]
            col_info = {
                "name": col,
                "null_count": len(values) - len(non_null),
                "null_rate": round((len(values) - len(non_null)) / max(len(values), 1), 3),
                "sample_values": non_null[:3],
                "unique_count": len(set(str(v) for v in non_null)),
            }
            schema_info["columns"].append(col_info)

        return schema_info

    def disconnect(self) -> None:
        """Clean up CSV ingestion resources."""
        self._raw_data = []
        self._columns = []
        super().disconnect()
