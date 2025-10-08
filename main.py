#!/usr/bin/env python3
"""
Railway deployment entry point for Window Cleaner AI Optimizer
"""
import uvicorn
import os
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"🚀 Starting Window Cleaner AI Optimizer on {host}:{port}")
    print(f"📡 Railway deployment ready!")
    
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_level="info"
    )