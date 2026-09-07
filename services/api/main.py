import os
import sys
import io
import csv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Add monorepo root to sys.path so we can import shared module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from shared.analyzer.engine import analyze_csv_stream
from routes.suppliers import router as suppliers_router

# Auth & Users infrastructure wiring
from infrastructure.database import get_db
from infrastructure.adapters.tiny_db_repository import TinyDBUserRepository, TinyDBProfileRepository
from infrastructure.adapters.security_adapter import JwtSecurityAdapter

# Initialize adapters (will crash if JWT_SECRET_KEY is missing, fulfilling the requirement)
security_adapter = JwtSecurityAdapter()
db_instance = get_db()
user_repository = TinyDBUserRepository(db_instance)
profile_repository = TinyDBProfileRepository(db_instance)

def get_security_adapter() -> JwtSecurityAdapter:
    return security_adapter

def get_user_repository() -> TinyDBUserRepository:
    return user_repository

def get_profile_repository() -> TinyDBProfileRepository:
    return profile_repository


app = FastAPI(title="Incident Analyzer API")

app.include_router(suppliers_router)

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev purposes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store the last analysis result in memory to allow downloading it
# In a real system, this would be stored in a DB or cache
last_analysis_result = None

@app.post("/api/incidents/analyze")
async def analyze_incidents(file: UploadFile = File(...)):
    global last_analysis_result
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")
            
        # Decode and stream to the engine
        text_stream = io.StringIO(content.decode("utf-8"))
        results = analyze_csv_stream(text_stream)
        
        last_analysis_result = results
        return results
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid encoding. File must be UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/incidents/results/export")
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
