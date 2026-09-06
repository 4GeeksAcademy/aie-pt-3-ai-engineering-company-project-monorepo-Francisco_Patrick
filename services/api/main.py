import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from routes import incidents, suppliers

app = FastAPI(title="TrackFlow API")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev purposes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router)
app.include_router(suppliers.router)
