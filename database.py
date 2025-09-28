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
            response = self.client.table("work_schedules").select("*").eq("user_id", user_id).execute()
            
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
        Save or update optimized schedule for user as a single JSON object in user_assignments
        """
        try:
            from datetime import datetime, date
            import json
            # Helper to recursively convert date objects to strings
            def serialize_dates(obj):
                if isinstance(obj, dict):
                    return {k: serialize_dates(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [serialize_dates(v) for v in obj]
                elif isinstance(obj, date):
                    return obj.isoformat()
                else:
                    return obj
            safe_schedule_data = serialize_dates(schedule_data)
            response = self.client.table("user_assignments").select("id").eq("user_id", user_id).execute()
            schedule_row = {
                "user_id": user_id,
                "schedule_data": safe_schedule_data,
                "updated_at": datetime.now().isoformat()
            }
            if not response.data:
                # Insert new row
                insert_response = self.client.table("user_assignments").insert(schedule_row).execute()
                print(f"✅ Inserted new schedule for user {user_id}")
                return insert_response.data[0]["id"] if insert_response.data else ""
            else:
                # Update existing row
                update_response = self.client.table("user_assignments").update({"schedule_data": safe_schedule_data, "updated_at": datetime.now().isoformat()}).eq("user_id", user_id).execute()
                print(f"✅ Updated schedule for user {user_id}")
                return response.data[0]["id"]
        except Exception as e:
            print(f"❌ Error saving optimized schedule: {e}")
            raise Exception(f"Failed to save optimized schedule: {str(e)}")

    async def is_first_time_user(self, user_id: str) -> bool:
        """
        Check if this is the first time user is optimizing (no existing user_assignments)
        
        Args:
            user_id: The user's UUID
            
        Returns:
            True if this is first-time user, False if they have existing schedules
        """
        try:
            response = self.client.table("user_assignments").select("id").eq("user_id", user_id).limit(1).execute()
            
            print(f"🔍 First-time check for user {user_id}: Found {len(response.data)} existing assignments")
            
            # If no existing assignments, this is a first-time user
            return len(response.data) == 0
            
        except Exception as e:
            print(f"Error checking first-time user status: {e}")
            return True  # Default to first-time if we can't determine


    async def get_todays_schedule(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get today's scheduled customers from user_assignments table
        
        Args:
            user_id: The user's UUID
            
        Returns:
            Today's schedule with customers or None if no schedule
        """
        try:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            # Get today's assignments from user_assignments table
            assignments_response = self.client.table("user_assignments").select("*").eq("user_id", user_id).eq("scheduled_date", today).order("route_order").execute()
            if assignments_response.data:
                return assignments_response.data
            else:
                return None
        except Exception as e:
            print(f"❌ Error fetching today's schedule: {e}")
            return None

# Global instance
db = SupabaseClient()