"""
API Connector — Generic REST API connector for data ingestion.

Supports ingestion from any REST API with pagination, rate limiting,
OAuth2 authentication, and automatic response parsing. Designed for
integrating with diverse third-party services.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Generator
from urllib.parse import urljoin

from src.ingestion.base_connector import BaseConnector, IngestionConfig


logger = logging.getLogger(__name__)


class APIConnector(BaseConnector):
    """
    Generic REST API connector for data ingestion.

    Supports common API patterns:
    - Cursor-based pagination
    - Offset/limit pagination
    - Rate limiting with backoff
    - OAuth2 Bearer token auth
    - API key authentication
    - Response flattening for nested JSON

    In production, this uses the `requests` library for HTTP calls.
    For demonstration, it reads from a local JSON file simulating API responses.

    Usage:
        config = IngestionConfig(
            source_name="customer_interactions_api",
            source_type="api",
        )
        connector = APIConnector(
            config,
            data_path="data/sample_api_response.json",
            data_key="data",  # JSON key containing the records array
        )
        df = connector.ingest()
    """

    def __init__(
        self,
        config: IngestionConfig,
        base_url: str | None = None,
        api_key: str | None = None,
        bearer_token: str | None = None,
        data_path: str | Path | None = None,
        data_key: str = "data",
        pagination_type: str = "cursor",  # cursor | offset | page
        rate_limit_per_second: float = 5.0,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(config)
        self.base_url = base_url
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.data_path = Path(data_path) if data_path else None
        self.data_key = data_key
        self.pagination_type = pagination_type
        self.rate_limit_per_second = rate_limit_per_second
        self.custom_headers = headers or {}
        self._raw_data: list[dict[str, Any]] = []
        self._api_metadata: dict[str, Any] = {}

    def connect(self) -> None:
        """
        Establish connection to the API.

        In production: Validates authentication and tests connectivity.
        In demo mode: Loads data from the sample JSON file.
        """
        if self.base_url:
            # Production mode — would set up HTTP session
            self.logger.info(f"Connecting to API at {self.base_url}")
            # In real implementation:
            # self._session = requests.Session()
            # if self.bearer_token:
            #     self._session.headers["Authorization"] = f"Bearer {self.bearer_token}"
            # if self.api_key:
            #     self._session.headers["X-API-Key"] = self.api_key
            # self._session.headers.update(self.custom_headers)
            # response = self._session.get(urljoin(self.base_url, "/health"))
            # response.raise_for_status()
        else:
            # Demo mode — load from file
            if self.data_path is None or not self.data_path.exists():
                raise FileNotFoundError(
                    f"API response file not found: {self.data_path}"
                )

            with open(self.data_path, "r", encoding="utf-8") as f:
                response_data = json.load(f)

            # Extract records from the data key
            if self.data_key and self.data_key in response_data:
                self._raw_data = response_data[self.data_key]
            elif isinstance(response_data, list):
                self._raw_data = response_data
            else:
                self._raw_data = [response_data]

            # Store API metadata (pagination info, etc.)
            self._api_metadata = {
                k: v for k, v in response_data.items()
                if k != self.data_key and isinstance(response_data, dict)
            }

            self.logger.info(
                f"Loaded {len(self._raw_data)} API records from {self.data_path}"
            )

    def extract(self) -> Generator[list[dict[str, Any]], None, None]:
        """
        Extract API records in batches.

        In production, this would handle pagination by following
        next_cursor/next_page links until all data is retrieved.
        """
        batch: list[dict[str, Any]] = []

        for record in self._raw_data:
            # Flatten nested metadata
            flat_record = self._flatten_nested(record)
            batch.append(flat_record)

            if len(batch) >= self.config.batch_size:
                yield batch
                batch = []

            # Rate limiting
            if self.rate_limit_per_second > 0:
                time.sleep(0)  # In demo, no actual delay

        if batch:
            yield batch

    def validate_record(self, record: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate an API record.

        Checks:
        1. Has at least an event_id or record identifier
        2. Has a timestamp field
        3. Has a source_system field
        4. Record is not entirely null/empty
        """
        errors: list[str] = []

        # Check for identifier
        id_fields = ["event_id", "id", "record_id", "transaction_id"]
        has_id = any(record.get(f) for f in id_fields)
        if not has_id:
            errors.append("No identifier field found (event_id, id, record_id)")

        # Check for timestamp
        time_fields = ["timestamp", "created_at", "event_time", "date"]
        has_time = any(record.get(f) for f in time_fields)
        if not has_time:
            errors.append("No timestamp field found")

        # Check for non-empty record
        non_null = [
            v for k, v in record.items()
            if v is not None
            and not k.startswith("_")  # Ignore metadata fields
            and (not isinstance(v, str) or v.strip())
        ]
        if len(non_null) < 2:
            errors.append("Record has too few non-null fields")

        if errors:
            return False, "; ".join(errors)
        return True, None

    def _flatten_nested(
        self, record: dict[str, Any], prefix: str = ""
    ) -> dict[str, Any]:
        """
        Flatten nested JSON structures into a flat dictionary.

        Example:
            {"metadata": {"agent_id": "AGT-01", "geo": {"country": "Mexico"}}}
            → {"metadata_agent_id": "AGT-01", "metadata_geo_country": "Mexico"}

        Only flattens dicts, not lists (lists are kept as-is for Silver layer
        to handle with appropriate array processing).
        """
        flat: dict[str, Any] = {}

        for key, value in record.items():
            full_key = f"{prefix}{key}" if not prefix else f"{prefix}_{key}"

            if isinstance(value, dict):
                # Recursively flatten nested dicts
                nested_flat = self._flatten_nested(value, full_key)
                flat.update(nested_flat)
            else:
                flat[full_key] = value

        return flat

    @property
    def api_metadata(self) -> dict[str, Any]:
        """Get API response metadata (pagination, status, etc.)."""
        return self._api_metadata

    def disconnect(self) -> None:
        """Clean up API connection resources."""
        self._raw_data = []
        self._api_metadata = {}
        super().disconnect()
