import sqlite3
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import ValidationError

from app.modules.data_factory.exporters import ExportFormat, MIME_TYPES
from app.modules.schema_import.models import DatabaseSchema, ParseRequest, Dataset, ValidationResult
from app.modules.schema_import.parser import parse_sql
from app.modules.schema_import.generator import generate as generate_dataset
from app.modules.schema_import.exporters import export_dataset
from app.modules.schema_import.store import SchemaStore

router = APIRouter(prefix="/api/v1/schema-import", tags=["Database Schema Importer"])


def checked(action):
    try:
        return action()
    except ValidationError as exc:
        messages = "; ".join(e["msg"] for e in exc.errors(include_input=False))
        raise HTTPException(422, messages) from None
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from None
    except KeyError:
        raise HTTPException(404, "Schema configuration not found") from None
    except (sqlite3.Error, OSError):
        raise HTTPException(503, "Schema storage is unavailable") from None


def store():
    return SchemaStore()


@router.post("/parse", response_model=DatabaseSchema)
def parse(request: ParseRequest):
    """Parse PostgreSQL DDL SQL and extract table structure with keys and relationships."""
    return checked(lambda: parse_sql(request.sql, request.name))


@router.post("/generate", response_model=Dataset)
def generate(schema: DatabaseSchema):
    """Generate synthetic data for the parsed database schema with foreign key integrity."""
    return checked(lambda: generate_dataset(schema))


@router.post("/validate", response_model=ValidationResult)
def validate(schema: DatabaseSchema):
    """Validate the schema configuration and return the table generation order."""
    data = checked(lambda: generate_dataset(schema))
    return ValidationResult(order=data.order)


@router.post("/export")
def export(schema: DatabaseSchema, format: ExportFormat = "json"):
    """Export generated synthetic data in JSON, CSV ZIP, or Excel format."""
    output = checked(lambda: export_dataset(generate_dataset(schema), format))
    extension = "zip" if format == "csv" else format
    return Response(output, media_type="application/zip" if format == "csv" else MIME_TYPES[format], headers={
        "Content-Disposition": f'attachment; filename="synthetic-schema-seed-{schema.seed}.{extension}"',
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/schemas", response_model=list[DatabaseSchema])
def list_schemas(db=Depends(store)):
    """List all saved database schema configurations."""
    return checked(db.list)


@router.post("/schemas", response_model=DatabaseSchema, status_code=201)
@router.post("/schemas/import", response_model=DatabaseSchema, status_code=201)
def create(schema: DatabaseSchema, db=Depends(store)):
    """Create a new schema configuration or import from JSON."""
    return checked(lambda: db.create(schema))


@router.get("/schemas/{id}", response_model=DatabaseSchema)
def get(id: UUID, db=Depends(store)):
    """Retrieve a specific schema configuration by ID."""
    return checked(lambda: db.get(id))


@router.put("/schemas/{id}", response_model=DatabaseSchema)
def update(id: UUID, schema: DatabaseSchema, db=Depends(store)):
    """Update an existing schema configuration."""
    return checked(lambda: db.update(id, schema))


@router.delete("/schemas/{id}", status_code=204)
def delete(id: UUID, db=Depends(store)):
    """Delete a schema configuration."""
    checked(lambda: db.delete(id))
    return Response(status_code=204)


@router.get("/schemas/{id}/export")
def export_schema(id: UUID, db=Depends(store)):
    """Export a schema configuration as JSON."""
    schema = checked(lambda: db.get(id))
    return Response(schema.model_dump_json(), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="schema-{id}.json"'})
