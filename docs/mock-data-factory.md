# Mock Data Factory

Start the backend in one PowerShell terminal from the repository root:

```powershell
cd apps/api
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```powershell
cd apps/web
npm ci
npm run dev
```

The frontend defaults to `http://localhost:8000`. To change the API address, copy
`apps/web/.env.example` to `apps/web/.env.local` and set `NEXT_PUBLIC_API_BASE_URL`.
Restart Next.js after changing it; production builds embed this public value.

Open http://localhost:3000, choose **Mock Data Factory**, keep Household Dataset,
enter 1–1,000 records and an optional non-negative integer seed, and select
**Generate Dataset**. An empty seed uses 42. The preview shows 25 records per page.
Downloads contain the entire last successful dataset, even after editing form
inputs. Failed generations leave the previous successful preview available.

Only the household preset is implemented. All data is synthetic; income categories
are illustrative. CSV and Excel neutralize spreadsheet formulas in text values.
JSON retains the API envelope, including `synthetic: true`.

## API Examples

### Generate 50 household records with custom seed

```http
GET /api/v1/data-factory/households?count=50&seed=123
```

### Export 200 households as Excel

```http
GET /api/v1/data-factory/households/export?count=200&seed=42&format=xlsx
```

### Generate maximum allowed records

```http
GET /api/v1/data-factory/households?count=1000&seed=999
```

## Response Format

The API returns a JSON response with the following structure:

```json
{
  "total_records": 100,
  "seed": 42,
  "data": [
    {
      "household_id": "HH-00001",
      "household_head": "Juan Dela Cruz",
      "barangay": "Fictional Sample Barangay A",
      "household_size": 4,
      "monthly_income": 25000,
      "income_category": "Middle"
    }
  ]
}
```

Checks:

```powershell
cd apps/api
uv run python -m pytest
cd ../web
npx tsc --noEmit
npm run lint
npm run build
```

With both servers running and Microsoft Edge installed, run the optional browser
integration check from `apps/api`:

```powershell
uv run --with playwright python ../../scripts/check-data-factory.py
```

Playwright is used only for this check, not added as an application dependency.

Implementation files:

- Backend: updated `apps/api/app/modules/data_factory/generator.py` and
  `apps/api/app/main.py`; added `schemas.py` and `exporters.py` alongside the
  generator, plus `apps/api/app/api/v1/data_factory.py` and package initializers.
- Dependencies: updated `apps/api/pyproject.toml` and `uv.lock` with OpenPyXL
  (and its transitive dependency et-xmlfile). Existing Pytest and HTTPX are reused.
- Frontend: updated `apps/web/src/app/page.tsx`; added the four components under
  `apps/web/src/components/data-factory/`, `src/lib/data-factory-api.ts`, and
  `src/types/data-factory.ts`. No frontend dependencies were added.
- Configuration: added `apps/web/.env.example`, updated its `.gitignore` to allow
  the example, and added `apps/api/.gitignore` for local Python artifacts.
- Verification and documentation: added `apps/api/tests/test_data_factory.py`,
  `scripts/check-data-factory.py`, this guide, and populated `apps/api/README.md`.

Verified: 45 backend tests, TypeScript compilation, ESLint, Next.js production
build, and the live browser integration check all passed. The backend test runner
emits a Starlette deprecation warning about the existing HTTPX test client; it does
not affect test results. No authentication or additional dataset presets were added.
