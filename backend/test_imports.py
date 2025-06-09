#!/usr/bin/env python3
"""
Simple synchronous test to validate imports
"""

import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

print("Testing imports...")

try:
    from orchestrator.core import CoreOrchestrator
    print("✅ CoreOrchestrator import successful")
except Exception as e:
    print(f"❌ CoreOrchestrator import failed: {e}")

try:
    from orchestrator.tool_registry import ToolRegistry
    print("✅ ToolRegistry import successful")
except Exception as e:
    print(f"❌ ToolRegistry import failed: {e}")

try:
    from config import settings
    print("✅ Settings import successful")
except Exception as e:
    print(f"❌ Settings import failed: {e}")

print("Import test completed!")
