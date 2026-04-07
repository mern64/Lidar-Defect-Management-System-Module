# Deployment Guide — PCD Application

> **System**: Flask · PostgreSQL · Docker  
> **Last updated**: April 2026

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Clone the Repository](#clone-the-repository)
3. [Configure Environment Variables](#configure-environment-variables)
4. [Build and Run with Docker Compose](#build-and-run-with-docker-compose)
5. [Create the First Admin User](#create-the-first-admin-user)
6. [Access the Application](#access-the-application)
7. [PostgreSQL Notes](#postgresql-notes)
8. [Stopping and Restarting](#stopping-and-restarting)
9. [Pushing to Your Own GitHub](#pushing-to-your-own-github)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Install the following on your machine before deploying:

| Tool | Version | Install |
|------|---------|---------|
| **Docker** | 24+ | https://docs.docker.com/get-docker/ |
| **Docker Compose** | v2 (bundled with Docker Desktop) | Included in Docker Desktop |
| **Git** | Any | https://git-scm.com/ |

> **No Python or database installation is required on your host machine** — everything runs inside Docker containers.

---

## Clone the Repository

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

---

## Configure Environment Variables

The application requires a `.env` file with secrets. **This file is never committed to git** — it stays on your machine only.

**Step 1** — Copy the template:
```bash
cp .env.example .env
```

**Step 2** — Edit `.env` and fill in the values:
```bash
nano .env     # or open with any text editor
```

**Required values to set:**

```env
# Generate a secure secret key:
#   python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=paste-your-generated-key-here

# PostgreSQL connection string (matches docker-compose credentials)
DATABASE_URL=postgresql://pcd_user:pcd_password@flask_db:5432/pcd_db

# Environment: 'development' or 'production'
FLASK_ENV=development
```

> **Security tip**: In production, change `pcd_user` and `pcd_password` in **both** `.env` and `docker-compose.yml` to something strong and unique.

---

## Build and Run with Docker Compose

```bash
# Build the images and start all services (Flask app + PostgreSQL)
docker compose up --build
```

- First run will take a few minutes to download and build images.
- Subsequent starts are much faster (layers are cached).
- The database tables are created automatically on first startup.

**Run in background (detached mode):**
```bash
docker compose up --build -d
```

**View logs while running in background:**
```bash
docker compose logs -f
```

---

## Create the First Admin User

After the containers are running, create your first developer (admin) account:

```bash
docker exec -it flask_app conda run -n pcd flask create-user
```

You will be prompted for:
- **Username** — e.g. `admin`
- **Password** — choose a secure password
- **Role** — choose `developer` for admin access, or `inspector` for a regular user

> Run this command once per user you want to create. You can create multiple users.

---

## Access the Application

Once running, open your browser and go to:

```
http://localhost:5100
```

| What | URL |
|------|-----|
| Flask App | http://localhost:5100 |
| PostgreSQL (direct) | `localhost:5432` |

---

## PostgreSQL Notes

### Credentials (default)

| Setting | Value |
|---------|-------|
| Host (inside Docker) | `flask_db` |
| Host (from your machine) | `localhost` |
| Port | `5432` |
| Database | `pcd_db` |
| Username | `pcd_user` |
| Password | `pcd_password` |

### Data Persistence

Database data is stored in a Docker **named volume** (`flask_db_data`). This means:
- ✅ Data **survives** `docker compose down` and `docker compose up`
- ❌ Data is **lost** if you run `docker compose down -v` (removes volumes)

### Access PostgreSQL directly

```bash
docker exec -it flask_db psql -U pcd_user -d pcd_db
```

### Backup the database

```bash
docker exec flask_db pg_dump -U pcd_user pcd_db > backup.sql
```

### Restore from backup

```bash
docker exec -i flask_db psql -U pcd_user pcd_db < backup.sql
```

---

## Stopping and Restarting

```bash
# Stop all containers (data is preserved)
docker compose down

# Stop and remove all data (full reset)
docker compose down -v

# Restart without rebuilding
docker compose up -d

# Rebuild after code changes
docker compose up --build -d
```

---

## Pushing to Your Own GitHub

### First time setup

```bash
# Inside your project directory
git remote set-url origin https://github.com/<your-username>/<your-repo>.git

# Push all code
git push -u origin main
```

### Before pushing — make sure these are NOT committed

```bash
git status
```

The following should **never** appear (confirm they are in `.gitignore`):
- `.env` — contains your secret key and DB password
- `instance/` — contains local SQLite files (if any)
- `__pycache__/` — Python bytecode

### Workflow for future updates

```bash
# 1. Make your code changes
# 2. Stage and commit
git add .
git commit -m "Brief description of changes"

# 3. Push to GitHub
git push
```

---

## Troubleshooting

### App says "unable to connect to database"

The app tried to start before PostgreSQL was ready. This is handled automatically by the `healthcheck` in `docker-compose.yml`. If it still happens:

```bash
docker compose down
docker compose up --build
```

### Port 5432 already in use

You have a local PostgreSQL running. Either stop it or change the host port in `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"   # Use 5433 instead
```

### Port 5100 already in use

Change the host port in `docker-compose.yml`:
```yaml
ports:
  - "5200:5000"   # Use 5200 instead
```

### Rebuild from scratch (wipe everything)

```bash
docker compose down -v --rmi all
docker compose up --build
```

### Check container status

```bash
docker compose ps
docker compose logs flask       # Flask logs
docker compose logs flask_db    # PostgreSQL logs
```
