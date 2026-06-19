"""
Business Aggregator — Gold layer aggregation engine.

Transforms Silver layer data into business-ready aggregations:
daily, weekly, monthly rollups, and dimensional summaries.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class BusinessAggregator:
    """
    Aggregation engine for Gold layer data.

    Produces business-ready aggregated datasets from Silver layer data.
    Supports configurable time windows and grouping dimensions.

    Usage:
        aggregator = BusinessAggregator()
        daily = aggregator.aggregate_daily(df_silver, date_col="order_date")
        weekly = aggregator.aggregate_weekly(df_silver, date_col="order_date")
    """

    def aggregate_daily(
        self,
        df: pd.DataFrame,
        date_col: str = "order_date",
        amount_col: str = "total_amount",
        group_cols: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Create daily aggregations from Silver layer data.

        Produces metrics per day:
        - total_revenue, transaction_count, unique_customers
        - avg_order_value, min/max order values
        - top category and country breakdowns
        """
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["_agg_date"] = df[date_col].dt.date

        # Ensure numeric amount
        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")

        # Base aggregations
        agg_funcs: dict[str, Any] = {
            amount_col: ["sum", "mean", "min", "max", "count"],
        }

        if "customer_id" in df.columns:
            agg_funcs["customer_id"] = "nunique"
        if "product_sku" in df.columns:
            agg_funcs["product_sku"] = "nunique"

        daily = df.groupby("_agg_date").agg(agg_funcs)

        # Flatten multi-level columns
        daily.columns = [
            f"{col}_{func}" if func != "nunique" else f"unique_{col}s"
            for col, func in daily.columns
        ]

        daily = daily.rename(columns={
            f"{amount_col}_sum": "total_revenue",
            f"{amount_col}_mean": "avg_order_value",
            f"{amount_col}_min": "min_order_value",
            f"{amount_col}_max": "max_order_value",
            f"{amount_col}_count": "transaction_count",
        })

        daily = daily.reset_index().rename(columns={"_agg_date": "date"})

        # Add top category per day
        if "category" in df.columns:
            top_cats = (
                df.groupby("_agg_date")["category"]
                .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
                .reset_index()
                .rename(columns={"_agg_date": "date", "category": "top_category"})
            )
            daily = daily.merge(top_cats, on="date", how="left")

        # Add top country per day
        if "country" in df.columns:
            top_countries = (
                df.groupby("_agg_date")["country"]
                .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
                .reset_index()
                .rename(columns={"_agg_date": "date", "country": "top_country"})
            )
            daily = daily.merge(top_countries, on="date", how="left")

        # Add metadata
        daily["_aggregation_type"] = "daily"
        daily["_aggregated_at"] = datetime.now(timezone.utc).isoformat()
        daily["_layer"] = "gold"

        logger.info(f"Daily aggregation: {len(daily)} rows produced")
        return daily

    def aggregate_weekly(
        self,
        df: pd.DataFrame,
        date_col: str = "order_date",
        amount_col: str = "total_amount",
    ) -> pd.DataFrame:
        """Create weekly aggregations."""
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["_week"] = df[date_col].dt.isocalendar().week
        df["_year"] = df[date_col].dt.year
        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")

        weekly = df.groupby(["_year", "_week"]).agg(
            total_revenue=(amount_col, "sum"),
            transaction_count=(amount_col, "count"),
            avg_order_value=(amount_col, "mean"),
        ).reset_index()

        weekly = weekly.rename(columns={"_year": "year", "_week": "week"})
        weekly["_aggregation_type"] = "weekly"
        weekly["_aggregated_at"] = datetime.now(timezone.utc).isoformat()
        weekly["_layer"] = "gold"

        logger.info(f"Weekly aggregation: {len(weekly)} rows produced")
        return weekly

    def aggregate_monthly(
        self,
        df: pd.DataFrame,
        date_col: str = "order_date",
        amount_col: str = "total_amount",
    ) -> pd.DataFrame:
        """Create monthly aggregations."""
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["_month"] = df[date_col].dt.month
        df["_year"] = df[date_col].dt.year
        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")

        monthly = df.groupby(["_year", "_month"]).agg(
            total_revenue=(amount_col, "sum"),
            transaction_count=(amount_col, "count"),
            avg_order_value=(amount_col, "mean"),
        ).reset_index()

        monthly = monthly.rename(columns={"_year": "year", "_month": "month"})
        monthly["_aggregation_type"] = "monthly"
        monthly["_aggregated_at"] = datetime.now(timezone.utc).isoformat()
        monthly["_layer"] = "gold"

        logger.info(f"Monthly aggregation: {len(monthly)} rows produced")
        return monthly

    def aggregate_by_dimension(
        self,
        df: pd.DataFrame,
        dimension_col: str,
        amount_col: str = "total_amount",
    ) -> pd.DataFrame:
        """Create aggregations by a specific dimension (category, region, etc.)."""
        if df.empty or dimension_col not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")

        dim_agg = df.groupby(dimension_col).agg(
            total_revenue=(amount_col, "sum"),
            transaction_count=(amount_col, "count"),
            avg_order_value=(amount_col, "mean"),
        ).reset_index()

        dim_agg["revenue_pct"] = (
            dim_agg["total_revenue"] / dim_agg["total_revenue"].sum() * 100
        ).round(2)

        dim_agg = dim_agg.sort_values("total_revenue", ascending=False)
        dim_agg["_aggregation_type"] = f"by_{dimension_col}"
        dim_agg["_aggregated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Dimension aggregation ({dimension_col}): {len(dim_agg)} groups")
        return dim_agg
