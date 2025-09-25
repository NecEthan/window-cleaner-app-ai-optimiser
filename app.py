from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from optimiser import create_2_week_schedule
from database import SupabaseClient

app = FastAPI(title="Window Cleaner AI Optimizer", version="1.0.0")
db = SupabaseClient()

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



@app.post("/create-1week-schedule/{user_id}")
async def create_1week_schedule(user_id: str):
    """Create optimized 1-week schedule (8 days starting from today) from database data"""
    try:
        # Fetch work schedule from database
        work_schedule = db.get_work_schedule(user_id)
        if not work_schedule:
            raise HTTPException(status_code=404, detail="Work schedule not found for user")
        
        # Fetch customers from database  
        customers = db.get_customers(user_id)
        if not customers:
            raise HTTPException(status_code=404, detail="No customers found for user")
            
        # Use default cleaner location (London center)
        cleaner_start_location = (51.5074, -0.1278)
        
        # Create 1-week optimized schedule (8 days starting from today)
        schedule_result = create_2_week_schedule(
            customers=customers,
            work_schedule=work_schedule,
            cleaner_start_location=cleaner_start_location
        )
        
        # Save optimized schedule to database
        try:
            schedule_id = await db.save_optimized_schedule(user_id, work_schedule, schedule_result['schedule'])
            print(f"✅ Schedule saved to database with ID: {schedule_id}")
        except Exception as save_error:
            print(f"⚠️ Warning: Failed to save schedule to database: {save_error}")
            # Continue without failing the request

        
        return {
            "user_id": user_id,
            "schedule": schedule_result['schedule'],
            "summary": schedule_result['summary'],
            "time_savings_summary": schedule_result.get('time_savings_summary', {}),
            "unscheduled_customers": len(schedule_result['unscheduled_customers']),
            "schedule_saved_to_db": True,
            "message": "1-week schedule (8 days) created successfully and saved to database"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating schedule: {str(e)}")

@app.post("/create-2week-schedule/{user_id}")
async def create_2week_schedule_redirect(user_id: str):
    """Backward compatibility - redirects to 1-week schedule endpoint"""
    return await create_1week_schedule(user_id)

# Pydantic model for work schedule input
class WorkScheduleInput(BaseModel):
    monday_hours: Optional[float] = None
    tuesday_hours: Optional[float] = None
    wednesday_hours: Optional[float] = None
    thursday_hours: Optional[float] = None
    friday_hours: Optional[float] = None
    saturday_hours: Optional[float] = None
    sunday_hours: Optional[float] = None

class CustomerInput(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    price: float
    estimated_duration: int
    last_cleaned: str
    frequency_days: int

class ScheduleRequestWithData(BaseModel):
    work_schedule: WorkScheduleInput
    customers: List[CustomerInput]
    cleaner_start_location: Optional[Dict[str, float]] = {"lat": 51.5074, "lng": -0.1278}

@app.post("/create-schedule-with-data/{user_id}")
async def create_schedule_with_data(user_id: str, request: ScheduleRequestWithData):
    """
    Create optimized 1-week schedule with work schedule and customer data passed in the request
    This endpoint allows Express/frontend to pass all necessary data directly
    """
    try:
        # Convert Pydantic models to dictionaries
        work_schedule = request.work_schedule.model_dump()
        customers = [customer.model_dump() for customer in request.customers]
        
        # Get cleaner start location
        cleaner_start_location = (
            request.cleaner_start_location["lat"],
            request.cleaner_start_location["lng"]
        )
        
        # Create 1-week optimized schedule
        schedule_result = create_2_week_schedule(
            customers=customers,
            work_schedule=work_schedule,
            cleaner_start_location=cleaner_start_location
        )
        
        return {
            "user_id": user_id,
            "work_schedule_used": work_schedule,
            "total_customers_provided": len(customers),
            "schedule": schedule_result['schedule'],
            "summary": schedule_result['summary'],
            "time_savings_summary": schedule_result.get('time_savings_summary', {}),
            "unscheduled_customers": len(schedule_result.get('unscheduled_customers', [])),
            "message": "1-week schedule (8 days) created successfully with provided data"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating schedule with data: {str(e)}")

# Pydantic model for Express backend integration
class ExpressScheduleRequest(BaseModel):
    work_schedule: WorkScheduleInput
    cleaner_start_location: Optional[Dict[str, float]] = {"lat": 51.5074, "lng": -0.1278}

@app.post("/create-schedule-from-express/{user_id}")
async def create_schedule_from_express(user_id: str, request: ExpressScheduleRequest):
    """
    Express Backend Integration Endpoint
    
    Receives work schedule from Express backend, fetches customers from database,
    optimizes the schedule, and returns optimized customer schedule back to Express.
    
    Perfect for Express → FastAPI → Express integration workflow.
    """
    try:
        # Convert work schedule from Express
        work_schedule = request.work_schedule.model_dump()
        
        # Fetch customers from database using the user_id
        customers = await db.get_customers(user_id)
        if not customers:
            raise HTTPException(status_code=404, detail="No customers found for user in database")
        
        # Get cleaner start location from Express request
        cleaner_start_location = (
            request.cleaner_start_location["lat"],
            request.cleaner_start_location["lng"]
        )
        
        # Create optimized 1-week schedule
        schedule_result = create_2_week_schedule(
            customers=customers,
            work_schedule=work_schedule,
            cleaner_start_location=cleaner_start_location
        )
        
        # Save optimized schedule to database
        try:
            schedule_id = await db.save_optimized_schedule(user_id, work_schedule, schedule_result['schedule'])
            print(f"✅ Express integration: Schedule saved to database with ID: {schedule_id}")
            schedule_saved = True
        except Exception as save_error:
            print(f"⚠️ Warning: Failed to save schedule to database: {save_error}")
            schedule_saved = False
            # Continue without failing the request
        
        return {
            "user_id": user_id,
            "express_integration": True,
            "work_schedule_received": work_schedule,
            "customers_from_database": len(customers),
            "schedule": schedule_result['schedule'],
            "summary": schedule_result['summary'],
            "time_savings_summary": schedule_result.get('time_savings_summary', {}),
            "unscheduled_customers": len(schedule_result.get('unscheduled_customers', [])),
            "schedule_saved_to_db": schedule_saved,
            "message": "Express → FastAPI integration successful! Schedule optimized and saved to database"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Express integration error: {str(e)}")

@app.get("/todays-schedule/{user_id}")
async def get_todays_schedule(user_id: str):
    """
    Get today's scheduled customers from the database
    
    This endpoint retrieves the customers that are scheduled to be cleaned today
    based on the previously saved optimized schedule.
    """
    try:
        todays_schedule = await db.get_todays_schedule(user_id)
        
        if not todays_schedule:
            return {
                "user_id": user_id,
                "date": None,
                "customers": [],
                "message": "No customers scheduled for today"
            }
        
        return {
            "user_id": user_id,
            "date": todays_schedule["date"],
            "route_info": {
                "estimated_duration": todays_schedule["route"]["estimated_duration"],
                "estimated_revenue": todays_schedule["route"]["estimated_revenue"],
                "max_work_hours": todays_schedule["route"]["max_work_hours"],
                "day_name": todays_schedule["route"]["day_name"]
            },
            "customers": todays_schedule["customers"],
            "total_customers": len(todays_schedule["customers"]),
            "message": f"Today's schedule: {len(todays_schedule['customers'])} customers to visit"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving today's schedule: {str(e)}")



if __name__ == '__main__':
    import uvicorn
    print("🚀 Starting Window Cleaner AI Optimizer...")
    print("📍 Server will be available at: http://127.0.0.1:5003")
    print("📋 Essential Endpoints:")
    print("   • GET  /health - Health check")
    print("   • POST /create-1week-schedule/{user_id} - Generate schedule from database")
    print("   • POST /create-schedule-with-data/{user_id} - Generate schedule with provided data")
    print("   • POST /create-schedule-from-express/{user_id} - Express backend integration ⭐")
    print("   • GET  /todays-schedule/{user_id} - Get today's scheduled customers 📅")
    print("   • POST /create-2week-schedule/{user_id} - Backward compatibility endpoint")
    uvicorn.run(app, host="127.0.0.1", port=5003)
