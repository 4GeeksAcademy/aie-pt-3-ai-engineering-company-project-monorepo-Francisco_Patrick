import sys
import os
import argparse
import csv

# Add monorepo root to sys.path so we can import shared module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.analyzer.engine import analyze_csv_stream

def print_summary(results: dict):
    m = results["metrics"]
    d = results["diagnostics"]
    
    print("=" * 50)
    print(" INCIDENT ANALYSIS SUMMARY")
    print("=" * 50)
    print(f"Total Elements Processed : {m['total_processed']}")
    print(f"  Valid Records          : {m['valid_records']}")
    print(f"  Invalid/Corrupt        : {m['invalid_records']}")
    print("-" * 50)
    
    print("Breakdown by Category:")
    for cat, count in m["category_breakdown"].items():
        print(f"  - {cat:<20}: {count}")
    print("-" * 50)
    
    print("Breakdown by Status:")
    for status, count in m["status_breakdown"].items():
        print(f"  - {status:<20}: {count}")
    print("-" * 50)
    
    print(f"Avg Satisfaction Index   : {m['average_satisfaction_index']} (closed cases only)")
    print("=" * 50)
    
    if m["invalid_records"] > 0:
        print("\n[WARNING] Invalid records detected!")
        print("Sample of invalid records:")
        for inv in d["invalid_sample"][:5]: # Show max 5
            print(f"  Row {inv['row']} (ID: {inv['id']}) - {inv['reason']}")

def export_to_csv(results: dict, output_path: str = "results.csv"):
    m = results["metrics"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Elements Processed", m["total_processed"]])
        writer.writerow(["Valid Records", m["valid_records"]])
        writer.writerow(["Invalid Records", m["invalid_records"]])
        for cat, count in m["category_breakdown"].items():
            writer.writerow([f"Category: {cat}", count])
        for status, count in m["status_breakdown"].items():
            writer.writerow([f"Status: {status}", count])
        writer.writerow(["Average Satisfaction Index", m["average_satisfaction_index"]])
    print(f"\nResults successfully exported to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Analyze incidents CSV.")
    parser.add_argument("csv_file", help="Path to the CSV file")
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"Error: File '{args.csv_file}' not found.")
        sys.exit(1)
        
    print(f"Analyzing {args.csv_file}...")
    try:
        with open(args.csv_file, "r", encoding="utf-8") as f:
            results = analyze_csv_stream(f)
    except Exception as e:
        print(f"Failed to process file: {e}")
        sys.exit(1)
        
    print_summary(results)
    
    # Prompt for export
    try:
        choice = input("\nExport results to CSV? [y / n]: ").strip().lower()
        if choice == 'y':
            export_to_csv(results)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
