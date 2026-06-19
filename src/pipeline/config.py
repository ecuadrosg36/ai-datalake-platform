"""
Pipeline Configuration — Loads and manages pipeline settings.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PipelineConfig:
    """Pipeline configuration container."""
    name: str = "ai-datalake-pipeline"
    version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    data_dir: str = "data"
    output_dir: str = "output"
    batch_size: int = 1000
    max_retries: int = 3
    aws_region: str = "us-east-1"
    s3_bucket: str = "ai-datalake-platform"
    anthropic_api_key: str = ""
    claude_default_model: str = "claude-sonnet-4-20250514"
    claude_analysis_model: str = "claude-opus-4-20250514"

    @classmethod
    def from_yaml(cls, path: str | Path = "config/pipeline_config.yaml") -> "PipelineConfig":
        """Load configuration from YAML file."""
        config_path = Path(path)
        if not config_path.exists():
            return cls()

        with open(config_path, "r") as f:
            raw = yaml.safe_load(f) or {}

        pipeline = raw.get("pipeline", {})
        processing = raw.get("processing", {})
        aws = raw.get("aws", {})

        return cls(
            name=pipeline.get("name", cls.name),
            version=pipeline.get("version", cls.version),
            environment=os.getenv("PIPELINE_ENV", pipeline.get("environment", cls.environment)),
            log_level=os.getenv("PIPELINE_LOG_LEVEL", pipeline.get("log_level", cls.log_level)),
            data_dir=os.getenv("DATA_DIR", cls.data_dir),
            output_dir=os.getenv("OUTPUT_DIR", cls.output_dir),
            batch_size=processing.get("batch_size", cls.batch_size),
            max_retries=processing.get("max_retries", cls.max_retries),
            aws_region=os.getenv("AWS_DEFAULT_REGION", aws.get("region", cls.aws_region)),
            s3_bucket=os.getenv("AWS_S3_BUCKET", aws.get("s3", {}).get("bucket", cls.s3_bucket)),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            claude_default_model=os.getenv("CLAUDE_DEFAULT_MODEL", cls.claude_default_model),
            claude_analysis_model=os.getenv("CLAUDE_ANALYSIS_MODEL", cls.claude_analysis_model),
        )
