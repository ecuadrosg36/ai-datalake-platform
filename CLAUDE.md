# AI Data Lake Platform — Claude Code Instructions

## Project Overview
AI-powered Data Lake platform using Medallion Architecture (Bronze → Silver → Gold)
with Claude AI integration and MCP Server for agent-driven data operations.

## Tech Stack
- **Language:** Python 3.10+
- **Cloud:** AWS (S3, Glue, Athena, Lambda, Step Functions, Lake Formation)
- **AI:** Anthropic Claude (Sonnet for fast tasks, Opus for deep analysis)
- **Data:** PySpark, pandas, dbt
- **Testing:** pytest
- **IaC:** CloudFormation

## Development Workflow

### 1. Make changes
Always work in the `src/` directory. Follow the module structure:
```
src/ingestion/    → Bronze layer (raw data connectors)
src/transformation/ → Silver layer (cleaning, validation)
src/analytics/    → Gold layer (KPIs, aggregations, reports)
src/ai/           → Claude AI integration
src/mcp/          → MCP Server for AI agents
src/pipeline/     → Orchestration
```

### 2. Run tests (always after changes)
```bash
python -m pytest tests/ -v
python -m pytest tests/ -v --tb=short   # Quick summary
python -m pytest tests/test_ingestion.py -v  # Single module
```

### 3. Type checking
```bash
python -m mypy src/ --ignore-missing-imports
```

### 4. Lint
```bash
python -m flake8 src/ --max-line-length=120
```

## Important Rules

### Code Style
- Use **snake_case** for all Python code
- Use **type hints** on all function signatures
- Use **dataclasses** or **Pydantic models**, never raw dicts for structured data
- Use **logging** module, never `print()` statements
- Maximum line length: **120 characters**

### Data Engineering Patterns
- All connectors MUST inherit from `BaseConnector`
- Raw data is IMMUTABLE in Bronze — never modify source data
- Silver layer transformations must be IDEMPOTENT
- Gold layer tables must have clear business definitions
- Always validate data quality at Silver layer before promoting to Gold
- Use **parameterized queries** — never raw SQL string concatenation

### Claude AI Integration
- Use **Sonnet** for automated profiling, SQL generation, and quick analysis
- Use **Opus** for deep business insights, trend analysis, and complex reasoning
- Always include cost tracking in AI calls
- Cache AI responses when analyzing the same dataset within 1 hour

### MCP Server
- All MCP tools must have clear descriptions for AI agents
- Resources must be read-only — agents cannot modify source data
- Log all MCP queries for audit trail

### Testing
- Tests go in `tests/` mirroring `src/` structure
- Use **pytest fixtures** for sample data
- Mock external services (AWS, Claude API)
- Dirty/invalid records in sample data are INTENTIONAL — test `PARTIAL` status
- Target: minimum 50% code coverage

### Git
- Commit messages: `type(scope): description` (e.g., `feat(ingestion): add WhatsApp connector`)
- One feature per branch
- Always run tests before committing

## Known Gotchas
- CRM sample data includes intentionally dirty records → ingestion returns `PARTIAL`, not `SUCCESS`
- The `.env` file is NOT committed — copy `.env.example` and add your keys
- PySpark requires Java 8+ on the system
- MCP Server runs on port 8080 by default

## Architecture Reference
See `docs/architecture.md` for the full Medallion Architecture diagram.
See `docs/claude_integration.md` for Claude Sonnet vs Opus decision matrix.
See `docs/mcp_integration.md` for MCP tool and resource specifications.

<!-- trimaran-stack:rules (always-follow; do not delete) -->

# The five Trimaran rules (always follow)

These are guardrails earned from real incidents. Apply them on every task; the full rationale
for each is in `rules/<n>-*.md` in this plugin, and `install.sh` inlines them into each repo's
CLAUDE.md (which is always loaded).

1. **memory-discipline** — Write every non-obvious lesson down as a rule (per-repo CLAUDE.md or
   the global memory index) instead of correcting it conversationally. It compounds forever.

2. **write-scope-guard** — Declare allowed write paths before writing. Write only *safe copies*;
   never a live system of record / prod account without an explicit human gate this session.
   Bridges are append-only + key-rotated. Snapshot before edit. *(Scar: Casa Prime "safe Excel
   copies only"; OGGI append-only bridge.)*

3. **verification-closes-the-loop** — "Done" = the *real behavior observed correct*, not the
   harness saying OK. Reconcile data to a known-good number, not a row count. Beware false-healthy
   monitors; add a liveness heartbeat. *(Scar: ProcessRecorder Guardian read HEALTHY while the
   fleet was frozen; Casa Prime false-zero digests.)*

4. **never-loosen-the-gate** — If a guard/test/threshold blocks you, fix the cause — never weaken
   the check to go green. A false positive gets *proven and fixed at the source*, not suppressed.
   *(Scar: Shyla tautology-fix rejected; Samurai iron rule.)*

5. **long-loop-safety** — For autonomous `/goal`+`/loop` runs: small editable surface, immutable
   harness, fixed budget, one metric, adversarial check before commit, liveness heartbeat.
   *(Shape: Karpathy autoresearch.)*

The 5 pillars these serve: **Automation · Worktrees · Skills · Connectors · Sub-agents.**
