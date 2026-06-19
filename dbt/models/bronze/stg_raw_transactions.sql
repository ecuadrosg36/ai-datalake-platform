-- =============================================================================
-- Bronze Layer: Staging Raw ERP Transactions
-- =============================================================================
-- Minimal transformation of raw data from S3.
-- Source: s3://ai-datalake-platform/raw/erp/
-- Format: CSV (Glue Crawler → Athena table)
-- =============================================================================

{{
    config(
        materialized='view',
        tags=['bronze', 'staging', 'erp']
    )
}}

WITH raw_transactions AS (
    SELECT
        transaction_id,
        order_date,
        customer_id,
        product_sku,
        product_name,
        category,
        CAST(quantity AS INTEGER) AS quantity,
        CAST(unit_price AS DOUBLE) AS unit_price,
        CAST(total_amount AS DOUBLE) AS total_amount,
        currency,
        payment_method,
        status,
        warehouse_id,
        ship_date,
        country,
        region,
        -- Ingestion metadata
        '$__FILE_NAME' AS _source_file,
        CURRENT_TIMESTAMP AS _loaded_at
    FROM {{ source('raw', 'erp_transactions') }}
)

SELECT
    *,
    -- Add row hash for change detection (SCD Type 2)
    MD5(
        COALESCE(transaction_id, '') ||
        COALESCE(CAST(total_amount AS VARCHAR), '') ||
        COALESCE(status, '') ||
        COALESCE(ship_date, '')
    ) AS _row_hash
FROM raw_transactions
WHERE transaction_id IS NOT NULL
  AND transaction_id != ''
