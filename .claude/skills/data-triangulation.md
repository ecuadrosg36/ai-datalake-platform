# Data Triangulation Skill

When validating data across multiple sources, use triangulation
to build confidence in the numbers.

## What is Triangulation?
Cross-checking the SAME metric from DIFFERENT sources to verify accuracy.

## Example
A company's June revenue should match across:
- **ERP:** SQL query → `SELECT SUM(amount) FROM transactions WHERE month='June'`
- **Excel:** Finance team's spreadsheet `ventas_junio_2026.xlsx`
- **WhatsApp:** Sales director's message "We closed 129 deals for $129K"

## Process

### Step 1: Extract the metric from each source
```python
erp_revenue = query_erp("SELECT SUM(amount) FROM transactions WHERE period='2026-06'")
excel_revenue = read_excel("ventas_junio_2026.xlsx", sheet="summary", cell="B12")
chat_revenue = extract_number(whatsapp_message, pattern=r'\$[\d,]+K?')
```

### Step 2: Compare values
```python
sources = {
    "ERP": erp_revenue,
    "Excel": excel_revenue,
    "WhatsApp": chat_revenue
}

# Flag discrepancies > 5%
baseline = sources["ERP"]  # ERP is usually the authoritative source
for name, value in sources.items():
    delta = abs(value - baseline) / baseline * 100
    if delta > 5:
        flag_discrepancy(name, value, baseline, delta)
```

### Step 3: Resolve discrepancies
- If 2 of 3 sources agree → the outlier is likely wrong
- If all 3 disagree → escalate to the human (ask via MCP chat)
- Always log which source was used as the "truth"

### Step 4: Create a confidence score
```
Confidence = (number of sources that agree) / (total sources)
HIGH:   3/3 agree (> 95% match)
MEDIUM: 2/3 agree
LOW:    All disagree → needs human validation
```
