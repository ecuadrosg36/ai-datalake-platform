"""
Shared test fixtures for the AI Data Lake Platform.
"""

import json
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def sample_crm_data():
    """Load sample CRM contacts data."""
    data_path = Path("data/sample_crm_contacts.json")
    if data_path.exists():
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # Inline fallback
    return [
        {
            "contact_id": "CRM-001",
            "first_name": "Carlos",
            "last_name": "Mendoza",
            "email": "carlos@empresa.mx",
            "company": "Industrias del Norte",
            "industry": "Manufacturing",
            "country": "Mexico",
            "deal_value_usd": 45000.0,
            "lifecycle_stage": "Customer",
            "created_at": "2025-01-15T10:30:00Z",
            "tags": ["enterprise"],
            "custom_fields": {"annual_revenue": 12000000},
        },
        {
            "contact_id": "CRM-002",
            "first_name": "Maria",
            "last_name": "Rodriguez",
            "email": "maria@techcorp.us",
            "company": "TechCorp",
            "industry": "Technology",
            "country": "United States",
            "deal_value_usd": 78000.0,
            "lifecycle_stage": "Opportunity",
            "created_at": "2025-02-20T08:15:00Z",
            "tags": ["technology"],
            "custom_fields": {},
        },
    ]


@pytest.fixture
def sample_erp_df():
    """Create a sample ERP transactions DataFrame."""
    return pd.DataFrame({
        "transaction_id": ["TXN-001", "TXN-002", "TXN-003", "TXN-004"],
        "order_date": ["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-03"],
        "customer_id": ["CUST-100", "CUST-101", "CUST-102", "CUST-100"],
        "product_sku": ["SKU-A1", "SKU-B2", "SKU-C3", "SKU-A1"],
        "product_name": ["Valve X200", "Helmet Pro", "Pump M500", "Valve X200"],
        "category": ["Equipment", "Safety", "Equipment", "Equipment"],
        "quantity": [5, 50, 2, 3],
        "unit_price": [1250.00, 45.99, 8500.00, 1250.00],
        "total_amount": [6250.00, 2299.50, 17000.00, 3750.00],
        "currency": ["USD", "USD", "USD", "USD"],
        "status": ["Completed", "Completed", "Completed", "Pending"],
        "country": ["Mexico", "Mexico", "United States", "Mexico"],
        "region": ["North", "West", "South", "North"],
    })


@pytest.fixture
def sample_erp_with_issues():
    """ERP DataFrame with data quality issues."""
    return pd.DataFrame({
        "transaction_id": ["TXN-001", "TXN-002", "TXN-001", "TXN-004", "TXN-005"],
        "order_date": ["2025-06-01", "2025-06-02", "2025-06-01", "2025-06-04", "2025-06-05"],
        "customer_id": ["CUST-100", None, "CUST-100", "CUST-103", ""],
        "product_sku": ["SKU-A1", "SKU-B2", "SKU-A1", "INVALID-SKU", "SKU-D4"],
        "quantity": [5, -2, 5, 1, 0],
        "total_amount": [6250.00, -500.00, 6250.00, 100.00, 0.00],
        "currency": ["USD", "MXN", "USD", "INVALID", "USD"],
        "status": ["Completed", "Error", "Completed", "Processing", "Completed"],
        "country": ["Mexico", "Mexico", "Mexico", "Unknown", "US"],
    })


@pytest.fixture
def mock_claude_response():
    """Mock Claude API response."""
    return {
        "content": "## Analysis\n\n1. Data quality is good\n2. No major issues found.",
        "model": "claude-sonnet-4-20250514",
        "tokens": {"input": 100, "output": 50, "total": 150},
        "cost_usd": 0.001,
        "is_mock": True,
    }
