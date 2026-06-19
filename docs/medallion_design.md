# Medallion Architecture Design

## Overview

The data lake follows the **Medallion Architecture** (Bronze → Silver → Gold), organizing data in progressive layers of quality and business value.

```
┌──────────────────────────────────────────────────────────────────────┐
│                          DATA LAKE (S3)                               │
├──────────────┬───────────────┬───────────────┬───────────────────────┤
│    BRONZE    │     SILVER    │      GOLD     │      REJECTED         │
│    (Raw)     │  (Processed)  │   (Curated)   │   (Dead Letter)       │
├──────────────┼───────────────┼───────────────┼───────────────────────┤
│ JSON, CSV    │ Parquet       │ Parquet       │ Parquet               │
│ As-received  │ Cleaned       │ Aggregated    │ Failed validation     │
│ Immutable    │ Validated     │ Business-ready│ For debugging         │
│ No transform │ Deduplicated  │ KPIs & metrics│                       │
│              │ Schema-enforced│ AI insights  │                       │
└──────────────┴───────────────┴───────────────┴───────────────────────┘
```

## Layer Details

### Bronze Layer (Raw)

**Purpose**: Preserve raw data exactly as received.

**S3 Path**: `s3://bucket/raw/{source}/{YYYY}/{MM}/{DD}/`

| Aspect | Details |
|--------|---------|
| Format | JSON, CSV (original format) |
| Transform | None (immutable copy) |
| Retention | 90 days Standard, then IA → Glacier |
| Access | Pipeline only (write), Data engineers (read) |
| Sources | CRM APIs, ERP exports, REST APIs, CSV uploads |

### Silver Layer (Processed)

**Purpose**: Clean, validate, and standardize data for reliable consumption.

**S3 Path**: `s3://bucket/processed/{source}/year={YYYY}/month={MM}/day={DD}/`

| Aspect | Details |
|--------|---------|
| Format | Parquet (Snappy compression) |
| Transforms | Type casting, null handling, deduplication, validation |
| Partitioning | year, month, day |
| Quality | Automated checks: completeness, accuracy, uniqueness |
| AI Integration | Claude Sonnet for quality advisory |
| Access | Analysts (read), Pipeline (write) |

### Gold Layer (Curated)

**Purpose**: Business-ready aggregations, KPIs, and insights.

**S3 Path**: `s3://bucket/curated/{domain}/year={YYYY}/month={MM}/`

| Aspect | Details |
|--------|---------|
| Format | Parquet (Snappy compression) |
| Content | Daily/weekly/monthly aggregations, KPIs, dimensions |
| Partitioning | year, month |
| AI Integration | Claude Opus for insight generation |
| Access | Dashboards, Reports, AI agents, Stakeholders |

## S3 Structure

```
s3://ai-datalake-platform/
├── raw/                          ← BRONZE
│   ├── crm/
│   │   └── 2025/06/15/
│   │       └── contacts_20250615.json
│   ├── erp/
│   │   └── 2025/06/15/
│   │       └── transactions_20250615.csv
│   └── api/
│       └── 2025/06/15/
│           └── interactions_20250615.json
│
├── processed/                    ← SILVER
│   ├── crm/
│   │   └── year=2025/month=06/day=15/
│   │       └── contacts_clean.parquet
│   └── erp/
│       └── year=2025/month=06/day=15/
│           └── transactions_clean.parquet
│
├── curated/                      ← GOLD
│   ├── daily_metrics/
│   │   └── year=2025/month=06/
│   │       └── daily_business_metrics.parquet
│   ├── customer_360/
│   │   └── customer_unified.parquet
│   └── reports/
│       └── weekly_executive_report.json
│
├── rejected/                     ← Dead Letter
│   └── 2025/06/15/
│       └── rejected_records.parquet
│
├── metadata/                     ← Schemas & Quality
│   ├── schemas/
│   └── quality_reports/
│
└── athena-results/               ← Query Results
```

## Data Quality Gates

Each layer transition has quality gates enforced by the pipeline:

| Gate | Bronze → Silver | Silver → Gold |
|------|----------------|---------------|
| Completeness | ≥ 95% | ≥ 98% |
| Accuracy | ≥ 98% | ≥ 99% |
| Uniqueness | 100% | 100% |
| Timeliness | ≤ 24h | ≤ 4h |

Records failing quality gates are sent to the `rejected/` prefix.
