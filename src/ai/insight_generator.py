"""
Insight Generator — Automated business insights using Claude Opus.

Extracts business insights, trends, and recommendations from
Gold layer data using Claude Opus for deep analysis.
"""

import json
import logging
from typing import Any

import pandas as pd

from src.ai.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class InsightGenerator:
    """
    AI-powered business insight extraction using Claude Opus.

    Analyzes Gold layer datasets to produce:
    - Key business insights
    - Trend analysis
    - Anomaly detection
    - Actionable recommendations
    - Executive summaries

    Uses Claude Opus for its superior analytical capabilities.

    Usage:
        client = ClaudeClient()
        generator = InsightGenerator(client)

        insights = generator.generate_insights(
            df_gold,
            dataset_name="daily_revenue",
            focus_area="revenue trends",
        )
    """

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def generate_insights(
        self,
        df: pd.DataFrame,
        dataset_name: str = "business_metrics",
        focus_area: str | None = None,
        time_period: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate comprehensive business insights from Gold layer data.

        Uses Claude Opus for deep analysis of aggregated business data.
        """
        # Prepare data summary for Claude
        data_summary = self._prepare_data_summary(df)

        focus = f"\nFocus Area: {focus_area}" if focus_area else ""
        period = f"\nTime Period: {time_period}" if time_period else ""

        prompt = (
            f"As a senior data analyst, analyze this Gold layer dataset "
            f"'{dataset_name}' and provide comprehensive business insights.\n"
            f"{focus}{period}\n\n"
            f"Data Summary:\n{json.dumps(data_summary, indent=2, default=str)}\n\n"
            f"Full Data (truncated):\n{df.head(20).to_string()}\n\n"
            "Provide:\n"
            "1. **Top 5 Key Insights** (most important business findings)\n"
            "2. **Trend Analysis** (what's improving, declining, stable)\n"
            "3. **Anomalies Detected** (unexpected patterns or outliers)\n"
            "4. **Business Risks** (potential issues to watch)\n"
            "5. **Actionable Recommendations** (3-5 specific actions)\n"
            "6. **Executive Summary** (2-3 paragraph overview)"
        )

        response = self.claude.analyze(
            prompt,
            model="opus",  # Use Opus for deep analysis
            system_prompt="business_analysis",
            max_tokens=8192,
        )

        return {
            "dataset_name": dataset_name,
            "focus_area": focus_area,
            "time_period": time_period,
            "record_count": len(df),
            "data_summary": data_summary,
            "insights": response.get("content", ""),
            "model_used": response.get("model", ""),
            "tokens_used": response.get("tokens", {}),
            "cost_usd": response.get("cost_usd", 0),
        }

    def compare_periods(
        self,
        current_df: pd.DataFrame,
        previous_df: pd.DataFrame,
        metric_columns: list[str],
        period_label: str = "current vs previous",
    ) -> dict[str, Any]:
        """
        Generate insights comparing two time periods.

        Useful for month-over-month, quarter-over-quarter analysis.
        """
        comparison: dict[str, Any] = {}

        for col in metric_columns:
            if col in current_df.columns and col in previous_df.columns:
                current_val = pd.to_numeric(
                    current_df[col], errors="coerce"
                ).sum()
                previous_val = pd.to_numeric(
                    previous_df[col], errors="coerce"
                ).sum()

                change = current_val - previous_val
                change_pct = (
                    (change / previous_val * 100) if previous_val != 0 else 0
                )

                comparison[col] = {
                    "current": round(float(current_val), 2),
                    "previous": round(float(previous_val), 2),
                    "change": round(float(change), 2),
                    "change_pct": round(float(change_pct), 2),
                }

        prompt = (
            f"Analyze this period-over-period comparison ({period_label}):\n\n"
            f"{json.dumps(comparison, indent=2)}\n\n"
            "Provide:\n"
            "1. Key changes and their business implications\n"
            "2. Which metrics improved and which declined\n"
            "3. Possible reasons for significant changes\n"
            "4. Recommendations for the next period"
        )

        response = self.claude.analyze(
            prompt,
            model="opus",
            system_prompt="business_analysis",
        )

        return {
            "period_label": period_label,
            "comparison": comparison,
            "ai_analysis": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }

    def generate_executive_summary(
        self,
        kpis: dict[str, Any],
        quality_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate an executive summary combining KPIs and quality metrics.

        Designed for stakeholder consumption.
        """
        prompt = (
            "Create a concise executive summary (3 paragraphs max) from "
            "these KPIs and data quality metrics.\n\n"
            f"KPIs:\n{json.dumps(kpis, indent=2, default=str)}\n\n"
        )

        if quality_report:
            prompt += (
                f"Data Quality Report:\n"
                f"{json.dumps(quality_report, indent=2, default=str)}\n\n"
            )

        prompt += (
            "Write for a C-level audience. Include:\n"
            "- 1-2 headline numbers\n"
            "- Key trend direction\n"
            "- Any quality concerns\n"
            "- Top recommendation"
        )

        response = self.claude.analyze(
            prompt,
            model="opus",
            system_prompt="business_analysis",
        )

        return {
            "executive_summary": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }

    def _prepare_data_summary(self, df: pd.DataFrame) -> dict[str, Any]:
        """Prepare a concise data summary for Claude analysis."""
        summary: dict[str, Any] = {
            "total_records": len(df),
            "columns": list(df.columns),
            "numeric_stats": {},
        }

        for col in df.select_dtypes(include=["number"]).columns:
            if not col.startswith("_"):
                clean = df[col].dropna()
                if len(clean) > 0:
                    summary["numeric_stats"][col] = {
                        "sum": round(float(clean.sum()), 2),
                        "mean": round(float(clean.mean()), 2),
                        "min": float(clean.min()),
                        "max": float(clean.max()),
                    }

        return summary
