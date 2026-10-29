from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.modules.data_factory.exporters import ExportFormat, MIME_TYPES, export_households
from app.modules.data_factory.generator import generate_households
from app.modules.data_factory.schemas import HouseholdDataset

router = APIRouter(prefix="/api/v1/data-factory", tags=["Mock Data Factory"])
Count = Annotated[int, Query(ge=1, le=1000, description="Number of synthetic records")]
Seed = Annotated[int, Query(ge=0, description="Seed for repeatable generation")]


@router.get("/households", response_model=HouseholdDataset)
def households(count: Count = 100, seed: Seed = 42) -> HouseholdDataset:
    """Generate synthetic household records with Filipino-style names."""
    return HouseholdDataset(total_records=count, seed=seed, data=generate_households(count, seed))


@router.get("/households/export")
def export(count: Count = 100, seed: Seed = 42, format: ExportFormat = "csv") -> Response:
    """Export synthetic household records in various formats (CSV, JSON, XLSX)."""
    dataset = households(count, seed)
    return Response(
        content=export_households(dataset, format),
        media_type=MIME_TYPES[format],
        headers={
            "Content-Disposition": f'attachment; filename="synthetic-households-{count}-seed-{seed}.{format}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
