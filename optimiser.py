from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

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


def create_2_week_schedule(customers: List[Dict], work_schedule: Dict, cleaner_start_location: Tuple[float, float]) -> Dict[str, Any]:
    """
    Create an optimized 2-week schedule for window cleaning
    
    Args:
        customers: List of customer dicts with id, name, address, lat, lng, frequency_days, 
                  last_cleaned, estimated_duration, price
        work_schedule: Dict with day_hours like {'monday_hours': 8, 'tuesday_hours': 6, ...}
        cleaner_start_location: Tuple of (lat, lng) for cleaner's starting location
    
    Returns:
        Dict with schedule for next 2 weeks including optimized routes
    """
    
    # Get working days and hours
    working_days = _get_working_days(work_schedule)
    
    # Generate customers that need cleaning in next 2 weeks
    customers_needing_service = _filter_customers_by_urgency(customers)
    
    # Create 2-week schedule
    schedule = {}
    today = datetime.now().date()
    
    for i in range(14):  # Next 2 weeks
        current_date = today + timedelta(days=i)
        day_name = current_date.strftime('%A').lower()
        
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
                    'estimated_travel_time': optimized_route['travel_time']
                }
                
                # Remove assigned customers from pool
                assigned_ids = [c['id'] for c in daily_customers]
                customers_needing_service = [c for c in customers_needing_service if c['id'] not in assigned_ids]
    
    return {
        'schedule': schedule,
        'summary': _create_schedule_summary(schedule),
        'unscheduled_customers': customers_needing_service
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
    """Optimize route for a single day's customers"""
    if not customers:
        return {
            'customers': [],
            'order': [],
            'total_duration': 0,
            'total_revenue': 0,
            'travel_time': 0
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
            optimized_customers.append(customer)
            total_duration += customer['estimated_duration']
            total_revenue += customer['price']
    
    # Estimate travel time (rough calculation)
    estimated_travel_time = len(customers) * 10  # 10 min average between customers
    
    return {
        'customers': optimized_customers,
        'order': route_order,
        'total_duration': total_duration,
        'total_revenue': total_revenue,
        'travel_time': estimated_travel_time
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
