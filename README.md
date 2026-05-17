# LDMS — LiDAR Defect Management System

Flask web app for managing building defects from LiDAR/Point Cloud Data scans.

**Tech Stack**: Python 3.11 · Flask 3.x · PostgreSQL 16 · Docker · Gunicorn · SQLAlchemy · Flask-Migrate · HTMX 1.9.12 · Alpine.js 3.14.1 · SweetAlert2 · NProgress

---

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Module Breakdown](#module-breakdown)
4. [Database Schema](#database-schema)
5. [User Roles](#user-roles)
6. [UI/UX Features](#uiux-features)
7. [Security](#security)
8. [Quick Start](#quick-start)
9. [Configuration Reference](#configuration-reference)

---

## Overview

The LDMS application bridges the gap between raw LiDAR scan data and actionable defect management. The workflow is:

```
Inspector uploads 3D GLB scan + PDF report
        ↓
AI Analysis (DBSCAN) extracts spatial clusters & defect points
        ↓
Defects logged with coordinates, room location, type, severity & AI priority
        ↓
Developer reviews via Dashboard with defect cards, charts, and My Tasks queue
        ↓
Defects are assigned, claimed, and tracked through status lifecycle
        ↓
Status updates (Reported/Under Review/Fixed) tracked via activity logs with idempotency
        ↓
Managers oversee portfolio, assign project owners, and monitor team workload
```

---

## Project Structure

```
pcd/
├── app/
│   ├── __init__.py          # App factory, blueprint registration, 403/404/500 handlers, CLI commands
│   ├── config.py            # Config: SECRET_KEY, DATABASE_URL, pool settings, email, Gemini, Maps
│   ├── extensions.py        # Flask extensions: db, migrate, login_manager, csrf, mail
│   ├── models.py            # User, Scan, Defect, ActivityLog (with DB indexes)
│   ├── utils.py             # Shared path utilities
│   ├── notifications.py     # Email notification system (critical alerts, status changes, bulk updates)
│   ├── auth/                # Login, register, profile, forgot/reset password
│   ├── upload_data/         # Upload GLB/PDF, PDF image extraction, UUID filenames, 100 MB limit
│   ├── process_data/        # GLB snapshot engine, DBSCAN clustering, defect detection
│   ├── defects/             # CRUD, CSV export (10k cap), global search API, origin validation
│   ├── developer/           # Dashboard, scan detail, My Tasks queue, bulk assign, activity log, admin
│   ├── services/            # developer_service.py
│   ├── templates/
│   │   ├── base.html        # Shared layout with SRI-hashed CDN links
│   │   ├── includes/        # search_modal.html, shortcuts_modal.html, breadcrumbs.html
│   │   ├── auth/            # login, register, profile, forgot_password, reset_password
│   │   ├── errors/          # 403, 404, 500
│   │   └── ...              # All other module templates
│   └── static/
│       ├── css/base.css     # Component styles (toast, loader, lightbox, search, skeleton, responsive)
│       ├── js/base.js       # Client-side: toasts, theme, lightbox, confirm, clipboard, NProgress+HTMX, keyboard shortcuts
│       └── favicon.svg
├── migrations/              # Alembic migrations
├── tests/                   # 50+ tests (auth flows, defect CRUD, upload/pipeline, admin, export, queue filters)
├── Dockerfile               # Production container
├── docker-compose.yml       # PostgreSQL + Flask
├── gunicorn.conf.py         # Workers, threads, timeouts
├── requirements.txt         # Pinned deps
└── .env.example             # All config vars documented
```

> Note: The `field_testing/` directory has been removed — it was used for academic research and is not part of the application.

---

## Module Breakdown

### Auth

| Route | Method | Description |
|-------|--------|-------------|
| /login | GET/POST | Login form |
| /logout | GET | Logout |
| /register | GET/POST | Register new user |
| /profile | GET/POST | View/edit profile, change email/password |
| /forgot-password | GET/POST | Request password reset email |
| /reset-password/\<token\> | GET/POST | Reset password with token |

### Upload Data

| Route | Method | Description |
|-------|--------|-------------|
| /inspector | GET | Inspector dashboard |
| /upload-data | GET/POST | Upload GLB + PDF, UUID-prefixed, 100 MB limit, magic byte validation |

### Process Data

| Route | Method | Description |
|-------|--------|-------------|
| /process-data | GET/POST | Run defect detection, save to DB |
| /process-data.json | GET | JSON endpoint for defect data |
| /process-data/image/\<id\> | GET | Serve extracted PDF images |
| /process-data/assign-image | POST | Assign/unassign images to defects |

### Defects

| Route | Method | Description |
|-------|--------|-------------|
| /projects | GET | List all scans/projects |
| /project/\<scan_id\> | GET | Project detail with severity/priority charts |
| /scans/\<scan_id\>/visualize | GET | 3D viewer (Three.js) |
| /scans/\<scan_id\>/defects | GET | JSON list of defects for scan |
| /scans/\<scan_id\>/defects | POST | Create defect (origin validated) |
| /defect/\<id\> | GET | JSON defect detail |
| /defect/\<id\>/status | PUT | Update status (origin validated) |
| /defect/\<id\> | DELETE | Delete defect (origin validated) |
| /api/search | GET | Global search across scans, defects, users |

### Developer

| Route | Method | Description |
|-------|--------|-------------|
| /developer | GET | Developer dashboard with scan list, metrics |
| /developer/scan/\<id\> | GET | Scan detail with defect cards, charts, bulk actions, DBSCAN hotspots |
| /developer/defect/\<id\>/update | POST | Update single defect status/notes |
| /developer/scan/\<id\>/bulk-update | POST | Bulk status/assignee updates |
| /developer/tasks | GET | My Tasks queue (Mine/Unassigned/All tabs) |
| /developer/tasks/\<id\>/update | POST | Update task status |
| /developer/tasks/bulk-assign | POST | Bulk claim/unassign/assign tasks |
| /developer/tasks/export.csv | GET | Export tasks as CSV (10k cap) |
| /developer/recent-activity | GET | Recent activity log |
| /developer/admin/users | GET | User management |
| /developer/admin/users/\<id\>/update | POST | Toggle active/available, change role, reset password, delete user |

### Manager

| Route | Method | Description |
|-------|--------|-------------|
| /manager/dashboard | GET | Cross-project dashboard, team workload, escalations |
| /developer/scan/\<id\>/assign | POST | Assign project owner |

---

## Database Schema

The application uses **4 database tables** managed via SQLAlchemy ORM.

```
┌──────────────┐         ┌───────────────┐
│    users     │         │     scans     │
├──────────────┤         ├───────────────┤
│ id (PK)      │         │ id (PK)       │
│ username     │         │ name          │
│ password_hash│         │ model_path    │
│ role         │         │ created_at    │
│ created_at   │         └───────┬───────┘
└──────────────┘                 │ 1
                                 │
                              many│
                         ┌───────▼───────┐
                         │    defects    │
                         ├───────────────┤
                         │ id (PK)       │
                         │ scan_id (FK)  │
                         │ x, y, z       │  ← 3D coordinates
                         │ element       │  ← Mesh/component name
                         │ location      │  ← Room/area
                         │ defect_type   │  ← crack, water damage, etc.
                         │ severity      │  ← Low/Medium/High/Critical
                         │ priority      │  ← Low/Medium/High/Urgent
                         │ status        │  ← Reported/Under Review/Fixed
                         │ assigned_to   │  ← Developer task ownership
                         │ due_date      │  ← Task deadline
                         │ description   │
                         │ image_path    │  ← Snapshot image
                         │ notes         │
                         │ created_at    │
                         └───────┬───────┘
                                 │ 1
                                 │
                              many│
                    ┌────────────▼────────────┐
                    │      activity_logs       │
                    ├─────────────────────────┤
                    │ id (PK)                 │
                    │ defect_id (FK)          │
                    │ scan_id (FK)            │
                    │ action                  │  ← e.g. "updated status"
                    │ old_value               │
                    │ new_value               │
                    │ event_uuid              │  ← idempotency key
                    │ request_id              │
                    │ actor_user_id           │
                    │ timestamp               │
                    └─────────────────────────┘
```

---

## User Roles

| Role | Access | Responsibility |
|------|--------|----------------|
| Inspector | Upload, Run AI, Priority Override | Field personnel who capture scans and manage uploads. |
| Developer | Review, Status, Assign, My Tasks | Maintenance team who fix defects, claim work, and track resolution progress. |
| Manager | Portfolio Oversight, Project Assignment, Team Workload, User Admin | Coordinates project ownership across developers and monitors cross-project queues. |

### My Tasks Workflow

The developer queue adds a lightweight task-management layer on top of defects:

- **Mine**: defects assigned to the current developer.
- **Unassigned**: defects awaiting ownership.
- **All**: full task queue for review or bulk action.

From the task page, developers can claim tasks, unassign them, bulk-assign to another developer, and export their queue as CSV.

### Endpoint Permission Matrix

| Area | Inspector | Developer | Manager |
|------|-----------|-----------|---------|
| Upload/process scans | Yes | Yes | No |
| Defect status updates | Yes | Yes | Yes |
| My Tasks queue and bulk assignment | No | Yes | No |
| Developer dashboard and analytics | No | Yes | No |
| Manager dashboard and project assignment | No | No | Yes |
| User management | No | No | Yes |

Implementation notes:

- Role checks are enforced server-side on protected routes.
- Disabled users cannot authenticate.
- Assignment targets are limited to active and available developers.
- Priority override is restricted to Inspectors to prevent unauthorized shifting.

---

## UI/UX Features

- **Global search modal** (Ctrl+K, `g s` shortcut) — searches across scans, defects, and users.
- **Keyboard shortcuts** (`?` to show help modal) — quick navigation throughout the app.
- **Theme toggle** — light and dark mode support.
- **Toast notifications** — non-intrusive feedback via SweetAlert2.
- **NProgress loading bar** — visual progress indicator for all HTMX requests.
- **SRI integrity hashes** — all CDN assets loaded with integrity verification.

---

## Security

- **CSRF protection** via Flask-WTF on all HTML forms.
- **`_validate_origin()`** guard on CSRF-exempt JSON API endpoints.
- **SRI integrity attributes** on all external scripts and stylesheets.
- **UUID-prefixed filenames** prevent overwrite attacks on uploads.
- **Magic byte validation** rejects non-GLB/non-PDF uploads at the network boundary.
- **Path traversal protection** on image serving endpoints.

---

## Quick Start

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY, DATABASE_URL
docker compose up --build

# In another terminal:
docker exec flask_app flask db upgrade
docker exec -it flask_app flask create-user
open http://localhost:5100
```

### Running Tests

All 50+ tests pass against the test suite:

```bash
docker exec flask_app pytest
```

---

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| SECRET_KEY | Yes | - | Flask secret key |
| DATABASE_URL | Yes | sqlite:///ldms.db | PostgreSQL DSN |
| FLASK_ENV | No | development | Environment |
| DB_POOL_SIZE | No | 5 | SQLAlchemy pool size |
| DB_POOL_RECYCLE | No | 300 | Connection recycle seconds |
| DB_POOL_TIMEOUT | No | 10 | Pool timeout |
| DB_MAX_OVERFLOW | No | 10 | Max overflow connections |
| MAIL_USERNAME | No | - | Gmail SMTP username |
| MAIL_PASSWORD | No | - | Gmail app password |
| MAIL_DEFAULT_SENDER | No | - | From address |
| NOTIFICATION_EMAILS | No | - | Comma-separated notify list |
| GEMINI_API_KEY | No | - | Google Gemini API key |
| GOOGLE_MAPS_API_KEY | No | - | Maps address autocomplete |

> **Important**: The `.env` file stores secrets and is never committed. Migrations are handled by Alembic/Flask-Migrate. PostgreSQL runs via Docker.
