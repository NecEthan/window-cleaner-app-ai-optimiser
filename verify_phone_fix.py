#!/usr/bin/env python3

import asyncio
import sys
import os

# Add current directory to path
sys.path.append('/Users/ethanwicks/Documents/window-cleaner-ai-optimiser')

from database import SupabaseClient
from optimiser import create_2_week_schedule

async def test_phone_preservation():
    print("🧪 Testing ACTUAL phone number preservation with real database...")
    
    try:
        # Get real customers from database
        db = SupabaseClient()
        customers = await db.get_customers('21f233f7-a527-4ece-be9f-77572faf1187')
        
        print(f"📞 Found {len(customers)} customers from database")
        
        # Show first few customers and their phone numbers
        print("🔍 Sample customers from database:")
        for i, customer in enumerate(customers[:3]):
            phone = customer.get('phone', 'MISSING')
            print(f"   {i+1}. {customer.get('name', 'Unknown')}: phone = '{phone}'")
        print('================')
        
        # Test work schedule
        work_schedule = {
            "monday_hours": 8,
            "tuesday_hours": 8,
            "wednesday_hours": 8,
            "thursday_hours": 8,
            "friday_hours": 8,
            "saturday_hours": 0,
            "sunday_hours": 0
        }
        
        # Test cleaner location
        cleaner_location = (51.5074, -0.1278)
        
        # Call the scheduler function with real data
        result = create_2_week_schedule(
            customers=customers,
            work_schedule=work_schedule,
            cleaner_start_location=cleaner_location
        )
        
        print("\n🎯 FINAL SCHEDULE CHECK:")
        phone_count = 0
        total_customers = 0
        
        for date, day_data in result['schedule'].items():
            if day_data['customers']:
                print(f"📅 {date} ({day_data['day']}):")
                for customer in day_data['customers']:
                    total_customers += 1
                    phone = customer.get('phone', 'MISSING')
                    if phone and phone != 'MISSING' and phone != '':
                        phone_count += 1
                    print(f"   📞 {customer.get('name', 'Unknown')}: phone = '{phone}'")
                print('----')
                
        print(f"\n📊 SUMMARY:")
        print(f"   Total customers in schedule: {total_customers}")
        print(f"   Customers with phone numbers: {phone_count}")
        print(f"   Phone preservation rate: {phone_count/total_customers*100:.1f}%" if total_customers > 0 else "   No customers scheduled")
        
        if phone_count == total_customers and total_customers > 0:
            print("✅ SUCCESS: All phone numbers preserved!")
        elif phone_count > 0:
            print("⚠️ PARTIAL: Some phone numbers missing")
        else:
            print("❌ FAILURE: No phone numbers in final schedule")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_phone_preservation())