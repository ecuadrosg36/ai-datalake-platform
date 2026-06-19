"""
Claude Client — Anthropic API wrapper for the data lake platform.

Provides a unified interface for interacting with Claude models (Sonnet + Opus)
with built-in retry logic, token tracking, cost estimation, and structured
output parsing. Designed for production data engineering workflows.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Cost per million tokens (approximate, as of 2025)
MODEL_COSTS = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}


@dataclass
class TokenUsage:
    """Tracks token usage and estimated costs."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_requests: int = 0
    total_errors: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def estimate_cost(self, model: str) -> float:
        """Estimate cost in USD based on token usage."""
        costs = MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})
        input_cost = (self.input_tokens / 1_000_000) * costs["input"]
        output_cost = (self.output_tokens / 1_000_000) * costs["output"]
        return round(input_cost + output_cost, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
        }


class ClaudeClient:
    """
    Anthropic Claude API client wrapper.

    Features:
    - Dual model support (Sonnet for daily tasks, Opus for complex analysis)
    - Automatic retry with exponential backoff
    - Token usage tracking and cost estimation
    - Structured JSON output parsing
    - System prompt management
    - Request/response logging

    Usage:
        client = ClaudeClient()

        # Quick analysis with Sonnet (default)
        result = client.analyze("Summarize this dataset: ...")

        # Complex analysis with Opus
        result = client.analyze(
            "Create a detailed execution plan...",
            model="opus",
        )

        # Structured output
        result = client.analyze_structured(
            "Extract entities from this data...",
            output_schema={"entities": [], "relationships": []},
        )

        # Check usage
        print(f"Total tokens: {client.usage.total_tokens}")
        print(f"Estimated cost: ${client.usage.estimate_cost('claude-sonnet-4-20250514')}")
    """

    # System prompts for different contexts
    SYSTEM_PROMPTS = {
        "data_engineering": (
            "You are an expert data engineer specializing in building data lakes "
            "on AWS. You have deep knowledge of Medallion architecture (Bronze, "
            "Silver, Gold layers), PySpark, SQL, DBT, and data quality frameworks. "
            "Provide concise, actionable technical guidance. When analyzing data, "
            "focus on data quality, schema design, and transformation logic."
        ),
        "business_analysis": (
            "You are a senior business analyst. Analyze data to extract actionable "
            "insights, identify trends, detect anomalies, and provide strategic "
            "recommendations. Use clear, executive-friendly language."
        ),
        "sql_expert": (
            "You are an expert SQL developer specializing in Amazon Athena (Presto). "
            "Generate optimized, well-commented SQL queries. Always consider partition "
            "pruning, efficient JOINs, and query performance. Return ONLY the SQL "
            "query unless asked for explanation."
        ),
        "quality_advisor": (
            "You are a data quality expert. Analyze quality reports to identify root "
            "causes of issues, suggest remediation steps, and recommend prevention "
            "strategies. Prioritize issues by business impact."
        ),
    }

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "claude-sonnet-4-20250514",
        analysis_model: str = "claude-opus-4-20250514",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.default_model = default_model
        self.analysis_model = analysis_model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.usage = TokenUsage()
        self._client = None

        if self.api_key:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize the Anthropic client."""
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("Anthropic client initialized successfully")
        except ImportError:
            logger.warning(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")

    def analyze(
        self,
        prompt: str,
        model: str = "default",
        system_prompt: str = "data_engineering",
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """
        Send an analysis request to Claude.

        Args:
            prompt: The analysis prompt.
            model: "default" (Sonnet) or "opus" (Opus).
            system_prompt: Key from SYSTEM_PROMPTS or custom string.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature (0.0 = deterministic).

        Returns:
            Dict with "content", "model", "tokens", and "cost" keys.
        """
        model_name = self.analysis_model if model == "opus" else self.default_model
        system = self.SYSTEM_PROMPTS.get(system_prompt, system_prompt)

        if not self._client:
            # Demo mode — return structured mock response
            return self._mock_response(prompt, model_name)

        # Execute with retry
        last_error = None
        delay = self.retry_delay

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )

                # Track usage
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self.usage.input_tokens += input_tokens
                self.usage.output_tokens += output_tokens
                self.usage.total_requests += 1

                content = response.content[0].text if response.content else ""

                result = {
                    "content": content,
                    "model": model_name,
                    "tokens": {
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": input_tokens + output_tokens,
                    },
                    "cost_usd": self._estimate_request_cost(
                        input_tokens, output_tokens, model_name
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Log to history
                self.usage.history.append({
                    "timestamp": result["timestamp"],
                    "model": model_name,
                    "tokens": result["tokens"]["total"],
                    "cost": result["cost_usd"],
                })

                logger.info(
                    f"Claude response: model={model_name}, "
                    f"tokens={result['tokens']['total']}, "
                    f"cost=${result['cost_usd']}"
                )

                return result

            except Exception as e:
                last_error = e
                self.usage.total_errors += 1

                if attempt < self.max_retries:
                    logger.warning(
                        f"Claude API error (attempt {attempt}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= 2

        logger.error(f"Claude API failed after {self.max_retries} attempts: {last_error}")
        return {
            "content": f"Error: {str(last_error)}",
            "model": model_name,
            "error": True,
            "tokens": {"input": 0, "output": 0, "total": 0},
            "cost_usd": 0,
        }

    def analyze_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
        model: str = "default",
        system_prompt: str = "data_engineering",
    ) -> dict[str, Any]:
        """
        Request structured JSON output from Claude.

        Wraps the prompt with instructions to return valid JSON
        matching the provided schema.
        """
        schema_str = json.dumps(output_schema, indent=2) if output_schema else "{}"

        structured_prompt = (
            f"{prompt}\n\n"
            f"Return your response as valid JSON matching this schema:\n"
            f"```json\n{schema_str}\n```\n"
            f"Return ONLY the JSON object, no markdown formatting or explanation."
        )

        response = self.analyze(
            structured_prompt,
            model=model,
            system_prompt=system_prompt,
        )

        # Try to parse JSON from response
        content = response.get("content", "")
        try:
            # Strip markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            parsed = json.loads(content.strip())
            response["parsed"] = parsed
        except (json.JSONDecodeError, IndexError):
            response["parsed"] = None
            response["parse_error"] = "Failed to parse JSON from response"

        return response

    def _estimate_request_cost(
        self, input_tokens: int, output_tokens: int, model: str
    ) -> float:
        """Estimate cost for a single request."""
        costs = MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        return round(input_cost + output_cost, 6)

    def _mock_response(self, prompt: str, model: str) -> dict[str, Any]:
        """Generate a mock response for demo/testing without API key."""
        logger.info("Using mock response (no API key configured)")

        mock_content = (
            "## Analysis Results\n\n"
            "Based on the provided data:\n\n"
            "1. **Data Quality**: Overall data quality is good with 95%+ completeness\n"
            "2. **Key Patterns**: Revenue shows stable trends with seasonal variations\n"
            "3. **Recommendations**:\n"
            "   - Implement automated quality checks at ingestion\n"
            "   - Set up alerting for anomaly detection\n"
            "   - Consider partitioning by region for query optimization\n\n"
            "*Note: This is a demo response. Configure ANTHROPIC_API_KEY for live analysis.*"
        )

        return {
            "content": mock_content,
            "model": model,
            "tokens": {"input": 0, "output": 0, "total": 0},
            "cost_usd": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_mock": True,
        }

    def get_usage_summary(self) -> dict[str, Any]:
        """Get a summary of API usage and costs."""
        return {
            "usage": self.usage.to_dict(),
            "estimated_cost_default": self.usage.estimate_cost(self.default_model),
            "estimated_cost_analysis": self.usage.estimate_cost(self.analysis_model),
            "models": {
                "default": self.default_model,
                "analysis": self.analysis_model,
            },
        }
