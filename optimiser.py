from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import os
import statistics

# Initialize Supabase connection for learning
try:
    from supabase import create_client
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
        LEARNING_ENABLED = True
        print("🧠 Learning system enabled - will use job history data")
    else:
        LEARNING_ENABLED = False
        print("⚠️ Learning disabled - missing Supabase credentials")
except ImportError:
    LEARNING_ENABLED = False
    print("⚠️ Learning disabled - supabase package not installed")
except Exception as e:
    LEARNING_ENABLED = False
    print(f"⚠️ Learning disabled - error: {e}")

def get_learned_duration(customer_id: str, fallback: int = 30) -> int:
    """Get learned average duration for a customer from job_times table"""
    if not LEARNING_ENABLED:
        return fallback
    
    try:
        # Get last 10 jobs for this customer
        result = supabase.table('job_times')\
            .select('actual_duration')\
            .eq('customer_id', str(customer_id))\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()
        
        if not result.data:
            return fallback
        
        durations = [row['actual_duration'] for row in result.data]
        
        # Fast learning algorithm
        if len(durations) == 1:
            return durations[0]  # Use first job immediately
        elif len(durations) == 2:
            return int(sum(durations) / 2)  # Average of 2 jobs
        else:
            return int(statistics.median(durations))  # Median for stability
            
    except Exception as e:
        print(f"❌ Error getting learned duration for customer {customer_id}: {e}")
        return fallback

def enhance_customers_with_learning(customers: List[Dict]) -> List[Dict]:
    """Replace estimated_duration with learned durations from job history"""
    if not LEARNING_ENABLED:
        return customers
    
    print("🧠 Enhancing customers with learned durations...")
    enhanced_customers = []
    learning_used_count = 0
    
    for customer in customers:
        customer_copy = customer.copy()
        customer_id = str(customer['id'])
        
        # Get original duration
        original_duration = customer.get('estimated_duration', 30)
        
        # Get learned duration from database
        learned_duration = get_learned_duration(customer_id, original_duration)
        
        if learned_duration != original_duration:
            improvement = abs(learned_duration - original_duration)
            print(f"📊 {customer.get('name', 'Unknown')}: {original_duration}min → {learned_duration}min (±{improvement}min learned)")
            customer_copy['estimated_duration'] = learned_duration
            customer_copy['duration_source'] = 'learned'
            learning_used_count += 1
        else:
            customer_copy['estimated_duration'] = original_duration
            customer_copy['duration_source'] = 'estimated'
            
        enhanced_customers.append(customer_copy)
    
    total_customers = len(customers)
    learning_percentage = (learning_used_count / total_customers) * 100 if total_customers > 0 else 0
    print(f"🎯 Using learned data for {learning_used_count}/{total_customers} customers ({learning_percentage:.1f}%)")
    
    return enhanced_customers

def get_learning_stats() -> Dict:
    """Get learning system statistics"""
    if not LEARNING_ENABLED:
        return {"learning_enabled": False}
    
    try:
        # Get total jobs recorded
        result = supabase.table('job_times')\
            .select('customer_id', count='exact')\
            .execute()
        
        total_jobs = result.count if result.count else 0
        
        # Get unique customers with data
        customers_result = supabase.table('job_times')\
            .select('customer_id')\
            .execute()
        
        unique_customers = len(set(row['customer_id'] for row in customers_result.data)) if customers_result.data else 0
        
        # Get recent accuracy (jobs with estimates)
        accuracy_result = supabase.table('job_times')\
            .select('estimated_duration, actual_duration')\
            .not_.is_('estimated_duration', 'null')\
            .order('created_at', desc=True)\
            .limit(50)\
            .execute()
        
        accuracy_stats = {}
        if accuracy_result.data:
            jobs = accuracy_result.data
            accurate_jobs = 0
            total_error = 0
            
            for job in jobs:
                estimated = job['estimated_duration']
                actual = job['actual_duration']
                error = abs(estimated - actual)
                total_error += error
                
                if error <= 5:  # Within ±5 minutes
                    accurate_jobs += 1
            
            accuracy_percent = (accurate_jobs / len(jobs)) * 100
            avg_error = total_error / len(jobs)
            
            accuracy_stats = {
                "accuracy_within_5min": f"{accuracy_percent:.1f}%",
                "average_error_minutes": round(avg_error, 1),
                "jobs_with_estimates": len(jobs)
            }
        
        return {
            "learning_enabled": True,
            "total_jobs_recorded": total_jobs,
            "unique_customers_with_data": unique_customers,
            "learning_status": "Excellent" if total_jobs > 100 else "Improving" if total_jobs > 20 else "Learning",
            **accuracy_stats
        }
        
    except Exception as e:
        return {"learning_enabled": True, "error": str(e)}

def optimize_route(locations):
    """Basic route optimization for a single day's customers"""
    # locations: list of (lat, lng)
    n = len(locations)
    if n <= 1:
        return list(range(n))
    
    # distance callback
    def distance_callback(i, j):
        if i == j:
            return 0
        from geopy.distance import geodesic
        # Return distance in meters, rounded to integer, capped at reasonable maximum
        dist = geodesic(locations[i], locations[j]).meters
        return min(int(round(dist)), 999999)  # Cap at ~1000km

    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    
    # Register the distance callback
    def distance_evaluator(from_index, to_index):
        try:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_callback(from_node, to_node)
        except Exception as e:
            print(f"Error in distance_evaluator: {e}, from_index={from_index}, to_index={to_index}")
            return 999999  # Return large distance on error
    
    transit_callback_index = routing.RegisterTransitCallback(distance_evaluator)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    solution = routing.SolveWithParameters(search_parameters)
    
    order = []
    if solution:
        index = routing.Start(0)
        while not routing.IsEnd(index):
            order.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
    return order


def create_2_week_schedule(customers: List[Dict], work_schedule: Dict, cleaner_start_location: Tuple[float, float], protect_near_dates: bool = False) -> Dict[str, Any]:
    """
    Create an optimized 1-week schedule for window cleaning (8 days starting from today)
    
    Args:
        customers: List of customer dicts with id, name, address, phone, lat, lng, frequency_days, 
                  last_cleaned, estimated_duration, price, payment_method (optional, defaults to 'card')
        work_schedule: Dict with day_hours like {'monday_hours': 8, 'tuesday_hours': 6, ...}
        cleaner_start_location: Tuple of (lat, lng) for cleaner's starting location
        protect_near_dates: If True, skip today and tomorrow (for returning users)
    
    Returns:
        Dict with schedule for next 8 days (1 week) including optimized routes with payment methods
    """
    
    # 🧠 STEP 1: Enhance customers with learned durations BEFORE optimization
    enhanced_customers = enhance_customers_with_learning(customers)
    
    # Get working days and hours
    working_days = _get_working_days(work_schedule)
    
    # Generate customers that need cleaning in next week (8 days)
    customers_needing_service = _filter_customers_by_urgency(enhanced_customers)
    
    # Create 1-week schedule (8 days starting from today)
    schedule = {}
    total_time_saved = 0
    total_fuel_saved = 0
    today = datetime.now().date()
    
    for i in range(8):  # Next 8 days (1 week starting from today)
        current_date = today + timedelta(days=i)
        day_name = current_date.strftime('%A').lower()
        
        # 🛡️ SMART DATE PROTECTION: Skip today/tomorrow if protect_near_dates is True
        if protect_near_dates and i < 2:  # Skip day 0 (today) and day 1 (tomorrow)
            schedule[current_date.strftime('%Y-%m-%d')] = {
                'date': current_date.strftime('%Y-%m-%d'),
                'day': current_date.strftime('%A'),
                'max_hours': 0,
                'customers': [],
                'route_order': [],
                'total_duration_minutes': 0,
                'total_revenue': 0,
                'estimated_travel_time': 0,
                'time_savings': {
                    'time_savings_minutes': 0,
                    'efficiency_improvement_percent': 0
                },
                'protected': True,
                'message': f'Protected - Cannot optimize {current_date.strftime("%A")} (too close to cleaner schedule)'
            }
            continue
        
        if f"{day_name}_hours" in working_days:
            max_hours = working_days[f"{day_name}_hours"]
            
            # Assign customers to this day
            daily_customers = _assign_customers_to_day(
                customers_needing_service, 
                current_date, 
                max_hours
            )
            
            if daily_customers:
                # Optimize route for this day
                optimized_route = _optimize_daily_route(
                    daily_customers, 
                    cleaner_start_location
                )
             
                
                schedule[current_date.strftime('%Y-%m-%d')] = {
                    'date': current_date.strftime('%Y-%m-%d'),
                    'day': current_date.strftime('%A'),
                    'max_hours': max_hours,
                    'customers': optimized_route['customers'],
                    'route_order': optimized_route['order'],
                    'total_duration_minutes': optimized_route['total_duration'],
                    'total_revenue': optimized_route['total_revenue'],
                    'estimated_travel_time': optimized_route['travel_time'],
                    'time_savings': optimized_route['time_savings']
                }
                
                # Accumulate savings
                total_time_saved += optimized_route['time_savings']['time_savings_minutes']
                total_fuel_saved += optimized_route['time_savings']['fuel_savings_estimate_gbp']
                
                # Remove assigned customers from pool
                assigned_ids = [c['id'] for c in daily_customers]
                customers_needing_service = [c for c in customers_needing_service if c['id'] not in assigned_ids]
    
    return {
        'schedule': schedule,
        'summary': _create_schedule_summary(schedule),
        'time_savings_summary': {
            'total_time_saved_minutes': round(total_time_saved, 1),
            'total_time_saved_hours': round(total_time_saved / 60, 2),
            'total_fuel_saved_gbp': round(total_fuel_saved, 2),
            'extra_customers_per_week': int(total_time_saved / 45) if total_time_saved > 0 else 0,
            'weekly_efficiency_gain': f"{round((total_time_saved / (sum([len(day['customers']) for day in schedule.values()]) * 45)) * 100, 1)}%" if schedule else "0%"
        },
        'unscheduled_customers': customers_needing_service,
        'machine_learning': {
            'learning_enabled': LEARNING_ENABLED,
            'customers_with_learned_data': len([c for c in enhanced_customers if c.get('duration_source') == 'learned']),
            'total_customers': len(customers),
            'learning_coverage_percent': round((len([c for c in enhanced_customers if c.get('duration_source') == 'learned']) / len(customers)) * 100, 1) if customers else 0,
            'accuracy_stats': get_learning_stats()
        }
    }


def _get_working_days(work_schedule: Dict) -> Dict[str, float]:
    """Extract working days and hours from work schedule"""
    working_days = {}
    day_keys = ['monday_hours', 'tuesday_hours', 'wednesday_hours', 
                'thursday_hours', 'friday_hours', 'saturday_hours', 'sunday_hours']
    
    for day_key in day_keys:
        hours = work_schedule.get(day_key)
        if hours is not None:
            # Convert to float and check if > 0
            hours_float = float(hours)
            if hours_float > 0:
                working_days[day_key] = hours_float
    return working_days


def _filter_customers_by_urgency(customers: List[Dict]) -> List[Dict]:
    """Filter and sort customers by cleaning urgency (overdue first)"""
    today = datetime.now().date()
    customers_with_urgency = []
    
    for customer in customers:
        try:
            last_cleaned = datetime.strptime(customer['last_cleaned'], '%Y-%m-%d').date()
            days_since_cleaned = (today - last_cleaned).days
            frequency_days = int(customer['frequency_days'])  # Ensure it's an integer
            
            # Calculate urgency score (higher = more urgent)
            days_overdue = days_since_cleaned - frequency_days
            urgency_score = max(0, days_overdue)  # 0 if not due yet, positive if overdue
            
            customer_copy = customer.copy()
            customer_copy['days_since_cleaned'] = days_since_cleaned
            customer_copy['days_overdue'] = days_overdue
            customer_copy['urgency_score'] = urgency_score
            customer_copy['next_due_date'] = last_cleaned + timedelta(days=frequency_days)
            
            customers_with_urgency.append(customer_copy)
        except (ValueError, KeyError) as e:
            print(f"Error processing customer {customer.get('name', 'Unknown')}: {e}")
            continue
    
    # Sort by urgency (most urgent first), then by next due date
    try:
        return sorted(customers_with_urgency, key=lambda x: (-x['urgency_score'], x['next_due_date']))
    except Exception as e:
        print(f"Error sorting customers: {e}")
        # Fallback to simple sorting by urgency score only
        return sorted(customers_with_urgency, key=lambda x: -x['urgency_score'])


def _assign_customers_to_day(customers: List[Dict], date: datetime.date, max_hours: float) -> List[Dict]:
    """Assign customers to a specific day based on available hours"""
    max_minutes = max_hours * 60
    assigned_customers = []
    total_minutes = 0
    
    for customer in customers:
        try:
            duration = int(customer['estimated_duration'])  # Ensure it's an integer
            
            # Check if customer fits in remaining time
            if total_minutes + duration <= max_minutes:
                assigned_customers.append(customer)
                total_minutes += duration
                
                # Leave some buffer time (don't pack too tightly)
                if total_minutes >= max_minutes * 0.9:  # Stop at 90% capacity
                    break
        except (ValueError, KeyError) as e:
            print(f"Error processing customer duration for {customer.get('name', 'Unknown')}: {e}")
            continue
    
    return assigned_customers


def _optimize_daily_route(customers: List[Dict], cleaner_start_location: Tuple[float, float]) -> Dict:
    """Optimize route for a single day's customers with time savings analysis"""
    

    
    if not customers:
        return {
            'customers': [],
            'order': [],
            'total_duration': 0,
            'total_revenue': 0,
            'travel_time': 0,
            'time_savings': {
                'time_savings_minutes': 0,
                'efficiency_improvement_percent': 0
            }
        }
        
    # Prepare locations (cleaner start + customer locations)
    locations = [cleaner_start_location]
    for customer in customers:
        locations.append((customer['lat'], customer['lng']))
    
    # Get optimal route order
    route_order = optimize_route(locations)
    
    # Build optimized customer list (excluding cleaner start location)
    optimized_customers = []
    total_duration = 0
    total_revenue = 0
    
    for i in route_order[1:]:  # Skip index 0 (cleaner start)
        customer_idx = i - 1  # Adjust for cleaner start location
        if 0 <= customer_idx < len(customers):
            customer = customers[customer_idx]
            
            # Build optimized customer with all data preserved
            optimized_customer = {
                **customer,  # This spreads ALL customer data including phone
                'route_order': len(optimized_customers) + 1,
                'payment_method': customer.get('payment_method', 'card')
            }
            
            optimized_customers.append(optimized_customer)
            total_duration += customer['estimated_duration']
            total_revenue += customer['price']
    
    # Calculate time savings
    time_savings = calculate_time_savings(customers, cleaner_start_location)
    
    # Calculate actual travel time
    actual_travel_time = _calculate_actual_travel_time(customers, cleaner_start_location, optimized=True)
    
    return {
        'customers': optimized_customers,
        'order': route_order,
        'total_duration': total_duration,
        'total_revenue': total_revenue,
        'travel_time': round(actual_travel_time, 1),
        'time_savings': time_savings
    }


def _create_schedule_summary(schedule: Dict) -> Dict:
    """Create summary statistics for the 2-week schedule"""
    total_customers = 0
    total_revenue = 0
    total_work_hours = 0
    working_days = 0
    
    for day_data in schedule.values():
        total_customers += len(day_data['customers'])
        total_revenue += day_data['total_revenue']
        total_work_hours += day_data['total_duration_minutes'] / 60
        working_days += 1
    
    return {
        'total_customers_scheduled': total_customers,
        'total_revenue': total_revenue,
        'total_work_hours': round(total_work_hours, 1),
        'working_days': working_days,
        'average_customers_per_day': round(total_customers / max(working_days, 1), 1),
        'average_revenue_per_day': round(total_revenue / max(working_days, 1), 2)
    }


def calculate_time_savings(customers: List[Dict], cleaner_start_location: Tuple[float, float]) -> Dict[str, Any]:
    """
    Calculate time savings between optimized vs non-optimized routes
    
    Returns:
        Dict with time savings analysis including travel time comparison
    """
    if not customers or len(customers) < 2:
        return {
            'time_savings_minutes': 0,
            'time_savings_hours': 0,
            'fuel_savings_estimate_gbp': 0,
            'efficiency_improvement_percent': 0
        }
    
    # Calculate optimized route travel time
    optimized_travel_time = _calculate_actual_travel_time(customers, cleaner_start_location, optimized=True)
    
    # Calculate non-optimized route travel time (customers in original order)
    unoptimized_travel_time = _calculate_actual_travel_time(customers, cleaner_start_location, optimized=False)
    
    # Calculate savings
    time_saved_minutes = unoptimized_travel_time - optimized_travel_time
    time_saved_hours = time_saved_minutes / 60
    
    # Estimate fuel savings (rough estimate: 1 minute driving = £0.50 fuel cost)
    fuel_savings = time_saved_minutes * 0.50
    
    # Calculate efficiency improvement percentage
    efficiency_improvement = (time_saved_minutes / max(unoptimized_travel_time, 1)) * 100
    
    return {
        'optimized_travel_time_minutes': round(optimized_travel_time, 1),
        'unoptimized_travel_time_minutes': round(unoptimized_travel_time, 1),
        'time_savings_minutes': round(time_saved_minutes, 1),
        'time_savings_hours': round(time_saved_hours, 2),
        'fuel_savings_estimate_gbp': round(fuel_savings, 2),
        'efficiency_improvement_percent': round(efficiency_improvement, 1),
        'extra_customers_possible': int(time_saved_minutes / 45) if time_saved_minutes > 0 else 0  # Assuming 45min per customer average
    }


def _calculate_actual_travel_time(customers: List[Dict], cleaner_start_location: Tuple[float, float], optimized: bool = True) -> float:
    """
    Calculate actual travel time for a route
    
    Args:
        customers: List of customer locations
        cleaner_start_location: Starting point
        optimized: If True, use optimized route order. If False, use original order
    
    Returns:
        Total travel time in minutes
    """
    if not customers:
        return 0
    
    # Import geopy here to avoid circular imports
    from geopy.distance import geodesic
    
    # Prepare locations
    locations = [cleaner_start_location]
    for customer in customers:
        locations.append((customer['lat'], customer['lng']))
    
    if optimized:
        # Get optimal route order
        route_order = optimize_route(locations)
    else:
        # Use original order (non-optimized)
        route_order = list(range(len(locations)))
    
    # Calculate total travel distance
    total_distance_meters = 0
    
    for i in range(len(route_order) - 1):
        from_idx = route_order[i]
        to_idx = route_order[i + 1]
        
        if 0 <= from_idx < len(locations) and 0 <= to_idx < len(locations):
            distance = geodesic(locations[from_idx], locations[to_idx]).meters
            total_distance_meters += distance
    
    # Add return trip home from last job
    if len(route_order) > 1:
        last_job_idx = route_order[-1]
        if 0 <= last_job_idx < len(locations):
            return_distance = geodesic(locations[last_job_idx], cleaner_start_location).meters
            total_distance_meters += return_distance
    
    # Convert distance to travel time
    # Assuming average speed of 25 km/h in urban areas (accounting for traffic, stops, parking)
    avg_speed_kmh = 25
    avg_speed_mps = (avg_speed_kmh * 1000) / 60  # meters per minute
    
    total_travel_time_minutes = total_distance_meters / avg_speed_mps
    
    # Add buffer time for parking, walking to door, etc. (2 minutes per stop)
    buffer_time = len(customers) * 2
    
    return total_travel_time_minutes + buffer_time
