Review all uncommitted changes in the working directory:

1. Run `git diff` to see all changes
2. For each changed file, analyze:
   - Does it follow the conventions in CLAUDE.md?
   - Are there type hints on all functions?
   - Is there proper error handling?
   - Are there any security issues (SQL injection, hardcoded secrets)?
   - Is the code DRY (Don't Repeat Yourself)?
3. Check for:
   - Missing tests for new functionality
   - Breaking changes to existing APIs
   - Unnecessary complexity that could be simplified
4. Provide a summary:
   - ✅ What looks good
   - ⚠️ What needs attention
   - ❌ What must be fixed before merging
