#!/bin/bash

# Personal Agent MVP Setup Script

echo "🤖 Setting up Personal Agent MVP..."

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Conda is required but not installed. Please install Anaconda or Miniconda and try again."
    exit 1
fi

# Check conda version
conda_version=$(conda --version)
echo "✅ Found $conda_version"

# Create conda environment
echo "📦 Creating conda environment 'personalagent'..."
conda create -n personalagent python=3.11 -y

# Activate conda environment
echo "🔄 Activating conda environment..."
eval "$(conda shell.bash hook)"
conda activate personalagent

# Install dependencies
echo "📋 Installing dependencies..."
pip install -r backend/requirements.txt

# Install frontend dependencies
if ! command -v npm &> /dev/null; then
    echo "❌ Node.js/npm is required for the Next.js frontend but was not found."
    echo "Install Node.js 18+ and run: cd frontend && npm install"
    exit 1
fi

node_major="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
if [ -z "$node_major" ] || [ "$node_major" -lt 18 ]; then
    echo "❌ Node.js 18+ is required for the Next.js frontend."
    echo "Detected: $(node -v)"
    exit 1
fi

echo "📋 Installing frontend dependencies..."
cd frontend || { echo "❌ frontend directory not found."; exit 1; }
npm install || { echo "❌ Failed to install frontend dependencies."; exit 1; }
cd ..

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚙️  Creating environment configuration..."
    cp .env.example .env
    echo "📝 Please edit .env and add your Gemini API key:"
    echo "   GEMINI_API_KEY=your_api_key_here"
    echo ""
fi

# Create data directory
echo "📁 Creating data directory..."
mkdir -p backend/data

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env and add your Gemini API key"
echo "2. Activate the conda environment: conda activate personalagent"
echo "3. Start the backend: uvicorn backend.main:app --reload"
echo "4. Start the frontend: cd frontend && npm run dev"
echo "5. Open http://127.0.0.1:3000 in your browser"
echo ""
echo "🚀 Your Personal Agent MVP is ready to use!"
