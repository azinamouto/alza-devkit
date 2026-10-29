"""In-memory exports of synthetic household records."""

import csv
import json
from io import BytesIO, StringIO
from typing import Literal

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from .schemas import HouseholdDataset

ExportFormat = Literal["csv", "json", "xlsx"]
FIELDS = (
    "household_id", "household_head", "barangay", "household_size",
    "monthly_income", "income_category",
)
MIME_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def spreadsheet_safe(value: str | int) -> str | int:
    """Neutralize formulas, including prefixes hidden behind whitespace/control chars."""
    if isinstance(value, str):
        stripped = value.lstrip("".join(chr(n) for n in range(33)) + "\ufeff")
        if stripped.startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
            return "'" + value
    return value


def export_households(dataset: HouseholdDataset, format: ExportFormat) -> bytes:
    return export_records(dataset.model_dump(), list(FIELDS), format, "Synthetic households")


def export_records(dataset: dict, fields: list[str], format: ExportFormat, title: str = "Synthetic dataset") -> bytes:
    if not dataset or "data" not in dataset:
        raise ValueError("Invalid dataset: missing data field")
    if not fields:
        raise ValueError("Field list cannot be empty")

    if format == "json":
        return json.dumps(dataset, ensure_ascii=False, indent=2).encode("utf-8")

    rows = [
        [spreadsheet_safe(record[field]) for field in fields]
        for record in dataset["data"]
    ]
    if format == "csv":
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow([spreadsheet_safe(field) for field in fields])
        writer.writerows(rows)
        return output.getvalue().encode("utf-8-sig")
    if format != "xlsx":
        raise ValueError(f"Unsupported export format: {format}")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    sheet.append([spreadsheet_safe(field) for field in fields])
    for row in rows:
        # XML cannot represent certain control characters; normalize line endings
        # explicitly so the saved workbook has a predictable round trip.
        sheet.append([
            spreadsheet_safe(ILLEGAL_CHARACTERS_RE.sub("", value).replace("\r\n", "\n").replace("\r", "\n"))
            if isinstance(value, str) else value
            for value in row
        ])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    workbook.properties.description = "Synthetic testing data; income categories are illustrative, not official."
    output = BytesIO()
    try:
        workbook.save(output)
        return output.getvalue()
    except Exception as exc:
        raise ValueError(f"Failed to export Excel file: {str(exc)}") from exc
    finally:
        workbook.close()
        output.close()
