from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from optimiser import optimize_route
from scheduler import WindowCleanerScheduler

app = FastAPI(title="Window Cleaner AI Optimizer", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Window Cleaner AI Optimizer FastAPI Server", "status": "running"}

# Pydantic models for request/response
class Customer(BaseModel):
    id: int
    lat: float
    lng: float
    last_cleaned: str
    frequency_days: int

class Location(BaseModel):
    lat: float
    lng: float

class Cleaner(BaseModel):
    id: int
    work_hours: List[int]
    start_location: Location

class Constraints(BaseModel):
    min_gap_days: int
    max_gap_days: int

class WorkSchedule(BaseModel):
    user_id: Optional[str] = None
    monday_hours: Optional[float] = None
    tuesday_hours: Optional[float] = None
    wednesday_hours: Optional[float] = None
    thursday_hours: Optional[float] = None
    friday_hours: Optional[float] = None
    saturday_hours: Optional[float] = None
    sunday_hours: Optional[float] = None
    total_weekly_hours: Optional[float] = None
    working_days_count: Optional[int] = None
    is_active: Optional[bool] = True

class ScheduleRequest(BaseModel):
    customers: List[Customer]
    cleaner: Cleaner
    constraints: Constraints
    work_schedule: Optional[WorkSchedule] = None

class SimpleRouteRequest(BaseModel):
    customers: List[Customer]

@app.post('/generate-schedule')
async def generate_schedule(request: ScheduleRequest):
    # Convert Pydantic models to dictionaries for the scheduler
    customers = [customer.model_dump() for customer in request.customers]
    cleaner = request.cleaner.model_dump()
    constraints = request.constraints.model_dump()
    work_schedule = request.work_schedule.model_dump() if request.work_schedule else None
    
    # Create scheduler instance
    scheduler = WindowCleanerScheduler()
    
    # Generate full multi-day schedule with work schedule
    full_schedule = scheduler.generate_full_schedule(customers, cleaner, work_schedule, constraints)
    
    return {"schedule": full_schedule}

# Keep the original simple route optimizer for backward compatibility
@app.post('/generate-simple-route')
async def generate_simple_route(request: SimpleRouteRequest):
    customers = [customer.model_dump() for customer in request.customers]
    # extract lat/lng
    locations = [(c['lat'], c['lng']) for c in customers]
    order = optimize_route(locations)
    # return ordered schedule
    schedule = [{"customer_id": customers[i]["id"], "order": idx+1} for idx, i in enumerate(order)]
    return {"schedule": schedule}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
