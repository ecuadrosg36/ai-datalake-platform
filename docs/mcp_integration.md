# MCP Server Integration — AI Agent Access to the Data Lake

## What is MCP?

**Model Context Protocol (MCP)** is an open standard that enables AI agents (Claude, Cursor, Antigravity, etc.) to interact with external tools and data sources through a standardized interface.

Our MCP Server allows any MCP-compatible AI agent to:
- Query datasets in the data lake
- Read metadata and schemas
- Check data quality metrics
- Trigger pipeline runs
- Generate business insights

## Architecture

```
┌─────────────────┐     MCP Protocol     ┌────────────────────┐
│  Claude Agent    │◄──────────────────►  │  MCP Server        │
│  (IDE / Desktop) │     stdio/HTTP       │  (Python)          │
└─────────────────┘                       ├────────────────────┤
                                          │  Tools:            │
┌─────────────────┐                       │  • query_dataset   │
│  Cursor IDE      │◄────────────────────►│  • get_schema      │
│                  │                       │  • check_quality   │
└─────────────────┘                       │  • run_pipeline    │
                                          │  • generate_insight│
┌─────────────────┐                       │  • list_datasets   │
│  Antigravity     │◄────────────────────►│                    │
│                  │                       │  Resources:        │
└─────────────────┘                       │  • Data Catalog    │
                                          │  • Quality Reports │
                                          │  • Pipeline Status │
                                          └─────────┬──────────┘
                                                    │
                                          ┌─────────▼──────────┐
                                          │  AWS Data Lake      │
                                          │  (S3/Glue/Athena)   │
                                          └────────────────────┘
```

## Available Tools

### 1. `query_dataset`
Execute SQL queries against the data lake via Amazon Athena.

```json
{
  "name": "query_dataset",
  "arguments": {
    "query": "SELECT category, SUM(total_amount) FROM erp_transactions_clean GROUP BY category",
    "layer": "silver",
    "limit": 100
  }
}
```

### 2. `get_schema`
Retrieve the schema for any table.

```json
{
  "name": "get_schema",
  "arguments": {
    "table_name": "crm_contacts_raw",
    "layer": "bronze"
  }
}
```

### 3. `check_quality`
Get data quality metrics for a dataset.

```json
{
  "name": "check_quality",
  "arguments": {
    "dataset_name": "erp_transactions_clean"
  }
}
// Returns: overall_score, dimension_scores, issues
```

### 4. `run_pipeline`
Trigger a pipeline run.

```json
{
  "name": "run_pipeline",
  "arguments": {
    "layer": "silver",
    "dry_run": true
  }
}
```

### 5. `generate_insight`
Generate AI-powered business insights.

```json
{
  "name": "generate_insight",
  "arguments": {
    "dataset_name": "daily_business_metrics",
    "focus_area": "revenue trends"
  }
}
```

### 6. `list_datasets`
Browse the data catalog.

```json
{
  "name": "list_datasets",
  "arguments": {
    "layer": "all"
  }
}
```

## Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-datalake-platform": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "env": {
        "ANTHROPIC_API_KEY": "your-key",
        "AWS_DEFAULT_REGION": "us-east-1"
      }
    }
  }
}
```

## Running the Server

```bash
# Start MCP server
python -m src.mcp_server.server

# Or use Make
make run-mcp
```
