# 🤖 AI-Powered Data Lake Platform

### An intelligent data pipeline that collects, cleans, and analyzes business data — powered by Claude AI

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Claude AI](https://img.shields.io/badge/Claude-Sonnet%20%2B%20Opus-orange.svg)](https://www.anthropic.com/)
[![AWS](https://img.shields.io/badge/AWS-S3%20%7C%20Glue%20%7C%20Athena-yellow.svg)](https://aws.amazon.com/)
[![MCP](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io/)
[![Tests](https://img.shields.io/badge/tests-61%20passing-brightgreen.svg)]()

---

## 📖 What Is This Project?

Imagine a company that has **customer data scattered everywhere**: contacts in a CRM (like HubSpot or Salesforce), transactions in an ERP system (like SAP), and interactions coming from APIs (like WhatsApp messages or web events). All this data is in **different formats** (JSON, CSV, API responses) and **different qualities** (missing fields, duplicates, wrong formats).

This project solves that problem. It's a **complete data pipeline** that:

1. **Collects** data from all those different sources automatically
2. **Cleans** the data — removes duplicates, fixes formats, fills in missing values
3. **Validates** the data — checks that everything makes sense (no negative prices, no fake emails)
4. **Organizes** the data into business-ready tables (daily revenue, KPIs, customer profiles)
5. **Uses AI (Claude)** at every step to make the whole process smarter and faster

Think of it like a **factory for data**: raw materials come in (messy data), get processed on the assembly line (cleaning, validation), and finished products come out (clean reports, dashboards, insights).

---

## 🧠 Key Concepts Explained Simply

### What is a Data Lake?

A **Data Lake** is a big storage system (we use Amazon S3) where you dump ALL your data — structured (tables), semi-structured (JSON), unstructured (text, logs). Unlike a traditional database, you don't need to organize the data before storing it. You store it first, then organize it later.

**Why?** Because companies have data coming from so many places that it's impossible to design a perfect database upfront. A data lake lets you collect everything and figure out the structure later.

### What is the Medallion Architecture (Bronze → Silver → Gold)?

This is the **organizing principle** of our data lake. Think of it like refining raw metal:

```
🥉 BRONZE (Raw)          🥈 SILVER (Clean)         🥇 GOLD (Business-Ready)
─────────────────      ─────────────────────      ─────────────────────────
• Data exactly as       • Duplicates removed       • Daily revenue totals
  we received it        • Formats standardized     • Customer KPIs
• Messy, duplicated     • Invalid data flagged     • Top products report
• JSON, CSV, etc.       • Types corrected          • Growth calculations
• Our "safety copy"     • Quality checked          • Executive summaries
```

**Why three layers?**
- **Bronze** = your safety net. If something goes wrong, you always have the original data.
- **Silver** = the workhorse. Most analysts and AI models read from here.
- **Gold** = ready for the CEO. Aggregated numbers, KPIs, and reports.

### What is Claude AI and Why Is It Here?

**Claude** is an AI model made by Anthropic (like ChatGPT but from a different company). In this project, we use **two versions**:

| Model | Think of it as... | We use it for... |
|-------|-------------------|------------------|
| **Claude Sonnet** | A fast, smart assistant | Quick tasks: "What type of data is this column?", "Write me a SQL query", "What's wrong with this data?" |
| **Claude Opus** | A senior analyst | Deep analysis: "What trends do you see in this revenue data?", "Write me an executive summary", "What business risks should I know about?" |

**How does AI help here?**

Without AI, a data engineer has to manually:
- Look at new data and figure out what each column means ← **Claude does this automatically**
- Write SQL queries for each business question ← **You just ask Claude in plain English**
- Investigate why data quality is bad ← **Claude analyzes the quality report and tells you what's wrong**
- Write weekly reports ← **Claude generates the report narrative**

This is exactly what the client described in the interview: *"He replaced 5 developers and does 3x the work using only Claude."*

### What is MCP (Model Context Protocol)?

**MCP** stands for **Model Context Protocol**. Think of it like a **USB port for AI**.

Right now, when you use Claude (or ChatGPT), it can only read/write text. It can't connect to your database, check your files, or trigger your pipeline. **MCP changes that.**

MCP is an **open standard** (created by Anthropic) that lets AI agents **interact with external tools and data** through a standardized interface. It's like giving Claude a set of tools it can use:

```
Without MCP:                          With MCP:
┌──────────┐                          ┌──────────┐
│  Claude   │                          │  Claude   │
│  "I can   │                          │  "I can:  │
│  only     │                          │  • Query your database
│  chat"    │                          │  • Check data quality
│           │                          │  • Run the pipeline
└──────────┘                          │  • Generate reports
                                       │  • List all datasets"
                                       └──────────┘
```

In our project, the **MCP Server** exposes 6 tools that any AI agent can use:

| MCP Tool | What It Does | Example |
|----------|-------------|---------|
| `query_dataset` | Run SQL queries against the data lake | "Show me revenue by country" |
| `get_schema` | Get the structure of any table | "What columns does the CRM table have?" |
| `check_quality` | Check data quality scores | "Is the ERP data clean enough?" |
| `list_datasets` | Browse all available datasets | "What data do we have?" |
| `run_pipeline` | Trigger the data pipeline | "Re-process today's data" |
| `generate_insight` | Get AI-powered business insights | "What are the top trends?" |

**Why does this matter?** Because it means an AI agent (like Claude in your IDE, or Cursor, or Antigravity) can autonomously work with your data — asking questions, running queries, and generating reports — without a human having to copy-paste data back and forth.

---

## 🏗️ What Did I Build? (Everything Explained)

### 1. 📥 Data Ingestion — The Bronze Layer (`src/ingestion/`)

This is where data **enters** the system. I built 4 connectors, each one designed to handle a different type of data source:

| File | What It Does | Real-World Example |
|------|-------------|-------------------|
| `base_connector.py` | The **blueprint** that all connectors follow. Defines how to connect, extract, validate, and track metrics. | Like an interface/contract — every connector must implement these methods |
| `crm_connector.py` | Ingests **CRM contact data** (JSON). Flattens nested fields, deduplicates by contact ID, validates email format. | HubSpot or Salesforce API data |
| `erp_connector.py` | Ingests **ERP transaction data** (CSV). Validates quantities (no negatives), checks currency codes, verifies amounts match (qty × price = total). | SAP or Oracle ERP exports |
| `csv_ingestion.py` | **Generic CSV** ingestor. Auto-detects delimiter (comma, semicolon, tab), encoding (UTF-8, Latin-1), and data types. | Any CSV file a client sends |
| `api_connector.py` | Ingests data from **REST APIs**. Handles pagination, flattens nested JSON (e.g., `address.city` → `address_city`). | WhatsApp API, web analytics |

**What makes these smart:**
- **Retry logic** — If a source fails, it retries automatically (configurable)
- **Validation** — Every record is validated before acceptance (bad records go to a "rejected" pile)
- **Metrics tracking** — Every ingestion run tracks: records read, accepted, rejected, duration, errors
- **Metadata enrichment** — Every record gets stamped with `_source`, `_ingested_at`, `_batch_id`

### 2. 🔄 Data Transformation — The Silver Layer (`src/transformation/`)

This is where **messy data gets cleaned**. Four modules work together:

| File | What It Does | Why It Matters |
|------|-------------|---------------|
| `spark_processor.py` | The main **cleaning engine**. Standardizes column names to `snake_case`, handles null values, normalizes strings (trim, lowercase emails), standardizes dates to UTC, adds partition columns. Works with both PySpark (AWS Glue) and Pandas (local). | Ensures all data looks the same regardless of where it came from |
| `data_quality.py` | A **quality checking framework** with 5 dimensions. You define rules like "email must be 95% complete" or "quantity must be between 0 and 10,000", and it checks every record. | Catches data problems before they reach business reports |
| `schema_enforcer.py` | **Validates data types** against predefined schemas. Has three modes: STRICT (reject bad rows), PERMISSIVE (keep but tag), DROP (remove extra columns). Comes with predefined schemas for CRM and ERP. | Prevents wrong data types from breaking downstream queries |
| `deduplication.py` | Removes **duplicate records** using three strategies: EXACT (hash-based, for clean data), FUZZY (similarity-based, for messy data with typos), WINDOW (time-based, for streaming data where events might arrive twice). | Critical for data that comes from multiple sources that might overlap |

**The 5 Quality Dimensions:**
1. **Completeness** — Are required fields filled in? (e.g., "95% of emails must be present")
2. **Accuracy** — Are values reasonable? (e.g., "quantity must be between 0 and 10,000")
3. **Consistency** — Do related fields agree? (e.g., "quantity × unit_price ≈ total_amount")
4. **Timeliness** — Is the data fresh enough? (e.g., "order dates must be within last 24 hours")
5. **Uniqueness** — Are there duplicates? (e.g., "transaction_id must be unique")

### 3. 📊 Business Analytics — The Gold Layer (`src/analytics/`)

This is where **clean data becomes business value**:

| File | What It Does | Output Example |
|------|-------------|---------------|
| `aggregations.py` | Creates **daily, weekly, monthly rollups**. Groups transactions by date, calculates totals, averages, top categories, top countries. | "Monday: $12K revenue, 15 transactions, top category: Equipment" |
| `kpi_calculator.py` | Computes **Key Performance Indicators**: total revenue, average order value, unique customers, customer concentration (Pareto), revenue by country/category. | "Top 10% of customers generate 65% of revenue" |
| `report_generator.py` | Generates **structured reports** with optional AI narratives. If Claude is connected, it writes the report summary. If not, it uses templates. | A full report with sections: revenue summary, volume metrics, top categories |

### 4. 🤖 Claude AI Integration (`src/ai/`)

This is the **differentiator** — AI is not an afterthought, it's built into the core:

| File | What It Does | When It Runs |
|------|-------------|-------------|
| `claude_client.py` | The **main API wrapper** for Anthropic's Claude. Handles: dual model support (Sonnet + Opus), automatic retry with exponential backoff, token counting, cost estimation, structured JSON output, mock mode for development (works without an API key). | Every time any AI feature is used |
| `data_analyzer.py` | **Automatic data profiling**. Sends a statistical summary + sample data to Claude and gets back: column descriptions, quality issues, suggested data types, recommended transformations. | When new data arrives in Bronze layer |
| `insight_generator.py` | **Business insight extraction** using Claude Opus. Analyzes Gold layer data and returns: top 5 insights, trend analysis, anomalies, business risks, actionable recommendations, executive summary. | After Gold layer is updated |
| `query_generator.py` | **Natural language → SQL**. You ask a question in plain English ("top 5 products by revenue last month?") and Claude generates an optimized Athena SQL query with proper partition filtering. | When analysts need data |
| `quality_advisor.py` | **AI quality doctor**. When quality checks fail, it analyzes the report and provides: root cause analysis, priority ranking, remediation steps, prevention strategies. | When data quality issues are detected |

**Important: Mock Mode** — The Claude client works **without an API key** for development. It returns mock responses so you can test the full pipeline without spending money on API calls.

### 5. 🔌 MCP Server (`src/mcp_server/`)

The **MCP Server** (explained above) that lets AI agents interact with the data lake. It includes:

- **6 tools**: query_dataset, get_schema, check_quality, list_datasets, run_pipeline, generate_insight
- **3 resources**: Data Catalog (all datasets), Quality Reports, Pipeline Status
- **In-memory data catalog**: Describes all Bronze, Silver, and Gold datasets with metadata
- **Standalone mode**: Works even without the MCP SDK installed (shows a demo)

### 6. 🔧 Pipeline Orchestrator (`src/pipeline/`)

The **main entry point** that coordinates everything:

```
orchestrator.py runs:

1. 🥉 BRONZE — Ingest CRM, ERP, API data
                → Claude profiles each dataset
2. 🥈 SILVER — Transform, deduplicate, validate
                → Claude advises on quality issues
3. 🥇 GOLD  — Aggregate, calculate KPIs, generate reports
                → Claude Opus generates business insights
```

You can run the full pipeline or just one layer:
```bash
python -m src.pipeline.orchestrator              # Full pipeline
python -m src.pipeline.orchestrator --layer bronze  # Just ingestion
```

### 7. 📐 DBT Models (`dbt/`)

**DBT (Data Build Tool)** is a popular tool for writing SQL transformations. I included 3 SQL models that mirror the Python pipeline:

| Model | Layer | What It Does |
|-------|-------|-------------|
| `stg_raw_transactions.sql` | Bronze | Reads raw data, adds a row hash for change detection |
| `int_cleaned_transactions.sql` | Silver | Deduplicates, validates business rules, standardizes values, adds quality flags |
| `fct_daily_metrics.sql` | Gold | Daily aggregations with revenue growth, top categories, quality scores |

These run on **Amazon Athena** (a SQL query engine that reads directly from S3 files).

### 8. ☁️ AWS Infrastructure (`infrastructure/`)

| File | What It Does |
|------|-------------|
| `datalake_stack.yaml` | A **CloudFormation template** (Infrastructure as Code) that creates ALL the AWS resources with one command: S3 bucket with lifecycle policies, 3 Glue databases (Bronze/Silver/Gold), Glue crawlers, Athena workgroup, Lambda trigger function, SNS alerts, CloudWatch dashboard, IAM roles |
| `etl_silver_transform.py` | A **PySpark script** designed to run on AWS Glue. Does the same cleaning/validation as the Python code but at scale using Spark distributed processing |

### 9. 🧪 Tests (`tests/`)

**61 test cases** covering every layer:

| Test File | Tests | What It Verifies |
|-----------|-------|-----------------|
| `test_ingestion.py` | 14 | CRM validation, ERP rejection rules, CSV auto-detection, API JSON flattening |
| `test_transformation.py` | 18 | Column standardization, null handling, quality checks, deduplication, schema enforcement |
| `test_ai_integration.py` | 13 | Claude mock mode, token tracking, cost estimation, data profiling, SQL generation |
| `test_mcp_server.py` | 16 | All 6 MCP tools, data catalog structure, quality reports |

### 10. 📊 Sample Data (`data/`)

Real-looking test data so you can run the pipeline immediately:

| File | Contents |
|------|---------|
| `sample_crm_contacts.json` | 8 CRM contacts (Mexico, US, Colombia) with intentional quality issues (invalid email, duplicate) |
| `sample_erp_transactions.csv` | 15 ERP transactions with products, quantities, amounts, and currencies |
| `sample_api_response.json` | 5 API interaction events (WhatsApp, Email, Web) with nested JSON |

---

## 🚀 How to Run

### 1. Install Dependencies

```bash
cd ai-datalake-platform
pip install -r requirements.txt
```

### 2. Run the Pipeline

```bash
# Full pipeline (Bronze → Silver → Gold)
python -m src.pipeline.orchestrator

# Just one layer
python -m src.pipeline.orchestrator --layer bronze
```

### 3. Run the MCP Server

```bash
python -m src.mcp_server.server
```

### 4. Run Tests

```bash
python -m pytest tests/ -v
```

### 5. (Optional) Connect Claude AI

```bash
# Copy the .env template
cp .env.example .env

# Edit .env and add your Anthropic API key:
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Now the pipeline will use real Claude AI instead of mock responses
```

### 6. (Optional) Deploy to AWS

```bash
aws cloudformation deploy \
    --template-file infrastructure/cloudformation/datalake_stack.yaml \
    --stack-name ai-datalake-dev \
    --parameter-overrides Environment=dev \
    --capabilities CAPABILITY_NAMED_IAM
```

---

## 📂 Project Structure

```
ai-datalake-platform/
│
├── src/                          # All source code
│   ├── ingestion/                # 🥉 BRONZE — Data collection
│   │   ├── base_connector.py    #    Base class for all connectors
│   │   ├── crm_connector.py     #    CRM data (HubSpot, Salesforce)
│   │   ├── erp_connector.py     #    ERP data (SAP, Oracle)
│   │   ├── csv_ingestion.py     #    Generic CSV files
│   │   └── api_connector.py     #    REST API data
│   │
│   ├── transformation/          # 🥈 SILVER — Data cleaning
│   │   ├── spark_processor.py   #    Main cleaning engine (PySpark/Pandas)
│   │   ├── data_quality.py      #    5-dimension quality checks
│   │   ├── schema_enforcer.py   #    Type validation + schemas
│   │   └── deduplication.py     #    Remove duplicates (3 strategies)
│   │
│   ├── analytics/               # 🥇 GOLD — Business analytics
│   │   ├── aggregations.py      #    Daily/weekly/monthly rollups
│   │   ├── kpi_calculator.py    #    Revenue, customer, ops KPIs
│   │   └── report_generator.py  #    Reports with AI narratives
│   │
│   ├── ai/                      # 🤖 Claude AI integration
│   │   ├── claude_client.py     #    API wrapper (Sonnet + Opus)
│   │   ├── data_analyzer.py     #    Automatic data profiling
│   │   ├── insight_generator.py #    Business insights (Opus)
│   │   ├── query_generator.py   #    English → SQL translation
│   │   └── quality_advisor.py   #    AI quality recommendations
│   │
│   ├── mcp_server/              # 🔌 MCP Server for AI agents
│   │   └── server.py            #    6 tools + 3 resources
│   │
│   └── pipeline/                # 🔧 Pipeline orchestration
│       ├── orchestrator.py      #    Runs Bronze→Silver→Gold
│       └── config.py            #    Configuration loader
│
├── dbt/                         # 📐 SQL transformations (for Athena)
│   └── models/
│       ├── bronze/              #    stg_raw_transactions.sql
│       ├── silver/              #    int_cleaned_transactions.sql
│       └── gold/                #    fct_daily_metrics.sql
│
├── infrastructure/              # ☁️ AWS resources (IaC)
│   ├── cloudformation/          #    S3, Glue, Athena, Lambda, etc.
│   └── glue_jobs/               #    PySpark ETL for AWS Glue
│
├── tests/                       # 🧪 61 automated tests
│   ├── test_ingestion.py        #    Bronze layer tests
│   ├── test_transformation.py   #    Silver layer tests
│   ├── test_ai_integration.py   #    Claude AI tests
│   └── test_mcp_server.py       #    MCP server tests
│
├── data/                        # 📊 Sample data to test with
│   ├── sample_crm_contacts.json
│   ├── sample_erp_transactions.csv
│   └── sample_api_response.json
│
├── config/                      # ⚙️ Configuration files
│   ├── pipeline_config.yaml     #    Pipeline settings
│   ├── claude_config.yaml       #    AI model settings
│   └── mcp_config.json          #    MCP server config
│
├── docs/                        # 📚 Documentation
│   ├── architecture.md          #    System architecture diagram
│   ├── claude_workflows.md      #    How AI is used at each stage
│   ├── mcp_integration.md       #    MCP server documentation
│   └── medallion_design.md      #    Data lake layer design
│
├── README.md                    # This file
├── pyproject.toml               # Python package configuration
├── requirements.txt             # Dependencies
├── Makefile                     # Shortcut commands
└── .env.example                 # Environment variables template
```

---

## 🛠️ Technology Stack

| Technology | What It Is | Why I Used It |
|-----------|-----------|---------------|
| **Python 3.10+** | Programming language | Industry standard for data engineering |
| **Pandas** | Data manipulation library | Works locally for data transformation |
| **PySpark** | Distributed data processing | Handles big data on AWS Glue/EMR |
| **Claude AI (Anthropic)** | AI language model | Automates profiling, analysis, SQL, reports |
| **MCP** | Protocol for AI tools | Lets AI agents interact with the data lake |
| **Amazon S3** | Cloud storage | Data lake storage (cheap, scalable, durable) |
| **AWS Glue** | ETL service + data catalog | Runs PySpark jobs, catalogs tables |
| **Amazon Athena** | SQL query engine | Query S3 data directly with SQL |
| **AWS Lambda** | Serverless functions | Triggers pipeline on new data |
| **CloudFormation** | Infrastructure as Code | Deploy all AWS resources with one command |
| **DBT** | SQL transformation tool | Standardized SQL models for Athena |
| **pytest** | Testing framework | 61 automated tests |
| **PyArrow/Parquet** | Columnar file format | Efficient storage, fast queries |

---

## 📈 How the Pipeline Works (Step by Step)

```
Step 1: INGEST (Bronze Layer)
   📥 CRM API → 8 contacts loaded → 2 rejected (invalid email, duplicate)
   📥 ERP CSV → 15 transactions loaded → 3 rejected (negative qty, no customer)
   📥 API     → 5 interaction events loaded → 0 rejected
   🤖 Claude AI profiles each dataset automatically

Step 2: TRANSFORM (Silver Layer)
   🔄 Column names standardized to snake_case
   🔄 Dates converted to UTC
   🔄 Strings trimmed, emails lowercased
   🔍 Quality check: 94% overall score
   🗑️ 2 duplicates removed
   📋 Schema validation: all types correct
   🤖 Claude advises on quality issues found

Step 3: ANALYZE (Gold Layer)
   📊 Daily aggregations: 5 rows produced
   📊 KPIs: $87K revenue, $7K avg order, 10 unique customers
   📊 Top category: Equipment (65% of revenue)
   📊 Top country: Mexico (55% of transactions)
   🤖 Claude Opus generates business insights and recommendations

Step 4: SERVE (MCP Server + Reports)
   🔌 AI agents can query all datasets via MCP tools
   📝 Automated report generated with AI narrative
   📊 Data ready for dashboards (QuickSight, Tableau)
```

---

## 🥋 Claude Code Workflow (Boris Cherny + Trimaran)

This project is configured with a professional Claude Code workflow, combining **Boris Cherny's 23 tips** (the creator of Claude Code), **Trimaran's production lakehouse standard**, and **CC-Sensei coaching**.

### What's Configured

```
.claude/
├── commands/                    # Slash commands (type / in Claude Code)
│   ├── run-tests.md            #   /run-tests → runs 61 tests + coverage report
│   ├── pipeline-health.md      #   /pipeline-health → spawns 4 agents to audit all layers
│   ├── review-changes.md       #   /review-changes → git diff + code review
│   └── commit-push-pr.md       #   /commit-push-pr → commit, push, open PR
│
├── agents/                      # Specialized AI sub-agents
│   ├── planner.md              #   Plans features by Medallion layer
│   ├── code-reviewer.md        #   Security, conventions, data pattern review
│   ├── build-validator.md      #   Full verification pipeline (test + lint + typecheck)
│   └── self-improvement.md     #   Factory of factories — learns from mistakes
│
├── skills/                      # Reusable workflow recipes
│   ├── data-pipeline-tdd.md    #   TDD cycle for data pipelines
│   ├── self-improvement-loop.md #   Planner → Generator → Critic → Tester → Persist
│   └── data-triangulation.md   #   Cross-validate data across ERP, Excel, WhatsApp
│
├── settings.json                # Hook permissions + safe commands
├── CLAUDE.template.md           # Trimaran lakehouse CLAUDE.md template
└── TRIMARAN_CHECKLIST.md        # Trimaran 5-pillar rubric
```

### Installed Plugins

| Plugin | Version | What It Does |
|--------|---------|-------------|
| **trimaran-lakehouse** | v0.1.0 | Trimaran's production data lake standard — 3 agents (`lakehouse-architect`, `dataops-engineer`, `iac-reviewer`), 7 skills (`medallion-design`, `ingestion-pattern`, `data-quality-suite`, `iac-scaffold`, `cost-audit`, `lakehouse-rules`, `rules`) |
| **cc-sensei** | v0.5.3 | AI coaching system — watches you work in Claude Code and surfaces one power-user tip at the right moment. Bilingual EN/ES. 24 curriculum rules, mastery tracking, anti-Clippy gate |

### CLAUDE.md Rules

The project's `CLAUDE.md` contains:
- **Project conventions** — code style, data engineering patterns, testing rules
- **Trimaran's 5 always-follow rules** (L1–L5):
  1. 🥉 **Medallion discipline** — never mutate bronze; idempotent, `dt`-partitioned
  2. 💰 **Cost-aware storage** — watch requests + GIR, not just storage
  3. 🏗️ **IaC for everything** — no console clickops, least-privilege IAM
  4. ✅ **Quality is a gate** — zero-vs-missing distinguished, self-healing loop
  5. 🎯 **Reconcile to the centavo** — fresh baselines, never manufacture false drift

### How to Use It

```bash
# Start Claude Code in this project
cd ai-datalake-platform
claude

# Run tests (Boris Tip #7 — Custom Commands)
> /run-tests

# Audit the full pipeline (spawns 4 agents in parallel)
> /pipeline-health

# Use Trimaran agents
> @lakehouse-architect Design the medallion layout for SAP ONE and Intelisis data
> @dataops-engineer Set up data quality gates for Bronze→Silver
> @iac-reviewer Review the CloudFormation stack for cost and security

# Check your Claude Code learning progress
> /sensei progress

# Use Plan Mode (Boris Tip — Shift+Tab ×2)
> Shift+Tab → Shift+Tab → "Add WhatsApp connector to Bronze layer"
```

---

## 🏢 OGGI Data Lake — Onboarding Status

This project is being integrated with **Trimaran's OGGI Data Lake** production infrastructure.  
OGGI is a **Mexican fashion/apparel company** that manufactures clothing and sells through retail chains: **Coppel, Sears, Suburbia**.

### AWS Access (Provided by Rodolfo)

| Resource | Details | Status |
|----------|---------|--------|
| **AWS Account** | `276483282865` | ✅ Configured |
| **Region** | `us-east-2` | ✅ Set in AWS CLI |
| **IAM User** | `enmanuel.cuadros` | ✅ Created |
| **MFA** | Device `aws-claude` (Google Authenticator) | ✅ Configured & working |
| **S3 Bucket** | `oggi-lakehouse-landing-276483282865-us-east-2` | ✅ Explored (18 folders) |
| **Glue Databases** | `oggi_bronze`, `oggi_lake`, `oggi_ontology` | ✅ Explored (schemas mapped) |
| **Athena** | Workgroup `oggi_lake` | ⏳ ListWorkGroups denied — direct query TBD |
| **CodeCommit** | `oggi-bronze-crackers`, `oggi-ontology-dbt` | 🔴 403 — credential invalid (escalated) |

### S3 Data Lake Structure (Discovered 2026-06-22)

```
oggi-lakehouse-landing-276483282865-us-east-2/
├── raw/              ← 4 files (Aspel NOI payroll backups, 2.7 GB)
├── bronze-parquet/   ← Bronze layer in Parquet
├── silver/           ← 82,681 files! (Aspel-COI, facturas, WMS, Sears XML, 55+ datasets)
├── gold/             ← 87 files (PnL, sell-in, rentabilidad, maquila, demand sensing)
├── ontology/         ← Business ontology (dbt models: party merge, item xref, DQ scorecard)
├── canonical/        ← Canonical/master data
├── finanzas/         ← Financial docs (CFDI XMLs + PDFs — thousands of invoices)
├── coppel/           ← 12,974 files (daily sell-out data from Coppel)
├── sears/            ← Sears retail chain data
├── suburbia/         ← Suburbia retail chain data
├── drive/            ← OneDrive/shared files
├── dashboards/       ← Dashboard data
├── backups/          ← Backups
├── _athena_results/  ← Athena query results
├── _code/            ← ETL code
├── _meta/            ← Metadata
├── athena/           ← Athena workgroup storage
└── runner-code/      ← Runner/pipeline code
```

### Key Tables Discovered

| Database | Table | Records | Description |
|----------|-------|---------|-------------|
| `oggi_lake` | **`g_factura_line`** | **12,748,379** 🔥 | Invoice line items — THE core table |
| `oggi_lake` | `g_dim_articulo` | 44,051 | Product/SKU catalog |
| `oggi_lake` | `g_dim_company` | 9 | OGGI legal entities (Mayoreo, Junior, SOF, Bluster, Dyclass, Buying, Nómina) |
| `oggi_lake` | `fct_sell_in` | — | Sell-in facts (12 MB Parquet) |
| `oggi_lake` | `rentabilidad_cliente` | — | Client profitability (1.3 MB, daily snapshots) |
| `oggi_lake` | `pnl_canonical` | — | P&L canonical (53 KB, daily snapshots) |
| `oggi_lake` | `fct_production_order` | — | Production orders (649 KB) |
| `oggi_lake` | `fct_bom_intensity` | 19,948 | Bill of materials intensity |
| `oggi_ontology` | `catalog_master` | — | Master catalog of all data assets |
| `oggi_ontology` | `dq_scorecard` | — | Data quality scorecard |
| `oggi_ontology` | `action_party_merge_candidates` | — | Fuzzy-matched party duplicates |
| `oggi_bronze` | *(thousands)* | — | CFDI XMLs, PDFs from `oggi-finanzas-docs` crawler |

### OGGI Company Entities (from `dim_company` Parquet)

| Company ID | Name | Role | Revenue? |
|-----------|------|------|----------|
| SJMC | OGGI Mayoreo | Ventas a Coppel (cadenas) | ✅ Q1: $219M |
| SJM0 | OGGI Junior | Tiendas propias y distribuidores | ✅ Q1: $64M |
| SJM1 | OGGI Teziutlán | Planta y operación Puebla | ✅ Q1: $10M |
| SOF0 | SOF / Open Fashion | Comercializadora alterna | ✅ Q1: $800K |
| BUYING | Buying Compras | Paga maquila externa | COGS source |
| SDY0 | Dyclass | Servicios administrativos | Overhead |
| SBS0 | BluSter | Marca — cobra regalías | Overhead |

### Silver Layer Datasets (55+ sources)

| Category | Datasets |
|----------|----------|
| **ERP (GM3S)** | `facturas`, `pagos`, `pedidos`, `customer`, `company`, `item`, `vendor` |
| **Accounting (Aspel)** | `aspel-coi` (contabilidad), `aspel-noi` (nómina) |
| **WMS/Warehouse** | `location`, `warehouse`, `carrier`, `receipt_*`, `shipment_*`, `location_inventory` |
| **Sales** | `VTA`, `PED`, `INV`, `presupuesto-ventas` |
| **Sears** | `xml_provsears_*` (daily inventory + sales XML reports) |
| **SKU/Products** | `productos-sku`, `item_unit_of_measure`, `CAT` |
| **Operations** | `process_history`, `transaction_history`, `labor_management_detail` |

### Gold Layer Analytics (32+ models)

| Model | What It Does |
|-------|-------------|
| `pnl_canonical` | Profit & Loss by company (daily snapshots) |
| `rentabilidad_cliente` | Client profitability analysis |
| `fct_sell_in` | Sell-in revenue facts (12.7M lines) |
| `fct_production_order` | Production order tracking |
| `fct_bom_intensity` | Bill of materials per SKU |
| `fct_maquila_*` | Maquila cost, assignment, quality, scorecard |
| `coppel_demand_sensing` | Demand forecasting for Coppel |
| `coppel_replenishment` | Replenishment planning |
| `coppel_sellout_history` | Sell-out history from Coppel stores |
| `size_curve` / `size_misalignment` | Size distribution analytics |
| `oggi_action_levers` | Action recommendations |
| `signal_maturity_tracker` | Data signal maturity |

### What's Been Done ✅

- [x] Project built with complete Medallion Architecture (Bronze/Silver/Gold)
- [x] 61 tests passing, 53% coverage
- [x] Claude AI integration (Sonnet + Opus) with mock mode
- [x] MCP Server with 6 tools for AI agent data access
- [x] Boris Cherny's Claude Code workflow (4 commands, 4 agents, 3 skills)
- [x] Trimaran lakehouse plugin installed + 5 rules appended to CLAUDE.md
- [x] CC-Sensei coaching plugin installed (bilingual EN/ES)
- [x] AWS CLI configured (us-east-2, credentials set)
- [x] Project pushed to GitHub: [ecuadrosg36/ai-datalake-platform](https://github.com/ecuadrosg36/ai-datalake-platform)
- [x] **MFA configured** — Device `aws-claude`, Google Authenticator ✅
- [x] **S3 bucket explored** — 18 top-level folders, 95K+ files discovered
- [x] **Glue databases mapped** — 3 databases, all table schemas documented
- [x] **dim_company Parquet downloaded** — 9 OGGI entities with Q1 revenue data
- [x] **Silver layer cataloged** — 55+ datasets (ERP, Aspel, WMS, Sears, SKU)
- [x] **Gold layer cataloged** — 32+ analytics models (PnL, demand sensing, maquila)
- [x] **OGGI S3 Connector built** — `oggi_s3_connector.py` with 31 passing tests ✅
- [x] **CodeCommit repos cloned** — `oggi-bronze-crackers` + `oggi-ontology-dbt` ✅

### CodeCommit Repos (Cloned 2026-06-22)

#### 🔨 [oggi-bronze-crackers](file:///c:/Users/enman/Downloads/ANTIGRAVITY/oggi-bronze-crackers) — ERP Data Extraction

Converts **raw database dumps** (Postgres, Firebird, SQL Server) into **queryable Parquet** in S3, triggered automatically by EventBridge when a dump lands.

```
dump lands in S3 → EventBridge → Dispatcher Lambda →
  ├─ GM3  (Postgres/pg_restore)  → Fargate task
  ├─ Aspel (Firebird/gbak)       → Fargate task (1 per empresa)
  └─ WMS  (SQL Server/RESTORE)   → Batch/EC2 (104GB .bak files)
→ s3://lake/bronze-parquet/source=<src>/table=<t>/dt=<YYYY-MM-DD>/part-0.parquet
→ Glue Data Catalog (oggi_bronze) → Athena/dbt → silver + gold
```

| Source | Engine | Tables Extracted | Status |
|--------|--------|-----------------|--------|
| **GM3** (ERP) | PostgreSQL | `d_factura_c`, all tables mode | ✅ Production |
| **Aspel COI** | Firebird | Contabilidad tables | ⚠️ Verify table names against real `.fbk` |
| **Aspel NOI** | Firebird | Nómina tables | ⚠️ Verify table names |
| **WMS** | SQL Server | **Placeholder** table names | 🔴 Need real tables from RESTORE |
| **Finanzas** | None (Glue crawler) | PDFs, CFDIs | ✅ Cataloged |

#### 🧠 [oggi-ontology-dbt](file:///c:/Users/enman/Downloads/ANTIGRAVITY/oggi-ontology-dbt) — Semantic Layer (Palantir-style)

dbt-athena project that turns cracked ERP data into a **governed ontology**: golden entities, links (graph), metrics, Actions, and RAG retrieval.

```
models/
├── staging/       ← Views over bronze tables
├── intermediate/  ← Intermediate transformations
├── mdm/           ← Master Data (mdm_party, mdm_item, item_xref, party_xref)
├── objects/       ← 28 domain objects (invoice, expense, payroll, inventory, etc.)
├── links/         ← Graph edges between objects
├── metrics/       ← Business metrics (PnL, profitability, reconciliation)
├── actions/       ← Action store (party_merge, item_xref candidates)
└── security/      ← Row-level security
```

**Key Files:**
- `AUDIT_2026-06-21.md` — Adversarial audit by 6 AI auditors (29 agents, ~1.2M tokens)
- `actions/rag_build.py` — Builds RAG index with Bedrock Titan v2
- `actions/ontology_mcp.py` — MCP server for agent-facing semantic search
- `buildspec.yml` — AWS CodeBuild CI/CD pipeline

**Audit Findings Fixed:**
- ✅ Fixed 8x snapshot inflation in customer profitability ($68B → $8.6B)
- ✅ Fixed P&L snapshot inflation ($734M → $91.7M)
- ✅ Fixed empty `item_xref` (0 → 12,818 rows)
- ✅ Fixed invoice-party coverage (96.4% → 98.3%)

### What's Pending 🔴 — Next Steps

#### Immediate (This Week)
- [ ] **Study `oggi-bronze-crackers`** — Understand the GM3/Aspel/WMS cracker pipeline
- [ ] **Study `oggi-ontology-dbt`** — Understand the 28 object models and semantic layer
- [ ] **Run dbt locally** — `dbt build --profiles-dir .` against Athena (needs profile config)
- [ ] **Query Athena** — Run SQL queries against `g_factura_line` (12.7M rows) and `pnl_canonical`
- [ ] **Download more sample data** — `fct_sell_in`, `rentabilidad_cliente`, `pnl_canonical`

#### Short-term (Next 2 Weeks)
- [ ] **Verify Aspel table names** — Compare `crackers/aspel/tables.yml` against real `.fbk` file
- [ ] **Fix WMS placeholders** — Run `RESTORE FILELISTONLY` to get real table names
- [ ] **Address audit findings** — Fix gold snapshot inflation, silver catalog explosion
- [ ] **Build Coppel Connector** — Sell-out data ingestion from `coppel/` daily feeds
- [ ] **Fill CLAUDE.md Placeholders** — Add real OGGI accounts, sources, freshness cadences

#### Medium-term (Month 1)
- [ ] **Integrate `ai-datalake-platform` with OGGI ontology** — Use MCP tools from ontology_mcp.py
- [ ] **Build RAG pipeline** — Connect our AI layer to the ontology's semantic search
- [ ] **Production pipeline** — Deploy connectors to AWS (Lambda/Fargate)
- [ ] **Dashboard MVP** — Build first business dashboard using gold layer data

---

## 📬 Author

**Emanuel Cuadros** — Data Engineer & AI Specialist

- GitHub: [@ecuadrosg36](https://github.com/ecuadrosg36)

*Built with ❤️ using Claude AI, Boris Cherny's Claude Code workflow, and Trimaran's lakehouse standard — demonstrating how one engineer with AI tools can deliver enterprise-grade data lake solutions.*

