from datetime import datetime, timedelta
from optimiser import optimize_route
import json

class WindowCleanerScheduler:
    def __init__(self):
        self.JOB_TIME_MINUTES = 30  # 30 minutes per job
        self.TRAVEL_TIME_MINUTES = 7  # 7 minutes average travel between jobs
    
    def calculate_max_jobs_for_hours(self, work_hours):
        """Calculate maximum jobs that can fit in the given work hours"""
        if work_hours <= 0:
            return 0
        
        # Total available minutes
        total_minutes = work_hours * 60
        
        # Time per job (including travel between jobs)
        minutes_per_job = self.JOB_TIME_MINUTES + self.TRAVEL_TIME_MINUTES
        
        # Maximum jobs that can fit
        max_jobs = int(total_minutes / minutes_per_job)
        
        # Enforce hard limits: minimum 15, maximum 23
        return min(23, max(0, max_jobs))
    
    def get_daily_work_hours(self, work_schedule, day_name):
        """Get work hours for a specific day from the work schedule"""
        day_mapping = {
            'Monday': 'monday_hours',
            'Tuesday': 'tuesday_hours', 
            'Wednesday': 'wednesday_hours',
            'Thursday': 'thursday_hours',
            'Friday': 'friday_hours',
            'Saturday': 'saturday_hours',
            'Sunday': 'sunday_hours'
        }
        
        hours_key = day_mapping.get(day_name)
        if hours_key and work_schedule.get(hours_key) is not None:
            return float(work_schedule[hours_key])
        return 0.0
    
    def can_optimize_date(self, target_date):
        """Check if we can optimize for this date (not today or tomorrow)"""
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        elif isinstance(target_date, datetime):
            target_date = target_date.date()
        
        return target_date not in [today, tomorrow]
    
    def calculate_cleaning_window(self, last_cleaned, frequency_days, buffer_days=14):
        """Calculate the cleaning window for a customer"""
        last_cleaned_date = datetime.strptime(last_cleaned, "%Y-%m-%d")
        next_clean_date = last_cleaned_date + timedelta(days=frequency_days)
        window_start = next_clean_date - timedelta(days=buffer_days)
        window_end = next_clean_date + timedelta(days=buffer_days)
        
        return {
            'next_clean_date': next_clean_date,
            'window_start': window_start,
            'window_end': window_end
        }
    
    def is_within_work_hours(self, work_hours):
        """Check if current time allows for work (simplified - in real app would consider time estimates)"""
        # For now, just return True - in real implementation would calculate job duration
        # and check if it fits within work_hours[0] to work_hours[1]
        return True
    
    def generate_date_range(self, start_date, end_date):
        """Generate all dates between start and end"""
        current = start_date
        dates = []
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)
        return dates
    
    def group_jobs_by_feasible_days(self, customers, constraints):
        """Group jobs by days they can be scheduled"""
        jobs_by_day = {}
        
        # Calculate 7-day window (today + 6 days ahead)
        today = datetime.now().date()
        
        for customer in customers:
            window = self.calculate_cleaning_window(
                customer['last_cleaned'], 
                customer['frequency_days']
            )
            
            # Find overlap between customer window and 7-day schedule window
            for days_ahead in range(7):  # Today + 6 days ahead = 7 days total
                schedule_date = today + timedelta(days=days_ahead)
                
                # Check if customer can be scheduled on this date (within their cleaning window)
                if window['window_start'].date() <= schedule_date <= window['window_end'].date():
                    date_str = schedule_date.strftime("%Y-%m-%d")
                    if date_str not in jobs_by_day:
                        jobs_by_day[date_str] = []
                    
                    jobs_by_day[date_str].append({
                        'customer_id': customer['id'],
                        'lat': customer['lat'],
                        'lng': customer['lng'],
                        'priority': self.calculate_priority(customer, window['next_clean_date']),
                        'next_due': window['next_clean_date'].date(),
                        'days_until_due': (window['next_clean_date'].date() - today).days
                    })
        
        return jobs_by_day
    
    def calculate_priority(self, customer, next_clean_date):
        """Calculate priority score for scheduling (higher = more urgent)"""
        today = datetime.now().date()
        days_until_due = (next_clean_date.date() - today).days
        
        # Higher priority for jobs that are due sooner
        # Also consider frequency (more frequent = higher priority when due)
        base_priority = max(1, 30 - days_until_due)  # More urgent as due date approaches
        frequency_factor = max(1, 30 / customer['frequency_days'])  # More frequent = higher priority
        
        return base_priority * frequency_factor
    
    def select_jobs_for_day(self, day_jobs, cleaner, min_jobs_per_day=15, max_jobs_per_day=23):
        """Select optimal jobs for a specific day (STRICT 15-23 jobs maximum)"""
        if not day_jobs:
            return []
        
        # Sort by priority (descending) - most urgent customers first
        sorted_jobs = sorted(day_jobs, key=lambda x: x['priority'], reverse=True)
        
        # STRICT enforcement: cannot exceed 23 customers per day
        available_jobs = len(sorted_jobs)
        
        if available_jobs >= min_jobs_per_day:
            # Take between 15-23 jobs (never more than 23)
            target_jobs = min(max_jobs_per_day, available_jobs)
            selected_jobs = sorted_jobs[:target_jobs]
        else:
            # Take all available jobs (even if less than 15)
            selected_jobs = sorted_jobs
        
        return selected_jobs
    
    def optimize_daily_route(self, jobs, cleaner):
        """Optimize route for jobs on a specific day"""
        if not jobs:
            return []
        
        if len(jobs) == 1:
            return [{
                'customer_id': jobs[0]['customer_id'], 
                'order': 1,
                'estimated_duration_minutes': 30  # Default 30 min per job
            }]
        
        # Extract locations for route optimization
        locations = [(job['lat'], job['lng']) for job in jobs]
        
        # Add cleaner's start location as the first point
        if 'start_location' in cleaner:
            start_loc = (cleaner['start_location']['lat'], cleaner['start_location']['lng'])
            locations.insert(0, start_loc)
            
            # Optimize route starting from cleaner's location
            route_indices = optimize_route(locations)
            
            # Remove the start location from results and adjust indices
            optimized_jobs = []
            for idx, route_idx in enumerate(route_indices):
                if route_idx > 0:  # Skip the start location
                    job_idx = route_idx - 1
                    optimized_jobs.append({
                        'customer_id': jobs[job_idx]['customer_id'],
                        'order': len(optimized_jobs) + 1,
                        'estimated_duration_minutes': 30  # 30 min per job
                    })
        else:
            # No start location specified, optimize jobs only
            route_indices = optimize_route(locations)
            optimized_jobs = []
            for idx, route_idx in enumerate(route_indices):
                optimized_jobs.append({
                    'customer_id': jobs[route_idx]['customer_id'],
                    'order': idx + 1,
                    'estimated_duration_minutes': 30  # 30 min per job
                })
        
        return optimized_jobs
    
    def calculate_daily_work_hours(self, jobs):
        """Calculate total work hours for a day"""
        if not jobs:
            return 0.0
        
        # Each job takes ~30 minutes on average
        # Add travel time estimate (5-10 min between jobs)
        job_time_minutes = len(jobs) * 30  # 30 min per job
        travel_time_minutes = max(0, len(jobs) - 1) * 7  # 7 min average travel between jobs
        
        total_minutes = job_time_minutes + travel_time_minutes
        total_hours = round(total_minutes / 60.0, 1)
        
        return total_hours
    
    def generate_full_schedule(self, customers, cleaner, work_schedule=None, constraints=None):
        """Generate complete 7-day schedule based on database work hours (today + 6 days ahead)"""
        # Group jobs by feasible days (7-day window) 
        jobs_by_day = self.group_jobs_by_feasible_days(customers, constraints)
        
        full_schedule = {}
        assigned_customers = set()
        
        # Generate exactly 7 days starting from today
        today = datetime.now().date()
        
        for days_ahead in range(7):  # 0 to 6 (today + 6 days ahead)
            current_date = today + timedelta(days=days_ahead)
            date_str = current_date.strftime("%Y-%m-%d")
            day_name = current_date.strftime("%A")
            
            # Check if we can optimize this date (not today or tomorrow)
            can_optimize = self.can_optimize_date(current_date)
            
            if not can_optimize:
                # Skip optimization for today and tomorrow
                full_schedule[date_str] = {
                    'date': date_str,
                    'day': day_name,
                    'jobs': [],
                    'estimated_work_hours': 0.0,
                    'work_time_breakdown': {'job_time_hours': 0.0, 'travel_time_hours': 0.0},
                    'message': f'Skipped - Cannot optimize {day_name} (today/tomorrow restriction)'
                }
                continue
            
            # Get work hours for this day from database schedule
            daily_work_hours = 0.0
            if work_schedule:
                daily_work_hours = self.get_daily_work_hours(work_schedule, day_name)
            
            if daily_work_hours <= 0:
                # No work scheduled for this day
                full_schedule[date_str] = {
                    'date': date_str,
                    'day': day_name,
                    'jobs': [],
                    'estimated_work_hours': 0.0,
                    'work_time_breakdown': {'job_time_hours': 0.0, 'travel_time_hours': 0.0},
                    'message': f'No work hours scheduled for {day_name}'
                }
                continue
            
            # Calculate maximum jobs based on available work hours
            max_jobs_for_day = self.calculate_max_jobs_for_hours(daily_work_hours)
            # Get available jobs for this day  
            day_jobs = jobs_by_day.get(date_str, [])
            
            # Filter out already assigned customers
            available_jobs = [job for job in day_jobs if job['customer_id'] not in assigned_customers]
            
            # Use work hours to determine max jobs (respecting 15-23 limits)
            min_jobs = 15 if max_jobs_for_day >= 15 else max_jobs_for_day
            max_jobs = min(23, max_jobs_for_day)
            
            # Select jobs based on available work hours
            selected_jobs = self.select_jobs_for_day(available_jobs, cleaner, min_jobs_per_day=min_jobs, max_jobs_per_day=max_jobs)
            
            if selected_jobs:
                # Optimize route for selected jobs
                optimized_schedule = self.optimize_daily_route(selected_jobs, cleaner)
                
                if optimized_schedule:
                    # Calculate work hours for this day
                    work_hours = self.calculate_daily_work_hours(optimized_schedule)
                    
                    full_schedule[date_str] = {
                        "jobs": optimized_schedule,
                        "total_jobs": len(optimized_schedule),
                        "estimated_work_hours": work_hours,
                        "work_time_breakdown": {
                            "job_time_hours": round(len(optimized_schedule) * 0.5, 1),  # 30 min per job
                            "travel_time_hours": round(max(0, len(optimized_schedule) - 1) * 0.12, 1)  # 7 min between jobs
                        }
                    }
                    
                    # Mark customers as assigned
                    for job in optimized_schedule:
                        assigned_customers.add(job['customer_id'])
            else:
                # Even if no jobs, include the date with empty schedule
                full_schedule[date_str] = {
                    "jobs": [],
                    "total_jobs": 0,
                    "estimated_work_hours": 0.0,
                    "work_time_breakdown": {
                        "job_time_hours": 0.0,
                        "travel_time_hours": 0.0
                    }
                }
        
        return full_schedule
