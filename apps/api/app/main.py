
"""
ALZA DevKit API - Main Application Entry Point

This FastAPI application provides the backend for the ALZA DevKit platform,
which includes:
- Mock Data Factory: Synthetic household data generation
- Custom Dataset Builder: Configurable data generation with templates
- Database Schema Importer: PostgreSQL DDL parsing and synthetic data generation

Architecture:
- API routes are organized under /api/v1/
- CORS is enabled for the Next.js frontend
- Request limits are enforced via middleware
- SQLite is used for persistent template storage
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.data_factory import router as data_factory_router
from app.api.v1.custom_data_factory import router as custom_data_factory_router
from app.api.v1.schema_import import router as schema_import_router
from app.modules.data_factory.request_limits import CustomBodyLimit

app = FastAPI(
    title="ALZA DevKit API",
    description="Private Developer Operations Platform",
    version="0.3.0",
)

app.add_middleware(CustomBodyLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(data_factory_router)
app.include_router(custom_data_factory_router)
app.include_router(schema_import_router)

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "application": "ALZA DevKit",
        "module": "Mock Data Factory",
        "version": app.version,
    }
