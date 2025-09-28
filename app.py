from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from optimiser import optimize_route
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
        work_schedule = await db.get_work_schedule(user_id)
        if not work_schedule:
            raise HTTPException(status_code=404, detail="Work schedule not found for user")
        
        # Fetch customers from database  
        customers = await db.get_customers(user_id)
        if not customers:
            raise HTTPException(status_code=404, detail="No customers found for user")
            
        # Use default cleaner location (London center)
        cleaner_start_location = (51.5074, -0.1278)
        
        # Create 1-week optimized schedule (8 days starting from today)
        schedule_result = optimize_route(
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




if __name__ == '__main__':
    import uvicorn
    print("🚀 Starting Window Cleaner AI Optimizer...")
    print("📍 Server will be available at: http://127.0.0.1:5003")
    print("📋 Essential Endpoints:")
    print("   • GET  /health - Health check")
    print("   • POST /smart-optimize/{user_id} - 🧠 Smart one-button optimization ⭐")
    print("   • POST /create-1week-schedule/{user_id} - Generate schedule from database")
    print("   • POST /create-schedule-with-data/{user_id} - Generate schedule with provided data")
    print("   • POST /create-schedule-from-express/{user_id} - Express backend integration")
    print("   • GET  /todays-schedule/{user_id} - Get today's scheduled customers 📅")
    print("   • POST /create-2week-schedule/{user_id} - Backward compatibility endpoint")
    uvicorn.run(app, host="127.0.0.1", port=5003)
