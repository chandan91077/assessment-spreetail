# Spreetail — Shared Expenses App

A clean, deliberate shared-expenses application built for four flatmates (Aisha, Rohan, Priya, Meera) and two joiners/leavers (Sam, Dev). It ingests a messy historical CSV, detects anomalies, and provides transparent balance summaries.

## Quick Start (Local)

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
cd spreetail
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000 in your browser.

### Pre-seeded Accounts

| Username | Password | Display Name |
|----------|----------|--------------|
| aisha    | password123 | Aisha |
| rohan    | password123 | Rohan |
| priya    | password123 | Priya |
| meera    | password123 | Meera |
| sam      | password123 | Sam |

## First Steps

1. **Login** as any flatmate
2. **Create a group** (e.g. "The Flat") via Groups → New Group
3. **Add members** with their correct join/leave dates:
   - Aisha, Rohan, Priya, Meera: joined 2024-02-01
   - Meera: left 2024-03-31
   - Sam: joined 2024-04-15
4. **Import the CSV** via Import CSV → select your group → upload `expenses_export.csv`
5. **Review anomalies** in the import report — approve, reject, or flag each one
6. **Check Balances** for the who-owes-whom summary
7. **Record settlements** when someone pays up

## Project Structure

```
spreetail/
├── app.py                  # Flask factory, DB init, seed users
├── models.py               # SQLAlchemy ORM (8 tables)
├── routes/
│   ├── auth.py             # Login / Register / Logout
│   ├── groups.py           # Group CRUD + membership timeline
│   ├── expenses.py         # Expense CRUD, 4 split types
│   ├── settlements.py      # Settlements + balance computation
│   └── imports.py          # CSV upload + anomaly review
├── services/
│   ├── csv_importer.py     # 14-rule anomaly engine
│   ├── balance_calculator.py # Net balance + minimal transactions
│   └── fx.py               # USD→INR static rate conversion
├── templates/index.html    # SPA (single-page app)
├── static/
│   ├── style.css           # Dark glassmorphism design system
│   └── app.js              # Vanilla JS, no frameworks
├── expenses_export.csv     # Test CSV with 14 deliberate anomalies
├── requirements.txt
├── README.md
├── SCOPE.md
├── DECISIONS.md
└── AI_USAGE.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/auth/login | Login |
| POST | /api/auth/register | Register |
| GET | /api/auth/me | Current user |
| GET | /api/groups/ | List groups |
| POST | /api/groups/ | Create group |
| POST | /api/groups/{id}/members | Add member |
| POST | /api/groups/{id}/members/{uid}/leave | Remove member |
| GET | /api/expenses/group/{id} | List expenses |
| POST | /api/expenses/ | Create expense |
| PUT | /api/expenses/{id} | Update expense |
| DELETE | /api/expenses/{id} | Delete expense |
| GET | /api/settlements/group/{id}/balances | Balances + minimal transactions |
| POST | /api/settlements/ | Record settlement |
| POST | /api/imports/upload | Upload CSV |
| GET | /api/imports/sessions/{id}/report | Import report text |
| POST | /api/imports/anomalies/{id}/resolve | Resolve anomaly |

## AI Tool Used

**Antigravity (Google DeepMind)** — see AI_USAGE.md for full details.
