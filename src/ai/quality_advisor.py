"""
Quality Advisor — AI-driven data quality recommendations.

Analyzes data quality reports and provides root cause analysis,
remediation recommendations, and prevention strategies using Claude.
"""

import json
import logging
from typing import Any

from src.ai.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class QualityAdvisor:
    """
    AI-driven data quality advisor using Claude.

    Analyzes quality reports from the DataQualityChecker and provides:
    - Root cause analysis for quality issues
    - Remediation recommendations
    - Prevention strategies
    - Priority ranking of issues

    Usage:
        client = ClaudeClient()
        advisor = QualityAdvisor(client)

        quality_report = checker.check(df, "erp_transactions", "silver")
        advice = advisor.analyze_report(quality_report.to_dict())
    """

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def analyze_report(
        self,
        quality_report: dict[str, Any],
        business_context: str = "",
    ) -> dict[str, Any]:
        """
        Analyze a quality report and provide recommendations.

        Args:
            quality_report: Quality report dict from DataQualityChecker.
            business_context: Additional business context.

        Returns:
            AI-generated quality recommendations.
        """
        prompt = (
            "Analyze this data quality report and provide actionable recommendations.\n\n"
            f"Quality Report:\n{json.dumps(quality_report, indent=2, default=str)}\n\n"
        )

        if business_context:
            prompt += f"Business Context: {business_context}\n\n"

        prompt += (
            "Provide:\n"
            "1. **Root Cause Analysis**: Why are these quality issues occurring?\n"
            "2. **Priority Ranking**: Rank issues by business impact (High/Medium/Low)\n"
            "3. **Remediation Steps**: Specific, actionable steps to fix each issue\n"
            "4. **Prevention Strategy**: How to prevent these issues in the future\n"
            "5. **Monitoring Recommendations**: What to monitor going forward\n"
            "6. **Estimated Effort**: Time estimate for remediation (hours/days)"
        )

        response = self.claude.analyze(
            prompt,
            model="default",
            system_prompt="quality_advisor",
        )

        return {
            "dataset": quality_report.get("dataset_name", "unknown"),
            "overall_score": quality_report.get("overall_score", 0),
            "issues_found": quality_report.get("rules_failed", 0),
            "ai_recommendations": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }

    def suggest_quality_rules(
        self,
        schema: dict[str, Any],
        sample_data: list[dict[str, Any]],
        source_type: str = "generic",
    ) -> dict[str, Any]:
        """
        Suggest quality rules for a new dataset.

        Given a schema and sample data, suggests appropriate
        quality rules to implement.
        """
        prompt = (
            "Based on this dataset schema and sample data, suggest "
            "comprehensive data quality rules to implement.\n\n"
            f"Source Type: {source_type}\n\n"
            f"Schema:\n{json.dumps(schema, indent=2, default=str)}\n\n"
            f"Sample Data:\n{json.dumps(sample_data[:5], indent=2, default=str)}\n\n"
            "For each rule, provide:\n"
            "1. Rule name and dimension (completeness/accuracy/consistency/timeliness/uniqueness)\n"
            "2. Target column(s)\n"
            "3. Threshold value\n"
            "4. Severity (error/warning/info)\n"
            "5. Business justification\n"
            "\nAlso suggest any composite rules that check relationships between columns."
        )

        response = self.claude.analyze(
            prompt,
            model="default",
            system_prompt="quality_advisor",
        )

        return {
            "source_type": source_type,
            "suggested_rules": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }

    def generate_quality_dashboard_config(
        self,
        datasets: list[str],
        quality_reports: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Generate configuration for a data quality monitoring dashboard.

        Suggests metrics, thresholds, and alert rules based on
        historical quality data.
        """
        prompt = (
            "Design a data quality monitoring dashboard configuration "
            "based on these quality reports.\n\n"
            f"Datasets: {datasets}\n\n"
            f"Recent Quality Reports:\n"
            f"{json.dumps(quality_reports[:3], indent=2, default=str)}\n\n"
            "Provide:\n"
            "1. Key metrics to display\n"
            "2. Alert thresholds for each metric\n"
            "3. Recommended refresh frequency\n"
            "4. Visualization suggestions (chart types)\n"
            "5. SLA definitions for data quality"
        )

        response = self.claude.analyze(
            prompt,
            model="default",
            system_prompt="quality_advisor",
        )

        return {
            "dashboard_config": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }
