#!/usr/bin/env python3
"""
Procurement Agent Server Startup Script
"""
import os
import sys
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check for OpenAI API key
if not os.getenv("OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY not found in environment variables")
    print("Please set your OpenAI API key:")
    print("  export OPENAI_API_KEY='your-api-key-here'")
    print("Or create a .env file with:")
    print("  OPENAI_API_KEY=your-api-key-here")
    sys.exit(1)

if __name__ == "__main__":
    print("=" * 80)
    print("Starting California Procurement Agent Server")
    print("=" * 80)
    print()
    print("Server will be available at:")
    print("  http://localhost:8000")
    print()
    print("API Documentation:")
    print("  http://localhost:8000/docs")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 80)
    print()

    uvicorn.run(
        "procurement_agent.api.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True  # Enable auto-reload during development
    )
