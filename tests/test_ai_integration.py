"""
Tests for Claude AI Integration.
"""

import pytest

from src.ai.claude_client import ClaudeClient, TokenUsage
from src.ai.data_analyzer import DataAnalyzer
from src.ai.query_generator import QueryGenerator
from src.ai.quality_advisor import QualityAdvisor


# =============================================================================
# ClaudeClient Tests
# =============================================================================

class TestClaudeClient:
    """Tests for the Anthropic API client wrapper."""

    def test_mock_response(self):
        """Test that mock responses work without API key."""
        client = ClaudeClient(api_key="")  # No key = mock mode
        result = client.analyze("Test prompt")
        assert "content" in result
        assert result.get("is_mock") is True

    def test_system_prompts(self):
        """Test system prompt selection."""
        client = ClaudeClient(api_key="")
        assert "data engineer" in client.SYSTEM_PROMPTS["data_engineering"].lower()
        assert "sql" in client.SYSTEM_PROMPTS["sql_expert"].lower()
        assert "quality" in client.SYSTEM_PROMPTS["quality_advisor"].lower()

    def test_token_usage_tracking(self):
        """Test token usage tracking."""
        usage = TokenUsage()
        usage.input_tokens = 1000
        usage.output_tokens = 500
        assert usage.total_tokens == 1500

    def test_cost_estimation(self):
        """Test cost estimation."""
        usage = TokenUsage()
        usage.input_tokens = 1_000_000  # 1M tokens
        usage.output_tokens = 500_000
        cost = usage.estimate_cost("claude-sonnet-4-20250514")
        assert cost > 0

    def test_usage_summary(self):
        """Test usage summary generation."""
        client = ClaudeClient(api_key="")
        client.analyze("Test")
        summary = client.get_usage_summary()
        assert "usage" in summary
        assert "models" in summary

    def test_structured_output(self):
        """Test structured JSON output request."""
        client = ClaudeClient(api_key="")
        result = client.analyze_structured(
            "Extract entities",
            output_schema={"entities": [], "count": 0},
        )
        assert "content" in result


# =============================================================================
# DataAnalyzer Tests
# =============================================================================

class TestDataAnalyzer:
    """Tests for AI-powered data analysis."""

    def test_profile_dataset(self, sample_erp_df):
        """Test dataset profiling."""
        client = ClaudeClient(api_key="")
        analyzer = DataAnalyzer(client)
        profile = analyzer.profile_dataset(sample_erp_df, "test_erp")
        assert profile["row_count"] == len(sample_erp_df)
        assert "stats_profile" in profile
        assert "ai_analysis" in profile

    def test_stats_profile_generation(self, sample_erp_df):
        """Test local statistics profile generation."""
        client = ClaudeClient(api_key="")
        analyzer = DataAnalyzer(client)
        stats = analyzer._generate_stats_profile(sample_erp_df)
        assert stats["shape"]["rows"] == len(sample_erp_df)
        assert "columns" in stats
        assert "quantity" in stats["columns"]

    def test_suggest_transformations(self, sample_erp_df):
        """Test transformation suggestions."""
        client = ClaudeClient(api_key="")
        analyzer = DataAnalyzer(client)
        suggestions = analyzer.suggest_transformations(
            sample_erp_df, target_layer="silver"
        )
        assert "ai_suggestions" in suggestions
        assert suggestions["target_layer"] == "silver"


# =============================================================================
# QueryGenerator Tests
# =============================================================================

class TestQueryGenerator:
    """Tests for natural language to SQL generation."""

    def test_register_table(self):
        """Test table schema registration."""
        client = ClaudeClient(api_key="")
        generator = QueryGenerator(client)
        generator.register_table("erp_transactions", {
            "columns": {"transaction_id": "STRING", "total_amount": "DOUBLE"},
            "partitions": ["year", "month"],
        })
        assert "erp_transactions" in generator.table_schemas

    def test_generate_query(self):
        """Test SQL query generation."""
        client = ClaudeClient(api_key="")
        generator = QueryGenerator(client)
        generator.register_table("erp_transactions", {
            "columns": {"transaction_id": "STRING"},
        })
        result = generator.generate("Show me top 5 products by revenue")
        assert "question" in result
        assert "sql" in result

    def test_extract_sql(self):
        """Test SQL extraction from response."""
        client = ClaudeClient(api_key="")
        generator = QueryGenerator(client)
        content = "```sql\nSELECT * FROM table;\n```\nExplanation: simple query"
        sql = generator._extract_sql(content)
        assert "SELECT" in sql


# =============================================================================
# QualityAdvisor Tests
# =============================================================================

class TestQualityAdvisor:
    """Tests for AI quality advisory."""

    def test_analyze_report(self):
        """Test quality report analysis."""
        client = ClaudeClient(api_key="")
        advisor = QualityAdvisor(client)

        report = {
            "dataset_name": "test_data",
            "overall_score": 0.85,
            "rules_failed": 2,
            "results": [
                {"rule_name": "completeness_email", "score": 0.80, "passed": False},
            ],
        }

        advice = advisor.analyze_report(report)
        assert "ai_recommendations" in advice
        assert advice["dataset"] == "test_data"

    def test_suggest_rules(self):
        """Test quality rule suggestions."""
        client = ClaudeClient(api_key="")
        advisor = QualityAdvisor(client)

        schema = {"columns": {"id": "STRING", "amount": "DOUBLE"}}
        sample = [{"id": "1", "amount": 100}]

        result = advisor.suggest_quality_rules(schema, sample, "erp")
        assert "suggested_rules" in result
