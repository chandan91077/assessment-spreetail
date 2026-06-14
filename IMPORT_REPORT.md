=== IMPORT REPORT: expenses_export.csv ===
Imported at: 2026-06-14 20:35:21.798980
Total rows: 30
Imported: 27
Skipped: 2
Pending review: 1
Anomalies detected: 49

--- ANOMALY DETAIL ---
Row   2 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-02-01 — excluded from split
Row   3 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-02-03 — excluded from split
Row   4 | INCONSISTENT_DATE              | AUTO_FIXED           | [PENDING] | INCONSISTENT_DATE: non-ISO date format 'March 5 2024' normalised
Row   4 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-05 — excluded from split
Row   5 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-02-10 — excluded from split
Row   6 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-02-15 — excluded from split
Row   7 | MISSING_PAID_BY                | PENDING_REVIEW       | [PENDING] | paid_by field is blank — cannot assign payer
Row   7 | INCONSISTENT_DATE              | SKIP                 | [PENDING] | Cannot parse date '' — skipping row
Row   8 | NEGATIVE_AMOUNT                | IMPORT_AS_REFUND     | [PENDING] | Negative amount -500.0 for 'Groceries week 3' — treating as refund
Row   8 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-02-20 — excluded from split
Row   9 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-02-22 — excluded from split
Row  10 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-01 — excluded from split
Row  11 | AMOUNT_WITH_SYMBOL             | AUTO_FIXED           | [PENDING] | AMOUNT_WITH_SYMBOL: stripped currency symbol from '₹3800'
Row  11 | DUPLICATE                      | PENDING_REVIEW       | [PENDING] | 'Dinner at Spice Garden' (₹3800.0) appears to duplicate row 5 (₹3200.0). User must decide which to keep.
Row  11 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-02-10 — excluded from split
Row  12 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-05 — excluded from split
Row  13 | INCONSISTENT_DATE              | AUTO_FIXED           | [PENDING] | INCONSISTENT_DATE: non-ISO date format '05-03-2024' normalised
Row  13 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-05 — excluded from split
Row  14 | CURRENCY_USD                   | AUTO_CONVERT         | [PENDING] | Amount 4500.0 USD will be converted to INR at documented rate
Row  14 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-10 — excluded from split
Row  15 | CURRENCY_USD                   | AUTO_CONVERT         | [PENDING] | Amount 1200.0 USD will be converted to INR at documented rate
Row  15 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-10 — excluded from split
Row  16 | CURRENCY_USD                   | AUTO_CONVERT         | [PENDING] | Amount 800.0 USD will be converted to INR at documented rate
Row  16 | WRONG_SPLIT_LABEL              | AUTO_FIXED           | [PENDING] | WRONG_SPLIT_LABEL: '50/50' normalised to 'equal'
Row  16 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-12 — excluded from split
Row  17 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-15 — excluded from split
Row  18 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-20 — excluded from split
Row  19 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-22 — excluded from split
Row  20 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-28 — excluded from split
Row  20 | BAD_PERCENTAGE_SUM             | AUTO_NORMALIZE       | [PENDING] | Percentages sum to 90.0% (not 100%) — normalised proportionally
Row  21 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2024-04-01 — excluded from split
Row  21 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-04-01 — excluded from split
Row  22 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2024-04-02 — excluded from split
Row  22 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-04-02 — excluded from split
Row  23 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2024-04-05 — excluded from split
Row  23 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-04-05 — excluded from split
Row  24 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-15 — excluded from split
Row  25 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2024-04-10 — excluded from split
Row  25 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-04-10 — excluded from split
Row  26 | ZERO_AMOUNT                    | SKIP                 | [PENDING] | Amount is zero for 'Lunch special' — skipping row
Row  26 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2024-04-12 — excluded from split
Row  26 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-04-12 — excluded from split
Row  27 | FUTURE_DATE                    | IMPORT_WITH_FLAG     | [PENDING] | Expense dated 2026-12-25 is in the future
Row  27 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2026-12-25 — excluded from split
Row  28 | INCONSISTENT_DATE              | AUTO_FIXED           | [PENDING] | INCONSISTENT_DATE: non-ISO date format '2024/03/08' normalised
Row  28 | PRE_JOIN                       | EXCLUDE_FROM_SPLIT   | [PENDING] | Sam joined on 2024-04-15 but expense date is 2024-03-08 — excluded from split
Row  29 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2024-04-20 — excluded from split
Row  30 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2024-04-25 — excluded from split
Row  31 | POST_DEPARTURE                 | EXCLUDE_FROM_SPLIT   | [PENDING] | Meera left on 2024-03-31 but expense date is 2024-04-30 — excluded from split