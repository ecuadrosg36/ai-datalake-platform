"""
MCP Server — Model Context Protocol server for the AI Data Lake Platform.

Enables Claude agents to interact with the data lake through standardized
tools and resources. Agents can query datasets, read metadata, check
data quality, trigger pipeline runs, and generate insights.

This server implements the MCP specification, allowing any MCP-compatible
AI agent (Claude, Cursor, etc.) to programmatically interact with the
data lake infrastructure.

Run with:
    python -m src.mcp_server.server
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# --- Data Lake Catalog (in-memory for demo) ---
DATA_CATALOG: dict[str, Any] = {
    "bronze": {
        "crm_contacts_raw": {
            "description": "Raw CRM contact records from multiple CRM platforms",
            "format": "JSON",
            "row_count": 8,
            "last_updated": "2025-06-15T12:00:00Z",
            "source": "HubSpot/Salesforce API",
            "s3_path": "s3://ai-datalake-platform/raw/crm/",
            "schema": {
                "contact_id": "STRING",
                "first_name": "STRING",
                "last_name": "STRING",
                "email": "STRING",
                "company": "STRING",
                "industry": "STRING",
                "country": "STRING",
                "deal_value_usd": "FLOAT",
                "lifecycle_stage": "STRING",
                "created_at": "TIMESTAMP",
                "tags": "STRING",
            },
        },
        "erp_transactions_raw": {
            "description": "Raw ERP transaction records from SAP/Oracle",
            "format": "CSV",
            "row_count": 15,
            "last_updated": "2025-06-15T12:00:00Z",
            "source": "SAP ERP Export",
            "s3_path": "s3://ai-datalake-platform/raw/erp/",
            "schema": {
                "transaction_id": "STRING",
                "order_date": "DATE",
                "customer_id": "STRING",
                "product_sku": "STRING",
                "product_name": "STRING",
                "category": "STRING",
                "quantity": "INTEGER",
                "unit_price": "FLOAT",
                "total_amount": "FLOAT",
                "currency": "STRING",
                "status": "STRING",
                "country": "STRING",
                "region": "STRING",
            },
        },
        "api_interactions_raw": {
            "description": "Raw customer interaction events from APIs",
            "format": "JSON",
            "row_count": 5,
            "last_updated": "2025-06-15T14:00:00Z",
            "source": "Multi-channel API (WhatsApp, Email, Web)",
            "s3_path": "s3://ai-datalake-platform/raw/api/",
        },
    },
    "silver": {
        "crm_contacts_clean": {
            "description": "Cleaned and validated CRM contacts",
            "format": "Parquet",
            "row_count": 6,
            "last_updated": "2025-06-15T13:00:00Z",
            "partitions": ["year", "month", "day"],
            "s3_path": "s3://ai-datalake-platform/processed/crm/",
            "quality_score": 0.96,
        },
        "erp_transactions_clean": {
            "description": "Cleaned and deduplicated ERP transactions",
            "format": "Parquet",
            "row_count": 12,
            "last_updated": "2025-06-15T13:00:00Z",
            "partitions": ["year", "month", "day"],
            "s3_path": "s3://ai-datalake-platform/processed/erp/",
            "quality_score": 0.94,
        },
    },
    "gold": {
        "daily_business_metrics": {
            "description": "Daily aggregated business metrics",
            "format": "Parquet",
            "row_count": 5,
            "last_updated": "2025-06-15T14:00:00Z",
            "partitions": ["year", "month"],
            "s3_path": "s3://ai-datalake-platform/curated/metrics/",
            "quality_score": 0.98,
        },
        "customer_360": {
            "description": "Unified customer view combining CRM and transaction data",
            "format": "Parquet",
            "row_count": 10,
            "last_updated": "2025-06-15T14:00:00Z",
            "s3_path": "s3://ai-datalake-platform/curated/customer_360/",
            "quality_score": 0.97,
        },
    },
}

QUALITY_REPORTS: dict[str, Any] = {
    "erp_transactions_clean": {
        "dataset_name": "erp_transactions_clean",
        "layer": "silver",
        "overall_score": 0.94,
        "dimension_scores": {
            "completeness": 0.93,
            "accuracy": 0.98,
            "uniqueness": 1.0,
            "timeliness": 0.89,
            "consistency": 0.96,
        },
        "issues": [
            {
                "rule": "completeness_customer_id",
                "score": 0.93,
                "details": "1 record missing customer_id",
            },
            {
                "rule": "timeliness_order_date",
                "score": 0.89,
                "details": "Some records older than 24h threshold",
            },
        ],
    },
    "crm_contacts_clean": {
        "dataset_name": "crm_contacts_clean",
        "layer": "silver",
        "overall_score": 0.96,
        "dimension_scores": {
            "completeness": 0.95,
            "accuracy": 0.97,
            "uniqueness": 1.0,
            "timeliness": 0.92,
            "consistency": 0.98,
        },
        "issues": [
            {
                "rule": "completeness_phone",
                "score": 0.95,
                "details": "Some contacts missing phone numbers",
            },
        ],
    },
}


def create_mcp_server():
    """
    Create and configure the MCP Server.

    The server exposes tools and resources for AI agents to interact
    with the data lake. It uses the MCP SDK for protocol handling.
    """
    try:
        from mcp.server import Server
        from mcp.types import (
            Resource,
            TextContent,
            Tool,
        )
        from mcp.server.stdio import stdio_server

        server = Server("ai-datalake-platform")

        # --- Tool Handlers ---

        @server.list_tools()
        async def list_tools() -> list[Tool]:
            """List all available MCP tools."""
            return [
                Tool(
                    name="query_dataset",
                    description="Execute SQL against the data lake (Athena-compatible)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "SQL query"},
                            "layer": {
                                "type": "string",
                                "enum": ["bronze", "silver", "gold"],
                            },
                            "limit": {"type": "integer", "default": 100},
                        },
                        "required": ["query", "layer"],
                    },
                ),
                Tool(
                    name="get_schema",
                    description="Get schema for a table in the data lake",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "table_name": {"type": "string"},
                            "layer": {
                                "type": "string",
                                "enum": ["bronze", "silver", "gold"],
                            },
                        },
                        "required": ["table_name", "layer"],
                    },
                ),
                Tool(
                    name="check_quality",
                    description="Get data quality metrics for a dataset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "dataset_name": {"type": "string"},
                        },
                        "required": ["dataset_name"],
                    },
                ),
                Tool(
                    name="list_datasets",
                    description="List all datasets in the data lake",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "layer": {
                                "type": "string",
                                "enum": ["bronze", "silver", "gold", "all"],
                            },
                        },
                    },
                ),
                Tool(
                    name="run_pipeline",
                    description="Trigger a pipeline run",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "layer": {
                                "type": "string",
                                "enum": ["bronze", "silver", "gold", "full"],
                            },
                            "dry_run": {"type": "boolean", "default": False},
                        },
                        "required": ["layer"],
                    },
                ),
                Tool(
                    name="generate_insight",
                    description="Generate AI insights for a Gold layer dataset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "dataset_name": {"type": "string"},
                            "focus_area": {"type": "string"},
                        },
                        "required": ["dataset_name"],
                    },
                ),
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool calls from MCP clients."""
            try:
                if name == "query_dataset":
                    result = handle_query_dataset(arguments)
                elif name == "get_schema":
                    result = handle_get_schema(arguments)
                elif name == "check_quality":
                    result = handle_check_quality(arguments)
                elif name == "list_datasets":
                    result = handle_list_datasets(arguments)
                elif name == "run_pipeline":
                    result = handle_run_pipeline(arguments)
                elif name == "generate_insight":
                    result = handle_generate_insight(arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str),
                )]

            except Exception as e:
                logger.error(f"Tool '{name}' error: {e}")
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}),
                )]

        # --- Resource Handlers ---

        @server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available MCP resources."""
            return [
                Resource(
                    uri="datalake://catalog",
                    name="Data Catalog",
                    description="Complete data lake catalog",
                    mimeType="application/json",
                ),
                Resource(
                    uri="datalake://quality/summary",
                    name="Quality Summary",
                    description="Data quality summary across all datasets",
                    mimeType="application/json",
                ),
                Resource(
                    uri="datalake://pipeline/status",
                    name="Pipeline Status",
                    description="Current pipeline status",
                    mimeType="application/json",
                ),
            ]

        @server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read an MCP resource."""
            if uri == "datalake://catalog":
                return json.dumps(DATA_CATALOG, indent=2)
            elif uri == "datalake://quality/summary":
                return json.dumps(QUALITY_REPORTS, indent=2)
            elif uri == "datalake://pipeline/status":
                return json.dumps({
                    "status": "idle",
                    "last_run": "2025-06-15T14:00:00Z",
                    "next_scheduled": "2025-06-15T15:00:00Z",
                    "layers": {
                        "bronze": "completed",
                        "silver": "completed",
                        "gold": "completed",
                    },
                })
            else:
                return json.dumps({"error": f"Resource not found: {uri}"})

        return server, stdio_server

    except ImportError:
        logger.warning(
            "MCP SDK not installed. Install with: pip install mcp\n"
            "Running in standalone mode."
        )
        return None, None


# --- Tool Implementation Functions ---

def handle_query_dataset(args: dict[str, Any]) -> dict[str, Any]:
    """Handle query_dataset tool calls (demo mode)."""
    query = args.get("query", "")
    layer = args.get("layer", "silver")
    limit = args.get("limit", 100)

    return {
        "status": "success",
        "query": query,
        "layer": layer,
        "message": (
            f"Query would be executed against {layer} layer via Amazon Athena. "
            f"In production, this connects to Athena with the configured workgroup."
        ),
        "demo_note": "Connect ANTHROPIC_API_KEY and AWS credentials for live execution.",
        "available_tables": list(DATA_CATALOG.get(layer, {}).keys()),
    }


def handle_get_schema(args: dict[str, Any]) -> dict[str, Any]:
    """Handle get_schema tool calls."""
    table_name = args.get("table_name", "")
    layer = args.get("layer", "bronze")

    layer_data = DATA_CATALOG.get(layer, {})
    table_data = layer_data.get(table_name)

    if table_data:
        return {
            "table_name": table_name,
            "layer": layer,
            "schema": table_data.get("schema", {}),
            "description": table_data.get("description", ""),
            "format": table_data.get("format", ""),
            "s3_path": table_data.get("s3_path", ""),
            "partitions": table_data.get("partitions", []),
        }

    return {"error": f"Table '{table_name}' not found in {layer} layer"}


def handle_check_quality(args: dict[str, Any]) -> dict[str, Any]:
    """Handle check_quality tool calls."""
    dataset_name = args.get("dataset_name", "")
    report = QUALITY_REPORTS.get(dataset_name)

    if report:
        return report
    return {
        "error": f"No quality report found for '{dataset_name}'",
        "available_datasets": list(QUALITY_REPORTS.keys()),
    }


def handle_list_datasets(args: dict[str, Any]) -> dict[str, Any]:
    """Handle list_datasets tool calls."""
    layer = args.get("layer", "all")

    if layer == "all":
        datasets = {}
        for l_name, l_data in DATA_CATALOG.items():
            datasets[l_name] = {
                name: {
                    "description": info.get("description", ""),
                    "row_count": info.get("row_count", 0),
                    "last_updated": info.get("last_updated", ""),
                    "quality_score": info.get("quality_score"),
                }
                for name, info in l_data.items()
            }
        return datasets

    layer_data = DATA_CATALOG.get(layer, {})
    return {
        name: {
            "description": info.get("description", ""),
            "row_count": info.get("row_count", 0),
            "last_updated": info.get("last_updated", ""),
        }
        for name, info in layer_data.items()
    }


def handle_run_pipeline(args: dict[str, Any]) -> dict[str, Any]:
    """Handle run_pipeline tool calls."""
    layer = args.get("layer", "full")
    dry_run = args.get("dry_run", False)

    return {
        "status": "accepted",
        "layer": layer,
        "dry_run": dry_run,
        "execution_id": "exec-demo-001",
        "message": (
            f"Pipeline {'dry run' if dry_run else 'execution'} triggered "
            f"for {layer} layer. In production, this invokes the pipeline "
            f"orchestrator via AWS Step Functions."
        ),
    }


def handle_generate_insight(args: dict[str, Any]) -> dict[str, Any]:
    """Handle generate_insight tool calls."""
    dataset_name = args.get("dataset_name", "")
    focus_area = args.get("focus_area", "")

    return {
        "status": "success",
        "dataset": dataset_name,
        "focus_area": focus_area,
        "message": (
            "In production, this triggers the InsightGenerator with Claude Opus "
            "to analyze the Gold layer dataset and produce business insights. "
            "Configure ANTHROPIC_API_KEY for live analysis."
        ),
        "sample_insights": [
            "Revenue trend is stable with 2% MoM growth",
            "Equipment category dominates at 65% of total revenue",
            "Mexico accounts for 55% of transactions",
            "Customer CUST-100 is the highest value account",
            "Consider expanding product mix to reduce concentration risk",
        ],
    }


# --- Main Entry Point ---

def main():
    """Start the MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Starting AI Data Lake Platform MCP Server...")

    server, stdio_server_func = create_mcp_server()

    if server and stdio_server_func:
        async def run():
            async with stdio_server_func() as (read_stream, write_stream):
                await server.run(read_stream, write_stream)

        asyncio.run(run())
    else:
        logger.info("MCP Server running in standalone mode (no MCP SDK)")
        logger.info(f"Available datasets: {list(DATA_CATALOG.keys())}")
        logger.info("Install MCP SDK with: pip install mcp")

        # Demo: show what the server can do
        print("\n" + "=" * 60)
        print("  AI Data Lake Platform — MCP Server (Standalone Mode)")
        print("=" * 60)
        print("\nAvailable Tools:")
        for tool in ["query_dataset", "get_schema", "check_quality",
                      "list_datasets", "run_pipeline", "generate_insight"]:
            print(f"  • {tool}")

        print("\nAvailable Resources:")
        print("  • datalake://catalog")
        print("  • datalake://quality/summary")
        print("  • datalake://pipeline/status")

        print("\nData Catalog:")
        for layer, datasets in DATA_CATALOG.items():
            print(f"\n  [{layer.upper()}]")
            for name, info in datasets.items():
                print(f"    • {name}: {info.get('description', '')}")

        print(f"\nInstall MCP SDK for full protocol support: pip install mcp")
        print("=" * 60)


if __name__ == "__main__":
    main()
