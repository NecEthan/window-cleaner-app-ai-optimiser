"""
Database connection and operations for Window Cleaner AI Optimizer
"""
import os
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SupabaseClient:
    def __init__(self):
        """Initialize Supabase client"""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        
        self.client: Client = create_client(self.url, self.key)
    
    async def get_work_schedule(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get active work schedule for a user from the work_schedules table
        
        Args:
            user_id: The user's UUID
            
        Returns:
            Work schedule dictionary or None if not found
        """
        try:
            response = self.client.table("work_schedules").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]  # Return the first active schedule
            return None
            
        except Exception as e:
            print(f"Error fetching work schedule: {e}")
            return None
    
    async def get_customers(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all customers for a user, mapped to scheduler format
        
        Args:
            user_id: The user's UUID
            
        Returns:
            List of customer dictionaries formatted for the scheduler
        """
        try:
            response = self.client.table("customers").select("*").eq("user_id", user_id).execute()
            
            if not response.data:
                return []
            
            # Map your database schema to scheduler format
            customers = []
            for customer in response.data:
                customers.append({
                    "id": customer["id"],
                    "lat": float(customer["latitude"]) if customer["latitude"] else 0.0,
                    "lng": float(customer["longitude"]) if customer["longitude"] else 0.0,
                    "last_cleaned": customer["last_completed"] or "2025-01-01",  # Default if never cleaned
                    "frequency_days": self._parse_frequency(customer["frequency"]),
                    "name": customer["name"],
                    "address": customer["address"],
                    "price": float(customer["price"]),
                    "estimated_duration": customer["estimated_duration"] or 30  # Default 30 minutes
                })
            
            return customers
        except Exception as e:
            print(f"Error fetching customers: {e}")
            return []
    
    def _parse_frequency(self, frequency_str: str) -> int:
        """Parse frequency string to days"""
        if not frequency_str:
            return 14  # Default bi-weekly
        
        frequency_map = {
            "weekly": 7,
            "bi-weekly": 14, 
            "biweekly": 14,
            "monthly": 30,
            "fortnightly": 14
        }
        
        return frequency_map.get(frequency_str.lower(), 14)
    
    async def get_cleaner_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cleaner profile information - since you don't have this table yet,
        we'll create a default profile or you can add this table later
        
        Args:
            user_id: The user's UUID
            
        Returns:
            Cleaner profile dictionary with default values
        """
        try:
            # For now, return a default cleaner profile
            # You can add a cleaner_profiles table later if needed
            return {
                "id": 1,
                "work_hours": [9, 17],  # 9 AM to 5 PM
                "start_location": {
                    "lat": 51.5,  # Default London location - update with your actual location
                    "lng": -0.1
                }
            }
            
        except Exception as e:
            print(f"Error creating cleaner profile: {e}")
            return None
    
    async def save_optimized_schedule(self, user_id: str, work_schedule: Dict[str, Any], schedule_data: Dict[str, Any]) -> str:
        """
        Save optimized schedule to database
        
        Args:
            user_id: The user's UUID
            work_schedule: The work schedule used for optimization
            schedule_data: The generated schedule data with daily customer assignments
            
        Returns:
            Schedule ID if saved successfully, raises exception otherwise
        """
        try:
            from datetime import datetime
            
            # 1. Save/Update work schedule in work_schedules table
            work_schedule_data = {
                "user_id": user_id,
                "monday_hours": work_schedule.get("monday_hours"),
                "tuesday_hours": work_schedule.get("tuesday_hours"), 
                "wednesday_hours": work_schedule.get("wednesday_hours"),
                "thursday_hours": work_schedule.get("thursday_hours"),
                "friday_hours": work_schedule.get("friday_hours"),
                "saturday_hours": work_schedule.get("saturday_hours"),
                "sunday_hours": work_schedule.get("sunday_hours"),
                "is_active": True,
                "updated_at": datetime.now().isoformat()
            }
            
            # First, deactivate any existing active schedules
            self.client.table("work_schedules").update({"is_active": False}).eq("user_id", user_id).execute()
            
            # Insert new work schedule
            work_schedule_response = self.client.table("work_schedules").insert(work_schedule_data).execute()
            
            if not work_schedule_response.data:
                raise Exception("Failed to save work schedule")
                
            schedule_id = work_schedule_response.data[0]["id"]
            
            # 2. Save daily customer assignments
            await self._save_daily_assignments(user_id, schedule_data)
            
            print(f"✅ Optimized schedule saved with ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            print(f"❌ Error saving optimized schedule: {e}")
            raise Exception(f"Failed to save optimized schedule: {str(e)}")

    async def _save_daily_assignments(self, user_id: str, schedule_data: Dict[str, Any]):
        """
        Save daily customer assignments to routes and route_jobs tables
        
        Args:
            user_id: The user's UUID
            schedule_data: The schedule data containing daily assignments
        """
        try:
            from datetime import datetime
            
            # Clear existing future routes for this user to avoid duplicates
            today = datetime.now().date().isoformat()
            self.client.table("routes").delete().eq("user_id", user_id).gte("date", today).execute()
            
            for date_str, day_data in schedule_data.items():
                customers = day_data.get("customers", [])
                
                if not customers:
                    continue  # Skip days with no customers
                
                # Create route for this day
                route_data = {
                    "user_id": user_id,
                    "date": date_str,
                    "status": "scheduled",
                    "estimated_duration": day_data.get("total_duration_minutes", 0),
                    "estimated_revenue": day_data.get("total_revenue", 0),
                    "estimated_travel_time": day_data.get("estimated_travel_time", 0),
                    "max_work_hours": day_data.get("max_hours", 8),
                    "day_name": day_data.get("day", ""),
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                route_response = self.client.table("routes").insert(route_data).execute()
                
                if route_response.data:
                    route_id = route_response.data[0]["id"]
                    
                    # Add customer assignments for this route
                    route_jobs = []
                    for customer in customers:
                        job_data = {
                            "route_id": route_id,
                            "customer_id": customer["id"],
                            "visit_order": customer.get("route_order", 1),
                            "estimated_duration": customer.get("estimated_duration", 30),
                            "price": customer.get("price", 0),
                            "customer_name": customer.get("name", ""),
                            "customer_address": customer.get("address", ""),
                            "completed": False,
                            "status": "scheduled",
                            "created_at": datetime.now().isoformat()
                        }
                        route_jobs.append(job_data)
                    
                    if route_jobs:
                        self.client.table("route_jobs").insert(route_jobs).execute()
                        print(f"📅 Saved {len(route_jobs)} customer assignments for {date_str}")
            
        except Exception as e:
            print(f"❌ Error saving daily assignments: {e}")
            raise Exception(f"Failed to save daily assignments: {str(e)}")

    async def get_todays_schedule(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get today's scheduled customers for a user
        
        Args:
            user_id: The user's UUID
            
        Returns:
            Today's schedule with customers or None if no schedule
        """
        try:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            
            # Get today's route
            route_response = self.client.table("routes").select("*").eq("user_id", user_id).eq("date", today).execute()
            
            if not route_response.data:
                return None
                
            route = route_response.data[0]
            
            # Get customer assignments for today's route
            jobs_response = self.client.table("route_jobs").select("*").eq("route_id", route["id"]).order("visit_order").execute()
            
            return {
                "date": today,
                "route": route,
                "customers": jobs_response.data if jobs_response.data else []
            }
            
        except Exception as e:
            print(f"Error fetching today's schedule: {e}")
            return None

    async def save_schedule(self, user_id: str, schedule_data: Dict[str, Any]) -> bool:
        """
        Save generated schedule to database using your routes and route_jobs tables
        
        Args:
            user_id: The user's UUID
            schedule_data: The generated schedule data
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            from datetime import datetime, timedelta
            
            # Clear existing future routes for this user (optional)
            # self.client.table("routes").delete().eq("user_id", user_id).gte("date", datetime.now().date()).execute()
            
            for date_str, day_data in schedule_data.items():
                if not day_data.get("jobs"):
                    continue  # Skip days with no jobs
                
                # Create route for this day
                route_data = {
                    "user_id": user_id,
                    "date": date_str,
                    "status": "planned",
                    "estimated_duration": int(day_data.get("estimated_work_hours", 0) * 60),  # Convert to minutes
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                route_response = self.client.table("routes").insert(route_data).execute()
                
                if route_response.data:
                    route_id = route_response.data[0]["id"]
                    
                    # Add route jobs for this route
                    for idx, job in enumerate(day_data["jobs"]):
                        job_data = {
                            "route_id": route_id,
                            "customer_id": job["customer_id"],
                            "visit_order": idx + 1,
                            "completed": False,
                            "created_at": datetime.now().isoformat()
                        }
                        
                        self.client.table("route_jobs").insert(job_data).execute()
            
            return True
        except Exception as e:
            print(f"Error saving schedule: {e}")
            return False

# Global instance
db = SupabaseClient()