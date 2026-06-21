# The Trimaran 5-Pillar Checklist

Every project — new or existing — should satisfy these five. This is the rubric from
"Loop Engineering" (trq212) + Boris Cherny, made concrete for how we work.

### 1. Automation  ⏰
- [ ] At least one always-on **routine** (cloud cron / GitHub-event), not a laptop job.
- [ ] It watches **freshness** (dead-pipeline / false-zero) and **cost** (spend anomaly).
- [ ] Alerts go somewhere a human reads; silence means healthy (no false ✅).

### 2. Worktrees  🌳
- [ ] Parallel/long work uses git **worktrees** so agents don't collide.
- [ ] Migrations & audits fan out via `parallel-worktrees` / `scripts/worktree-fanout.sh` — one PR each.

### 3. Skills  🧩
- [ ] `trimaran-stack` plugin installed; gstack `/review` `/cso` `/ship` + `/trimaran-ship` available.
- [ ] Project conventions codified in `CLAUDE.md` so the loop stops re-deriving them.
- [ ] New skills authored to the `writing-skills` standard.

### 4. Connectors  🔌
- [ ] The project's data source is wired as an **MCP connector** from day one (copy from
      `mcp/mcp-servers.example.json`), not scraped by hand.
- [ ] Secrets in a manager, not in code/chat; rotated on exposure. `.scope_allow` set; `scope_check.py` wired.

### 5. Sub-agents  🤖
- [ ] Nothing is "done" until **adversarial-review** has failed to break it (×2 for money/data).
- [ ] One agent proposes, a *different* one disposes.

### Always-on rules (loaded by the plugin)
memory-discipline · write-scope-guard · verification-closes-the-loop · never-loosen-the-gate · long-loop-safety
