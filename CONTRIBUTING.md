# Contributing to ALZA DevKit

Thank you for your interest in contributing to ALZA DevKit. This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Node.js 18+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Git

### Getting Started

1. Clone the repository:
```bash
git clone https://github.com/SPATIBAIII/alza-devkit.git
cd alza-devkit
```

2. Backend setup:
```bash
cd apps/api
uv sync
```

3. Frontend setup:
```bash
cd apps/web
npm ci
```

### Running the Application

**Terminal 1 - Backend:**
```bash
cd apps/api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd apps/web
npm run dev -- --hostname 127.0.0.1
```

Access the application at http://localhost:3000

## Code Style

### Python (Backend)

- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Write docstrings for functions and classes
- Run `uv run python -m pytest` to run tests

### TypeScript/React (Frontend)

- Follow existing code patterns
- Use TypeScript for type safety
- Run `npx tsc --noEmit` for type checking
- Run `npm run lint` for linting
- Run `npm run build` to verify production build

## Testing

### Backend Tests
```bash
cd apps/api
uv run python -m pytest -q
```

### Frontend Checks
```bash
cd apps/web
npx tsc --noEmit
npm run lint
npm run build
```

### Browser Integration Tests
With both servers running and Microsoft Edge installed:
```bash
cd apps/api
uv run --with playwright python ../../scripts/check-schema-importer.py
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes with clear messages
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Project Structure

```
alza-devkit/
├── apps/
│   ├── web/          # Next.js frontend
│   └── api/          # FastAPI backend
├── docs/             # Documentation
├── scripts/          # Verification scripts
├── infra/            # Infrastructure
└── storage/          # Local workspace data
```

## Guidelines

- Keep changes focused and minimal
- Write clear commit messages
- Update documentation as needed
- Ensure all tests pass before submitting
- Follow the existing code style and patterns

## Issues

If you find a bug or have a feature request, please open an issue on GitHub with:
- A clear description
- Steps to reproduce (for bugs)
- Expected behavior
- Environment details

## License

No license is specified. All rights reserved unless a license is added.
