from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from optimiser import optimize_route, create_2_week_schedule
from scheduler import WindowCleanerScheduler
from database import db

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

@app.get("/health")
async def health_check():
    """Health check endpoint that also tests database connection"""
    try:
        # Test database connection
        test_response = db.client.table("work_schedules").select("count", count="exact").limit(1).execute()
        return {
            "status": "healthy",
            "database": "connected",
            "message": "FastAPI server and Supabase database are operational"
        }
    except Exception as e:
        return {
            "status": "degraded", 
            "database": "error",
            "message": f"Database connection issue: {str(e)}"
        }

@app.get("/customers/{user_id}")
async def get_customers(user_id: str):
    """Get all customers for a specific user"""
    try:
        customers = await db.get_customers(user_id)
        return {
            "user_id": user_id,
            "count": len(customers),
            "customers": customers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching customers: {str(e)}")

@app.post("/create-1week-schedule/{user_id}")
async def create_1week_schedule(user_id: str):
    """Create optimized 1-week schedule (8 days starting from today) from database data"""
    try:
        # Fetch work schedule from database
        work_schedule = await db.get_work_schedule(user_id)
        if not work_schedule:
            raise HTTPException(status_code=404, detail="Work schedule not found for user")
        
        # Fetch customers from database  
        customers = await db.get_customers(user_id)
        if not customers:
            raise HTTPException(status_code=404, detail="No customers found for user")
            
        # Fetch cleaner profile from database
        cleaner_profile = await db.get_cleaner_profile(user_id)
        if not cleaner_profile:
            # Use default cleaner location
            cleaner_start_location = (51.5, -0.1)  # London default
        else:
            cleaner_start_location = (
                cleaner_profile['start_location']['lat'],
                cleaner_profile['start_location']['lng']
            )
        
        # Create 1-week optimized schedule (8 days starting from today)
        schedule_result = create_2_week_schedule(
            customers=customers,
            work_schedule=work_schedule,
            cleaner_start_location=cleaner_start_location
        )
        
        # Save schedule to database (optional)
        await db.save_schedule(user_id, schedule_result['schedule'])
        
        return {
            "user_id": user_id,
            "schedule": schedule_result['schedule'],
            "summary": schedule_result['summary'],
            "time_savings_summary": schedule_result.get('time_savings_summary', {}),
            "unscheduled_customers": len(schedule_result['unscheduled_customers']),
            "message": "1-week schedule (8 days) created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating schedule: {str(e)}")

@app.post("/create-2week-schedule/{user_id}")
async def create_2week_schedule_redirect(user_id: str):
    """Backward compatibility - redirects to 1-week schedule endpoint"""
    return await create_1week_schedule(user_id)

@app.get("/time-savings/{user_id}")
async def get_time_savings_analysis(user_id: str):
    """Get detailed time savings analysis for a user's route optimization"""
    try:
        # Get data from database
        work_schedule = await db.get_work_schedule(user_id)
        customers = await db.get_customers(user_id)
        
        if not work_schedule:
            raise HTTPException(status_code=404, detail="Work schedule not found")
        
        if not customers:
            raise HTTPException(status_code=404, detail="No customers found")
        
        # Default cleaner location (you can make this configurable)
        cleaner_start_location = (51.5074, -0.1278)  # London center as default
        
        # Calculate time savings for all customers
        from optimiser import calculate_time_savings
        time_savings = calculate_time_savings(customers, cleaner_start_location)
        
        # Also get 1-week schedule with savings
        full_schedule = create_2_week_schedule(customers, work_schedule, cleaner_start_location)
        
        return {
            "user_id": user_id,
            "total_customers": len(customers),
            "daily_time_savings": time_savings,
            "one_week_savings": full_schedule.get('time_savings_summary', {}),
            "efficiency_analysis": {
                "average_time_saved_per_customer": round(time_savings['time_savings_minutes'] / max(len(customers), 1), 2),
                "potential_monthly_savings_hours": round(time_savings['time_savings_hours'] * 4, 1),
                "potential_annual_fuel_savings": round(time_savings['fuel_savings_estimate_gbp'] * 52, 2)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating time savings: {str(e)}")

@app.post('/generate-schedule-from-db/{user_id}')
async def generate_schedule_from_database(user_id: str):
    """
    Generate schedule using data from Supabase database
    
    Args:
        user_id: UUID of the user
    """
    try:
        # Fetch work schedule from database
        work_schedule = await db.get_work_schedule(user_id)
        if not work_schedule:
            raise HTTPException(status_code=404, detail="Work schedule not found for user")
        
        # Fetch customers from database  
        customers = await db.get_customers(user_id)
        if not customers:
            raise HTTPException(status_code=404, detail="No customers found for user")
            
        # Fetch cleaner profile from database (uses default profile for now)
        cleaner_profile = await db.get_cleaner_profile(user_id)
        if not cleaner_profile:
            # Fallback to default cleaner profile
            cleaner_profile = {
                "id": 1,
                "work_hours": [9, 17],
                "start_location": {"lat": 51.5, "lng": -0.1}
            }
        
        # Set default constraints (you can make this configurable)
        constraints = {"min_gap_days": 0, "max_gap_days": 2}
        
        # Create scheduler instance
        scheduler = WindowCleanerScheduler()
        
        # Generate schedule with database data
        full_schedule = scheduler.generate_full_schedule(
            customers, 
            cleaner_profile, 
            work_schedule, 
            constraints
        )
        
        # Optionally save the generated schedule back to database
        await db.save_schedule(user_id, full_schedule)
        
        return {
            "schedule": full_schedule,
            "user_id": user_id,
            "work_schedule_applied": work_schedule,
            "total_customers": len(customers)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating schedule: {str(e)}")

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
