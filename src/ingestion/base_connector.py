"""
Base Connector — Abstract base class for all data source connectors.

Provides a standardized interface for ingesting data from diverse sources
(CRMs, ERPs, APIs, files) into the Bronze layer of the data lake.
Handles logging, retry logic, error tracking, and metadata enrichment.
"""

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generator

import pandas as pd


logger = logging.getLogger(__name__)


class IngestionStatus(Enum):
    """Status of an ingestion operation."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"          # Some records failed
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class IngestionMetrics:
    """Tracks metrics for a single ingestion run."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = ""
    source_type: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    records_read: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    bytes_processed: int = 0
    status: IngestionStatus = IngestionStatus.PENDING
    errors: list[dict[str, Any]] = field(default_factory=list)
    retries: int = 0

    @property
    def duration_seconds(self) -> float:
        """Calculate duration of the ingestion run."""
        if self.end_time is None:
            return (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    @property
    def rejection_rate(self) -> float:
        """Calculate the rejection rate as a percentage."""
        if self.records_read == 0:
            return 0.0
        return (self.records_rejected / self.records_read) * 100

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics to dictionary for logging/storage."""
        return {
            "run_id": self.run_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "records_read": self.records_read,
            "records_accepted": self.records_accepted,
            "records_rejected": self.records_rejected,
            "rejection_rate_pct": round(self.rejection_rate, 2),
            "bytes_processed": self.bytes_processed,
            "status": self.status.value,
            "errors_count": len(self.errors),
            "retries": self.retries,
        }


@dataclass
class IngestionConfig:
    """Configuration for a connector."""
    source_name: str
    source_type: str
    batch_size: int = 1000
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    retry_backoff_factor: float = 2.0
    timeout_seconds: int = 300
    validate_schema: bool = True
    add_metadata: bool = True
    target_path: str = "raw/"


class BaseConnector(ABC):
    """
    Abstract base class for all data source connectors.

    Provides common functionality:
    - Retry logic with exponential backoff
    - Structured logging
    - Metrics collection
    - Metadata enrichment (adds _ingested_at, _source, _run_id, etc.)
    - Error tracking and dead letter queue support

    Subclasses must implement:
    - connect(): Establish connection to the data source
    - extract(): Extract data from the source
    - validate_record(): Validate a single record
    - disconnect(): Clean up the connection

    Usage:
        connector = CRMConnector(config)
        df = connector.ingest()  # Returns a pandas DataFrame
        print(connector.metrics.to_dict())
    """

    def __init__(self, config: IngestionConfig):
        self.config = config
        self.metrics = IngestionMetrics(
            source_name=config.source_name,
            source_type=config.source_type,
        )
        self._connected = False
        self._rejected_records: list[dict[str, Any]] = []
        self.logger = logging.getLogger(f"{__name__}.{config.source_name}")

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the data source."""
        pass

    @abstractmethod
    def extract(self) -> Generator[list[dict[str, Any]], None, None]:
        """
        Extract data from the source in batches.

        Yields lists of records (dicts) in batch_size chunks.
        This generator pattern supports memory-efficient processing
        of large datasets.
        """
        pass

    @abstractmethod
    def validate_record(self, record: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate a single record.

        Args:
            record: The record to validate.

        Returns:
            Tuple of (is_valid, error_message).
            error_message is None if valid.
        """
        pass

    def disconnect(self) -> None:
        """Clean up the connection. Override if needed."""
        self._connected = False
        self.logger.info(f"Disconnected from {self.config.source_name}")

    def enrich_metadata(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Add ingestion metadata to a record.

        Enriches each record with:
        - _ingested_at: UTC timestamp of ingestion
        - _source_system: Name of the source system
        - _source_type: Type of connector used
        - _run_id: Unique ID for this ingestion run
        - _pipeline_version: Version of the pipeline
        """
        if not self.config.add_metadata:
            return record

        record["_ingested_at"] = datetime.now(timezone.utc).isoformat()
        record["_source_system"] = self.config.source_name
        record["_source_type"] = self.config.source_type
        record["_run_id"] = self.metrics.run_id
        record["_pipeline_version"] = "1.0.0"
        return record

    def _execute_with_retry(self, operation: str, func, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic and exponential backoff.

        Args:
            operation: Name of the operation (for logging).
            func: The function to execute.
            *args, **kwargs: Arguments to pass to the function.

        Returns:
            The result of the function call.

        Raises:
            Exception: If all retries are exhausted.
        """
        last_exception = None
        delay = self.config.retry_delay_seconds

        for attempt in range(1, self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                self.metrics.retries += 1

                if attempt < self.config.max_retries:
                    self.logger.warning(
                        f"[{operation}] Attempt {attempt}/{self.config.max_retries} "
                        f"failed: {str(e)}. Retrying in {delay:.1f}s..."
                    )
                    self.metrics.status = IngestionStatus.RETRYING
                    time.sleep(delay)
                    delay *= self.config.retry_backoff_factor
                else:
                    self.logger.error(
                        f"[{operation}] All {self.config.max_retries} attempts "
                        f"exhausted. Last error: {str(e)}"
                    )

        raise last_exception  # type: ignore[misc]

    def ingest(self) -> pd.DataFrame:
        """
        Execute the full ingestion pipeline.

        Steps:
        1. Connect to the data source (with retries)
        2. Extract data in batches
        3. Validate each record
        4. Enrich with metadata
        5. Collect accepted/rejected records
        6. Return accepted records as DataFrame

        Returns:
            pd.DataFrame with ingested and validated records.
        """
        self.logger.info(
            f"Starting ingestion from {self.config.source_name} "
            f"(type: {self.config.source_type})"
        )
        self.metrics.status = IngestionStatus.RUNNING
        accepted_records: list[dict[str, Any]] = []

        try:
            # Step 1: Connect
            self._execute_with_retry("connect", self.connect)
            self._connected = True

            # Step 2-5: Extract, validate, enrich
            for batch in self.extract():
                for record in batch:
                    self.metrics.records_read += 1

                    # Validate
                    is_valid, error_msg = self.validate_record(record)

                    if is_valid:
                        # Enrich and accept
                        enriched = self.enrich_metadata(record)
                        accepted_records.append(enriched)
                        self.metrics.records_accepted += 1
                    else:
                        # Track rejection
                        self._rejected_records.append({
                            "record": record,
                            "error": error_msg,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        self.metrics.records_rejected += 1
                        self.logger.debug(
                            f"Record rejected: {error_msg}"
                        )

            # Determine final status
            if self.metrics.records_rejected == 0:
                self.metrics.status = IngestionStatus.SUCCESS
            elif self.metrics.records_accepted > 0:
                self.metrics.status = IngestionStatus.PARTIAL
            else:
                self.metrics.status = IngestionStatus.FAILED

        except Exception as e:
            self.metrics.status = IngestionStatus.FAILED
            self.metrics.errors.append({
                "error": str(e),
                "type": type(e).__name__,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self.logger.error(f"Ingestion failed: {str(e)}")
            raise

        finally:
            self.metrics.end_time = datetime.now(timezone.utc)
            if self._connected:
                self.disconnect()

        # Log summary
        self.logger.info(
            f"Ingestion complete: {self.metrics.records_accepted} accepted, "
            f"{self.metrics.records_rejected} rejected "
            f"({self.metrics.rejection_rate:.1f}% rejection rate) "
            f"in {self.metrics.duration_seconds:.2f}s"
        )

        # Step 6: Return DataFrame
        if accepted_records:
            return pd.DataFrame(accepted_records)
        return pd.DataFrame()

    @property
    def rejected_records(self) -> list[dict[str, Any]]:
        """Get all rejected records for dead-letter queue processing."""
        return self._rejected_records
