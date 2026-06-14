# SCOPE.md — Anomaly Log & Database Schema

## Database Schema

### users
| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| id | INTEGER | PK | |
| username | TEXT | UNIQUE NOT NULL | Login identifier |
| password_hash | TEXT | NOT NULL | Werkzeug pbkdf2 |
| display_name | TEXT | NOT NULL | Shown in UI |
| created_at | DATETIME | | |

### groups
| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | e.g. "The Flat" |
| description | TEXT | | |
| created_at | DATETIME | | |

### group_members
| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| id | INTEGER | PK | |
| group_id | INTEGER | FK → groups | |
| user_id | INTEGER | FK → users | |
| joined_at | DATE | NOT NULL | Membership start |
| left_at | DATE | NULL = active | Membership end |

**Key design**: `joined_at` and `left_at` enable date-aware split exclusion. Querying "who was in the group on date X" is a single range query.

### expenses
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | |
| group_id | FK → groups | |
| description | TEXT | |
| amount_inr | DECIMAL(12,2) | Always INR — canonical store |
| original_amount | DECIMAL(12,2) | Raw CSV value |
| original_currency | TEXT | INR / USD |
| fx_rate_used | DECIMAL(10,4) | Rate applied at import time |
| date | DATE | |
| paid_by_id | FK → users | NULL = unresolved import |
| split_type | TEXT | equal/exact/percentage/shares |
| is_settlement | BOOLEAN | Settlements are not expenses |
| import_source | TEXT | 'manual' or 'csv_import' |
| import_session_id | FK → import_sessions | Traceability |
| notes | TEXT | Anomaly notes |

### expense_splits
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | |
| expense_id | FK → expenses | |
| user_id | FK → users | |
| amount_owed | DECIMAL(12,2) | Final INR owed by this user |
| split_value | DECIMAL(10,4) | Raw % / share count / exact amt |

**Key design**: One row per person per expense. `amount_owed` is the authoritative value; `split_value` is the raw input for auditability.

### settlements
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | |
| group_id | FK → groups | |
| payer_id | FK → users | Who transferred money |
| payee_id | FK → users | Who received money |
| amount_inr | DECIMAL(12,2) | |
| date | DATE | |
| notes | TEXT | |

### import_sessions
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | |
| filename | TEXT | |
| imported_at | DATETIME | |
| total_rows | INTEGER | |
| imported_count | INTEGER | |
| skipped_count | INTEGER | |
| pending_review_count | INTEGER | |
| group_id | FK → groups | |
| status | TEXT | pending / complete |

### import_anomalies
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | |
| session_id | FK → import_sessions | |
| row_number | INTEGER | 1-indexed, header = row 1 |
| raw_row | TEXT (JSON) | Original CSV row as JSON |
| anomaly_type | TEXT | See table below |
| description | TEXT | Human-readable explanation |
| suggested_action | TEXT | System recommendation |
| user_decision | TEXT | NULL until reviewed |
| resolved | BOOLEAN | |

---

## Anomaly Log: All 14 Deliberate Data Problems

### Anomaly 1 — DUPLICATE (Row 4 and Row 10)
**Problem**: "Dinner at Spice Garden" appears twice: Row 4 (Meera, ₹3200) and Row 10 (Rohan, ₹3800). Same event, different payers and amounts.

**Detection**: The importer maintains a `seen_descriptions` dict mapping description → (row_num, amount). On second occurrence, flags DUPLICATE.

**Policy**: Both rows are held in PENDING_REVIEW state. The user (Meera, per the brief) must approve one and reject the other. The importer does NOT silently pick a winner.

**Rationale**: Two people logging the same dinner with different amounts is a genuine ambiguity. Silent resolution (keep first, keep highest) would be wrong either way. User decides.

---

### Anomaly 2 — NEGATIVE_AMOUNT (Row 7)
**Problem**: Groceries row has amount = -500. Could be a data entry error or a genuine refund/rebate.

**Detection**: `amount < 0` check after parsing.

**Policy**: Treat as refund. Import as a negative expense (effectively a credit). Flag it with type NEGATIVE_AMOUNT so the user can see it in the report. A refund means the payer *receives* money from the group rather than paying out.

**Rationale**: Silent skip loses data. Silent treat-as-positive reverses intent. Treating as refund is the most semantically correct interpretation of a negative amount in a shared-expense context.

---

### Anomaly 3 — CURRENCY_USD (Rows 13, 14, 15)
**Problem**: Three trip expenses have currency=USD. The original spreadsheet treated USD amounts as if they were INR (i.e., $4500 was recorded as ₹4500, which is wrong).

**Detection**: `currency.upper() == 'USD'`

**Policy**: Automatically convert USD → INR using the documented static rate table (2024-03: 83.20). Log the conversion in the anomaly report and in the expense's `fx_rate_used` field. The original USD amount is preserved in `original_amount`.

**Conversion rates used**:
- 2024-02: 83.00 INR/USD
- 2024-03: 83.20 INR/USD
- 2024-04: 83.50 INR/USD

**Rationale**: Any conversion is better than treating $1 = ₹1. We use a static table rather than a live API because (a) the dates are historical, (b) a live API would give today's rate which is also wrong, and (c) the rate is documented so it's auditable.

---

### Anomaly 4 — SETTLEMENT_AS_EXPENSE (Row 18)
**Problem**: Row 18 describes "Rohan pays Aisha back" — a settlement, not an expense. If treated as an expense, it would double-count Rohan's debt.

**Detection**: Description contains keywords from `SETTLEMENT_KEYWORDS` list (e.g. "pays back", "settles", "repays").

**Policy**: Reclassify as a Settlement record. The expense is not created. The split_details column (Aisha:2500) is used to identify the payee.

**Rationale**: Settlements must be tracked separately from expenses to avoid corrupting balance calculations.

---

### Anomaly 5 — POST_DEPARTURE (Row 21)
**Problem**: Row 21 is an electricity bill for April 2024, but Meera left on March 31. Including her in the split would charge her for a period when she no longer lived in the flat.

**Detection**: At import time, the importer checks `group_members.left_at < expense.date` for each member. If true, that member is flagged as POST_DEPARTURE and excluded from the split.

**Policy**: Exclude Meera from the April electricity split. Split the cost among the remaining active members (Aisha, Rohan, Priya, Sam).

**Rationale**: Charging someone for expenses after they moved out is unfair and incorrect.

---

### Anomaly 6 — PRE_JOIN (Row 23)
**Problem**: Row 23 is the March internet bill, but Sam joined on April 15. Sam had no obligation for March expenses.

**Detection**: `group_members.joined_at > expense.date` for a member who appears in the CSV.

**Policy**: Exclude Sam from splits on expenses dated before their join date.

**Rationale**: Sam paying March rent would be equivalent to paying for a flat they didn't live in yet.

---

### Anomaly 7 — MISSING_PAID_BY (Row 6)
**Problem**: Row 6 (Water bill February) has an empty `paid_by` field. Without a payer, balance calculation is impossible.

**Detection**: `paid_by` field is blank or whitespace-only.

**Policy**: Hold in PENDING_REVIEW. The expense is not imported until a user assigns the payer. This prevents silent creation of an unattributed expense.

**Rationale**: Guessing the payer (e.g. defaulting to the current user) would corrupt balances silently.

---

### Anomaly 8 — UNKNOWN_MEMBER (Row 14)
**Problem**: "Dev" appears as the payer for weekend trip meals. Dev is not a registered flatmate.

**Detection**: `paid_by` name not found in `user_by_name` lookup.

**Policy**: Create a read-only guest account for Dev. The expense is imported with Dev as payer. The anomaly is flagged so the admin can later merge Dev's account with an existing user or leave it as a guest.

**Rationale**: Dev participated in real spending. Dropping the expense loses real money. Creating a guest account preserves the data while making the anomaly visible.

---

### Anomaly 9 — INCONSISTENT_DATE (Rows 3, 12, 27)
**Problem**: Three different date formats appear:
- Row 3: "March 5 2024" (plain English)
- Row 12: "05-03-2024" (DD-MM-YYYY)
- Row 27: "2024/03/08" (YYYY/MM/DD with slashes)

**Detection**: Any date that doesn't match `YYYY-MM-DD` ISO format.

**Policy**: Parse using `python-dateutil` which handles all three formats. Normalise to `date` object and store as ISO. Flag the original format in the anomaly report.

**Rationale**: Losing rows due to date format differences is unacceptable. `dateutil` is a well-tested library for exactly this purpose.

---

### Anomaly 10 — AMOUNT_WITH_SYMBOL (Row 10)
**Problem**: Row 10 has amount = "₹3800" — the rupee symbol is embedded in the amount field.

**Detection**: Regex check for `₹`, `$`, `£`, `€` in the amount string.

**Policy**: Strip the symbol using regex, parse the remaining string as float. Flag as AUTO_FIXED.

**Rationale**: This is a trivially fixable formatting error. Stripping symbols is safe and unambiguous.

---

### Anomaly 11 — WRONG_SPLIT_LABEL (Row 15)
**Problem**: Row 15 uses split type "50/50" instead of the canonical "equal".

**Detection**: Normalisation table `SPLIT_LABEL_MAP` maps known variants to canonical labels.

**Policy**: Normalise "50/50" → "equal". Log as AUTO_FIXED.

**Rationale**: The intent is clear. Rejecting the row for a cosmetic formatting difference would be overly strict.

---

### Anomaly 12 — ZERO_AMOUNT (Row 25)
**Problem**: Row 25 has amount = 0.

**Detection**: `amount == 0` check after parsing.

**Policy**: Skip the row. A zero-amount expense has no financial impact and is almost certainly a data entry error.

**Rationale**: Importing a ₹0 expense would create split rows with ₹0 each, adding noise without value.

---

### Anomaly 13 — FUTURE_DATE (Row 26)
**Problem**: Row 26 has a date in 2026 — clearly a future date relative to the February–April 2024 timeline.

**Detection**: `parsed_date > date.today()`

**Policy**: Import the row with a FUTURE_DATE flag in the anomaly report. Do not block the import — the user may have intentionally pre-logged an expense.

**Rationale**: A future date is suspicious but not definitively wrong. We surface it and let the user decide.

---

### Anomaly 14 — BAD_PERCENTAGE_SUM (Row 19)
**Problem**: Row 19 splits by percentage: Aisha 30%, Rohan 30%, Priya 30% = 90%, not 100%.

**Detection**: `sum(percentages) != 100` within tolerance of 0.01.

**Policy**: Normalise proportionally: each percentage is rescaled by `100 / sum`. In this case, each 30% becomes 33.33%. Flag as AUTO_NORMALIZE.

**Rationale**: The relative proportions (equal thirds) are clear from the data. Rejecting the row or silently losing 10% would both be wrong.
