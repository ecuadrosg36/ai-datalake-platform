"""
KPI Calculator — Business KPI computation engine.

Computes key performance indicators from Gold layer data:
revenue metrics, customer metrics, operational metrics,
and growth calculations.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class KPICalculator:
    """
    KPI computation engine for business metrics.

    Calculates standardized KPIs that can be consumed by dashboards,
    reports, and Claude AI for insight generation.

    Usage:
        calc = KPICalculator()
        revenue_kpis = calc.calculate_revenue_kpis(df_gold)
        customer_kpis = calc.calculate_customer_kpis(df_gold)
        all_kpis = calc.calculate_all(df_gold)
    """

    def calculate_all(self, df: pd.DataFrame) -> dict[str, Any]:
        """Calculate all available KPIs."""
        return {
            "revenue": self.calculate_revenue_kpis(df),
            "customer": self.calculate_customer_kpis(df),
            "operational": self.calculate_operational_kpis(df),
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(df),
        }

    def calculate_revenue_kpis(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Calculate revenue-related KPIs.

        KPIs:
        - Total Revenue
        - Average Order Value (AOV)
        - Revenue Growth Rate (period over period)
        - Revenue by Category
        - Revenue by Region
        """
        amount_col = self._find_amount_column(df)
        if amount_col is None:
            return {"error": "No amount column found"}

        amounts = pd.to_numeric(df[amount_col], errors="coerce").dropna()

        kpis: dict[str, Any] = {
            "total_revenue": round(float(amounts.sum()), 2),
            "avg_order_value": round(float(amounts.mean()), 2),
            "median_order_value": round(float(amounts.median()), 2),
            "max_order_value": round(float(amounts.max()), 2),
            "min_order_value": round(float(amounts.min()), 2),
            "std_dev": round(float(amounts.std()), 2) if len(amounts) > 1 else 0,
            "total_transactions": int(len(amounts)),
        }

        # Revenue by category
        if "category" in df.columns:
            cat_revenue = (
                df.groupby("category")[amount_col]
                .sum()
                .sort_values(ascending=False)
                .head(10)
            )
            kpis["revenue_by_category"] = {
                str(k): round(float(v), 2) for k, v in cat_revenue.items()
            }

        # Revenue by country/region
        if "country" in df.columns:
            country_revenue = (
                df.groupby("country")[amount_col]
                .sum()
                .sort_values(ascending=False)
            )
            kpis["revenue_by_country"] = {
                str(k): round(float(v), 2) for k, v in country_revenue.items()
            }

        return kpis

    def calculate_customer_kpis(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Calculate customer-related KPIs.

        KPIs:
        - Total Unique Customers
        - Average Revenue per Customer
        - Customer Concentration (top 10% share)
        - New vs Returning ratio
        """
        customer_col = self._find_customer_column(df)
        if customer_col is None:
            return {"error": "No customer column found"}

        amount_col = self._find_amount_column(df)

        kpis: dict[str, Any] = {
            "total_unique_customers": int(df[customer_col].nunique()),
        }

        if amount_col:
            customer_revenue = df.groupby(customer_col)[amount_col].sum()
            kpis["avg_revenue_per_customer"] = round(
                float(customer_revenue.mean()), 2
            )
            kpis["max_revenue_customer"] = round(
                float(customer_revenue.max()), 2
            )

            # Customer concentration (Pareto)
            sorted_rev = customer_revenue.sort_values(ascending=False)
            top_10_pct = max(1, int(len(sorted_rev) * 0.1))
            top_10_revenue = sorted_rev.head(top_10_pct).sum()
            total_revenue = sorted_rev.sum()

            kpis["top_10pct_revenue_share"] = round(
                float(top_10_revenue / max(total_revenue, 1) * 100), 2
            )

        # Customer by country
        if "country" in df.columns:
            cust_by_country = (
                df.groupby("country")[customer_col]
                .nunique()
                .sort_values(ascending=False)
            )
            kpis["customers_by_country"] = {
                str(k): int(v) for k, v in cust_by_country.items()
            }

        return kpis

    def calculate_operational_kpis(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Calculate operational KPIs.

        KPIs:
        - Average Quantity per Order
        - Top Products by Volume
        - Order Status Distribution
        - Category Distribution
        """
        kpis: dict[str, Any] = {}

        if "quantity" in df.columns:
            qty = pd.to_numeric(df["quantity"], errors="coerce").dropna()
            kpis["avg_quantity_per_order"] = round(float(qty.mean()), 2)
            kpis["total_units_sold"] = int(qty.sum())

        if "product_sku" in df.columns:
            top_products = (
                df["product_sku"]
                .value_counts()
                .head(5)
            )
            kpis["top_products_by_volume"] = {
                str(k): int(v) for k, v in top_products.items()
            }

        if "status" in df.columns:
            status_dist = df["status"].value_counts(normalize=True) * 100
            kpis["status_distribution_pct"] = {
                str(k): round(float(v), 2) for k, v in status_dist.items()
            }

        if "category" in df.columns:
            cat_dist = df["category"].value_counts()
            kpis["category_distribution"] = {
                str(k): int(v) for k, v in cat_dist.items()
            }

        return kpis

    def calculate_growth(
        self,
        current_period: pd.DataFrame,
        previous_period: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Calculate growth metrics between two periods.

        Returns percentage change in key metrics.
        """
        amount_col = self._find_amount_column(current_period)
        if amount_col is None:
            return {"error": "No amount column found"}

        current_rev = pd.to_numeric(
            current_period[amount_col], errors="coerce"
        ).sum()
        previous_rev = pd.to_numeric(
            previous_period[amount_col], errors="coerce"
        ).sum()

        revenue_growth = (
            ((current_rev - previous_rev) / max(previous_rev, 1)) * 100
            if previous_rev > 0
            else 0
        )

        return {
            "current_period_revenue": round(float(current_rev), 2),
            "previous_period_revenue": round(float(previous_rev), 2),
            "revenue_growth_pct": round(float(revenue_growth), 2),
            "current_transactions": len(current_period),
            "previous_transactions": len(previous_period),
            "transaction_growth_pct": round(
                ((len(current_period) - len(previous_period))
                 / max(len(previous_period), 1) * 100),
                2,
            ),
        }

    @staticmethod
    def _find_amount_column(df: pd.DataFrame) -> str | None:
        """Find the most likely amount/revenue column."""
        candidates = [
            "total_amount", "total_revenue", "amount", "revenue",
            "deal_value_usd", "value", "price", "total",
        ]
        for col in candidates:
            if col in df.columns:
                return col
        return None

    @staticmethod
    def _find_customer_column(df: pd.DataFrame) -> str | None:
        """Find the most likely customer identifier column."""
        candidates = [
            "customer_id", "contact_id", "client_id", "user_id",
            "account_id", "buyer_id",
        ]
        for col in candidates:
            if col in df.columns:
                return col
        return None
