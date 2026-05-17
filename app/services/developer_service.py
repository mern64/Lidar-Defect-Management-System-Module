from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple

from app.extensions import db
from app.models import Defect, DefectStatus, DefectPriority, Scan, User
from sqlalchemy import case, func


def get_scans_with_defect_counts(
    *,
    user_id: Optional[int] = None,
    is_manager: bool = False,
    sort: str = "recent",
    date_range: str = "all",
    status_filter: str = "all",
) -> List[tuple]:
    """Query scans with aggregated defect counts.

    When *user_id* is provided (developer view), results are filtered
    to scans assigned to that user.  When *is_manager* is ``True``,
    all scans are returned (manager portfolio view).
    """
    order_clause = Scan.created_at.desc() if sort == "recent" else Scan.created_at.asc()

    query = db.session.query(
        Scan,
        func.count(Defect.id).label('defect_count'),
        func.coalesce(func.sum(case((Defect.status == DefectStatus.REPORTED.value, 1), else_=0)), 0).label('reported_count'),
        func.coalesce(func.sum(case((Defect.status == DefectStatus.UNDER_REVIEW.value, 1), else_=0)), 0).label('review_count'),
        func.coalesce(func.sum(case((Defect.status == DefectStatus.FIXED.value, 1), else_=0)), 0).label('fixed_count'),
    ).outerjoin(Defect).group_by(Scan.id).order_by(order_clause)

    if user_id is not None:
        query = query.filter(Scan.assigned_to_user_id == user_id)

    query = _apply_date_filter(query, date_range, Scan)

    scans = query.all()

    if status_filter != "all":
        scans = _filter_scans_by_status(scans, status_filter)

    return scans


def get_dashboard_metrics() -> dict:
    """Return high-level dashboard metrics."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    urgent_attention = Defect.query.filter(
        Defect.priority.in_([DefectPriority.URGENT, DefectPriority.HIGH]),
        Defect.status != DefectStatus.FIXED,
    ).count()

    stale_reviews = Defect.query.filter(
        Defect.status == DefectStatus.UNDER_REVIEW,
        Defect.created_at < (now_utc - timedelta(days=7)),
    ).count()

    new_defects_24h = Defect.query.filter(
        Defect.created_at >= (now_utc - timedelta(hours=24)),
    ).count()

    return {
        'urgent_attention': urgent_attention,
        'stale_reviews': stale_reviews,
        'new_24h': new_defects_24h,
    }


def get_team_workload(developers: List[User]) -> List[dict]:
    """Build workload data for each developer."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    workload = []
    for dev in developers:
        assigned_projects = Scan.query.filter_by(assigned_to_user_id=dev.id).count()
        open_defect_rows = Defect.query.join(Scan, Scan.id == Defect.scan_id).filter(
            Scan.assigned_to_user_id == dev.id,
            Defect.status != DefectStatus.FIXED,
            Defect.is_active.is_(True),
        ).all()
        open_defects = len(open_defect_rows)
        urgent_open = sum(
            1 for d in open_defect_rows
            if d.priority in (DefectPriority.URGENT, DefectPriority.HIGH)
        )
        average_age_days = 0.0
        if open_defect_rows:
            ages = [
                max((now_utc - (d.created_at or now_utc)).total_seconds() / 86400, 0)
                for d in open_defect_rows
            ]
            average_age_days = round(sum(ages) / len(ages), 1)

        if open_defects >= 20 or urgent_open >= 8:
            load_state = 'overloaded'
        elif open_defects >= 8 or urgent_open >= 3:
            load_state = 'balanced'
        else:
            load_state = 'underloaded'

        utilization_percent = min(int((open_defects / 20) * 100), 100) if open_defects > 0 else 0

        workload.append({
            'developer': dev,
            'assigned_projects': assigned_projects,
            'open_defects': open_defects,
            'urgent_open': urgent_open,
            'average_age_days': average_age_days,
            'load_state': load_state,
            'utilization_percent': utilization_percent,
        })
    return workload


def get_escalation_data(scan_ids: List[int]) -> dict:
    """Return escalation counts (urgent, stale, overdue) per scan."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    seven_days_ago = now_utc - timedelta(days=7)

    if not scan_ids:
        return {}

    rows = db.session.query(
        Defect.scan_id,
        func.coalesce(
            func.sum(
                case(
                    (
                        db.and_(
                            Defect.priority.in_([DefectPriority.URGENT, DefectPriority.HIGH]),
                            Defect.status != DefectStatus.FIXED,
                            Defect.is_active.is_(True),
                        ), 1,
                    ), else_=0,
                )
            ), 0,
        ).label('urgent_open_count'),
        func.coalesce(
            func.sum(
                case(
                    (
                        db.and_(
                            Defect.status == DefectStatus.UNDER_REVIEW,
                            Defect.created_at < seven_days_ago,
                            Defect.is_active.is_(True),
                        ), 1,
                    ), else_=0,
                )
            ), 0,
        ).label('stale_review_count'),
    ).filter(
        Defect.scan_id.in_(scan_ids),
    ).group_by(Defect.scan_id).all()

    return {
        row.scan_id: {
            'urgent_open_count': int(row.urgent_open_count or 0),
            'stale_review_count': int(row.stale_review_count or 0),
            'overdue_open_count': 0,
        }
        for row in rows
    }


def build_escalation_flags(scan: Scan, counts: dict) -> dict:
    """Build human-readable escalation flags for a single scan."""
    flags = []
    summary = {'urgent_hotspots': 0, 'stale_reviews': 0, 'overdue_backlog': 0}

    if counts['urgent_open_count'] >= 3:
        flags.append({
            'type': 'urgent_hotspots', 'label': 'Urgent Hotspot',
            'detail': f"{counts['urgent_open_count']} urgent/high open",
            'level': 'danger',
        })
        summary['urgent_hotspots'] += 1
    if counts['stale_review_count'] >= 2:
        flags.append({
            'type': 'stale_reviews', 'label': 'Stale Review',
            'detail': f"{counts['stale_review_count']} reviews older than 7d",
            'level': 'warning',
        })
        summary['stale_reviews'] += 1

    return {'flags': flags, 'counts': counts}


def _apply_date_filter(query, date_range: str, model) -> Any:
    """Apply a date-range WHERE clause."""
    if date_range == "week":
        cutoff = datetime.now() - timedelta(days=7)
        return query.filter(model.created_at >= cutoff)
    elif date_range == "month":
        cutoff = datetime.now() - timedelta(days=30)
        return query.filter(model.created_at >= cutoff)
    elif date_range == "3months":
        cutoff = datetime.now() - timedelta(days=90)
        return query.filter(model.created_at >= cutoff)
    return query


def _filter_scans_by_status(
    scans: List[tuple], status_filter: str,
) -> List[tuple]:
    """Filter scan result tuples by overall status."""
    filtered = []
    for scan_data in scans:
        scan, defect_count, reported, review, fixed = scan_data
        if status_filter == "complete" and defect_count > 0 and fixed == defect_count:
            filtered.append(scan_data)
        elif status_filter == "in_progress" and review > 0:
            filtered.append(scan_data)
        elif status_filter == "started" and reported > 0 and review == 0 and fixed == 0:
            filtered.append(scan_data)
    return filtered
