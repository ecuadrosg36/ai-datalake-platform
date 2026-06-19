Analyze the data pipeline for potential issues:

1. Check Bronze layer connectors:
   - Are all data sources connected? (CRM, ERP, CSV, API)
   - Is error handling robust for network failures?
   - Are retries configured with exponential backoff?

2. Check Silver layer transformations:
   - Are deduplication rules correct?
   - Is schema enforcement catching all edge cases?
   - Are data quality checks comprehensive?
   - Cross-validate: do numbers from different sources match?

3. Check Gold layer analytics:
   - Are KPI calculations correct? (verify with sample data)
   - Are aggregations handling NULL values properly?
   - Do date ranges align across all reports?

4. Check AI integration:
   - Are Claude API calls being tracked for cost?
   - Is the response caching working?
   - Are prompts well-structured for consistent output?

5. Report findings as a data quality scorecard:
   - 🟢 Healthy | 🟡 Warning | 🔴 Critical
