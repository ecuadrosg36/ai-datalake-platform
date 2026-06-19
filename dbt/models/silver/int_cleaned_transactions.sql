-- =============================================================================
-- Silver Layer: Cleaned & Validated ERP Transactions
-- =============================================================================
-- Applies business rule validation, deduplication, and standardization.
-- Source: Bronze layer (stg_raw_transactions)
-- Output: Parquet, partitioned by year/month/day
-- =============================================================================

{{
    config(
        materialized='table',
        tags=['silver', 'intermediate', 'erp'],
        partition_by=['year', 'month'],
        file_format='parquet'
    )
}}

WITH deduplicated AS (
    -- Remove exact duplicates by transaction_id (keep first occurrence)
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id
            ORDER BY _loaded_at ASC
        ) AS _dedup_rank
    FROM {{ ref('stg_raw_transactions') }}
),

cleaned AS (
    SELECT
        -- Primary key
        transaction_id,

        -- Standardize dates
        CAST(order_date AS DATE) AS order_date,
        CAST(ship_date AS DATE) AS ship_date,

        -- Validate and clean customer_id
        CASE
            WHEN customer_id IS NOT NULL AND TRIM(customer_id) != ''
            THEN TRIM(customer_id)
            ELSE 'UNKNOWN'
        END AS customer_id,

        -- Product info (trimmed)
        TRIM(product_sku) AS product_sku,
        TRIM(product_name) AS product_name,

        -- Standardize category
        CASE
            WHEN category IS NULL OR TRIM(category) = '' THEN 'Uncategorized'
            ELSE INITCAP(TRIM(category))
        END AS category,

        -- Validate quantity (must be positive)
        CASE
            WHEN quantity > 0 THEN quantity
            ELSE NULL  -- Flag invalid quantities
        END AS quantity,

        -- Validate amounts (must be non-negative)
        CASE
            WHEN unit_price >= 0 THEN ROUND(unit_price, 2)
            ELSE NULL
        END AS unit_price,

        CASE
            WHEN total_amount >= 0 THEN ROUND(total_amount, 2)
            ELSE NULL
        END AS total_amount,

        -- Standardize currency (default USD)
        CASE
            WHEN currency IN ('USD', 'MXN', 'EUR', 'CAD') THEN currency
            WHEN currency IS NULL THEN 'USD'
            ELSE 'OTHER'
        END AS currency,

        -- Standardize status
        CASE
            WHEN status IN ('Completed', 'Pending', 'Shipped', 'Processing')
            THEN status
            ELSE 'Unknown'
        END AS status,

        TRIM(country) AS country,
        TRIM(region) AS region,

        -- Data quality flags
        CASE
            WHEN quantity <= 0 OR quantity IS NULL THEN TRUE
            ELSE FALSE
        END AS _is_invalid_quantity,

        CASE
            WHEN ABS(quantity * unit_price - total_amount) > 0.01
            THEN TRUE
            ELSE FALSE
        END AS _amount_mismatch,

        -- Metadata
        CURRENT_TIMESTAMP AS _processed_at,
        'silver' AS _layer,
        '1.0.0' AS _pipeline_version

    FROM deduplicated
    WHERE _dedup_rank = 1                    -- Keep only first occurrence
      AND product_sku NOT LIKE 'INVALID%'    -- Remove invalid SKUs
      AND status != 'Error'                  -- Remove error records
),

-- Add partition columns
final AS (
    SELECT
        *,
        YEAR(order_date) AS year,
        MONTH(order_date) AS month,
        DAY(order_date) AS day
    FROM cleaned
    WHERE quantity IS NOT NULL               -- Remove invalid quantities
      AND total_amount IS NOT NULL           -- Remove invalid amounts
)

SELECT * FROM final
