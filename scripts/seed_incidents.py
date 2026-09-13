import sys
import os
import csv
import argparse

# Add monorepo root and services/api to sys.path
MONOREPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, MONOREPO_ROOT)

API_DIR = os.path.join(MONOREPO_ROOT, 'services', 'api')
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from shared.incidents.transformation import validate_csv_record, transform_csv_record_to_incident_dict
from infrastructure.database import get_db
from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository
from domain.incident_model import Incident


def seed_incidents_from_csv(csv_path: str) -> dict:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    db = get_db()
    repo = TinyDBIncidentRepository(db)

    inserted_count = 0
    skipped_duplicate_count = 0
    invalid_count = 0
    invalid_records = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2): # Header is row 1
            try:
                is_valid, reason = validate_csv_record(row)
                if not is_valid:
                    invalid_count += 1
                    invalid_records.append({
                        "row": row_num,
                        "id": row.get("id", "N/A"),
                        "reason": reason
                    })
                    print(f"[WARN] Row {row_num}: Invalid record ({reason})", file=sys.stderr)
                    continue

                legacy_id = str(row.get("id", "")).strip()

                # Idempotency check: verify if record with legacy_id already exists in database
                existing = repo.find_by_legacy_id(legacy_id)
                if existing:
                    skipped_duplicate_count += 1
                    continue

                # Transform CSV record to domain Incident model
                incident_data = transform_csv_record_to_incident_dict(row)
                incident = Incident.from_dict(incident_data)
                repo.save(incident)
                inserted_count += 1
            except Exception as row_err:
                invalid_count += 1
                reason = f"Unexpected row processing failure: {row_err}"
                invalid_records.append({
                    "row": row_num,
                    "id": row.get("id", "N/A") if isinstance(row, dict) else "N/A",
                    "reason": reason
                })
                print(f"[ERROR] Row {row_num}: Skipped due to error: {row_err}", file=sys.stderr)
                continue

    return {
        "total_processed": inserted_count + skipped_duplicate_count + invalid_count,
        "inserted_count": inserted_count,
        "skipped_duplicate_count": skipped_duplicate_count,
        "invalid_count": invalid_count,
        "invalid_records": invalid_records
    }

def print_summary(results: dict):
    print("=" * 60)
    print(" HISTORICAL INCIDENT SEED SUMMARY")
    print("=" * 60)
    print(f"Total CSV Rows Processed : {results['total_processed']}")
    print(f"  Inserted Records (customer) : {results['inserted_count']}")
    print(f"  Skipped (Idempotent Dupes) : {results['skipped_duplicate_count']}")
    print(f"  Invalid / Corrupt Rows     : {results['invalid_count']}")
    print("=" * 60)

    if results["invalid_count"] > 0:
        print("\n[REPORT] Invalid CSV Records Excluded From Insert:")
        for inv in results["invalid_records"]:
            print(f"  - Row {inv['row']} (Legacy ID: {inv['id']}): {inv['reason']}")

def main():
    parser = argparse.ArgumentParser(description="Seed historical customer incidents into database.")
    default_csv = os.path.join(os.path.dirname(__file__), "incidents-COMPANY.csv")
    parser.add_argument("csv_file", nargs="?", default=default_csv, help="Path to historical CSV dataset")
    args = parser.parse_args()

    print(f"Seeding historical incidents from {args.csv_file}...")
    try:
        results = seed_incidents_from_csv(args.csv_file)
        print_summary(results)
    except FileNotFoundError as fnf_err:
        print(f"[ERROR] File not found: {fnf_err}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Seeding process interrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] Failed to seed incidents: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
