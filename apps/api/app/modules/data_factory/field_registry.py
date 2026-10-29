"""Generators take an isolated context, field, and zero-based row index."""
import string
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Callable
from uuid import UUID

INTEGER = {"integer", "quantity", "household_size", "grade_level"}
NUMERIC = INTEGER | {"decimal", "price"}
DATES = {"date", "datetime", "birth_date", "transaction_date"}
SEQUENCES = {"sequence", "student_id", "employee_id", "transaction_id"}
FICTIONAL_BARANGAYS = ["Fictional Maligaya", "Fictional Mabuhay", "Fictional Liwanag"]


@dataclass(frozen=True)
class FieldGenerator:
    generate: Callable
    domain: Callable = lambda field: None


REGISTRY: dict[str, FieldGenerator] = {}


def register(name, generate, domain=lambda field: None):
    if name in REGISTRY:
        raise ValueError(f"Generator already registered: {name}")
    REGISTRY[name] = FieldGenerator(generate, domain)


def numeric_limits(field):
    o = field.options
    scale = 1 if field.type in INTEGER else 10 ** o.precision
    low = int((Decimal(str(o.min)) * scale).to_integral_value(rounding=ROUND_CEILING))
    high = int((Decimal(str(o.max)) * scale).to_integral_value(rounding=ROUND_FLOOR))
    return low, high, scale

def number(ctx, field, index):
    low, high, scale = numeric_limits(field)
    value = ctx.rng.randint(low, high)
    return value if field.type in INTEGER else value / scale


def date_value(ctx, field, index):
    o = field.options
    days = (o.max_date - o.min_date).days
    value = datetime.combine(o.min_date + timedelta(days=ctx.rng.randint(0, days)), time())
    if field.type == "datetime":
        value += timedelta(seconds=ctx.rng.randrange(86400))
    return value.strftime(o.format)


for kind in NUMERIC:
    register(kind, number, lambda f: max(0, numeric_limits(f)[1] - numeric_limits(f)[0] + 1))
for kind in DATES:
    register(kind, date_value, lambda f: ((f.options.max_date - f.options.min_date).days + 1) * (86400 if f.type == "datetime" and "H" in f.options.format else 1))
for kind in SEQUENCES:
    register(kind, lambda c, f, i: f"{f.options.prefix}{f.options.start + i * f.options.step:0{f.options.padding}d}{f.options.suffix}", lambda f: 1 if f.options.step == 0 else None)
register("string", lambda c, f, i: f.options.prefix + "".join(c.rng.choices(string.ascii_letters, k=c.rng.randint(f.options.min_length, f.options.max_length))) + f.options.suffix,
         lambda f: sum(52 ** n for n in range(f.options.min_length, f.options.max_length + 1)))
register("boolean", lambda c, f, i: bool(c.rng.getrandbits(1)), lambda f: 2)
register("uuid", lambda c, f, i: str(UUID(int=c.rng.getrandbits(128), version=4)))
register("enum", lambda c, f, i: c.rng.choices(f.options.values, weights=f.options.weights, k=1)[0],
         lambda f: sum(w > 0 for w in f.options.weights) if f.options.weights is not None else len(f.options.values))
register("barangay", lambda c, f, i: c.rng.choice(FICTIONAL_BARANGAYS), lambda f: len(FICTIONAL_BARANGAYS))
register("product_name", lambda c, f, i: c.rng.choice(["Sample Notebook", "Demo Keyboard", "Test Backpack", "Sample Pen"]), lambda f: 4)
register("sku", lambda c, f, i: "SYN-" + f"{c.rng.getrandbits(48):012X}")
register("school_year", lambda c, f, i: f"{(year := c.rng.randint(2000, 2030))}-{year + 1}", lambda f: 31)
for kind, method in {
    "full_name": "name", "first_name": "first_name", "last_name": "last_name",
    "email": "ascii_safe_email", "phone_number": "phone_number", "street_address": "street_address",
    "city": "city", "postal_code": "postcode", "company_name": "company",
}.items():
    register(kind, lambda c, f, i, method=method: getattr(c.faker, method, getattr(c.fallback, method))())
