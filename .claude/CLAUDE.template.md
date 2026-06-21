# CLAUDE.md — <PROJECT NAME> (lakehouse / DataOps)

> Built the Trimaran way, lakehouse variant. Base rules + lakehouse rules L1–L5 are in effect.
> Keep this file current — it's the project's institutional memory.

## What this is
<one-paragraph: business, owner/client, what the lake serves, the system(s) of record>

## Accounts & access
- AWS account: `<id>` · SSO/profile: `<profile>` · region: `<region>`
- IaC: `<CDK-Python repo/path | Terraform>` — all infra is code (no console clickops)
- Catalog/query: Glue db `<db>` · Athena workgroup `<wg>` · results bucket `<s3>`
- Access tiers: ingest role (landing/raw write) · transform role · analyst (gold only) — raw blocked
- Secrets in: `<Secrets Manager/SSM path>` (never here; rotate on exposure)

## Medallion layout (L1 — never mutate bronze)
| Layer | S3 prefix | Format | Guarantee |
|---|---|---|---|
| landing | `landing/source=<s>/dt=` | as-received | transient |
| raw/bronze | `raw/source=<s>/dt=` | Parquet/Iceberg | immutable copy + `load_ts` |
| silver | `silver/<domain>/` | Parquet/Iceberg | conformed/typed/deduped |
| gold | `gold_<metric>` / `gold/<mart>/` | Iceberg/Parquet | reconciled to SoR |
- dbt: `<repo/venv/target>` · schema `<schema>` · models stg→obj→gold

## Sources & freshness (drives the routine — L4)
| Source | Read method | Cadence | Freshness check | SoR | Owner |
|---|---|---|---|---|---|
| `<source>` | `<CDC/export/API>` | nightly | `max(load_ts) ≥ today−1` | `<SoR>` | <name> |

## DataOps gates (L4 — gate, not dashboard)
- Tests on every gold mart: freshness · schema · integrity (keys/null/rowcount) · reconciliation.
- Zero-vs-missing distinguished. Liveness heartbeat: `<how producers prove they're alive>`.
- Self-healing: breach → flag → trigger → review → approve/reject. Never auto-mutate to pass.

## Reconciliation (L5 — to the centavo, fresh baseline)
- `<gold metric>` reconciles to `<SoR>` within `<tolerance>`; baseline pinned `<date>`, refreshed `<how>`.

## Cost guardrails (L2 — requests + GIR, not storage)
- Budget `$<n>` + anomaly alarm → SNS `<topic>`. Compaction: `<schedule>`. No GIR tiering of hot prefixes.

## The 5 pillars
1. **Automation** — `freshness-and-cost-watch` routine scheduled daily → `<channel>`.
2. **Worktrees** — parallel migrations/audits via `parallel-worktrees`, one PR each.
3. **Skills** — `medallion-design`, `ingestion-pattern`, `data-quality-suite`, `iac-scaffold`, `cost-audit`.
4. **Connectors** — MCP wired: `<AWS / data source / Gmail / Drive>`.
5. **Sub-agents** — `lakehouse-architect`, `dataops-engineer`, `iac-reviewer` + adversarial-review before "done".

## Known gotchas (add every non-obvious lesson here)
- <e.g. "metric X double-counts SOF; canonical Q1 = $…; the other figure is a bug">

<!-- trimaran-lakehouse rules L1–L5 are appended below by install.sh -->
