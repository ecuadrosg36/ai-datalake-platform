"""
Pipeline Orchestrator — Main entry point for the data lake pipeline.

Orchestrates the full Bronze → Silver → Gold pipeline with
Claude AI integration at each stage.

Usage:
    # Run full pipeline
    python -m src.pipeline.orchestrator

    # Run specific layer
    python -m src.pipeline.orchestrator --layer bronze
    python -m src.pipeline.orchestrator --layer silver
    python -m src.pipeline.orchestrator --layer gold
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.ai.claude_client import ClaudeClient
from src.ai.data_analyzer import DataAnalyzer
from src.ai.insight_generator import InsightGenerator
from src.ai.quality_advisor import QualityAdvisor
from src.analytics.aggregations import BusinessAggregator
from src.analytics.kpi_calculator import KPICalculator
from src.analytics.report_generator import ReportGenerator
from src.ingestion.base_connector import IngestionConfig
from src.ingestion.crm_connector import CRMConnector
from src.ingestion.erp_connector import ERPConnector
from src.ingestion.api_connector import APIConnector
from src.pipeline.config import PipelineConfig
from src.transformation.data_quality import DataQualityChecker
from src.transformation.deduplication import DeduplicationEngine, DeduplicationStrategy
from src.transformation.schema_enforcer import (
    SchemaEnforcer,
    SchemaMode,
    CRM_SCHEMA,
    ERP_SCHEMA,
)
from src.transformation.spark_processor import SparkProcessor


logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Main pipeline orchestrator.

    Coordinates all pipeline stages:
    1. Bronze: Multi-source data ingestion
    2. Silver: Transformation, quality, deduplication
    3. Gold: Aggregation, KPI calculation, reporting

    With Claude AI integration:
    - Data profiling at ingestion
    - Quality advisory at transformation
    - Insight generation at analytics
    - Report narratives at output

    Usage:
        config = PipelineConfig.from_yaml()
        orchestrator = PipelineOrchestrator(config)
        results = orchestrator.run()
    """

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig.from_yaml()
        self.claude = ClaudeClient(
            api_key=self.config.anthropic_api_key,
            default_model=self.config.claude_default_model,
            analysis_model=self.config.claude_analysis_model,
        )
        self.results: dict[str, Any] = {
            "pipeline_run_id": f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "start_time": None,
            "end_time": None,
            "layers": {},
        }

    def run(self, layer: str | None = None) -> dict[str, Any]:
        """
        Execute the pipeline.

        Args:
            layer: Specific layer to run ("bronze", "silver", "gold")
                   or None for full pipeline.
        """
        self.results["start_time"] = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"{'=' * 60}\n"
            f"  AI Data Lake Pipeline — {self.config.name} v{self.config.version}\n"
            f"  Environment: {self.config.environment}\n"
            f"  Run ID: {self.results['pipeline_run_id']}\n"
            f"{'=' * 60}"
        )

        try:
            if layer in (None, "bronze"):
                bronze_data = self._run_bronze()
            else:
                bronze_data = {}

            if layer in (None, "silver"):
                silver_data = self._run_silver(bronze_data)
            else:
                silver_data = {}

            if layer in (None, "gold"):
                self._run_gold(silver_data)

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.results["error"] = str(e)
            raise

        finally:
            self.results["end_time"] = datetime.now(timezone.utc).isoformat()
            self.results["claude_usage"] = self.claude.get_usage_summary()

        # Print summary
        self._print_summary()

        return self.results

    def _run_bronze(self) -> dict[str, pd.DataFrame]:
        """Execute Bronze layer — Data Ingestion."""
        logger.info("\n🥉 BRONZE LAYER — Data Ingestion")
        logger.info("-" * 40)
        bronze_results: dict[str, pd.DataFrame] = {}
        layer_metrics: dict[str, Any] = {"sources": {}}

        # Ingest CRM data
        try:
            crm_config = IngestionConfig(
                source_name="crm",
                source_type="crm",
                batch_size=self.config.batch_size,
                max_retries=self.config.max_retries,
            )
            crm_path = Path(self.config.data_dir) / "sample_crm_contacts.json"
            crm_connector = CRMConnector(crm_config, data_path=crm_path)
            df_crm = crm_connector.ingest()
            bronze_results["crm"] = df_crm
            layer_metrics["sources"]["crm"] = crm_connector.metrics.to_dict()
            logger.info(f"  ✅ CRM: {len(df_crm)} records ingested")
        except Exception as e:
            logger.error(f"  ❌ CRM ingestion failed: {e}")
            layer_metrics["sources"]["crm"] = {"error": str(e)}

        # Ingest ERP data
        try:
            erp_config = IngestionConfig(
                source_name="erp",
                source_type="erp",
                batch_size=self.config.batch_size,
                max_retries=self.config.max_retries,
            )
            erp_path = Path(self.config.data_dir) / "sample_erp_transactions.csv"
            erp_connector = ERPConnector(erp_config, data_path=erp_path)
            df_erp = erp_connector.ingest()
            bronze_results["erp"] = df_erp
            layer_metrics["sources"]["erp"] = erp_connector.metrics.to_dict()
            logger.info(f"  ✅ ERP: {len(df_erp)} records ingested")
        except Exception as e:
            logger.error(f"  ❌ ERP ingestion failed: {e}")
            layer_metrics["sources"]["erp"] = {"error": str(e)}

        # Ingest API data
        try:
            api_config = IngestionConfig(
                source_name="api",
                source_type="api",
                batch_size=self.config.batch_size,
            )
            api_path = Path(self.config.data_dir) / "sample_api_response.json"
            api_connector = APIConnector(api_config, data_path=api_path, data_key="data")
            df_api = api_connector.ingest()
            bronze_results["api"] = df_api
            layer_metrics["sources"]["api"] = api_connector.metrics.to_dict()
            logger.info(f"  ✅ API: {len(df_api)} records ingested")
        except Exception as e:
            logger.error(f"  ❌ API ingestion failed: {e}")
            layer_metrics["sources"]["api"] = {"error": str(e)}

        # AI: Profile ingested data
        if bronze_results:
            analyzer = DataAnalyzer(self.claude)
            for source_name, df in bronze_results.items():
                if not df.empty:
                    logger.info(f"  🤖 AI profiling {source_name}...")
                    profile = analyzer.profile_dataset(df, source_name=source_name)
                    layer_metrics["sources"].setdefault(source_name, {})["ai_profile"] = (
                        profile.get("ai_analysis", "")[:200] + "..."
                    )

        layer_metrics["total_records"] = sum(
            len(df) for df in bronze_results.values()
        )
        self.results["layers"]["bronze"] = layer_metrics

        return bronze_results

    def _run_silver(self, bronze_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """Execute Silver layer — Transformation & Quality."""
        logger.info("\n🥈 SILVER LAYER — Transformation & Quality")
        logger.info("-" * 40)
        silver_results: dict[str, pd.DataFrame] = {}
        layer_metrics: dict[str, Any] = {"datasets": {}}

        processor = SparkProcessor(use_spark=False)
        schema_enforcer = SchemaEnforcer(mode=SchemaMode.PERMISSIVE)
        schema_enforcer.register_schema(CRM_SCHEMA)
        schema_enforcer.register_schema(ERP_SCHEMA)

        quality_checker = DataQualityChecker()
        quality_checker.add_completeness_rule("customer_id", threshold=0.95)
        quality_checker.add_accuracy_rule("quantity", min_value=0, max_value=10000)
        quality_checker.add_uniqueness_rule(["transaction_id"])

        dedup_engine = DeduplicationEngine(
            strategy=DeduplicationStrategy.EXACT,
            key_columns=["transaction_id", "contact_id"],
        )

        for source_name, df in bronze_data.items():
            if df.empty:
                continue

            logger.info(f"  Processing {source_name}...")
            dataset_metrics: dict[str, Any] = {"input_rows": len(df)}

            # Transform
            df_transformed = processor.transform(df, source_type=source_name)
            dataset_metrics["after_transform"] = len(df_transformed)

            # Deduplicate
            df_deduped, dedup_result = dedup_engine.deduplicate(df_transformed)
            dataset_metrics["dedup"] = dedup_result.to_dict()

            # Quality check
            quality_report = quality_checker.check(
                df_deduped, dataset_name=f"{source_name}_clean", layer="silver"
            )
            dataset_metrics["quality"] = {
                "score": quality_report.overall_score,
                "passed": quality_report.all_passed,
                "dimensions": quality_report.dimension_scores,
            }

            # AI Quality Advisory
            if not quality_report.all_passed:
                advisor = QualityAdvisor(self.claude)
                logger.info(f"  🤖 AI quality advisory for {source_name}...")
                advice = advisor.analyze_report(quality_report.to_dict())
                dataset_metrics["ai_quality_advice"] = (
                    advice.get("ai_recommendations", "")[:200] + "..."
                )

            silver_results[source_name] = df_deduped
            layer_metrics["datasets"][source_name] = dataset_metrics
            logger.info(
                f"  ✅ {source_name}: {len(df_deduped)} rows, "
                f"quality={quality_report.overall_score:.2%}"
            )

        layer_metrics["total_records"] = sum(
            len(df) for df in silver_results.values()
        )
        self.results["layers"]["silver"] = layer_metrics

        return silver_results

    def _run_gold(self, silver_data: dict[str, pd.DataFrame]) -> None:
        """Execute Gold layer — Analytics & Insights."""
        logger.info("\n🥇 GOLD LAYER — Analytics & Insights")
        logger.info("-" * 40)
        layer_metrics: dict[str, Any] = {}

        aggregator = BusinessAggregator()
        kpi_calc = KPICalculator()
        report_gen = ReportGenerator(claude_client=self.claude)

        # Process ERP transactions for business metrics
        df_erp = silver_data.get("erp", pd.DataFrame())
        if not df_erp.empty:
            # Daily aggregation
            daily = aggregator.aggregate_daily(df_erp, date_col="order_date")
            layer_metrics["daily_aggregation"] = {
                "rows": len(daily),
            }
            logger.info(f"  ✅ Daily aggregation: {len(daily)} rows")

            # KPIs
            kpis = kpi_calc.calculate_all(df_erp)
            layer_metrics["kpis"] = kpis
            logger.info(f"  ✅ KPIs calculated")

            # Generate report
            report = report_gen.generate(
                df_erp,
                report_type="daily_business",
                title=f"Daily Business Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            )
            layer_metrics["report"] = {
                "title": report.get("title"),
                "sections": list(report.get("sections", {}).keys()),
            }
            logger.info(f"  ✅ Report generated: {report.get('title')}")

            # AI Insights (using Opus)
            insight_gen = InsightGenerator(self.claude)
            logger.info("  🤖 Generating AI insights with Claude Opus...")
            insights = insight_gen.generate_insights(
                df_erp,
                dataset_name="erp_transactions",
                focus_area="revenue and customer trends",
            )
            layer_metrics["ai_insights"] = (
                insights.get("insights", "")[:300] + "..."
            )

        self.results["layers"]["gold"] = layer_metrics

    def _print_summary(self) -> None:
        """Print pipeline execution summary."""
        logger.info(f"\n{'=' * 60}")
        logger.info("  PIPELINE EXECUTION SUMMARY")
        logger.info(f"{'=' * 60}")
        logger.info(f"  Run ID: {self.results['pipeline_run_id']}")
        logger.info(f"  Start:  {self.results['start_time']}")
        logger.info(f"  End:    {self.results['end_time']}")

        for layer_name, layer_data in self.results.get("layers", {}).items():
            total = layer_data.get("total_records", "N/A")
            logger.info(f"\n  [{layer_name.upper()}] {total} records")

        usage = self.results.get("claude_usage", {})
        tokens = usage.get("usage", {})
        logger.info(f"\n  Claude AI Usage:")
        logger.info(f"    Requests: {tokens.get('total_requests', 0)}")
        logger.info(f"    Tokens:   {tokens.get('total_tokens', 0)}")
        logger.info(f"{'=' * 60}\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI Data Lake Pipeline Orchestrator"
    )
    parser.add_argument(
        "--layer",
        choices=["bronze", "silver", "gold"],
        default=None,
        help="Run a specific pipeline layer (default: full pipeline)",
    )
    parser.add_argument(
        "--config",
        default="config/pipeline_config.yaml",
        help="Path to pipeline config file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = PipelineConfig.from_yaml(args.config)
    orchestrator = PipelineOrchestrator(config)
    results = orchestrator.run(layer=args.layer)

    # Save results
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file = output_dir / f"pipeline_results_{results['pipeline_run_id']}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Results saved to: {results_file}")


if __name__ == "__main__":
    main()
