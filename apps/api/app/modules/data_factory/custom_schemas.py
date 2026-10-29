"""Strict, bounded schemas shared by generation and durable templates."""
from datetime import date, datetime
import math
from typing import Literal
from uuid import UUID

from faker.config import AVAILABLE_LOCALES
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Options(StrictModel):
    min: float = Field(default=0, ge=-1e9, le=1e9)
    max: float = Field(default=100, ge=-1e9, le=1e9)
    precision: int = Field(default=2, ge=0, le=6)
    distribution: Literal["uniform"] = "uniform"
    min_length: int = Field(default=5, ge=0, le=256)
    max_length: int = Field(default=20, ge=0, le=256)
    prefix: str = Field(default="", max_length=64)
    suffix: str = Field(default="", max_length=64)
    values: list[str] = Field(default_factory=list, max_length=500)
    weights: list[float] | None = Field(default=None, max_length=500)
    min_date: date = date(2000, 1, 1)
    max_date: date = date(2025, 12, 31)
    format: Literal["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"] = "%Y-%m-%d"
    start: int = Field(default=1, ge=-1_000_000_000, le=1_000_000_000)
    step: int = Field(default=1, ge=-1_000_000, le=1_000_000)
    padding: int = Field(default=5, ge=0, le=20)

    @model_validator(mode="after")
    def bounds(self):
        if self.min > self.max or self.min_length > self.max_length or self.min_date > self.max_date:
            raise ValueError("Minimum must not exceed maximum")
        if any(len(v) > 256 for v in self.values) or len(set(self.values)) != len(self.values):
            raise ValueError("Enum values must be distinct and at most 256 characters")
        if self.weights is not None and (
            len(self.weights) != len(self.values)
            or any(w < 0 for w in self.weights)
            or not math.isfinite(sum(self.weights))
            or sum(self.weights) <= 0
        ):
            raise ValueError("Weights must match values, be non-negative, and have a positive total")
        return self


class Computation(StrictModel):
    operation: Literal["multiply", "age", "full_name"]
    sources: list[str] = Field(min_length=1, max_length=2)
    reference_date: date | None = None

    @model_validator(mode="after")
    def parameters(self):
        if len(self.sources) != (1 if self.operation == "age" else 2):
            raise ValueError("Incorrect number of computed sources")
        if self.operation == "age" and self.reference_date is None:
            raise ValueError("Age requires a reference date")
        return self


class CustomField(StrictModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    label: str = Field(default="", max_length=100)
    type: str = Field(max_length=40)
    required: bool = True
    unique: bool = False
    default: str | int | float | bool | None = None
    null_probability: float = Field(default=0, ge=0, le=1)
    options: Options = Field(default_factory=Options)
    computed: Computation | None = None

    @model_validator(mode="after")
    def validate_field(self):
        from .field_registry import REGISTRY, NUMERIC, INTEGER, DATES, SEQUENCES
        if self.type not in REGISTRY and self.type != "computed":
            raise ValueError("Unsupported field type")
        if (self.type == "computed") != (self.computed is not None):
            raise ValueError("Computed fields require an allowlisted computation")
        if self.required and self.null_probability:
            raise ValueError("Required fields cannot have a null probability")
        if self.type == "enum" and not self.options.values:
            raise ValueError("Enum requires values")
        if self.type in INTEGER and (
            not float(self.options.min).is_integer()
            or not float(self.options.max).is_integer()
        ):
            raise ValueError("Integer bounds must be whole numbers")
        if self.type in SEQUENCES and self.unique and self.options.step == 0:
            raise ValueError("Unique sequences require a nonzero increment")
        if self.type in {"household_size", "grade_level"}:
            if "min" not in self.options.model_fields_set:
                self.options.min = 1
            if "max" not in self.options.model_fields_set:
                self.options.max = 12
        if self.type in {"quantity", "price", "household_size", "grade_level"} and self.options.min < 0:
            raise ValueError("This field requires non-negative numeric bounds")
        if self.options.min > self.options.max:
            raise ValueError("Minimum must not exceed maximum")
        if self.default is not None:
            v = self.default
            if self.type == "computed":
                raise ValueError("Computed fields cannot have defaults")
            if self.type in NUMERIC:
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not self.options.min <= v <= self.options.max:
                    raise ValueError("Default must satisfy numeric bounds")
                if self.type in INTEGER and int(v) != v:
                    raise ValueError("Default must be an integer")
            elif self.type == "boolean":
                if not isinstance(v, bool):
                    raise ValueError("Boolean default must be true or false")
            elif not isinstance(v, str) or len(v) > 384:
                raise ValueError("Default must be a string of at most 384 characters")
            if self.type == "enum" and v not in self.options.values:
                raise ValueError("Default must be an enum value")
            if self.type == "string" and not self.options.min_length <= len(v) <= self.options.max_length:
                raise ValueError("Default must satisfy string length bounds")
            if self.type == "uuid":
                try:
                    UUID(v)
                except ValueError:
                    raise ValueError("UUID default must be a valid UUID") from None
            if self.type in DATES:
                try:
                    parsed = datetime.strptime(v, self.options.format).date()
                except (ValueError, TypeError):
                    raise ValueError("Date default must match output format") from None
                if not self.options.min_date <= parsed <= self.options.max_date:
                    raise ValueError("Date default must satisfy date bounds")
        return self


class TemplateInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    version: Literal[1] = 1
    locale: str = "en_PH"
    fields: list[CustomField] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_template(self):
        from .custom_generator import dependency_order
        if not self.name.strip():
            raise ValueError("Dataset name cannot be blank")
        if self.locale not in AVAILABLE_LOCALES:
            raise ValueError("Unsupported Faker locale")
        dependency_order(self.fields)
        return self


class SavedTemplate(TemplateInput):
    id: UUID


class GenerateRequest(StrictModel):
    template: TemplateInput
    count: int = Field(default=100, ge=1, le=1000, strict=True)
    seed: int = Field(default=42, ge=0, le=9007199254740991, strict=True)


class CustomDataset(StrictModel):
    total_records: int
    seed: int
    fields: list[str]
    data: list[dict[str, str | int | float | bool | None]]


class ValidationResult(StrictModel):
    valid: bool = True
    message: str = "Schema and generation constraints are valid."
