"""
AWS Glue ETL Job — Silver Layer Transformation

PySpark script executed by AWS Glue to transform Bronze layer data
into the Silver layer. Applies cleaning, validation, deduplication,
and standardization.

Deployed to: s3://ai-datalake-platform/glue-scripts/etl_silver_transform.py
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window


# Initialize Glue context
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'source_database',
    'source_table',
    'target_bucket',
    'target_prefix',
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

logger = glueContext.get_logger()
logger.info(f"Starting Silver transform for {args['source_table']}")


# =============================================================================
# Step 1: Read Bronze Data from Glue Catalog
# =============================================================================
dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
    database=args['source_database'],
    table_name=args['source_table'],
    transformation_ctx="read_bronze",
)

df = dynamic_frame.toDF()
initial_count = df.count()
logger.info(f"Read {initial_count} records from Bronze layer")


# =============================================================================
# Step 2: Data Cleaning & Standardization
# =============================================================================

# Trim all string columns
for col_name in df.columns:
    if df.schema[col_name].dataType.simpleString() == 'string':
        df = df.withColumn(col_name, F.trim(F.col(col_name)))

# Replace empty strings with null
for col_name in df.columns:
    if df.schema[col_name].dataType.simpleString() == 'string':
        df = df.withColumn(
            col_name,
            F.when(F.col(col_name) == '', None).otherwise(F.col(col_name))
        )

# Standardize dates
if 'order_date' in df.columns:
    df = df.withColumn('order_date', F.to_date(F.col('order_date')))

if 'ship_date' in df.columns:
    df = df.withColumn('ship_date', F.to_date(F.col('ship_date')))

# Cast numeric columns
numeric_cols = {
    'quantity': 'integer',
    'unit_price': 'double',
    'total_amount': 'double',
}

for col_name, col_type in numeric_cols.items():
    if col_name in df.columns:
        df = df.withColumn(col_name, F.col(col_name).cast(col_type))


# =============================================================================
# Step 3: Data Validation
# =============================================================================

# Filter out invalid records
df_valid = df.filter(
    # Must have transaction_id
    (F.col('transaction_id').isNotNull()) &
    (F.col('transaction_id') != '') &
    # Must have positive quantity
    (F.col('quantity') > 0) &
    # Must have non-negative amount
    (F.col('total_amount') >= 0) &
    # Remove error status
    (F.col('status') != 'Error') &
    # Remove invalid SKUs
    (~F.col('product_sku').startswith('INVALID'))
)

rejected_count = initial_count - df_valid.count()
logger.info(f"Rejected {rejected_count} invalid records")


# =============================================================================
# Step 4: Deduplication
# =============================================================================

# Remove duplicates by transaction_id (keep first by order_date)
window = Window.partitionBy('transaction_id').orderBy(F.col('order_date').asc())
df_deduped = df_valid.withColumn('_rank', F.row_number().over(window))
df_deduped = df_deduped.filter(F.col('_rank') == 1).drop('_rank')

dedup_removed = df_valid.count() - df_deduped.count()
logger.info(f"Removed {dedup_removed} duplicate records")


# =============================================================================
# Step 5: Enrichment & Derived Columns
# =============================================================================

df_enriched = df_deduped \
    .withColumn('_processed_at', F.current_timestamp()) \
    .withColumn('_layer', F.lit('silver')) \
    .withColumn('_pipeline_version', F.lit('1.0.0')) \
    .withColumn('_amount_validated',
        F.abs(F.col('quantity') * F.col('unit_price') - F.col('total_amount')) < 0.01
    ) \
    .withColumn('year', F.year(F.col('order_date'))) \
    .withColumn('month', F.month(F.col('order_date'))) \
    .withColumn('day', F.dayofmonth(F.col('order_date')))


# =============================================================================
# Step 6: Write to Silver Layer (Parquet, partitioned)
# =============================================================================

target_path = f"s3://{args['target_bucket']}/{args['target_prefix']}"

df_enriched.write \
    .mode("overwrite") \
    .partitionBy("year", "month", "day") \
    .parquet(target_path)

final_count = df_enriched.count()
logger.info(
    f"Silver transform complete: {final_count} records written to {target_path}"
)
logger.info(
    f"Summary: {initial_count} input → {rejected_count} rejected → "
    f"{dedup_removed} deduplicated → {final_count} output"
)


# =============================================================================
# Step 7: Commit Job
# =============================================================================
job.commit()
