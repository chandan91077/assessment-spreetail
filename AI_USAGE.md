# AI_USAGE.md — AI Tool Usage Log

## AI Tool Used

**Antigravity** (Google DeepMind Advanced Agentic Coding assistant)

Used as the primary development collaborator for this project. I (the developer) acted as the product manager and engineering lead, specifying requirements, reviewing all output, and correcting errors before accepting code.

---

## Role Division

| Task | Developer | AI |
|------|-----------|-----|
| Read and interpret assignment | ✅ | Used as input |
| Identify all 14 CSV anomalies | ✅ (primary) | Assisted |
| Design database schema | ✅ (approved) | Draft |
| Write anomaly detection logic | ✅ (reviewed line by line) | Draft |
| Write balance calculator | ✅ (hand-verified) | Draft |
| Design UI/UX | ✅ | Draft |
| Write SCOPE/DECISIONS docs | ✅ | Draft |
| Debug runtime errors | ✅ | Assisted |

---

## Key Prompts Used

### P1 — Initial planning
> "Build a shared expenses app for these flatmates. Four flatmates, one CSV with deliberate anomalies. Build an implementation plan first."

### P2 — CSV anomaly specification
> "Create the expenses_export.csv with exactly these 14 anomalies: [listed all 14]. Do not clean up any anomaly — leave them all in the file as they would appear in a real messy spreadsheet."

### P3 — Importer logic
> "Write the csv_importer.py. For each of the 14 anomaly types, I want to see the exact detection logic, the policy applied, and the anomaly record created. Do NOT silently fix anything without recording it."

### P4 — Balance calculator
> "Write balance_calculator.py. Balances must NEVER be stored. The greedy algorithm must work in integer paise to avoid float errors. Walk me through a worked example for Rohan."

### P5 — Frontend design
> "Build a dark glassmorphism SPA. No framework, vanilla JS. Every button must have a unique ID. The balance page must have a click-to-expand breakdown per person."

---

## Three Concrete Cases Where AI Produced Something Wrong

### Case 1: Wrong greedy algorithm (balance_calculator.py)

**What the AI generated**:
```python
# Original (wrong) version
while creditors and debtors:
    c_uid, c_amt = creditors.pop()
    d_uid, d_amt = debtors.pop()
    settle = min(c_amt, d_amt)
    transactions.append(...)
    if c_amt > settle: creditors.append(...)
    if d_amt > settle: debtors.append(...)
```
The AI used a plain list with `.pop()` and `.append()` but did not maintain sorted order. After the first iteration, the list was no longer sorted, so it would not always match the largest creditor with the largest debtor.

**How I caught it**: I hand-traced a three-person example:
- Aisha: +300 (owed)
- Rohan: -500 (owes)
- Priya: +200 (owed)

The correct minimal solution is: Rohan pays Aisha 300, Rohan pays Priya 200. The AI's version (after one iteration consumed Aisha's 300) would pop Priya as the next creditor but might try to settle with a depleted Rohan entry. I ran through the while loop manually and found it would sometimes produce an extra transaction.

**Fix applied**: Used `sorted()` at initialisation and rebuilt with index pointers (`ci`, `di`) rather than pop/append. This maintains the invariant that we always match the current-largest creditor and current-largest debtor.

---

### Case 2: The date parser treated "05-03-2024" as May 3, not March 5

**What the AI generated**:
```python
parsed = dateutil_parser.parse(original, dayfirst=False)
```
`dayfirst=False` is correct for ISO dates but wrong for DD-MM-YYYY format. The AI did not handle this ambiguity — it assumed `dayfirst=False` would always be right.

**How I caught it**: I looked at the CSV Row 12 which has "05-03-2024" and traced through the parser. With `dayfirst=False`, dateutil would parse this as May 3, 2024 — two months later than the actual expense. This would cause the PRE_JOIN/POST_DEPARTURE checks to use the wrong date, potentially allowing Sam to be included in a March split or Meera to be excluded from a May split.

**Fix applied**: Added explicit detection: if the date string matches `DD-MM-YYYY` pattern (two leading digits, then month ≤ 12 in second position), re-parse with `dayfirst=True`. Added a warning to the anomaly log:
```python
parsed = dateutil_parser.parse(original, dayfirst=True)
return parsed.date(), warnings + [f"Date '{original}' parsed with dayfirst=True"]
```

---

### Case 3: The split rounding left remainders un-distributed

**What the AI generated**:
```python
per_person = round(total / n, 2)
for user in members:
    db.session.add(ExpenseSplit(..., amount_owed=per_person))
```
For a ₹1000 expense split 3 ways: `1000 / 3 = 333.333...`, `round(..., 2) = 333.33`. Three rows of 333.33 = 999.99. The missing ₹0.01 was never assigned to anyone.

**How I caught it**: I manually computed: 3 × 333.33 = 999.99 ≠ 1000.00. The balance calculator would then compute total paid (₹1000) minus total owed (₹999.99) = ₹0.01 left over, which would appear as a phantom balance for the payer.

**Fix applied**: Used `Decimal` with `ROUND_HALF_UP` and added remainder distribution:
```python
per_person = Decimal(str(total / n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
total_distributed = per_person * n
remainder = Decimal(str(total)).quantize(Decimal("0.01")) - total_distributed
# First member gets the remainder (1 paisa)
for i, user in enumerate(members):
    amt = per_person + (remainder if i == 0 else Decimal("0"))
```
This guarantees that `sum(splits) == expense.amount_inr` exactly.

---

## Summary Assessment

The AI was a highly productive collaborator for scaffolding, documentation, and CSS. The three cases above were all caught by manual tracing — which is exactly the engineering discipline this assignment calls for. I reviewed every line of the importer, balance calculator, and route handlers before accepting them. The AI produced good first drafts that required targeted corrections, not wholesale rewrites.
