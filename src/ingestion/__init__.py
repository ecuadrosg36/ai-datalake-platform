"""Bronze Layer — Multi-source data ingestion connectors."""

from src.ingestion.base_connector import BaseConnector
from src.ingestion.crm_connector import CRMConnector
from src.ingestion.erp_connector import ERPConnector
from src.ingestion.csv_ingestion import CSVIngestor
from src.ingestion.api_connector import APIConnector

__all__ = [
    "BaseConnector",
    "CRMConnector",
    "ERPConnector",
    "CSVIngestor",
    "APIConnector",
]
