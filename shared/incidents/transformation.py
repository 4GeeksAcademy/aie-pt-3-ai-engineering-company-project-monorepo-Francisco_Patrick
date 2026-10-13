from typing import Dict, Tuple, Any, Optional
from datetime import datetime, timezone
from shared.incidents.enums import IncidentCategory, IncidentStatus, IncidentOrigin

STATUS_MAP = {
    "open": IncidentStatus.OPEN,
    "closed": IncidentStatus.RESOLVED,
    "resolved": IncidentStatus.RESOLVED,
    "in_progress": IncidentStatus.IN_PROGRESS,
    "discarded": IncidentStatus.DISCARDED
}

ALLOWED_CATEGORIES = {cat.value for cat in IncidentCategory}
ALLOWED_STATUSES = set(STATUS_MAP.keys())
REQUIRED_CSV_FIELDS = {"id", "date", "category", "status"}

def validate_csv_record(record: Dict[str, str]) -> Tuple[bool, str]:
    """Validates a single CSV record row against required fields and allowed enums."""
    for field in REQUIRED_CSV_FIELDS:
        if field not in record or not str(record[field]).strip():
            return False, f"Missing or empty required field: {field}"
    
    cat = str(record["category"]).strip()
    if cat not in ALLOWED_CATEGORIES:
        return False, f"Invalid category: {cat}"
    
    st = str(record["status"]).strip()
    if st not in ALLOWED_STATUSES:
        return False, f"Invalid status: {st}"
        
    return True, ""

def transform_csv_record_to_incident_dict(record: Dict[str, str]) -> Dict[str, Any]:
    """
    Transforms a validated CSV row into an Incident dictionary.
    - origin: 'customer'
    - status: mapped ('closed' -> 'resolved', 'open' -> 'open', 'discarded' -> 'discarded')
    - title & description: generated from CSV record attributes
    - created_at: ISO-8601 string from CSV date
    - branch: 'central' (default)
    - legacy_id: original CSV id
    """
    legacy_id = str(record["id"]).strip()
    raw_cat = str(record["category"]).strip()
    raw_status = str(record["status"]).strip()
    raw_date = str(record["date"]).strip()
    
    mapped_status = STATUS_MAP.get(raw_status, IncidentStatus.OPEN)
    
    # Parse date to ISO-8601 format
    try:
        dt = datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        iso_date = dt.isoformat()
    except Exception:
        iso_date = datetime.now(timezone.utc).isoformat()
        
    title = str(record.get("description", "")).strip()
    if not title:
        title = f"Historical Incident #{legacy_id} ({raw_cat.replace('_', ' ').title()})"
        
    description = str(record.get("details", "")).strip()
    if not description:
        description = f"Historical incident imported from legacy CSV record ID {legacy_id}. Original status: {raw_status}."

    branch = str(record.get("branch", record.get("location", "central"))).strip()
    if not branch:
        branch = "central"

    return {
        "title": title,
        "description": description,
        "category": raw_cat,
        "status": mapped_status.value,
        "origin": IncidentOrigin.CUSTOMER.value,
        "branch": branch,
        "created_at": iso_date,
        "updated_at": iso_date,
        "legacy_id": legacy_id
    }
