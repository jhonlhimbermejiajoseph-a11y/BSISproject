"""Subsidy rules. Change the percentages below to match your barangay's policy."""

CATEGORIES = ["Regular", "Senior Citizen", "PWD", "Low-income"]

# Share of the medicine cost that the barangay covers (0.50 = 50%).
SUBSIDY_RATES = {
    "Regular": 0.00,
    "Senior Citizen": 0.50,
    "PWD": 0.50,
    "Low-income": 0.80,
}


def subsidy_rate(category):
    return SUBSIDY_RATES.get(category, 0.0)


def calculate(unit_price, quantity, category):
    """Return gross, rate, subsidy and the amount the resident still pays."""
    gross = round(unit_price * quantity, 2)
    rate = subsidy_rate(category)
    subsidy = round(gross * rate, 2)
    return {"gross": gross, "rate": rate, "subsidy": subsidy, "total": round(gross - subsidy, 2)}