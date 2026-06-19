# Claude AI Workflows — How AI Powers Every Pipeline Stage

## Overview

This document describes how Claude/Anthropic AI is integrated into every stage of the data lake pipeline, accelerating development and improving data quality.

## Model Selection Strategy

| Model | Use Case | Why |
|-------|----------|-----|
| **Claude Sonnet** | Day-to-day tasks: profiling, validation, SQL generation | Fast, cost-effective, great for structured tasks |
| **Claude Opus** | Complex analysis: insights, planning, executive summaries | Superior analytical depth, better reasoning |

## Workflow 1: AI-Powered Data Profiling (Bronze → Silver)

**When**: New data arrives in the Bronze layer
**Model**: Claude Sonnet

```python
# The DataAnalyzer automatically profiles new datasets
analyzer = DataAnalyzer(claude_client)
profile = analyzer.profile_dataset(df, source_name="new_client_crm")

# Claude returns:
# - Business meaning of each column
# - Data quality issues found
# - Suggested data types
# - Recommended Silver layer transformations
```

**Impact**: Reduces manual data exploration from hours to seconds.

## Workflow 2: AI Quality Advisory (Silver Layer)

**When**: Quality checks detect issues
**Model**: Claude Sonnet

```python
# After running quality checks
report = quality_checker.check(df, "erp_transactions", "silver")

# If issues found, get AI recommendations
advisor = QualityAdvisor(claude_client)
advice = advisor.analyze_report(report.to_dict())

# Claude returns:
# - Root cause analysis
# - Priority ranking (High/Medium/Low)
# - Specific remediation steps
# - Prevention strategies
```

**Impact**: Automated root cause analysis instead of manual debugging.

## Workflow 3: Natural Language → SQL (Consumption)

**When**: Business users or AI agents need to query data
**Model**: Claude Sonnet

```python
# Convert business questions to Athena SQL
generator = QueryGenerator(claude_client)
result = generator.generate(
    "What were the top 5 products by revenue in Mexico last quarter?"
)
# Claude generates optimized Athena SQL with partition pruning
```

**Impact**: Non-technical stakeholders can query the data lake directly.

## Workflow 4: AI Insight Generation (Gold Layer)

**When**: Gold layer data is updated with new aggregations
**Model**: Claude Opus

```python
# Generate deep business insights
insights = insight_gen.generate_insights(
    df_gold,
    dataset_name="daily_business_metrics",
    focus_area="revenue and customer trends",
)

# Claude Opus returns:
# - Top 5 key business insights
# - Trend analysis (improving, declining, stable)
# - Anomaly detection
# - Business risks
# - Actionable recommendations
# - Executive summary
```

**Impact**: Automated strategic analysis that would take analysts days.

## Workflow 5: MCP Server Integration

**When**: AI agents (Claude in IDE, Cursor, etc.) need data lake access
**Model**: Both (depending on tool)

```json
// MCP Tools available to AI agents:
{
  "query_dataset": "Execute SQL against the data lake",
  "get_schema": "Retrieve table schemas",
  "check_quality": "Get quality metrics",
  "run_pipeline": "Trigger pipeline runs",
  "generate_insight": "Generate AI insights",
  "list_datasets": "Browse the data catalog"
}
```

**Impact**: AI agents become autonomous data engineers.

## Cost Optimization

- **Sonnet** for 90% of calls (fast, $3/$15 per 1M tokens)
- **Opus** reserved for deep analysis (10% of calls)
- Token tracking and budget alerts built into the client
- Response caching for repeated queries (not yet implemented)
