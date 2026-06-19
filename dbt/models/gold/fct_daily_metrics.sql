-- =============================================================================
-- Gold Layer: Daily Business Metrics Fact Table
-- =============================================================================
-- Aggregated daily metrics for dashboards and business analysis.
-- Source: Silver layer (int_cleaned_transactions)
-- Output: Parquet, partitioned by year/month
-- Claude AI consumes this for insight generation.
-- =============================================================================

{{
    config(
        materialized='table',
        tags=['gold', 'reporting', 'metrics'],
        partition_by=['year', 'month'],
        file_format='parquet'
    )
}}

WITH daily_aggregates AS (
    SELECT
        order_date AS date,

        -- Revenue Metrics
        SUM(total_amount) AS total_revenue_usd,
        COUNT(*) AS transaction_count,
        COUNT(DISTINCT customer_id) AS unique_customers,
        AVG(total_amount) AS avg_order_value_usd,
        MAX(total_amount) AS max_order_value_usd,
        MIN(total_amount) AS min_order_value_usd,
        STDDEV(total_amount) AS stddev_order_value,

        -- Volume Metrics
        SUM(quantity) AS total_units_sold,
        AVG(quantity) AS avg_units_per_order,

        -- Product Metrics
        COUNT(DISTINCT product_sku) AS unique_products_sold,

        -- Geographic Metrics
        COUNT(DISTINCT country) AS countries_served,

        -- Quality Metrics
        SUM(CASE WHEN _is_invalid_quantity THEN 1 ELSE 0 END) AS invalid_quantity_count,
        SUM(CASE WHEN _amount_mismatch THEN 1 ELSE 0 END) AS amount_mismatch_count,
        ROUND(
            1.0 - (
                CAST(SUM(CASE WHEN _is_invalid_quantity OR _amount_mismatch THEN 1 ELSE 0 END) AS DOUBLE)
                / NULLIF(COUNT(*), 0)
            ),
            4
        ) AS data_quality_score

    FROM {{ ref('int_cleaned_transactions') }}
    GROUP BY order_date
),

-- Add top category per day
top_categories AS (
    SELECT
        order_date,
        category,
        SUM(total_amount) AS category_revenue,
        ROW_NUMBER() OVER (
            PARTITION BY order_date
            ORDER BY SUM(total_amount) DESC
        ) AS category_rank
    FROM {{ ref('int_cleaned_transactions') }}
    GROUP BY order_date, category
),

-- Add top country per day
top_countries AS (
    SELECT
        order_date,
        country,
        COUNT(*) AS country_txn_count,
        ROW_NUMBER() OVER (
            PARTITION BY order_date
            ORDER BY COUNT(*) DESC
        ) AS country_rank
    FROM {{ ref('int_cleaned_transactions') }}
    GROUP BY order_date, country
),

-- Revenue growth (day-over-day)
with_growth AS (
    SELECT
        da.*,
        LAG(da.total_revenue_usd) OVER (ORDER BY da.date) AS prev_day_revenue,
        ROUND(
            (da.total_revenue_usd - LAG(da.total_revenue_usd) OVER (ORDER BY da.date))
            / NULLIF(LAG(da.total_revenue_usd) OVER (ORDER BY da.date), 0) * 100,
            2
        ) AS revenue_growth_pct
    FROM daily_aggregates da
),

-- Final: combine all metrics
final AS (
    SELECT
        wg.date,
        wg.total_revenue_usd,
        wg.transaction_count,
        wg.unique_customers,
        ROUND(wg.avg_order_value_usd, 2) AS avg_order_value_usd,
        wg.max_order_value_usd,
        wg.min_order_value_usd,
        wg.total_units_sold,
        ROUND(wg.avg_units_per_order, 1) AS avg_units_per_order,
        wg.unique_products_sold,
        wg.countries_served,
        tc.category AS top_category,
        tc.category_revenue AS top_category_revenue,
        tco.country AS top_country,
        wg.revenue_growth_pct,
        wg.data_quality_score,

        -- Metadata
        CURRENT_TIMESTAMP AS _aggregated_at,
        'gold' AS _layer,
        '1.0.0' AS _pipeline_version,

        -- Partition columns
        YEAR(wg.date) AS year,
        MONTH(wg.date) AS month

    FROM with_growth wg
    LEFT JOIN top_categories tc
        ON wg.date = tc.order_date AND tc.category_rank = 1
    LEFT JOIN top_countries tco
        ON wg.date = tco.order_date AND tco.country_rank = 1
)

SELECT * FROM final
ORDER BY date
