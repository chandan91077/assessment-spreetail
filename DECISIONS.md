# DECISIONS.md — Engineering Decision Log

Each significant decision is documented with the options considered and the rationale for the choice made.

---

## D1: Tech Stack — Flask + SQLite vs. alternatives

**Decision**: Flask (Python) + SQLite + SQLAlchemy + Vanilla JS SPA

**Options considered**:
| Option | Pros | Cons |
|--------|------|------|
| Flask + SQLite | Lightweight, zero infra, Python readable, great for live code review | Not horizontally scalable |
| FastAPI + PostgreSQL | Async, production-ready | Heavier setup, PostgreSQL requires a running server |
| Node.js + Express | JS full-stack | Python is better for data-heavy importer logic |
| Django | Batteries included | Too much magic for a 2-day build; harder to trace in a live session |

**Why Flask + SQLite**: The assignment explicitly says "relational DBs only" — SQLite qualifies. The live session will involve reading code line-by-line; Flask's explicit routing makes every HTTP call easy to trace. SQLite is file-based, so there is zero infra to set up. The importer is Python-heavy (dateutil, regex, Decimal arithmetic), so Python is the natural choice.

---

## D2: Balance Storage — Computed vs. Cached

**Decision**: Balances are NEVER stored in the database. They are computed fresh on every `/balances` request.

**Options considered**:
| Option | Pros | Cons |
|--------|------|------|
| Always compute | Always correct; no sync bugs | Slightly more computation |
| Cache in DB | Faster reads | Can go stale; requires invalidation logic |
| Materialised view | DB-native caching | SQLite doesn't support materialised views |

**Why always compute**: For a flat of 5 people and a few dozen expenses, the computation is microseconds. Caching introduces a class of bugs (stale cache after edit/delete) with zero benefit at this scale. The live session may ask "walk me through the balance calculation" — a fresh computation is trivially traceable.

---

## D3: Duplicate Detection — Which Row Wins?

**Decision**: Neither row is auto-selected. Both are held in PENDING_REVIEW and the user (Meera, the "data steward" per the brief) decides.

**Options considered**:
| Option | Rationale |
|--------|-----------|
| Keep first row | Arbitrary; the first logger isn't always correct |
| Keep highest amount | Biases toward overpayment |
| Keep latest row | Biases toward the last person to log |
| Ask the user | Correct — but adds friction |

**Why ask the user**: The assignment explicitly says "Meera: I want to approve anything the app deletes or changes." A duplicate deletion is exactly the kind of action that needs her approval. Silently picking a winner violates Meera's requirement.

---

## D4: Currency Conversion — Static Rate vs. Live API

**Decision**: Static rate table (USD→INR indexed by year-month).

**Options considered**:
| Option | Pros | Cons |
|--------|------|------|
| Live API (e.g. exchangerate.host) | Accurate today's rate | Requires network, API key; gives the WRONG rate for historical dates |
| Static constant (83.0) | Simple | Slightly less accurate |
| Static rate table by month | Good approximation; auditable; no external dependency | Slightly more code |

**Why static rate table**: Historical expenses need historical rates. A live API would give today's exchange rate for a March 2024 expense — which is wrong. Our rate table approximates the actual March 2024 USD/INR rate (~83.20). The rate used is stored in `expenses.fx_rate_used` so every conversion is fully auditable.

---

## D5: Minimal Transactions Algorithm

**Decision**: Greedy creditor-debtor matching.

**Options considered**:
| Option | Complexity | Quality |
|--------|-----------|---------|
| Greedy (largest creditor ↔ largest debtor) | O(n log n) | Near-optimal; correct |
| Integer programming (true optimal) | NP-hard | Overkill for n ≤ 10 |
| Simple pairwise (everyone pays everyone) | O(n²) | Maximum transactions |

**Why greedy**: For a group of ≤ 10 people, the greedy algorithm produces optimal or near-optimal results and is O(n log n). The true optimal (min cut / integer program) is NP-hard and unnecessary at this scale. The greedy approach is also easy to explain line-by-line in a live session.

**Implementation detail**: We work in integer paise (1 INR = 100 paise) to avoid floating-point rounding errors in the greedy matching.

---

## D6: Date Parsing — dateutil vs. custom regex

**Decision**: `python-dateutil` for all date parsing.

**Options considered**:
| Option | Pros | Cons |
|--------|------|------|
| Custom regex per format | Full control | Misses edge cases; more code |
| dateutil.parser.parse | Handles 50+ formats; battle-tested | Occasional ambiguity (dayfirst) |
| strptime with multiple formats | Explicit | Verbose; need to enumerate all formats |

**Why dateutil**: The CSV has three distinct date formats already identified. dateutil handles all three. We explicitly flag non-ISO formats as INCONSISTENT_DATE anomalies so the original format is never silently lost.

**Ambiguity handling**: For "05-03-2024", dateutil with `dayfirst=False` would parse as May 3, not March 5. We detect this case and re-parse with `dayfirst=True`, logging a warning.

---

## D7: Post-Departure and Pre-Join Splits

**Decision**: Exclude departed/not-yet-joined members from splits; split among active members only.

**Options considered**:
| Option | Fairness |
|--------|---------|
| Include everyone (ignore dates) | Unfair — charges people for periods they weren't present |
| Exclude and adjust proportionally | Fair and correct |
| Prorate by days present | Most precise but complex for equal splits |

**Why exclude and adjust**: The assignment explicitly states Sam's concern about March electricity. The fairest approach is binary: if you were in the flat on the expense date, you share it equally; if not, you don't. Prorating by days would require knowing exact move-in times, which the CSV doesn't provide.

**Implementation**: `Group.active_members_on(date)` encapsulates the membership query. The importer calls this for every expense and builds an `excluded_members` set.

---

## D8: Settlement Reclassification

**Decision**: Detect settlement-like descriptions and reclassify as Settlement records, not Expense records.

**Options considered**:
| Option | Problem |
|--------|---------|
| Import as expense | Double-counts the debt (inflates balances) |
| Skip the row | Loses the settlement from balance calculation |
| Reclassify as Settlement | Correct — preserves the data in the right table |

**Why reclassify**: A settlement is not an expense. Storing "Rohan pays Aisha back" as an Expense would make Rohan's balance appear worse than it is. The Settlement table is specifically designed for this case.

---

## D9: Zero-Amount Expenses

**Decision**: Skip silently (log as warning, not imported).

**Rationale**: A ₹0 expense has no financial effect. Its only effect would be cluttering the expense list and adding ₹0 split rows to the database. The anomaly is logged so it's visible, but not imported.

---

## D10: Unknown Members (Dev)

**Decision**: Create a read-only guest account.

**Options considered**:
| Option | Problem |
|--------|---------|
| Skip rows with unknown members | Loses real trip expenses |
| Assign to a default user | Wrong payer attribution |
| Create guest account | Preserves data; makes anomaly visible |

**Why guest account**: Dev paid real money on the trip. Dropping his rows would undercount trip expenses. A guest account with `password_hash = "GUEST_NO_LOGIN"` preserves the data while making clear this is a provisional record awaiting resolution (e.g. merging with an existing user, or leaving as-is since Dev was a one-time guest).
