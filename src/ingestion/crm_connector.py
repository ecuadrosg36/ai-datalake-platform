"""
CRM Connector — Ingests contact and deal data from CRM systems.

Supports ingestion from CRM platforms (HubSpot, Salesforce, etc.)
via REST API. Handles pagination, rate limiting, and field mapping
for standardized Bronze layer storage.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Generator

from src.ingestion.base_connector import BaseConnector, IngestionConfig


logger = logging.getLogger(__name__)


# Standard fields expected in CRM contact records
REQUIRED_FIELDS = {"contact_id", "email", "company"}
VALID_LIFECYCLE_STAGES = {"Lead", "Opportunity", "Customer", "Churned", "Other"}
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class CRMConnector(BaseConnector):
    """
    Connector for CRM data sources (HubSpot, Salesforce, Pipedrive, etc.).

    Ingests contacts, deals, and interactions from CRM systems.
    In production, this would call the CRM REST API. For demonstration,
    it reads from a local JSON file simulating CRM API responses.

    Features:
    - Contact record validation (email, required fields, lifecycle stage)
    - Deduplication by contact_id
    - Custom field extraction and flattening
    - Pagination handling for large datasets
    - Tag normalization

    Usage:
        config = IngestionConfig(
            source_name="hubspot_crm",
            source_type="crm",
        )
        connector = CRMConnector(config, data_path="data/sample_crm_contacts.json")
        df = connector.ingest()
    """

    def __init__(
        self,
        config: IngestionConfig,
        data_path: str | Path = "data/sample_crm_contacts.json",
        api_base_url: str | None = None,
        api_key: str | None = None,
    ):
        super().__init__(config)
        self.data_path = Path(data_path)
        self.api_base_url = api_base_url
        self.api_key = api_key
        self._raw_data: list[dict[str, Any]] = []
        self._seen_ids: set[str] = set()

    def connect(self) -> None:
        """
        Establish connection to the CRM data source.

        In production: Authenticates with the CRM API using OAuth2/API key.
        In demo mode: Loads data from the sample JSON file.
        """
        if self.api_base_url and self.api_key:
            # Production mode — would authenticate with CRM API
            self.logger.info(
                f"Connecting to CRM API at {self.api_base_url}"
            )
            # In real implementation:
            # self._session = requests.Session()
            # self._session.headers["Authorization"] = f"Bearer {self.api_key}"
            # response = self._session.get(f"{self.api_base_url}/health")
            # response.raise_for_status()
        else:
            # Demo mode — load from file
            if not self.data_path.exists():
                raise FileNotFoundError(
                    f"CRM data file not found: {self.data_path}"
                )
            with open(self.data_path, "r", encoding="utf-8") as f:
                self._raw_data = json.load(f)

            self.logger.info(
                f"Loaded {len(self._raw_data)} CRM contacts from {self.data_path}"
            )

    def extract(self) -> Generator[list[dict[str, Any]], None, None]:
        """
        Extract CRM records in batches.

        Handles pagination for API mode and chunking for file mode.
        Each batch contains up to `batch_size` records.
        """
        batch: list[dict[str, Any]] = []

        for record in self._raw_data:
            # Flatten custom fields into the main record
            flat_record = self._flatten_record(record)
            batch.append(flat_record)

            if len(batch) >= self.config.batch_size:
                yield batch
                batch = []

        # Yield remaining records
        if batch:
            yield batch

    def validate_record(self, record: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate a CRM contact record.

        Checks:
        1. Required fields present and non-empty
        2. Email format is valid
        3. contact_id is not empty
        4. deal_value_usd is non-negative (if present)
        5. Lifecycle stage is valid
        6. No duplicate contact_id
        """
        errors: list[str] = []

        # Check required fields
        for field_name in REQUIRED_FIELDS:
            value = record.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Missing or empty required field: {field_name}")

        # Validate email format
        email = record.get("email", "")
        if email and not EMAIL_REGEX.match(email):
            errors.append(f"Invalid email format: {email}")

        # Validate deal value
        deal_value = record.get("deal_value_usd")
        if deal_value is not None and isinstance(deal_value, (int, float)):
            if deal_value < 0:
                errors.append(f"Negative deal value: {deal_value}")

        # Validate lifecycle stage
        lifecycle = record.get("lifecycle_stage", "")
        if lifecycle and lifecycle not in VALID_LIFECYCLE_STAGES:
            # Don't reject — just warn. Allow unknown stages.
            self.logger.debug(f"Unknown lifecycle stage: {lifecycle}")

        # Check for duplicates
        contact_id = record.get("contact_id", "")
        if contact_id and contact_id in self._seen_ids:
            errors.append(f"Duplicate contact_id: {contact_id}")
        elif contact_id:
            self._seen_ids.add(contact_id)

        if errors:
            return False, "; ".join(errors)
        return True, None

    def _flatten_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Flatten nested structures (custom_fields, tags) into a flat record.

        CRM systems often have nested custom fields. We flatten these
        for easier processing in the Silver layer.

        Example:
            {"custom_fields": {"annual_revenue": 1000000}}
            → {"cf_annual_revenue": 1000000}
        """
        flat = {}

        for key, value in record.items():
            if key == "custom_fields" and isinstance(value, dict):
                for cf_key, cf_value in value.items():
                    flat[f"cf_{cf_key}"] = cf_value
            elif key == "tags" and isinstance(value, list):
                flat["tags"] = ",".join(sorted(value)) if value else ""
            else:
                flat[key] = value

        return flat

    def disconnect(self) -> None:
        """Clean up CRM connection resources."""
        self._raw_data = []
        self._seen_ids.clear()
        super().disconnect()
