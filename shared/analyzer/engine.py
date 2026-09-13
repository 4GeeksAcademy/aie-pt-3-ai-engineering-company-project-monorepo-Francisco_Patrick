from shared.incidents.transformation import (
    validate_csv_record,
    transform_csv_record_to_incident_dict,
    ALLOWED_CATEGORIES,
    ALLOWED_STATUSES,
    REQUIRED_CSV_FIELDS
)

def validate_record(record: Dict[str, str]) -> Tuple[bool, str]:
    """Validates a single record and returns (is_valid, error_reason)."""
    return validate_csv_record(record)


def analyze_csv_stream(file_stream: TextIO) -> Dict[str, Any]:
    """
    Processes the CSV stream and returns the calculated metrics.
    Scalable: reads line by line.
    """
    reader = csv.DictReader(file_stream)
    
    valid_count = 0
    invalid_count = 0
    invalid_records = []
    
    category_breakdown = {cat: 0 for cat in ALLOWED_CATEGORIES}
    status_breakdown = {status: 0 for status in ALLOWED_STATUSES}
    
    closed_satisfaction_sum = 0.0
    closed_satisfaction_count = 0
    
    for row_num, row in enumerate(reader, start=2): # Header is line 1
        is_valid, error = validate_record(row)
        if not is_valid:
            invalid_count += 1
            # Store up to 100 invalid records to prevent memory overflow on huge files
            if len(invalid_records) < 100:
                invalid_records.append({
                    "row": row_num,
                    "id": row.get("id", "UNKNOWN"),
                    "reason": error
                })
            continue
            
        valid_count += 1
        category_breakdown[row["category"]] += 1
        status_breakdown[row["status"]] += 1
        
        if row["status"] == "closed":
            score_str = row.get("satisfaction_index", "").strip()
            if score_str:
                try:
                    score = float(score_str)
                    closed_satisfaction_sum += score
                    closed_satisfaction_count += 1
                except ValueError:
                    pass # Ignore unparseable scores
                    
    avg_satisfaction = 0.0
    if closed_satisfaction_count > 0:
        avg_satisfaction = closed_satisfaction_sum / closed_satisfaction_count
        
    return {
        "metrics": {
            "total_processed": valid_count + invalid_count,
            "valid_records": valid_count,
            "invalid_records": invalid_count,
            "category_breakdown": category_breakdown,
            "status_breakdown": status_breakdown,
            "average_satisfaction_index": round(avg_satisfaction, 2)
        },
        "diagnostics": {
            "invalid_sample": invalid_records
        }
    }
