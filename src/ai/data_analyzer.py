"""
Data Analyzer — AI-powered dataset analysis using Claude.

Automatically profiles datasets, detects anomalies, suggests
transformations, and validates data quality using Claude Sonnet.
"""

import json
import logging
from typing import Any

import pandas as pd

from src.ai.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class DataAnalyzer:
    """
    AI-powered data analysis engine using Claude.

    Provides automated dataset profiling, anomaly detection,
    and transformation suggestions. Uses Claude Sonnet for
    fast, cost-effective analysis.

    Usage:
        client = ClaudeClient()
        analyzer = DataAnalyzer(client)

        # Profile a dataset
        profile = analyzer.profile_dataset(df, source_name="crm_contacts")

        # Detect anomalies
        anomalies = analyzer.detect_anomalies(df)

        # Suggest transformations
        suggestions = analyzer.suggest_transformations(df, target_layer="silver")
    """

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def profile_dataset(
        self,
        df: pd.DataFrame,
        source_name: str = "unknown",
        sample_size: int = 10,
    ) -> dict[str, Any]:
        """
        Profile a dataset using Claude AI.

        Generates a comprehensive profile including:
        - Column descriptions and inferred business meaning
        - Data quality assessment
        - Statistical summaries
        - Suggested schema for Silver layer

        Args:
            df: DataFrame to profile.
            source_name: Name of the data source.
            sample_size: Number of sample rows to send to Claude.

        Returns:
            Profiling results with AI-generated descriptions.
        """
        # Generate statistical profile locally
        stats_profile = self._generate_stats_profile(df)

        # Get sample data
        sample = df.head(sample_size).to_dict("records")

        # Ask Claude to analyze
        prompt = (
            f"Profile this dataset from '{source_name}'.\n\n"
            f"Statistical Summary:\n{json.dumps(stats_profile, indent=2, default=str)}\n\n"
            f"Sample Data (first {sample_size} rows):\n"
            f"{json.dumps(sample, indent=2, default=str)}\n\n"
            "Provide:\n"
            "1. Business description of each column\n"
            "2. Data quality issues identified\n"
            "3. Suggested data types for each column\n"
            "4. Recommended transformations for Silver layer\n"
            "5. Potential business use cases for this data"
        )

        response = self.claude.analyze(
            prompt,
            model="default",
            system_prompt="data_engineering",
        )

        return {
            "source_name": source_name,
            "row_count": len(df),
            "column_count": len(df.columns),
            "stats_profile": stats_profile,
            "ai_analysis": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }

    def detect_anomalies(
        self,
        df: pd.DataFrame,
        focus_columns: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Detect anomalies in the dataset using Claude.

        Identifies:
        - Statistical outliers
        - Unexpected patterns
        - Data consistency issues
        - Business rule violations
        """
        columns = focus_columns or [
            c for c in df.columns if not c.startswith("_")
        ]

        # Generate anomaly context
        context: dict[str, Any] = {}
        for col in columns[:10]:  # Limit to 10 columns
            if col in df.columns:
                series = df[col]
                col_info: dict[str, Any] = {
                    "dtype": str(series.dtype),
                    "null_count": int(series.isna().sum()),
                    "unique_count": int(series.nunique()),
                }

                if pd.api.types.is_numeric_dtype(series):
                    clean = series.dropna()
                    if len(clean) > 0:
                        col_info.update({
                            "mean": round(float(clean.mean()), 2),
                            "std": round(float(clean.std()), 2),
                            "min": float(clean.min()),
                            "max": float(clean.max()),
                            "q25": float(clean.quantile(0.25)),
                            "q75": float(clean.quantile(0.75)),
                        })

                context[col] = col_info

        prompt = (
            "Analyze this dataset for anomalies and data quality issues.\n\n"
            f"Column Statistics:\n{json.dumps(context, indent=2)}\n\n"
            f"Sample Data:\n{df.head(5).to_string()}\n\n"
            "Identify:\n"
            "1. Statistical outliers\n"
            "2. Unexpected null patterns\n"
            "3. Data consistency issues\n"
            "4. Possible data quality problems\n"
            "5. Recommended actions for each issue"
        )

        response = self.claude.analyze(
            prompt,
            model="default",
            system_prompt="data_engineering",
        )

        return {
            "column_stats": context,
            "ai_anomaly_analysis": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }

    def suggest_transformations(
        self,
        df: pd.DataFrame,
        target_layer: str = "silver",
        business_context: str = "",
    ) -> dict[str, Any]:
        """
        Get AI-powered transformation suggestions.

        Claude analyzes the data and suggests specific transformations
        needed to move data from Bronze to Silver or Silver to Gold.
        """
        schema_info = {
            col: {
                "dtype": str(df[col].dtype),
                "sample_values": df[col].dropna().head(3).tolist(),
                "null_rate": round(float(df[col].isna().mean()), 3),
            }
            for col in df.columns
            if not col.startswith("_")
        }

        prompt = (
            f"Suggest specific data transformations to move this data "
            f"to the {target_layer} layer.\n\n"
            f"Current Schema:\n{json.dumps(schema_info, indent=2, default=str)}\n\n"
            f"Business Context: {business_context or 'General data lake pipeline'}\n\n"
            "For each column, suggest:\n"
            "1. Type casting (if needed)\n"
            "2. Cleaning transformations\n"
            "3. Normalization rules\n"
            "4. Derived columns to create\n"
            "5. Columns to drop or rename\n"
            "Provide your suggestions as actionable steps."
        )

        response = self.claude.analyze(
            prompt,
            model="default",
            system_prompt="data_engineering",
        )

        return {
            "target_layer": target_layer,
            "current_schema": schema_info,
            "ai_suggestions": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }

    def _generate_stats_profile(self, df: pd.DataFrame) -> dict[str, Any]:
        """Generate local statistical profile (no API call needed)."""
        profile: dict[str, Any] = {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": {},
            "memory_mb": round(
                float(df.memory_usage(deep=True).sum() / 1024 / 1024), 2
            ),
        }

        for col in df.columns:
            if col.startswith("_"):
                continue

            series = df[col]
            col_profile: dict[str, Any] = {
                "dtype": str(series.dtype),
                "null_count": int(series.isna().sum()),
                "null_pct": round(float(series.isna().mean() * 100), 2),
                "unique_count": int(series.nunique()),
            }

            if pd.api.types.is_numeric_dtype(series):
                clean = series.dropna()
                if len(clean) > 0:
                    col_profile["stats"] = {
                        "mean": round(float(clean.mean()), 2),
                        "std": round(float(clean.std()), 2),
                        "min": float(clean.min()),
                        "max": float(clean.max()),
                        "median": float(clean.median()),
                    }
            elif series.dtype == "object":
                col_profile["top_values"] = (
                    series.value_counts().head(5).to_dict()
                )

            profile["columns"][col] = col_profile

        return profile
