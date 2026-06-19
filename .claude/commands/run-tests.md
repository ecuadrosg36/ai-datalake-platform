Run the full test suite and analyze results:

1. Run: `python -m pytest tests/ -v --tb=short`
2. If any tests fail:
   - Read the error output carefully
   - Fix the failing test or the source code (whichever is wrong)
   - Re-run only the failing test to verify
   - Run the full suite again to check for regressions
3. Report:
   - Total tests: passed / failed / skipped
   - Any new failures introduced
   - Coverage if available: `python -m pytest tests/ --cov=src --cov-report=term-missing`
