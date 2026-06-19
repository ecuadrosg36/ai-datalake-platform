# Data Pipeline TDD Skill

When building or modifying data pipeline components, follow this strict TDD workflow:

## Process

### 1. Write the Test FIRST
- Define sample input data (include dirty records)
- Define the EXACT expected output
- Write the test using pytest fixtures

### 2. Run the Test (it MUST fail)
```bash
python -m pytest tests/test_<module>.py -v -k "test_<new_feature>"
```
The test should fail with a clear message showing what's missing.

### 3. Implement the Minimum Code
Write ONLY enough code to make the test pass. No extras.

### 4. Run the Test Again (it MUST pass)
```bash
python -m pytest tests/test_<module>.py -v -k "test_<new_feature>"
```

### 5. Add Edge Cases
- NULL values
- Empty DataFrames
- Duplicate records
- Wrong data types
- Timestamps in different formats
- Unicode characters in strings

### 6. Refactor
- Remove duplication
- Improve naming
- Add type hints
- Add docstrings

### 7. Coverage Check
```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```
Target: > 50% coverage. If below, add more tests.

## Data Quality Edge Cases to Always Test
- Records with missing required fields
- Records with future dates
- Negative values where positives expected
- String values where numbers expected
- Extremely large values (overflow protection)
