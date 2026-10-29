import re
import sqlite3
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.modules.data_factory.custom_generator import generate_custom
from app.modules.data_factory.custom_schemas import CustomDataset, GenerateRequest, SavedTemplate, TemplateInput, ValidationResult
from app.modules.data_factory.exporters import ExportFormat, MIME_TYPES, export_records
from app.modules.data_factory.field_registry import REGISTRY
from app.modules.data_factory.template_store import TemplateStore

router = APIRouter(prefix="/api/v1/data-factory", tags=["Custom Dataset Builder"])


def store():
    return TemplateStore()


def storage_call(action):
    try:
        return action()
    except KeyError:
        raise HTTPException(404, "Template not found. Please check the template ID and try again.") from None
    except (sqlite3.Error, OSError):
        raise HTTPException(503, "Template storage is unavailable. Please check if the database file is accessible.") from None


@router.get("/custom/field-types", response_model=list[str])
def field_types():
    return sorted(REGISTRY) + ["computed"]


@router.post("/custom/generate", response_model=CustomDataset)
@router.post("/custom/preview", response_model=CustomDataset)
def generate(request: GenerateRequest):
    return checked_generate(request)


def checked_generate(request):
    try:
        return generate_custom(request)
    except ValueError as exc:
        raise HTTPException(422, f"Validation error: {str(exc)}. Please check your field configurations.") from None
    except OverflowError:
        raise HTTPException(422, "Generated value exceeds supported range. Please adjust your field constraints.") from None


@router.post("/custom/validate", response_model=ValidationResult)
def validate(request: GenerateRequest):
    checked_generate(request)
    return ValidationResult()


@router.post("/custom/export")
def export(request: GenerateRequest, format: ExportFormat = "csv"):
    dataset = checked_generate(request)
    filename = re.sub(r"[^A-Za-z0-9_-]+", "-", request.template.name).strip("-") or "dataset"
    return Response(export_records(dataset.model_dump(), dataset.fields, format), media_type=MIME_TYPES[format], headers={
        "Content-Disposition": f'attachment; filename="{filename}-{request.count}-seed-{request.seed}.{format}"',
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/templates", response_model=list[SavedTemplate])
def list_templates(db=Depends(store)):
    return storage_call(db.list)


@router.post("/templates", response_model=SavedTemplate, status_code=201)
def create_template(template: TemplateInput, db=Depends(store)):
    return storage_call(lambda: db.create(template))


@router.post("/templates/import", response_model=SavedTemplate, status_code=201)
def import_template(template: SavedTemplate | TemplateInput, db=Depends(store)):
    return storage_call(lambda: db.create(TemplateInput.model_validate(template.model_dump(exclude={"id"}))))


@router.get("/templates/{id}", response_model=SavedTemplate)
def get_template(id: UUID, db=Depends(store)):
    return storage_call(lambda: db.get(id))


@router.get("/templates/{id}/export")
def export_template(id: UUID, db=Depends(store)):
    template = storage_call(lambda: db.get(id))
    return Response(template.model_dump_json(), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="template-{id}.json"'})


@router.put("/templates/{id}", response_model=SavedTemplate)
def update_template(id: UUID, template: TemplateInput, db=Depends(store)):
    return storage_call(lambda: db.update(id, template))


@router.delete("/templates/{id}", status_code=204)
def delete_template(id: UUID, db=Depends(store)):
    storage_call(lambda: db.delete(id))
    return Response(status_code=204)


@router.post("/templates/{id}/duplicate", response_model=SavedTemplate, status_code=201)
def duplicate_template(id: UUID, db=Depends(store)):
    original = storage_call(lambda: db.get(id))
    template = TemplateInput.model_validate(original.model_dump(exclude={"id"}))
    template.name = original.name[:93] + " (copy)"
    return storage_call(lambda: db.create(template))
