"""
Data Quality Checker — Comprehensive data quality validation framework.

Evaluates data across five quality dimensions:
1. Completeness — Are all required values present?
2. Accuracy — Are values within expected ranges/formats?
3. Consistency — Are values consistent across related fields?
4. Timeliness — Is data fresh enough?
5. Uniqueness — Are there duplicates?

Generates quality reports compatible with Claude AI analysis.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class QualityRule:
    """Defines a single data quality rule."""
    name: str
    dimension: str          # completeness | accuracy | consistency | timeliness | uniqueness
    column: str | None      # Specific column, or None for row-level rules
    description: str
    threshold: float = 0.95  # Minimum acceptable score (0.0 — 1.0)
    severity: str = "error"  # error | warning | info


@dataclass
class QualityResult:
    """Result of a quality check."""
    rule: QualityRule
    score: float                    # 0.0 — 1.0
    passed: bool
    total_records: int
    failed_records: int
    sample_failures: list[dict[str, Any]] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule.name,
            "dimension": self.rule.dimension,
            "column": self.rule.column,
            "score": round(self.score, 4),
            "passed": self.passed,
            "threshold": self.rule.threshold,
            "severity": self.rule.severity,
            "total_records": self.total_records,
            "failed_records": self.failed_records,
            "details": self.details,
            "sample_failures": self.sample_failures[:5],
        }


@dataclass
class QualityReport:
    """Aggregated quality report for a dataset."""
    dataset_name: str
    layer: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_records: int = 0
    results: list[QualityResult] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Calculate weighted average quality score."""
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    @property
    def all_passed(self) -> bool:
        """Check if all quality rules passed."""
        return all(r.passed for r in self.results)

    @property
    def dimension_scores(self) -> dict[str, float]:
        """Calculate average score per quality dimension."""
        dims: dict[str, list[float]] = {}
        for r in self.results:
            dims.setdefault(r.rule.dimension, []).append(r.score)
        return {dim: sum(scores) / len(scores) for dim, scores in dims.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "layer": self.layer,
            "timestamp": self.timestamp,
            "total_records": self.total_records,
            "overall_score": round(self.overall_score, 4),
            "all_passed": self.all_passed,
            "dimension_scores": {
                k: round(v, 4) for k, v in self.dimension_scores.items()
            },
            "rules_checked": len(self.results),
            "rules_passed": sum(1 for r in self.results if r.passed),
            "rules_failed": sum(1 for r in self.results if not r.passed),
            "results": [r.to_dict() for r in self.results],
        }


class DataQualityChecker:
    """
    Comprehensive data quality validation engine.

    Runs configurable quality rules against DataFrames and generates
    detailed reports. Reports are designed to be consumed by Claude AI
    for automated root cause analysis and remediation recommendations.

    Usage:
        checker = DataQualityChecker()

        # Add rules
        checker.add_completeness_rule("email", threshold=0.98)
        checker.add_accuracy_rule("quantity", min_value=0, max_value=10000)
        checker.add_uniqueness_rule(["transaction_id"])

        # Run checks
        report = checker.check(df, dataset_name="erp_transactions", layer="silver")
        print(f"Overall score: {report.overall_score:.2%}")
    """

    def __init__(self):
        self.rules: list[QualityRule] = []

    def add_completeness_rule(
        self,
        column: str,
        threshold: float = 0.95,
        severity: str = "error",
    ) -> "DataQualityChecker":
        """Add a completeness check — ensures values are not null/empty."""
        self.rules.append(QualityRule(
            name=f"completeness_{column}",
            dimension="completeness",
            column=column,
            description=f"Column '{column}' must be at least {threshold:.0%} complete",
            threshold=threshold,
            severity=severity,
        ))
        return self

    def add_accuracy_rule(
        self,
        column: str,
        min_value: float | None = None,
        max_value: float | None = None,
        pattern: str | None = None,
        allowed_values: list[Any] | None = None,
        threshold: float = 0.98,
        severity: str = "error",
    ) -> "DataQualityChecker":
        """Add an accuracy check — ensures values are within expected ranges."""
        rule = QualityRule(
            name=f"accuracy_{column}",
            dimension="accuracy",
            column=column,
            description=f"Column '{column}' values must be valid",
            threshold=threshold,
            severity=severity,
        )
        # Store validation params as custom attributes
        rule._params = {  # type: ignore[attr-defined]
            "min_value": min_value,
            "max_value": max_value,
            "pattern": pattern,
            "allowed_values": allowed_values,
        }
        self.rules.append(rule)
        return self

    def add_uniqueness_rule(
        self,
        columns: list[str],
        threshold: float = 1.0,
        severity: str = "error",
    ) -> "DataQualityChecker":
        """Add a uniqueness check — ensures no duplicate records by key columns."""
        col_str = "+".join(columns)
        rule = QualityRule(
            name=f"uniqueness_{col_str}",
            dimension="uniqueness",
            column=col_str,
            description=f"Columns [{col_str}] must be unique",
            threshold=threshold,
            severity=severity,
        )
        rule._key_columns = columns  # type: ignore[attr-defined]
        self.rules.append(rule)
        return self

    def add_timeliness_rule(
        self,
        column: str,
        max_age_hours: int = 24,
        threshold: float = 0.95,
        severity: str = "warning",
    ) -> "DataQualityChecker":
        """Add a timeliness check — ensures data is fresh."""
        rule = QualityRule(
            name=f"timeliness_{column}",
            dimension="timeliness",
            column=column,
            description=f"Column '{column}' must be within {max_age_hours}h",
            threshold=threshold,
            severity=severity,
        )
        rule._max_age_hours = max_age_hours  # type: ignore[attr-defined]
        self.rules.append(rule)
        return self

    def add_consistency_rule(
        self,
        column_a: str,
        column_b: str,
        relationship: str = "a_lte_b",  # a_lte_b | a_equals_b | a_gte_b
        threshold: float = 0.98,
        severity: str = "warning",
    ) -> "DataQualityChecker":
        """Add a consistency check — ensures related fields are consistent."""
        rule = QualityRule(
            name=f"consistency_{column_a}_vs_{column_b}",
            dimension="consistency",
            column=f"{column_a},{column_b}",
            description=f"'{column_a}' must be {relationship} '{column_b}'",
            threshold=threshold,
            severity=severity,
        )
        rule._col_a = column_a  # type: ignore[attr-defined]
        rule._col_b = column_b  # type: ignore[attr-defined]
        rule._relationship = relationship  # type: ignore[attr-defined]
        self.rules.append(rule)
        return self

    def check(
        self, df: pd.DataFrame, dataset_name: str, layer: str = "silver"
    ) -> QualityReport:
        """
        Run all quality checks against a DataFrame.

        Args:
            df: The DataFrame to validate.
            dataset_name: Name of the dataset (for reporting).
            layer: Data lake layer (bronze/silver/gold).

        Returns:
            QualityReport with detailed results for each rule.
        """
        report = QualityReport(
            dataset_name=dataset_name,
            layer=layer,
            total_records=len(df),
        )

        for rule in self.rules:
            try:
                if rule.dimension == "completeness":
                    result = self._check_completeness(df, rule)
                elif rule.dimension == "accuracy":
                    result = self._check_accuracy(df, rule)
                elif rule.dimension == "uniqueness":
                    result = self._check_uniqueness(df, rule)
                elif rule.dimension == "timeliness":
                    result = self._check_timeliness(df, rule)
                elif rule.dimension == "consistency":
                    result = self._check_consistency(df, rule)
                else:
                    continue

                report.results.append(result)

            except Exception as e:
                logger.error(f"Quality check '{rule.name}' failed: {e}")
                report.results.append(QualityResult(
                    rule=rule,
                    score=0.0,
                    passed=False,
                    total_records=len(df),
                    failed_records=len(df),
                    details=f"Check failed with error: {str(e)}",
                ))

        logger.info(
            f"Quality check complete for '{dataset_name}': "
            f"score={report.overall_score:.2%}, "
            f"passed={report.all_passed}"
        )

        return report

    def _check_completeness(self, df: pd.DataFrame, rule: QualityRule) -> QualityResult:
        """Check completeness of a column."""
        col = rule.column
        if col not in df.columns:
            return QualityResult(
                rule=rule, score=0.0, passed=False,
                total_records=len(df), failed_records=len(df),
                details=f"Column '{col}' not found in DataFrame",
            )

        null_mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
        null_count = null_mask.sum()
        score = 1.0 - (null_count / max(len(df), 1))

        return QualityResult(
            rule=rule,
            score=score,
            passed=score >= rule.threshold,
            total_records=len(df),
            failed_records=int(null_count),
            details=f"{null_count} null/empty values found",
        )

    def _check_accuracy(self, df: pd.DataFrame, rule: QualityRule) -> QualityResult:
        """Check accuracy of values in a column."""
        col = rule.column
        params = getattr(rule, "_params", {})

        if col not in df.columns:
            return QualityResult(
                rule=rule, score=0.0, passed=False,
                total_records=len(df), failed_records=len(df),
                details=f"Column '{col}' not found",
            )

        valid_mask = pd.Series([True] * len(df), index=df.index)
        non_null = df[col].notna()

        # Range check
        if params.get("min_value") is not None:
            numeric_vals = pd.to_numeric(df[col], errors="coerce")
            valid_mask &= non_null & (numeric_vals >= params["min_value"]) | ~non_null
        if params.get("max_value") is not None:
            numeric_vals = pd.to_numeric(df[col], errors="coerce")
            valid_mask &= non_null & (numeric_vals <= params["max_value"]) | ~non_null

        # Allowed values check
        if params.get("allowed_values"):
            valid_mask &= non_null & df[col].isin(params["allowed_values"]) | ~non_null

        # Pattern check
        if params.get("pattern"):
            valid_mask &= non_null & df[col].astype(str).str.match(
                params["pattern"], na=False
            ) | ~non_null

        failed = (~valid_mask).sum()
        score = 1.0 - (failed / max(len(df), 1))

        return QualityResult(
            rule=rule,
            score=score,
            passed=score >= rule.threshold,
            total_records=len(df),
            failed_records=int(failed),
            details=f"{failed} values failed accuracy check",
        )

    def _check_uniqueness(self, df: pd.DataFrame, rule: QualityRule) -> QualityResult:
        """Check uniqueness across key columns."""
        key_cols = getattr(rule, "_key_columns", [])
        existing_cols = [c for c in key_cols if c in df.columns]

        if not existing_cols:
            return QualityResult(
                rule=rule, score=0.0, passed=False,
                total_records=len(df), failed_records=len(df),
                details=f"Key columns not found: {key_cols}",
            )

        duplicates = df.duplicated(subset=existing_cols, keep="first")
        dup_count = duplicates.sum()
        score = 1.0 - (dup_count / max(len(df), 1))

        sample = []
        if dup_count > 0:
            dup_rows = df[duplicates].head(5)
            for _, row in dup_rows.iterrows():
                sample.append({col: row[col] for col in existing_cols})

        return QualityResult(
            rule=rule,
            score=score,
            passed=score >= rule.threshold,
            total_records=len(df),
            failed_records=int(dup_count),
            sample_failures=sample,
            details=f"{dup_count} duplicate records found",
        )

    def _check_timeliness(self, df: pd.DataFrame, rule: QualityRule) -> QualityResult:
        """Check if data is fresh (within max_age_hours)."""
        col = rule.column
        max_age = getattr(rule, "_max_age_hours", 24)

        if col not in df.columns:
            return QualityResult(
                rule=rule, score=0.0, passed=False,
                total_records=len(df), failed_records=len(df),
                details=f"Column '{col}' not found",
            )

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age)
        dates = pd.to_datetime(df[col], errors="coerce", utc=True)
        stale = dates.notna() & (dates < cutoff)
        stale_count = stale.sum()
        score = 1.0 - (stale_count / max(len(df), 1))

        return QualityResult(
            rule=rule,
            score=score,
            passed=score >= rule.threshold,
            total_records=len(df),
            failed_records=int(stale_count),
            details=f"{stale_count} records older than {max_age}h",
        )

    def _check_consistency(self, df: pd.DataFrame, rule: QualityRule) -> QualityResult:
        """Check consistency between two related columns."""
        col_a = getattr(rule, "_col_a", "")
        col_b = getattr(rule, "_col_b", "")
        relationship = getattr(rule, "_relationship", "a_lte_b")

        if col_a not in df.columns or col_b not in df.columns:
            return QualityResult(
                rule=rule, score=0.0, passed=False,
                total_records=len(df), failed_records=len(df),
                details=f"Columns '{col_a}' or '{col_b}' not found",
            )

        a = pd.to_numeric(df[col_a], errors="coerce")
        b = pd.to_numeric(df[col_b], errors="coerce")
        both_valid = a.notna() & b.notna()

        if relationship == "a_lte_b":
            inconsistent = both_valid & (a > b)
        elif relationship == "a_gte_b":
            inconsistent = both_valid & (a < b)
        elif relationship == "a_equals_b":
            inconsistent = both_valid & (a != b)
        else:
            inconsistent = pd.Series([False] * len(df))

        failed = inconsistent.sum()
        score = 1.0 - (failed / max(both_valid.sum(), 1))

        return QualityResult(
            rule=rule,
            score=score,
            passed=score >= rule.threshold,
            total_records=len(df),
            failed_records=int(failed),
            details=f"{failed} records violate {col_a} {relationship} {col_b}",
        )
