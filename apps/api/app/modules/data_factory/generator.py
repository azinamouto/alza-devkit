
import random
from typing import Literal

from faker import Faker

from .schemas import HouseholdRecord


BARANGAYS = [
    "Fictional Sample Barangay A",
    "Fictional Sample Barangay B",
    "Fictional Sample Barangay C",
    "Fictional Sample Barangay D",
]

IncomeCategory = Literal["Low", "Middle", "High"]


def generate_households(
    count: int = 100,
    seed: int = 42,
) -> list[HouseholdRecord]:
    """Generate synthetic records. Income thresholds are illustrative, not official."""
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError("Record count must be an integer between 1 and 1,000.")
    if type(seed) is not int or seed < 0:
        raise ValueError("Seed must be a non-negative integer.")
    fake = Faker("en_PH")
    fake.seed_instance(seed)
    rng = random.Random(seed)

    households: list[HouseholdRecord] = []

    for index in range(1, count + 1):
        household_size = rng.randint(1, 12)
        monthly_income = rng.randint(3000, 80000)

        if monthly_income < 12000:
            income_category: IncomeCategory = "Low"
        elif monthly_income < 40000:
            income_category: IncomeCategory = "Middle"
        else:
            income_category: IncomeCategory = "High"

        household: HouseholdRecord = {
            "household_id": f"HH-{index:05d}",
            "household_head": fake.name(),
            "barangay": rng.choice(BARANGAYS),
            "household_size": household_size,
            "monthly_income": monthly_income,
            "income_category": income_category,
        }

        households.append(household)

    return households
