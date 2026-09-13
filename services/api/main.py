import os
import sys
import io
import csv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse


app = FastAPI(title="Incident Analyzer API")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []
    for err in exc.errors():
        locs = [str(l) for l in err.get("loc", []) if str(l) != "body"]
        field_name = " -> ".join(locs) if locs else "payload"
        errors.append({"field": field_name, "issue": err.get("msg")})
    return JSONResponse(
        status_code=400,
        content={
            "error": "Validation Error",
            "message": f"Validation failed for field '{errors[0]['field']}': {errors[0]['issue']}" if errors else "Validation failed",
            "details": errors
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
            "detail": exc.detail
        }
    )


from domain.exceptions import InvalidStatusTransitionError, IncidentNotFoundError, DomainException

@app.exception_handler(InvalidStatusTransitionError)
async def invalid_status_transition_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid Status Transition",
            "message": str(exc),
            "detail": str(exc)
        }
    )

@app.exception_handler(IncidentNotFoundError)
async def incident_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": str(exc),
            "detail": str(exc)
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Server Error",
            "message": "An unexpected error occurred. Please try again or contact support."
        }
    )



# Add monorepo root to sys.path so we can import shared module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from shared.analyzer.engine import analyze_csv_stream
from routes.suppliers import router as suppliers_router
from presentation.api.user_routes import router as user_router
from presentation.api.auth_routes import router as auth_router
from presentation.api.profile_routes import router as profile_router
from presentation.api.incident_routes import router as incident_router
from presentation.dependencies import get_security_adapter_dep, get_user_service_dep, get_auth_service_dep, get_profile_service_dep, get_incident_service_dep
from application.services.user_service import UserService
from application.services.auth_service import AuthService
from application.services.profile_service import ProfileService
from application.services.incident_service import IncidentService

# Auth & Users infrastructure wiring
from infrastructure.database import get_db
from infrastructure.adapters.tiny_db_repository import TinyDBUserRepository, TinyDBProfileRepository
from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository
from infrastructure.adapters.security_adapter import JwtSecurityAdapter

# Initialize adapters (will crash if JWT_SECRET_KEY is missing, fulfilling the requirement)
security_adapter = JwtSecurityAdapter()
db_instance = get_db()
user_repository = TinyDBUserRepository(db_instance)
profile_repository = TinyDBProfileRepository(db_instance)
incident_repository = TinyDBIncidentRepository(db_instance)

def get_security_adapter() -> JwtSecurityAdapter:
    return security_adapter

def get_user_repository() -> TinyDBUserRepository:
    return user_repository

def get_profile_repository() -> TinyDBProfileRepository:
    return profile_repository

# Initialize application services
user_service = UserService(
    user_repo=user_repository,
    profile_repo=profile_repository,
    security_port=security_adapter
)
auth_service = AuthService(
    user_repo=user_repository,
    security_port=security_adapter
)
profile_service = ProfileService(
    profile_repo=profile_repository
)

# Dependency overrides for routing
app.dependency_overrides[get_security_adapter_dep] = lambda: security_adapter
app.dependency_overrides[get_user_service_dep] = lambda: user_service
app.dependency_overrides[get_auth_service_dep] = lambda: auth_service
app.dependency_overrides[get_profile_service_dep] = lambda: profile_service





app.include_router(suppliers_router)
app.include_router(user_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(incident_router)


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
    
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    try:
        content = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read uploaded file payload.")
        
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            
    try:
        text_stream = io.StringIO(content.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid encoding. File must be UTF-8 encoded.")

    try:
        results = analyze_csv_stream(text_stream)
        last_analysis_result = results
        return results
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=f"CSV processing failed: {str(ve)}")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while analyzing the incident data. Please verify file format and try again."
        )


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
