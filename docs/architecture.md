# System Architecture — AI-Powered Data Lake Platform

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AI-POWERED DATA LAKE PLATFORM                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │  CRM API │  │ ERP CSV  │  │ REST API │  │  WhatsApp/Other  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬──────────┘    │
│       │              │              │                │               │
│  ─────┴──────────────┴──────────────┴────────────────┴─────── ─ ─   │
│                    INGESTION LAYER (Bronze)                          │
│    ┌──────────────────────────────────────────────────────┐         │
│    │  Connectors: CRM | ERP | CSV | API                  │         │
│    │  • Validation  • Metadata Enrichment  • Retry Logic │         │
│    └──────────────────────┬───────────────────────────────┘         │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │   S3 Raw/   │  ← Bronze (JSON/CSV)             │
│                    └──────┬──────┘                                  │
│                           │                                         │
│  ─────────────────────────┴──────────────────────────────── ─ ─     │
│                 TRANSFORMATION LAYER (Silver)                       │
│    ┌──────────────────────────────────────────────────────┐         │
│    │  SparkProcessor | SchemaEnforcer | DataQuality       │         │
│    │  DeduplicationEngine | 🤖 Claude AI Quality Advisory │         │
│    └──────────────────────┬───────────────────────────────┘         │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │ S3 Processed│  ← Silver (Parquet, Partitioned) │
│                    └──────┬──────┘                                  │
│                           │                                         │
│  ─────────────────────────┴──────────────────────────────── ─ ─     │
│                   ANALYTICS LAYER (Gold)                            │
│    ┌──────────────────────────────────────────────────────┐         │
│    │  Aggregator | KPI Calculator | Report Generator      │         │
│    │  🤖 Claude Opus Insight Generator                    │         │
│    └──────────────────────┬───────────────────────────────┘         │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │ S3 Curated/ │  ← Gold (Parquet, Aggregated)    │
│                    └──────┬──────┘                                  │
│                           │                                         │
│  ─────────────────────────┴──────────────────────────────── ─ ─     │
│                    CONSUMPTION LAYER                                 │
│    ┌────────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐      │
│    │   Athena   │  │QuickSight│  │ MCP Server│  │ Reports  │      │
│    │   (SQL)    │  │(Dashbrd) │  │ (AI Agent)│  │  (Auto)  │      │
│    └────────────┘  └──────────┘  └───────────┘  └──────────┘      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## AWS Services Architecture

| Service | Purpose | Layer |
|---------|---------|-------|
| **Amazon S3** | Data Lake storage (raw/, processed/, curated/) | All |
| **AWS Glue** | Data Catalog + ETL Jobs (PySpark) | Silver |
| **Amazon Athena** | SQL queries on S3 data | Gold/Consumption |
| **AWS Lambda** | Pipeline trigger, event processing | Bronze/Silver |
| **Amazon CloudWatch** | Monitoring, logging, alarms | All |
| **Amazon SNS** | Alert notifications | All |
| **AWS IAM** | Access control and roles | All |

## Data Flow

1. **Ingestion** → Raw data from CRM, ERP, APIs lands in `s3://bucket/raw/`
2. **Transformation** → Glue/Spark cleans and validates → `s3://bucket/processed/`
3. **Analytics** → Aggregations and KPIs → `s3://bucket/curated/`
4. **Consumption** → Athena queries, dashboards, MCP Server for AI agents

## Claude AI Integration Points

| Stage | Model | Purpose |
|-------|-------|---------|
| **Ingestion** | Sonnet | Data profiling, schema inference |
| **Transformation** | Sonnet | Quality advisory, transformation suggestions |
| **Analytics** | Opus | Insight generation, trend analysis |
| **Consumption** | Both | NL→SQL, report narratives, executive summaries |
| **MCP Server** | Both | AI agent queries, quality checks, insights |
