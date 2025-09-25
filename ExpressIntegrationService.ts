/**
 * Express Backend Integration Service for Window Cleaner AI Optimizer
 * 
 * This service handles communication between your Express backend and the 
 * FastAPI optimization engine. It sends work schedules to FastAPI, which
 * fetches customers from the database and returns optimized schedules.
 */

import axios, { AxiosResponse } from 'axios';

// TypeScript interfaces for type safety
interface WorkSchedule {
  monday_hours?: number | null;
  tuesday_hours?: number | null;
  wednesday_hours?: number | null;
  thursday_hours?: number | null;
  friday_hours?: number | null;
  saturday_hours?: number | null;
  sunday_hours?: number | null;
}

interface CleanerLocation {
  lat: number;
  lng: number;
}

interface Customer {
  id: string;
  name: string;
  address: string;
  lat: number;
  lng: number;
  price: number;
  estimated_duration: number;
  days_since_cleaned: number;
  days_overdue: number;
  urgency_score: number;
  next_due_date: string;
  route_order: number;
}

interface DaySchedule {
  date: string;
  day: string;
  max_hours: number;
  customers: Customer[];
  total_duration_minutes: number;
  total_revenue: number;
  estimated_travel_time: number;
  time_savings: {
    optimized_travel_time_minutes: number;
    unoptimized_travel_time_minutes: number;
    time_savings_minutes: number;
    time_savings_hours: number;
    fuel_savings_estimate_gbp: number;
    efficiency_improvement_percent: number;
    extra_customers_possible: number;
  };
}

interface ScheduleSummary {
  total_customers_scheduled: number;
  total_revenue: number;
  total_work_hours: number;
  working_days: number;
  average_customers_per_day: number;
  average_revenue_per_day: number;
}

interface TimeSavingsSummary {
  total_time_saved_minutes: number;
  total_time_saved_hours: number;
  total_fuel_saved_gbp: number;
  extra_customers_per_week: number;
  weekly_efficiency_gain: string;
}

interface OptimizedScheduleResponse {
  user_id: string;
  express_integration: boolean;
  work_schedule_received: WorkSchedule;
  customers_from_database: number;
  schedule: { [date: string]: DaySchedule };
  summary: ScheduleSummary;
  time_savings_summary: TimeSavingsSummary;
  unscheduled_customers: number;
  message: string;
}

interface ExpressScheduleRequest {
  work_schedule: WorkSchedule;
  cleaner_start_location?: CleanerLocation;
}

export class WindowCleanerOptimizationService {
  private readonly baseUrl: string;
  private readonly timeout: number;

  constructor(
    baseUrl: string = 'http://127.0.0.1:5003',
    timeout: number = 30000
  ) {
    this.baseUrl = baseUrl;
    this.timeout = timeout;
  }

  /**
   * 🎯 MAIN EXPRESS INTEGRATION METHOD
   * 
   * Send work schedule from Express → FastAPI fetches customers from DB → 
   * Returns optimized 1-week schedule back to Express
   * 
   * Perfect for: Express backend → FastAPI → Express workflow
   */
  async generateOptimizedScheduleFromDatabase(
    userId: string,
    workSchedule: WorkSchedule,
    cleanerLocation?: CleanerLocation
  ): Promise<OptimizedScheduleResponse> {
    try {
      const requestData: ExpressScheduleRequest = {
        work_schedule: workSchedule,
        cleaner_start_location: cleanerLocation || { lat: 51.5074, lng: -0.1278 } // Default London
      };

      console.log(`🚀 Sending work schedule to FastAPI for user: ${userId}`);
      console.log(`📊 Work Schedule:`, workSchedule);
      
      const response: AxiosResponse<OptimizedScheduleResponse> = await axios.post(
        `${this.baseUrl}/create-schedule-from-express/${userId}`,
        requestData,
        {
          headers: {
            'Content-Type': 'application/json',
          },
          timeout: this.timeout,
        }
      );

      console.log(`✅ Successfully optimized schedule for ${response.data.customers_from_database} customers`);
      console.log(`💰 Total revenue: £${response.data.summary.total_revenue}`);
      console.log(`📅 Working days: ${response.data.summary.working_days}`);
      
      return response.data;

    } catch (error) {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message = error.response?.data?.detail || error.message;
        
        console.error(`❌ FastAPI Error (${status}):`, message);
        
        // Handle specific error cases
        if (status === 404) {
          throw new Error(`No customers found for user ${userId}. Please ensure the user has customers in the database.`);
        } else if (status === 500) {
          throw new Error(`Optimization engine error: ${message}`);
        } else {
          throw new Error(`FastAPI request failed: ${message}`);
        }
      } else {
        console.error('❌ Network Error:', error);
        throw new Error(`Network error: Unable to connect to optimization service at ${this.baseUrl}`);
      }
    }
  }

  /**
   * 🏥 Health Check
   * Verify that the FastAPI optimization service is running and database is connected
   */
  async healthCheck(): Promise<{ status: string; database: string; message: string }> {
    try {
      const response = await axios.get(`${this.baseUrl}/health`, {
        timeout: 5000,
      });
      
      console.log(`✅ FastAPI Service: ${response.data.status}`);
      console.log(`🗄️  Database: ${response.data.database}`);
      
      return response.data;
    } catch (error) {
      console.error('❌ Health Check Failed:', error);
      throw new Error('FastAPI optimization service is not available');
    }
  }

  /**
   * 📈 Extract Key Metrics
   * Helper method to extract important metrics for your Express API responses
   */
  extractKeyMetrics(scheduleResponse: OptimizedScheduleResponse) {
    return {
      // Business Metrics
      totalCustomers: scheduleResponse.summary.total_customers_scheduled,
      totalRevenue: scheduleResponse.summary.total_revenue,
      workingDays: scheduleResponse.summary.working_days,
      totalWorkHours: scheduleResponse.summary.total_work_hours,
      
      // Efficiency Metrics
      timeSavedHours: scheduleResponse.time_savings_summary.total_time_saved_hours,
      fuelSavedGBP: scheduleResponse.time_savings_summary.total_fuel_saved_gbp,
      efficiencyGain: scheduleResponse.time_savings_summary.weekly_efficiency_gain,
      extraCustomersPossible: scheduleResponse.time_savings_summary.extra_customers_per_week,
      
      // Unscheduled Info
      unscheduledCustomers: scheduleResponse.unscheduled_customers,
      customersFromDatabase: scheduleResponse.customers_from_database,
      
      // Schedule Data
      dailySchedules: Object.keys(scheduleResponse.schedule).length,
      scheduleData: scheduleResponse.schedule
    };
  }

  /**
   * 📅 Get Today's Schedule
   * Extract just today's customers and route from the optimized schedule
   */
  getTodaysSchedule(scheduleResponse: OptimizedScheduleResponse): DaySchedule | null {
    const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD format
    return scheduleResponse.schedule[today] || null;
  }

  /**
   * 🎯 Usage Example for Express Route Handler
   */
  static createExampleExpressRoute() {
    return 
    app.post('/api/optimize-schedule/:userId', async (req, res) => {
      try {
        const { userId } = req.params;
        const { workSchedule, cleanerLocation } = req.body;
        
        const optimizationService = new WindowCleanerOptimizationService();
        
        // Send work schedule to FastAPI, get optimized customer schedule back
        const optimizedSchedule = await optimizationService.generateOptimizedScheduleFromDatabase(
          userId,
          workSchedule,
          cleanerLocation
        );
        
        // Extract key metrics for your frontend
        const metrics = optimizationService.extractKeyMetrics(optimizedSchedule);
        
        // Get today's schedule specifically
        const todaysSchedule = optimizationService.getTodaysSchedule(optimizedSchedule);
        
        res.json({
          success: true,
          data: {
            fullSchedule: optimizedSchedule.schedule,
            todaysSchedule,
            metrics,
            message: 'Schedule optimized successfully'
          }
        });
        
      } catch (error) {
        console.error('Optimization failed:', error);
        res.status(500).json({
          success: false,
          error: error.message
        });
      }
    });
    ;
  }
}

export default WindowCleanerOptimizationService;