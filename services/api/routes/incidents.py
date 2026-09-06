import io
import csv
import os
import sys
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from shared.analyzer.engine import analyze_csv_stream

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

last_analysis_result = None

@router.post("/analyze")
async def analyze_incidents(file: UploadFile = File(...)):
    global last_analysis_result
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")
            
        text_stream = io.StringIO(content.decode("utf-8"))
        results = analyze_csv_stream(text_stream)
        
        last_analysis_result = results
        return results
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid encoding. File must be UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/export")
async def export_results():
    if not last_analysis_result:
        raise HTTPException(status_code=404, detail="No previous analysis found to export.")
        
    m = last_analysis_result["metrics"]
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Elements Processed", m["total_processed"]])
    writer.writerow(["Valid Records", m["valid_records"]])
    writer.writerow(["Invalid Records", m["invalid_records"]])
    for cat, count in m["category_breakdown"].items():
        writer.writerow([f"Category: {cat}", count])
    for status, count in m["status_breakdown"].items():
        writer.writerow([f"Status: {status}", count])
    writer.writerow(["Average Satisfaction Index", m["average_satisfaction_index"]])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"}
    )
