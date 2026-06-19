"""
Query Generator — Natural language to Athena SQL translation.

Converts natural language questions into optimized Amazon Athena
SQL queries using Claude Sonnet with schema-aware prompting.
"""

import json
import logging
import re
from typing import Any

from src.ai.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class QueryGenerator:
    """
    Natural language → SQL query generator using Claude.

    Converts business questions into optimized Athena-compatible SQL
    queries, incorporating schema awareness and partition pruning.

    Usage:
        client = ClaudeClient()
        generator = QueryGenerator(client)

        # Register schemas
        generator.register_table("erp_transactions", {
            "columns": {...},
            "partitions": ["year", "month", "day"],
        })

        # Generate query
        result = generator.generate(
            "What were the top 5 products by revenue last month?"
        )
        print(result["sql"])
    """

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client
        self.table_schemas: dict[str, dict[str, Any]] = {}

    def register_table(
        self,
        table_name: str,
        schema: dict[str, Any],
    ) -> None:
        """Register a table schema for context-aware query generation."""
        self.table_schemas[table_name] = schema
        logger.info(f"Registered table schema: {table_name}")

    def generate(
        self,
        question: str,
        tables: list[str] | None = None,
        include_explanation: bool = True,
    ) -> dict[str, Any]:
        """
        Generate an Athena SQL query from a natural language question.

        Args:
            question: Natural language question.
            tables: Optional list of table names to consider.
            include_explanation: Whether to include query explanation.

        Returns:
            Dict with "sql", "explanation", "tables_used", etc.
        """
        # Get relevant schemas
        relevant_schemas = {}
        if tables:
            relevant_schemas = {
                t: s for t, s in self.table_schemas.items() if t in tables
            }
        else:
            relevant_schemas = self.table_schemas

        schema_str = json.dumps(relevant_schemas, indent=2, default=str)

        prompt = (
            f"Convert this question to an Amazon Athena (Presto) SQL query.\n\n"
            f"Question: {question}\n\n"
            f"Available Tables and Schemas:\n{schema_str}\n\n"
            f"Rules:\n"
            f"- Use ANSI SQL compatible with Amazon Athena (Presto engine)\n"
            f"- Include partition filters (year, month, day) when applicable\n"
            f"- Use CTEs for complex logic\n"
            f"- Add SQL comments explaining the logic\n"
            f"- Use proper JOINs (not implicit)\n"
            f"- Handle NULLs appropriately\n"
            f"- Optimize for cost (minimize data scanned)\n"
        )

        if include_explanation:
            prompt += (
                "\nReturn your response in this format:\n"
                "```sql\n<your SQL query>\n```\n\n"
                "**Explanation:**\n<brief explanation of the query logic>"
            )
        else:
            prompt += "\nReturn ONLY the SQL query, no explanation."

        response = self.claude.analyze(
            prompt,
            model="default",
            system_prompt="sql_expert",
        )

        # Parse SQL from response
        content = response.get("content", "")
        sql = self._extract_sql(content)
        explanation = self._extract_explanation(content)

        return {
            "question": question,
            "sql": sql,
            "explanation": explanation,
            "tables_used": list(relevant_schemas.keys()),
            "tokens_used": response.get("tokens", {}),
            "cost_usd": response.get("cost_usd", 0),
        }

    def validate_query(self, sql: str) -> dict[str, Any]:
        """
        Validate a SQL query using Claude.

        Checks for:
        - Syntax correctness
        - Performance concerns
        - Missing partition filters
        - Potential issues
        """
        prompt = (
            f"Review this Athena SQL query for issues:\n\n"
            f"```sql\n{sql}\n```\n\n"
            f"Check for:\n"
            f"1. Syntax errors\n"
            f"2. Performance issues (full table scans, missing partition filters)\n"
            f"3. Logic errors\n"
            f"4. Best practice violations\n"
            f"5. Suggestions for optimization\n"
            f"\nRate the query 1-10 and explain."
        )

        response = self.claude.analyze(
            prompt,
            model="default",
            system_prompt="sql_expert",
        )

        return {
            "sql": sql,
            "review": response.get("content", ""),
            "tokens_used": response.get("tokens", {}),
        }

    def _extract_sql(self, content: str) -> str:
        """Extract SQL query from Claude's response."""
        # Try to find SQL in code block
        sql_match = re.search(
            r"```sql\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE
        )
        if sql_match:
            return sql_match.group(1).strip()

        # Try generic code block
        code_match = re.search(r"```\s*(.*?)\s*```", content, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # If no code block, try to find SELECT statement
        select_match = re.search(
            r"(SELECT\s+.*?;)", content, re.DOTALL | re.IGNORECASE
        )
        if select_match:
            return select_match.group(1).strip()

        return content.strip()

    def _extract_explanation(self, content: str) -> str:
        """Extract explanation from Claude's response."""
        # Look for text after the SQL block
        parts = content.split("```")
        if len(parts) >= 3:
            explanation = parts[-1].strip()
            # Remove "Explanation:" prefix if present
            explanation = re.sub(
                r"^\*?\*?Explanation:?\*?\*?\s*", "", explanation
            )
            return explanation

        return ""
