# Self-Improvement Loop Skill

When the system detects a data quality issue or receives user feedback
that data is incorrect, use this workflow:

## The Loop (Planner → Generator → Critic → Tester)

### Phase 1: PLAN
Analyze the user's complaint and identify:
- Which Gold table has wrong data
- Which Silver transformation feeds it
- Which Bronze source is the origin
- What the user says the correct value should be

### Phase 2: GENERATE
Create a fix:
- Write corrected SQL/transformation logic
- Create a new data quality check to prevent recurrence
- Update the relevant Silver or Gold layer code

### Phase 3: CRITIQUE
Review the fix:
- Does it solve the reported issue?
- Does it break any existing functionality?
- Is it idempotent (safe to re-run)?
- Does it handle edge cases?

### Phase 4: TEST
Verify the fix:
```bash
python -m pytest tests/ -v -k "test_<affected_module>"
```
- Run existing tests (no regressions)
- Run the new test case (fix works)
- Verify with sample data that matches user's complaint

### Phase 5: PERSIST LEARNING
Add to CLAUDE.md under "Known Gotchas":
```markdown
- [Date]: [What was wrong] → [Root cause] → [Fix applied]
```

## Memory Format
Store learnings so they survive across sessions:
```json
{
  "date": "2026-06-18",
  "issue": "Revenue showed $1M instead of $129K",
  "root_cause": "Missing WHERE status='completed' filter",
  "fix": "Added filter to gold/revenue_daily.sql",
  "prevention": "Added quality check: monthly revenue delta < 200%"
}
```
