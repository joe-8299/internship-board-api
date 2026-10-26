# Internship Board API

A small REST API for managing internship listings, with safe create / read / update / delete operations,
input validation, and consistent responses. **No installs needed** – Python 3.9+ standard library only (SQLite built in).

## Quick start (2 minutes)
```bash
python server.py          # creates internships.db and loads seed.json on first run
# open http://localhost:8000                  -> live preview UI
# open http://localhost:8000/api/internships  -> raw API
```
Other commands:
```bash
python seed.py                         # reset the database to the seed records
python -m unittest tests/test_api.py   # run the automated tests
PORT=9000 python server.py             # use a different port
```

## Project layout
| File | Purpose |
|---|---|
| `server.py` | API: routing, validation, error handling |
| `schema.sql` | SQLite schema (CHECK constraints + UNIQUE rule) |
| `seed.json` | 8 fictional internships used to seed the DB |
| `seed.py` | Resets and re-seeds the database |
| `public/index.html` | Preview UI that calls the API (search, create, edit, delete) |
| `tests/test_api.py` | Automated tests for CRUD, validation and errors |
| `docs/API_EXAMPLES.md` | Copy-paste curl examples with real responses |

## Data model – `internships`
| Field | Type | Rules |
|---|---|---|
| `id` | integer | auto-generated |
| `title` | string | required, 3–120 chars |
| `company` | string | required, 2–80 chars |
| `location` | string | required, 2–80 chars |
| `work_mode` | string | required: `remote` \| `hybrid` \| `onsite` |
| `stipend_monthly` | integer or null | optional, ≥ 0 (null = unpaid) |
| `duration_weeks` | integer | required, 1–52 |
| `status` | string | optional (default `open`): `draft` \| `open` \| `closed` |
| `apply_url` | string or null | optional, must start with http(s):// |
| `description` | string | optional, ≤ 2000 chars |
| `created_at`, `updated_at` | ISO‑8601 UTC | set by the server |

`(title, company)` must be unique.

## Endpoints
| Method & path | Purpose | Success |
|---|---|---|
| `GET /api/internships` | List (filters: `status`, `work_mode`, `q`; paging: `page`, `limit` ≤ 50) | 200 |
| `GET /api/internships/{id}` | Detail | 200 |
| `POST /api/internships` | Create (returns `Location` header) | 201 |
| `PUT /api/internships/{id}` | Replace (all required fields) | 200 |
| `PATCH /api/internships/{id}` | Partial update (≥ 1 field) | 200 |
| `DELETE /api/internships/{id}` | Delete | 204 (no body) |
| `GET /api/health` | Health check | 200 |

## Response format
Success: `{"data": <object or array>, "meta": {...}}` (`meta` only on list).
Error (always this shape):
```json
{"error": {"code": "VALIDATION_ERROR", "message": "…", "details": [{"field": "title", "message": "…"}]}}
```

## Status codes
| Code | `error.code` | When |
|---|---|---|
| 400 | `INVALID_JSON` / `INVALID_ID` | Malformed JSON body, or id isn't a positive integer |
| 404 | `NOT_FOUND` | Unknown id or route |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method (`Allow` header returned) |
| 409 | `CONFLICT` | Duplicate title + company |
| 413 | `PAYLOAD_TOO_LARGE` | Body over 100 KB |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Content-Type isn't `application/json` |
| 422 | `VALIDATION_ERROR` | Bad/missing/unknown fields or bad query params |
| 500 | `INTERNAL_ERROR` | Unexpected bug (details never leaked) |

## Safety notes
- All SQL uses parameterised queries; column names come from a fixed allow-list.
- Unknown fields are rejected and types are checked strictly (e.g. `true` is not a number).
- The database also enforces rules with `CHECK` and `UNIQUE` constraints as a second line of defence.

More examples: `docs/API_EXAMPLES.md`.
