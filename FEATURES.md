# LDMS Feature History & Roadmap

This document tracks the evolution of the **LiDAR Defect Management System (LDMS)**, highlighting major milestones and technical implementations.

## 🚀 Core Engine
- **Asynchronous Defect Detection**: Multi-threaded processing of GLB/PCD files to identify surface anomalies.
- **3D Spatial Mapping**: Conversion of raw scan coordinates into a navigable defect database.
- **GLB Snapshot Engine**: Automatic generation of 2D images from 3D model viewpoints for visual reporting.

## 🧠 AI & Analytics (The "Brain")
- **AI Spatial Insights (DBSCAN)**:
    - Automatically clusters related defects into "Hotspots" based on spatial proximity (using `scikit-learn`).
    - **Engine Parameters**: Uses an epsilon of `5.0m` (radius) and a minimum density of `2 defects` to trigger a cluster alert.
    - **Verified Cluster Logic**: Intelligent extraction of room names (e.g., Master Bedroom, Kitchen) to provide human-readable location tags for hotspots.
- **Dynamic Risk Scoring (0–100 Scale)**:
    - Automatically calculates a numeric risk value based on two primary factors:
        - **Severity Weight (Max 50 pts)**: Critical (50), High (35), Medium (20), Low (5).
        - **Defect Type Weight (Max 50 pts)**:
            - *Structural/Safety Focus (50)*: Core structural issues.
            - *Life Safety & Integrity (35)*: Water damage, electrical hazards, or cracks.
            - *Service/Utility (20)*: Mechanical or plumbing issues.
            - *Minor/Cosmetic (10)*: Finishes or unknown types.
    - **Automated Priority Thresholds**:
        - 🚨 **Urgent**: Score 80+ (Critical/Structural combination).
        - 🟠 **High**: Score 60–79.
        - 🔵 **Medium**: Score 30–59.
        - 🟢 **Low**: Score < 30.
- **Defect Analytics**: Interactive charts (doughnut/bar) showing status distribution and severity breakdowns.

## 🎨 Premium UI/UX
- **Bento Grid Dashboard**: A modern, data-dense layout that organizes key metrics and logs into a sleek, responsive grid.
- **Glassmorphism Design**: High-end aesthetic with backdrop filters, semi-transparent panels, and premium typography (Space Grotesk).
- **High-Visibility Alerts**: Danger-red accents for critical hotspots and verified cluster banners for high-risk zones.
- **Defect Master Log**: Enhanced table with mini-progress bars for risk scores and status-badge tracking.
- **Developer My Tasks Queue**: Personal task view with Mine, Unassigned, Overdue, and All tabs plus bulk assignment actions.

## 👥 Roles & Security
- **Role-Based Access Control (RBAC)**:
    - **Inspector**: Permissions to upload scans, run AI detection, change defect priority, and generate PDF Reports.
    - **Developer**: Permissions to track progress, update repair notes, change defect status, and manage defect assignments/due dates.
    - **Manager**: Permissions to access the manager dashboard, assign project ownership to developers, and monitor team workload.
- **Permission Guarding**: Manual priority overrides are restricted for Developers to ensure repair teams focus on AI-driven risk targets; only Inspectors or the AI logic can influence priority rankings.

## 🧩 Task Management
- **Task Ownership Fields**: Defects now carry assignee metadata, assignment timestamps, and due dates.
- **Task Queue Filters**: Developers can filter tasks by personal ownership, unassigned items, and overdue work.
- **Bulk Actions**: Selected tasks can be claimed, unassigned, or re-assigned to another developer in one operation.
- **Activity Logging**: Status, assignee, and due-date changes are tracked with idempotent activity entries.

## 📄 Data Integration & Orchestration
- **PDF Image Extraction Engine**: Professional extraction of embedded images from uploaded PDF inspection reports, ensuring defect records are visually linked to field notes.
- **Email Notifications**: Integration for notifying team members of status changes (Reported -> Fixed).
- **Dockerized Deployment**: Fully containerized stack for consistent development and production environments.

