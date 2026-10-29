# Custom Dataset Builder

Open Mock Data Factory and select **Custom Dataset**. The Student Enrollment preset includes a synthetic student ID, full name, grade enum, and enrollment date. Configure the fields, validate, generate 100 records, download Excel, and save the template. Saved definitions live in SQLite and survive application restarts.

## Architecture

- `apps/api/app/modules/data_factory/custom_schemas.py`: bounded Pydantic request, template, field, option, computation, and response schemas. Extra keys are rejected.
- `field_registry.py`: extensible generator registry with optional finite-domain cardinality functions. Register a callable accepting context, field, and row index; the engine does not dispatch on each individual Faker field type.
- `custom_generator.py`: framework-independent generation with private Python RNG and Faker instances, dependency sorting, null planning, unique-domain checks, bounded retries, and output limits.
- `template_store.py`: parameterized SQLite repository with per-operation connections and transactions. No SQLAlchemy/PostgreSQL infrastructure existed, so SQLite from the standard library avoids another dependency.
- `request_limits.py`: ASGI body-size limit before JSON parsing, including chunked requests.
- `exporters.py`: shared household/custom CSV, JSON, and XLSX serialization. Spreadsheet formula protection applies to CSV and Excel; JSON preserves original values. XML-invalid controls are removed for Excel.
- `apps/api/app/api/v1/custom_data_factory.py`: custom generation and template endpoints, using the existing API prefix.
- `apps/web/src/components/data-factory/custom-*`: vertical field editor, template library, generation controls, and paginated dynamic table. Existing UI primitives, navigation, and household generator remain in use.
- `apps/web/src/lib/custom-dataset-api.ts` and `src/types/custom-dataset.ts`: API access, downloads, shared frontend types, and built-in presets.

The preview retains an immutable generation request. Changes to name, description, locale, fields, count, or seed mark it outdated and disable downloads until regeneration. Exports regenerate from that exact request, with no time-relative or global random inputs. Reproducibility assumes unchanged application/Faker versions. Template JSON downloads contain the persisted definition; save edits first.

## Field types and constraints

General: `string`, `integer`, `decimal`, `boolean`, `date`, `datetime`, `uuid`, `sequence`, `enum`.

Personal: `full_name`, `first_name`, `last_name`, `email`, `phone_number`, `street_address`, `city`, `postal_code`, `birth_date`.

Business: `company_name`, `product_name`, `sku`, `price`, `quantity`, `transaction_id`, `transaction_date`.

Government/education: `household_size`, `barangay`, `student_id`, `employee_id`, `grade_level`, `school_year`. Barangays use explicitly fictional names. IDs are configurable synthetic sequences, not official government identifiers. The student preset prefixes its IDs with `STU-`.

All fields support labels, required/nullable, unique, and default values. Nullable is a property of any type: clear Required and choose a null probability between 0 and 1. Uniqueness applies to non-null values only. A default replaces the generator on non-null rows and must satisfy the field's scalar type and applicable constraints. Empty UI defaults mean no default; JSON can specify an empty string when its length constraints allow it.

Numeric options: `min`, `max`, `precision` (0–6), `distribution: "uniform"`. Integer bounds must be whole numbers. Grade and household size default to 1–12; other numbers default to 0–100. Numeric unique values sample without replacement. Enum `values` must be distinct, with optional non-negative `weights`; zero-weight entries cannot be generated. Weighted unique enums sample without replacement.

Strings: `min_length`, `max_length` (0–256 generated characters), `prefix`, `suffix` (up to 64 characters each). Length settings describe the generated core; affixes are additional. Sequence options: `start`, `step`, `padding`, `prefix`, `suffix`.

Dates: `min_date`, `max_date` inclusive, and `format`: `%Y-%m-%d`, `%d/%m/%Y`, `%m/%d/%Y`, or `%Y-%m-%dT%H:%M:%S`. DateTime generates whole seconds without a timezone; choose the timestamp format to display the time. Fixed defaults are 2000-01-01 through 2025-12-31 to ensure repeatability. Date-only types use midnight with the timestamp format.

Locale defaults to `en_PH`. If a locale lacks a Faker method (including phone numbers in the installed Philippine provider), an independently seeded `en_US` Faker instance supplies that method. Names and addresses are fabricated testing data and do not represent verified real identities.

Computed fields have `type: "computed"` and an explicit `computed` object:

```json
{"name":"total_amount","type":"computed","computed":{"operation":"multiply","sources":["quantity","unit_price"]},"options":{"precision":2}}
```

Other operations: `full_name` joins two string/name sources; `age` uses one date source and a mandatory `reference_date` in ISO format. Sources may appear later in the display order. The engine validates the dependency DAG and source types. Missing/circular references are rejected. Null inputs propagate null; required computed fields cannot depend on nullable sources. No user code or expression evaluation is supported.

## Schema example

POST this request to `/api/v1/data-factory/custom/generate`:

```json
{
  "count": 100,
  "seed": 42,
  "template": {
    "name": "Student Enrollment",
    "description": "Synthetic student records",
    "version": 1,
    "locale": "en_PH",
    "fields": [
      {"name":"student_id","label":"Student ID","type":"sequence","required":true,"unique":true,"options":{"prefix":"STU-","start":1,"step":1,"padding":5}},
      {"name":"student_name","label":"Name","type":"full_name"},
      {"name":"grade_level","type":"enum","options":{"values":["Grade 7","Grade 8","Grade 9","Grade 10"]}},
      {"name":"enrollment_date","type":"date","options":{"min_date":"2026-06-01","max_date":"2026-06-30"}}
    ]
  }
}
```

Responses retain `total_records`, `seed`, and `data`, adding an ordered `fields` list. Household responses and endpoints are unchanged. Template create/update bodies are the inner `template` object; imports also accept exported objects with a UUID, assigning a new UUID on import.

## Endpoints

All routes below are relative to `/api/v1/data-factory`.

| Method | Route | Purpose |
|---|---|---|
| GET | `/custom/field-types` | Registered field types |
| POST | `/custom/validate` | Validate schema and actual generation constraints |
| POST | `/custom/preview` | Generate a bounded preview dataset |
| POST | `/custom/generate` | Generate 1–1,000 rows |
| POST | `/custom/export?format=csv\|json\|xlsx` | Generate matching downloadable dataset |
| GET / POST | `/templates` | List / create |
| GET / PUT / DELETE | `/templates/{uuid}` | View / update / delete |
| POST | `/templates/{uuid}/duplicate` | Persist a copy |
| POST | `/templates/import` | Validate and persist JSON |
| GET | `/templates/{uuid}/export` | Download saved template JSON |

Create/import/duplicate return 201, delete returns 204, missing UUIDs return 404, invalid schemas/constraints return 422, oversized bodies return 413, and unavailable storage returns 503. Error responses do not include stack traces.

## Persistence and migration

Default database: `apps/api/data/templates.sqlite3`, independent of the current working directory and ignored by Git. Override with `DATA_FACTORY_DB` (an absolute path is recommended). The repository initializes `dataset_templates(id TEXT PRIMARY KEY, definition TEXT NOT NULL)` and SQLite `user_version = 1`. Back up this database with the application stopped. No browser-only template persistence is used; localStorage holds only up to five recently used UUIDs.

When PostgreSQL is introduced, replace the repository behind the API's `store` dependency, migrate UUID and JSON definitions to UUID/JSONB columns using Alembic, and retain request/response schemas. Do not run a second template store beside an established shared database. Schema version 1 currently has no upgrade transformations.

## Setup and startup

No new application dependencies. From the repository root, use two terminals:

```powershell
cd apps/api
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd apps/web
npm ci
npm run dev -- --hostname 127.0.0.1
```

Open `http://localhost:3000`. Keep the API local for this private MVP; authentication/authorization are not included. Existing `NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000`. CORS supports the existing localhost origins and the template PUT/DELETE methods.

## Verification

```powershell
cd apps/api
uv run python -m pytest -q
cd ../web
npx tsc --noEmit
npm run lint
npm run build
```

With both servers running and Microsoft Edge installed:

```powershell
cd apps/api
uv run --with playwright python ../../scripts/check-data-factory.py
uv run --with playwright python ../../scripts/check-custom-dataset.py
```

Playwright is an ephemeral test dependency. The custom browser script creates and removes its own saved templates. Backend tests use isolated temporary databases and check every registered field, constraints, determinism, computation, uniqueness, persistence, template import/export, exports, formula safety, and size limits.

Verified during implementation: 127 backend tests, TypeScript, ESLint, production build, the existing household browser script, and the custom builder browser script passed. A saved template was also loaded after an actual API process restart and generated 100 records successfully. The existing Starlette/HTTPX test-client deprecation warning remains.

## Troubleshooting

### Template not saving
- Check that the SQLite database file is writable
- Verify the `DATA_FACTORY_DB` environment variable points to a valid path
- Ensure the application has file system permissions for the database directory

### Generation fails with "Template not found"
- This error occurs when attempting to retrieve a template that doesn't exist
- Verify the template UUID is correct
- Check if the template was deleted from a different session

### Export download not working
- Ensure the generation was successful before attempting to export
- Check browser popup blockers are not preventing the download
- Verify the API server is running and accessible

### Validation errors on computed fields
- Computed fields require valid source field names
- Ensure source fields exist in the template
- Check that source field types are compatible with the operation
- For "age" operation, ensure reference_date is provided in ISO format

### Unique constraint failures
- Reduce the requested count or increase the domain size
- Check that min/max ranges allow enough unique values
- For enums, ensure enough distinct values are available
- Numeric unique fields may fail if the range is too small

### Slow generation with many fields
- Generation time scales with field count and row count
- Consider breaking large datasets into smaller templates
- Unique constraints require additional validation time

## Limits and future work

- 50 fields, 1,000 rows, 256 KB request body, 1,024 characters per generated value, and 10 MB compact row output per request. Exports are in memory and may be larger than compact JSON due to formatting/encoding.
- 2,000 attempts per unique cell and 150,000 attempts per request. Known finite domains reject impossible requests early; unknown domains can fail with a clear bounded-attempt error. Nullable masks are fixed by the seed before checking capacity. Validation performs the same bounded generation to catch computed and uniqueness failures.
- UI pagination is client-side, 25 rows per page. Template lists are unpaginated for the private MVP. SQLite is intended for one local application, with last-write-wins updates.
- Only uniform numeric distribution and three allowlisted computed operations; no arbitrary expressions, cross-dataset relations, timezone arithmetic, background jobs, or official identifiers.
- Phone/locality formatting depends on available Faker providers. Persisted definitions survive restarts; generated rows are not stored. Pin dependency versions when comparing output across environments.
- Future improvements: server pagination for large template libraries, optimistic edit versions, PostgreSQL migration when needed, additional distributions, and explicit generator-version metadata for archived exports.
