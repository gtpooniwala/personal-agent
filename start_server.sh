#!/bin/bash

# Personal Agent Backend Startup Script
# This script activates the conda environment and starts the backend server

echo "🚀 Starting Personal Agent Backend Server..."
echo "========================================"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Error: conda is not installed or not in PATH"
    echo "Please install Anaconda/Miniconda first"
    exit 1
fi

# Initialize conda for shell script
eval "$(conda shell.bash hook)"

# Check if personalagent environment exists
if ! conda env list | grep -q "personalagent"; then
    echo "❌ Error: conda environment 'personalagent' not found"
    echo "Please create the environment first:"
    echo "conda create -n personalagent python=3.11"
    echo "conda activate personalagent"
    echo "pip install -r backend/requirements.txt"
    exit 1
fi

# Activate the conda environment
echo "🔧 Activating conda environment 'personalagent'..."
conda activate personalagent

# Check if activation was successful
if [ "$CONDA_DEFAULT_ENV" != "personalagent" ]; then
    echo "❌ Error: Failed to activate conda environment 'personalagent'"
    exit 1
fi

echo "✅ Environment activated: $CONDA_DEFAULT_ENV"

# Change to backend directory
cd backend

# Check if requirements are installed
echo "🔍 Checking dependencies..."
if ! python -c "import uvicorn, fastapi" &> /dev/null; then
    echo "⚠️  Some dependencies might be missing. Installing requirements..."
    pip install -r requirements.txt
fi

# Start the server
echo "🌟 Starting FastAPI server..."
echo "Backend will be available at: http://localhost:8000"
echo "Frontend should be served separately (e.g., Live Server in VS Code)"
echo "========================================"

# Run the server
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
