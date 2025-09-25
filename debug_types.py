#!/usr/bin/env python3
"""
Debug customer data types
"""
import asyncio
from database import SupabaseClient

async def debug_customer_data():
    """Debug the data types coming from database"""
    try:
        db = SupabaseClient()
        user_id = "947af734-4e40-44f7-8d8e-d0f304dee2dd"
        
        customers = await db.get_customers(user_id)
        
        print("=== Customer Data Types Debug ===")
        for customer in customers[:1]:  # Just check first customer
            print(f"Customer: {customer['name']}")
            for key, value in customer.items():
                print(f"  {key}: {value} (type: {type(value)})")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_customer_data())