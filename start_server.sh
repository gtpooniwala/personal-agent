#!/bin/bash

# Personal Agent Backend Startup Script (macOS version)
# This script opens two new Terminal windows and runs the backend and frontend servers separately

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Error: conda is not installed or not in PATH"
    echo "Please install Anaconda/Miniconda first"
    exit 1
fi

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed or not in PATH"
    echo "Please install Node.js 18+"
    exit 1
fi

# Check if personalagent environment exists
if ! conda env list | grep -q "personalagent"; then
    echo "❌ Error: conda environment 'personalagent' not found"
    echo "Please create the environment first:"
    echo "conda create -n personalagent python=3.11"
    echo "conda activate personalagent"
    echo "pip install -r backend/requirements.txt"
    exit 1
fi

# Get absolute path to project root
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Open backend server in new Terminal window
osascript <<END
  tell application "Terminal"
    do script "cd $PROJECT_ROOT; source ~/.zshrc; conda activate personalagent; uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
    activate
  end tell
END

echo "✅ Backend server started in a new Terminal window."

# Open frontend Next.js dev server in new Terminal window
osascript <<END
  tell application "Terminal"
    do script "cd $PROJECT_ROOT/frontend; if [ ! -d node_modules ]; then npm install; fi; npm run dev"
    activate
  end tell
END

echo "✅ Frontend Next.js server started in a new Terminal window."

echo "========================================"
echo "Backend running at: http://localhost:8000"
echo "Frontend running at: http://localhost:3000"
echo "Press Ctrl+C in the respective Terminal windows to stop the servers."
