"""SQLite repository; no database connections are shared across requests.

Replace this repository with a PostgreSQL implementation when a shared DB is introduced.
"""
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from .custom_schemas import SavedTemplate, TemplateInput

logger = logging.getLogger(__name__)


class TemplateStore:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("DATA_FACTORY_DB", Path(__file__).resolve().parents[3] / "data" / "templates.sqlite3"))

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS dataset_templates (id TEXT PRIMARY KEY, definition TEXT NOT NULL)")
            conn.execute("PRAGMA user_version = 1")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def list(self):
        with self.connection() as conn:
            templates = [SavedTemplate.model_validate_json(row[0]) for row in conn.execute("SELECT definition FROM dataset_templates ORDER BY rowid DESC")]
            logger.info(f"Retrieved {len(templates)} templates from database")
            return templates

    def get(self, id: UUID):
        with self.connection() as conn:
            row = conn.execute("SELECT definition FROM dataset_templates WHERE id = ?", (str(id),)).fetchone()
        if row is None:
            logger.warning(f"Template not found: {id}")
            raise KeyError(id)
        logger.info(f"Retrieved template: {id}")
        return SavedTemplate.model_validate_json(row[0])

    def create(self, template: TemplateInput):
        saved = SavedTemplate(**template.model_dump(), id=uuid4())
        with self.connection() as conn:
            conn.execute("INSERT INTO dataset_templates VALUES (?, ?)", (str(saved.id), saved.model_dump_json()))
        logger.info(f"Created new template: {saved.id} - {template.name}")
        return saved

    def update(self, id: UUID, template: TemplateInput):
        saved = SavedTemplate(**template.model_dump(), id=id)
        with self.connection() as conn:
            if not conn.execute("UPDATE dataset_templates SET definition = ? WHERE id = ?", (saved.model_dump_json(), str(id))).rowcount:
                logger.warning(f"Template not found for update: {id}")
                raise KeyError(id)
        logger.info(f"Updated template: {id} - {template.name}")
        return saved

    def delete(self, id: UUID):
        with self.connection() as conn:
            if not conn.execute("DELETE FROM dataset_templates WHERE id = ?", (str(id),)).rowcount:
                logger.warning(f"Template not found for deletion: {id}")
                raise KeyError(id)
        logger.info(f"Deleted template: {id}")
