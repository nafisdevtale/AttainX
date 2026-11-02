# Smart CO PO AttainX — OBE Attainment Dashboard

A Flask-based college dashboard for CO–PO/PSO mapping, direct and indirect attainment calculations, and dashboard generation.

## Application source

The full application source, HTML templates, CSV templates, and college logo are packaged in [obe-source.zip](./obe-source.zip). The small root-level Flask entry point extracts this bundle into the function's temporary directory and loads the Flask application from it.

## Stack

- Python 3.12
- Flask 3.0.0
- Pandas 2.1.4
- NumPy 1.26.2

## Deploy to Vercel

Import this repository in Vercel. Keep the root directory at the repository root and use the Python/Flask runtime.

Configure these environment variables in Vercel for Production (and Preview if needed):

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Long, randomly generated Flask session secret |
| `TEACHER_PASSWORD` | Shared password for the teacher accounts listed in the application |
| `ADMIN_EMAILS` | Optional comma-separated administrator email addresses |
| `ADMIN_PASSWORD` | Administrator password; required when `ADMIN_EMAILS` is set |

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not commit `.env` files or real credentials. The application limits uploads to 4 MB.

## Data and storage note

Uploaded CSVs are processed in the request and are not stored as a permanent student-record database. Vercel function storage is ephemeral; use an external storage/database service before extending the application to retain student data.
