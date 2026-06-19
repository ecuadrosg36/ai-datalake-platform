Commit all staged changes with a descriptive conventional commit message.
Push to the current branch.
Create a pull request with:

1. A clear PR title following conventional commits (feat/fix/refactor/docs/test)
2. A bullet-point description of all changes made
3. Link any related issues if mentioned in the code
4. A section noting any breaking changes

Before committing:
- Run `python -m pytest tests/ -v` and ensure all tests pass
- Run `python -m flake8 src/ --max-line-length=120` for lint
- If any test fails, fix it before committing

Use this git workflow:
```bash
git add -A
git commit -m "type(scope): description"
git push origin HEAD
```
