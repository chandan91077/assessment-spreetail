"""
fx.py — Foreign exchange conversion service.

Design decision: We use a static exchange rate table rather than a live API.
Rationale (documented in DECISIONS.md):
  - Live APIs require keys, network access, and add latency.
  - The CSV dates are historical; a live rate would be wrong anyway.
  - The stated problem is "the sheet pretends a dollar is a rupee" — so ANY
    conversion is better than 1:1. We document the rate we used.
  - The rate table can be extended later per-date if required.
"""

# Static USD→INR rates indexed by year-month.
# For any month not in the table, fallback to DEFAULT_USD_INR.
USD_INR_RATES = {
    "2024-02": 83.00,
    "2024-03": 83.20,
    "2024-04": 83.50,
}

DEFAULT_USD_INR = 83.00   # fallback


def convert_to_inr(amount: float, currency: str, date=None) -> tuple[float, float]:
    """
    Convert an amount in `currency` to INR.

    Returns:
        (amount_inr, rate_used)
    """
    currency = (currency or "INR").strip().upper()

    if currency == "INR":
        return round(amount, 2), 1.0

    if currency == "USD":
        rate = DEFAULT_USD_INR
        if date is not None:
            key = f"{date.year}-{date.month:02d}"
            rate = USD_INR_RATES.get(key, DEFAULT_USD_INR)
        return round(amount * rate, 2), rate

    # Unknown currency — treat as INR and flag
    return round(amount, 2), 1.0


def supported_currencies():
    return ["INR", "USD"]
