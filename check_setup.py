#!/usr/bin/env python3
"""
Setup Validation Script
Checks if all prerequisites are met before starting the server
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_openai_key():
    """Check if OpenAI API key is set"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False, "OPENAI_API_KEY not found in environment"
    if not api_key.startswith("sk-"):
        return False, "OPENAI_API_KEY format looks incorrect"
    return True, f"Found (starts with: {api_key[:10]}...)"

def check_mongodb():
    """Check if MongoDB is accessible"""
    try:
        from pymongo import MongoClient
        from procurement_agent.config import Config

        client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command('ping')

        # Check if procurement database exists
        db = client[Config.MONGO_DB]
        collection = db[Config.MONGO_COLLECTION]
        count = collection.count_documents({})

        return True, f"Connected - {count:,} documents in {Config.MONGO_COLLECTION}"
    except Exception as e:
        return False, str(e)

def check_dependencies():
    """Check if required packages are installed"""
    missing = []
    try:
        import fastapi
    except ImportError:
        missing.append("fastapi")

    try:
        import uvicorn
    except ImportError:
        missing.append("uvicorn")

    try:
        import langgraph
    except ImportError:
        missing.append("langgraph")

    try:
        import chromadb
    except ImportError:
        missing.append("chromadb")

    try:
        import sentence_transformers
    except ImportError:
        missing.append("sentence_transformers")

    if missing:
        return False, f"Missing packages: {', '.join(missing)}"
    return True, "All required packages installed"

def check_static_files():
    """Check if static files exist"""
    static_files = [
        "procurement_agent/static/index.html",
        "procurement_agent/static/style.css",
        "procurement_agent/static/app.js"
    ]

    missing = [f for f in static_files if not os.path.exists(f)]

    if missing:
        return False, f"Missing files: {', '.join(missing)}"
    return True, "All static files present"

def main():
    print("=" * 80)
    print("Procurement Agent - Setup Validation")
    print("=" * 80)
    print()

    checks = [
        ("OpenAI API Key", check_openai_key),
        ("Python Dependencies", check_dependencies),
        ("Static Files", check_static_files),
        ("MongoDB Connection", check_mongodb),
    ]

    all_passed = True

    for name, check_func in checks:
        print(f"Checking {name}...", end=" ")
        passed, message = check_func()

        if passed:
            print(f"[OK] {message}")
        else:
            print(f"[FAILED] {message}")
            all_passed = False

    print()
    print("=" * 80)

    if all_passed:
        print("All checks passed! You're ready to start the server.")
        print()
        print("Run: python run_server.py")
        print("=" * 80)
        return 0
    else:
        print("Some checks failed. Please fix the issues above.")
        print()
        print("Common fixes:")
        print("  - Set API key: export OPENAI_API_KEY='your-key'")
        print("  - Install deps: pip install -r requirements.txt")
        print("  - Start MongoDB: mongod")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
