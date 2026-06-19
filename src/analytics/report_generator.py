"""
Report Generator — Automated report generation with AI narratives.

Generates structured reports from Gold layer data with optional
Claude AI-powered narrative summaries and recommendations.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Automated report generation engine.

    Produces structured reports from Gold layer datasets.
    When Claude AI is available, generates narrative summaries
    and business recommendations.

    Usage:
        generator = ReportGenerator(claude_client=claude)
        report = generator.generate(
            df_gold,
            report_type="daily_business",
            title="Daily Business Report — June 2025",
        )
    """

    def __init__(self, claude_client: Any = None):
        """
        Initialize report generator.

        Args:
            claude_client: Optional ClaudeClient instance for AI narratives.
                          If None, reports use template-based summaries.
        """
        self.claude_client = claude_client

    def generate(
        self,
        df: pd.DataFrame,
        report_type: str = "daily_business",
        title: str = "Data Lake Report",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a complete report.

        Args:
            df: Gold layer DataFrame to report on.
            report_type: Type of report (daily_business, quality, pipeline).
            title: Report title.
            metadata: Additional metadata to include.

        Returns:
            Structured report dictionary.
        """
        report: dict[str, Any] = {
            "title": title,
            "type": report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(df),
            "metadata": metadata or {},
        }

        if report_type == "daily_business":
            report["sections"] = self._generate_business_sections(df)
        elif report_type == "quality":
            report["sections"] = self._generate_quality_sections(df)
        elif report_type == "pipeline":
            report["sections"] = self._generate_pipeline_sections(df)

        # Add AI narrative if available
        if self.claude_client:
            report["ai_narrative"] = self._generate_ai_narrative(report)
        else:
            report["ai_narrative"] = self._generate_template_narrative(report)

        logger.info(
            f"Report generated: '{title}' ({report_type}), "
            f"{len(report.get('sections', {}))} sections"
        )

        return report

    def _generate_business_sections(self, df: pd.DataFrame) -> dict[str, Any]:
        """Generate business report sections."""
        sections: dict[str, Any] = {}

        # Revenue Summary
        amount_col = None
        for col in ["total_revenue", "total_amount", "revenue", "amount"]:
            if col in df.columns:
                amount_col = col
                break

        if amount_col:
            amounts = pd.to_numeric(df[amount_col], errors="coerce").dropna()
            sections["revenue_summary"] = {
                "total": round(float(amounts.sum()), 2),
                "average": round(float(amounts.mean()), 2),
                "median": round(float(amounts.median()), 2),
                "trend": self._calculate_trend(amounts),
            }

        # Volume Metrics
        sections["volume_metrics"] = {
            "total_records": len(df),
            "date_range": self._get_date_range(df),
        }

        # Top Performers
        if "category" in df.columns and amount_col:
            top_cats = (
                df.groupby("category")[amount_col]
                .sum()
                .sort_values(ascending=False)
                .head(5)
            )
            sections["top_categories"] = {
                str(k): round(float(v), 2) for k, v in top_cats.items()
            }

        return sections

    def _generate_quality_sections(self, df: pd.DataFrame) -> dict[str, Any]:
        """Generate quality report sections."""
        null_rates = {}
        for col in df.columns:
            if not col.startswith("_"):
                null_rate = df[col].isna().mean()
                if null_rate > 0:
                    null_rates[col] = round(float(null_rate * 100), 2)

        return {
            "completeness": {
                "overall_completeness_pct": round(
                    float((1 - df.isna().mean().mean()) * 100), 2
                ),
                "columns_with_nulls": null_rates,
            },
            "record_count": len(df),
            "column_count": len([c for c in df.columns if not c.startswith("_")]),
        }

    def _generate_pipeline_sections(self, df: pd.DataFrame) -> dict[str, Any]:
        """Generate pipeline execution report sections."""
        return {
            "records_processed": len(df),
            "columns": list(df.columns),
            "memory_usage_mb": round(
                float(df.memory_usage(deep=True).sum() / 1024 / 1024), 2
            ),
        }

    def _generate_ai_narrative(self, report: dict[str, Any]) -> str:
        """Generate AI-powered narrative using Claude."""
        try:
            prompt = (
                "Generate a concise executive summary (3-4 paragraphs) for "
                f"this data report:\n\n{json.dumps(report.get('sections', {}), indent=2)}\n\n"
                "Include: key findings, trends, and 2-3 actionable recommendations."
            )
            response = self.claude_client.analyze(prompt)
            return response.get("content", "AI narrative unavailable.")
        except Exception as e:
            logger.warning(f"AI narrative generation failed: {e}")
            return self._generate_template_narrative(report)

    def _generate_template_narrative(self, report: dict[str, Any]) -> str:
        """Generate template-based narrative (fallback when AI unavailable)."""
        sections = report.get("sections", {})
        parts: list[str] = []

        if "revenue_summary" in sections:
            rev = sections["revenue_summary"]
            parts.append(
                f"Total revenue for the period: ${rev.get('total', 0):,.2f} "
                f"(average: ${rev.get('average', 0):,.2f}). "
                f"Trend: {rev.get('trend', 'N/A')}."
            )

        if "volume_metrics" in sections:
            vol = sections["volume_metrics"]
            parts.append(
                f"Total records processed: {vol.get('total_records', 0):,}."
            )

        if not parts:
            parts.append("Report generated successfully. See sections for details.")

        return " ".join(parts)

    @staticmethod
    def _calculate_trend(values: pd.Series) -> str:
        """Calculate simple trend direction."""
        if len(values) < 2:
            return "insufficient_data"
        midpoint = len(values) // 2
        first_half = values.iloc[:midpoint].mean()
        second_half = values.iloc[midpoint:].mean()
        change_pct = ((second_half - first_half) / max(first_half, 1)) * 100

        if change_pct > 5:
            return "increasing"
        elif change_pct < -5:
            return "decreasing"
        return "stable"

    @staticmethod
    def _get_date_range(df: pd.DataFrame) -> dict[str, str | None]:
        """Extract date range from DataFrame."""
        for col in ["date", "order_date", "timestamp", "created_at"]:
            if col in df.columns:
                dates = pd.to_datetime(df[col], errors="coerce").dropna()
                if not dates.empty:
                    return {
                        "start": str(dates.min()),
                        "end": str(dates.max()),
                    }
        return {"start": None, "end": None}
