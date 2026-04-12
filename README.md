# Lidar Defect Management System (LDMS)

A **Flask web application** for managing building defects detected from **LiDAR / Point Cloud Data (PCD)** scans. The system enables inspectors to upload 3D scan data, process it to identify defects, and allows developers to review, prioritise, and track those defects through their lifecycle.

> **Tech Stack**: Python · Flask · PostgreSQL · Docker · Gunicorn

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Project Structure](#project-structure)
4. [Module Breakdown](#module-breakdown)
5. [Database Schema](#database-schema)
6. [User Roles](#user-roles)
7. [Tech Stack & Dependencies](#tech-stack--dependencies)
8. [Quick Start](#quick-start)
9. [Deployment](#deployment)

---

The LDMS application bridges the gap between raw LiDAR scan data and actionable defect management. The workflow is:

```
Inspector uploads 3D PCD/GLB scan
        ↓
AI Analysis (DBSCAN) extracts spatial clusters & defect points
        ↓
Defects logged with coordinates, room location, type, severity & AI priority
        ↓
Developer reviews via Premium Bento Grid Dashboard
        ↓
Status updates (Reported/Review/Fixed) tracked via activity logs
        ↓
Analytics & PDF Reports generated for project close-out
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Web Browser                        │
│              (Inspector / Developer)                 │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP
┌─────────────────▼───────────────────────────────────┐
│              Flask Application (Gunicorn)            │
│                                                      │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────┐  │
│  │   auth   │ │upload_data│ │ process  │ │defect│  │
│  │blueprint │ │ blueprint │ │  _data   │ │  s   │  │
│  └──────────┘ └───────────┘ │blueprint │ │  bp  │  │
│                              └──────────┘ └──────┘  │
│                    ┌──────────────┐                  │
│                    │  developer   │                  │
│                    │  blueprint   │                  │
│                    └──────────────┘                  │
└─────────────────────────────┬───────────────────────┘
                              │ SQLAlchemy ORM
┌─────────────────────────────▼───────────────────────┐
│                  PostgreSQL Database                 │
│        (users · scans · defects · activity_logs)    │
└─────────────────────────────────────────────────────┘
```

---

## Project Structure

```
pcd/
│
├── app/                            # Core Flask application package
│   ├── __init__.py                 # App factory (create_app), blueprint registration, CLI commands
│   ├── config.py                   # Configuration class (SECRET_KEY, DATABASE_URL, etc.)
│   ├── extensions.py               # Flask extension instances (db, login_manager, csrf)
│   ├── models.py                   # SQLAlchemy database models
│   ├── utils.py                    # Shared utility functions
│   │
│   ├── auth/                       # Authentication module (Blueprint)
│   │   ├── __init__.py
│   │   └── routes.py               # Login, logout, register routes
│   │
│   ├── upload_data/                # Inspector upload module (Blueprint)
│   │   ├── routes.py               # Upload scan files, inspector dashboard
│   │   └── pdf_utils.py            # PDF report generation utilities
│   │
│   ├── process_data/               # 3D data processing module (Blueprint)
│   │   ├── routes.py               # PCD/GLB processing, defect detection endpoints
│   │   └── glb_snapshot.py         # Renders snapshots from GLB 3D models
│   │
│   ├── defects/                    # Defect management module (Blueprint)
│   │   └── routes.py               # CRUD operations for defects, status updates
│   │
│   ├── developer/                  # Developer dashboard module (Blueprint)
│   │   └── routes.py               # Developer views, analytics, defect tracking
│   │
│   ├── templates/                  # Jinja2 HTML templates
│   │   ├── auth/                   # Login page templates
│   │   ├── upload_data/            # Inspector dashboard & upload templates
│   │   ├── process_data/           # 3D viewer and processing templates
│   │   ├── defects/                # Defect list and detail templates
│   │   ├── developer/              # Developer dashboard templates
│   │   └── errors/                 # 404 and 500 error pages
│   │
│   └── static/                     # Static assets
│       ├── css/                    # Stylesheets
│       ├── js/                     # JavaScript (3D viewer, UI interactions)
│       └── img/                    # Images and icons
│
├── instance/                       # Instance-specific files (SQLite, local uploads)
├── scripts/                        # Utility & maintenance scripts (e.g., fix_db.py)
├── Dockerfile                      # Production Docker container definition
├── docker-compose.yml              # Local Dev/Prod orchestration
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── DEPLOYMENT.md                   # Full production guide
└── README.md                       # This file
```

---

## Module Breakdown

### `auth` — Authentication
Handles user login and logout using **Flask-Login** with session management.

| Route | Method | Description |
|-------|--------|-------------|
| `/login` | GET/POST | Login form, validates credentials |
| `/logout` | GET | Logs out the current user |

---

### `upload_data` — Inspector Dashboard & File Upload
The **inspector-facing** module. Inspectors upload scan files and manage submissions.

| Route | Method | Description |
|-------|--------|-------------|
| `/upload` | POST | Upload a new PCD/GLB scan file + PDF Report |
| `/view/<id>` | GET | View the 3D model and extracted images |

Key file: `pdf_utils.py` — handles extraction of defect images from uploaded PDF inspection reports.

---

### `process_data` — 3D Data Processing
Processes uploaded scan files, extracts defect coordinates, and stores them in the database.

| Route | Method | Description |
|-------|--------|-------------|
| `/process/<scan_id>` | GET/POST | Run defect detection on an uploaded scan |
| `/view/<scan_id>` | GET | 3D viewer for the GLB model |
| `/snapshot/<scan_id>` | POST | Capture a 2D snapshot from the 3D model |

Key file: `glb_snapshot.py` — renders GLB 3D model frames to generate snapshot images for defect records.

---

### `defects` — Defect CRUD
Manages individual defect records — viewing, editing, and status changes.

| Route | Method | Description |
|-------|--------|-------------|
| `/defects` | GET | List all defects (filterable) |
| `/defects/<id>` | GET | View a single defect detail |
| `/defects/<id>/edit` | POST | Update defect fields (status, priority, notes) |
| `/defects/<id>/delete` | POST | Delete a defect record |

---

### `developer` — Developer Dashboard & Analytics
The **developer-facing** module. Provides an overview of all scans, defects, and activity logs.

| Route | Method | Description |
|-------|--------|-------------|
| `/developer` | GET | Developer dashboard — scans and defect summary |
| `/developer/defects` | GET | Full defect table with filter/sort |
| `/developer/activity` | GET | Activity log for all defect changes |

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
                    │ timestamp               │
                    └─────────────────────────┘
```

---

## User Roles & Permissions

| Role | Access | Responsibility |
|------|--------|----------------|
| `Inspector` | Upload, Run AI, Reports | Field personnel who capture scans and generate closing documents. |
| `Developer` | Review, Status, Analytics | Maintenance team who fix defects and track resolution progress. |

> [!NOTE]
> **Data Integrity**: Developers can update defect **Status** and **Notes**, but **Priority** is automatically managed by the AI system (DBSCAN/Risk Score) or restricted to Inspectors to prevent unauthorized priority shifting.


---

## Tech Stack & Dependencies

| Category | Technology |
|----------|-----------|
| **Web Framework** | Flask 3.x |
| **ORM** | Flask-SQLAlchemy |
| **Database** | PostgreSQL 16 (via Docker) |
| **DB Driver** | psycopg2-binary |
| **Authentication** | Flask-Login |
| **Forms & CSRF** | Flask-WTF |
| **3D File Handling** | pygltflib (GLB/glTF) |
| **PDF Data Extraction** | pypdf |
| **Image Processing** | Pillow |
| **WSGI Server** | Gunicorn |
| **Containerisation** | Docker + Docker Compose |
| **Migrations** | Flask-Migrate |

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/mern64/Lidar-Defect-Management-System-Module.git
cd Lidar-Defect-Management-System-Module

# 2. Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY and confirm DATABASE_URL

# 3. Build and start
docker compose up --build

# 4. Create your first user (in a new terminal)
docker exec -it flask_app flask create-user

# 5. Open the app
open http://localhost:5100
```

---

## Deployment

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for the full guide, including:
- PostgreSQL credential setup
- Creating admin users
- Database backup & restore
- Pushing updates to GitHub
- Troubleshooting common issues