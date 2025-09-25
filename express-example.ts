/**
 * 🚀 EXPRESS BACKEND USAGE EXAMPLE
 * 
 * This shows exactly how to integrate the Window Cleaner AI Optimizer
 * into your Express.js backend application.
 */

import express from 'express';
import { WindowCleanerOptimizationService } from './ExpressIntegrationService';

const app = express();
app.use(express.json());

// Initialize the optimization service
const optimizationService = new WindowCleanerOptimizationService('http://127.0.0.1:5003');

/**
 * 🎯 MAIN OPTIMIZATION ENDPOINT
 * 
 * Your frontend sends work schedule → Express processes → FastAPI optimizes → 
 * Express returns optimized customer schedule to frontend
 */
app.post('/api/optimize-schedule/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const { workSchedule, cleanerLocation } = req.body;

    console.log(`🔧 Optimizing schedule for user: ${userId}`);

    // Validate required data
    if (!workSchedule) {
      return res.status(400).json({
        success: false,
        error: 'Work schedule is required'
      });
    }

    // 🚀 Send work schedule to FastAPI → Fetch customers from DB → Get optimized schedule
    const optimizedSchedule = await optimizationService.generateOptimizedScheduleFromDatabase(
      userId,
      workSchedule,
      cleanerLocation
    );

    // Extract key metrics for easy frontend consumption
    const metrics = optimizationService.extractKeyMetrics(optimizedSchedule);
    
    // Get today's specific schedule
    const todaysSchedule = optimizationService.getTodaysSchedule(optimizedSchedule);

    // Return structured response to frontend
    res.json({
      success: true,
      message: 'Schedule optimized successfully',
      data: {
        // Full 8-day optimized schedule
        fullSchedule: optimizedSchedule.schedule,
        
        // Today's customers and route
        todaysSchedule,
        
        // Key business metrics
        metrics: {
          totalCustomers: metrics.totalCustomers,
          totalRevenue: metrics.totalRevenue,
          workingDays: metrics.workingDays,
          timeSavedHours: metrics.timeSavedHours,
          fuelSavedGBP: metrics.fuelSavedGBP,
          efficiencyGain: metrics.efficiencyGain,
          unscheduledCustomers: metrics.unscheduledCustomers
        },
        
        // Database info
        customersFromDatabase: optimizedSchedule.customers_from_database,
        workScheduleUsed: optimizedSchedule.work_schedule_received
      }
    });

  } catch (error) {
    console.error('❌ Optimization failed:', error);
    
    res.status(500).json({
      success: false,
      error: error.message || 'Failed to optimize schedule'
    });
  }
});

/**
 * 🏥 HEALTH CHECK ENDPOINT
 * Check if the FastAPI optimization service is running
 */
app.get('/api/optimizer/health', async (req, res) => {
  try {
    const health = await optimizationService.healthCheck();
    
    res.json({
      success: true,
      optimizer: health,
      message: 'Optimization service is healthy'
    });
    
  } catch (error) {
    res.status(503).json({
      success: false,
      error: 'Optimization service unavailable',
      details: error.message
    });
  }
});

/**
 * 📅 GET TODAY'S SCHEDULE ONLY
 * Quick endpoint to get just today's optimized schedule
 */
app.post('/api/todays-schedule/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const { workSchedule, cleanerLocation } = req.body;

    // Get full optimized schedule
    const optimizedSchedule = await optimizationService.generateOptimizedScheduleFromDatabase(
      userId,
      workSchedule,
      cleanerLocation
    );

    // Extract just today's schedule
    const todaysSchedule = optimizationService.getTodaysSchedule(optimizedSchedule);

    if (!todaysSchedule) {
      return res.json({
        success: true,
        message: 'No work scheduled for today',
        data: {
          todaysSchedule: null,
          totalCustomersInWeek: optimizedSchedule.summary.total_customers_scheduled
        }
      });
    }

    res.json({
      success: true,
      message: `Today's schedule: ${todaysSchedule.customers.length} customers`,
      data: {
        todaysSchedule,
        revenue: todaysSchedule.total_revenue,
        workHours: todaysSchedule.max_hours,
        travelTime: todaysSchedule.estimated_travel_time,
        timeSavings: todaysSchedule.time_savings
      }
    });

  } catch (error) {
    console.error('❌ Failed to get today\'s schedule:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 Express server running on port ${PORT}`);
  console.log(`📋 Available endpoints:`);
  console.log(`   • POST /api/optimize-schedule/:userId - Generate optimized 8-day schedule`);
  console.log(`   • POST /api/todays-schedule/:userId - Get today's schedule only`);
  console.log(`   • GET  /api/optimizer/health - Check FastAPI service health`);
});

/**
 * 📱 EXAMPLE FRONTEND REQUEST
 * 
 * Here's how your frontend would call the Express API:
 * 
 * ```javascript
 * const response = await fetch('/api/optimize-schedule/947af734-4e40-44f7-8d8e-d0f304dee2dd', {
 *   method: 'POST',
 *   headers: {
 *     'Content-Type': 'application/json'
 *   },
 *   body: JSON.stringify({
 *     workSchedule: {
 *       monday_hours: 8.0,
 *       tuesday_hours: 7.5,
 *       wednesday_hours: 6.0,
 *       thursday_hours: 8.0,
 *       friday_hours: 7.0,
 *       saturday_hours: null,
 *       sunday_hours: null
 *     },
 *     cleanerLocation: {
 *       lat: 51.5074,
 *       lng: -0.1278
 *     }
 *   })
 * });
 * 
 * const data = await response.json();
 * 
 * if (data.success) {
 *   console.log('Full 8-day schedule:', data.data.fullSchedule);
 *   console.log('Today\'s customers:', data.data.todaysSchedule?.customers);
 *   console.log('Total revenue:', data.data.metrics.totalRevenue);
 *   console.log('Time saved:', data.data.metrics.timeSavedHours, 'hours');
 * }
 * ```
 */

export default app;