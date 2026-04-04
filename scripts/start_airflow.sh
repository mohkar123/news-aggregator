#!/bin/bash
#
# Start Airflow in standalone mode
# This runs scheduler, webserver, and triggerer in one process
#
# Usage: ./scripts/start_airflow.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}   Airflow News Aggregator          ${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Run the setup first (see README.md)"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Load environment variables
if [ -f ".env" ]; then
    source .env
    echo -e "${GREEN}✅ Loaded .env file${NC}"
else
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
fi

# Set Airflow home
export AIRFLOW_HOME="$PROJECT_ROOT"
export AIRFLOW__CORE__DAGS_FOLDER="$PROJECT_ROOT/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False

# Check API key
if [ -z "$NYTIMES_API_KEY" ] || [ "$NYTIMES_API_KEY" == "your_api_key_here" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  NYTimes API key not configured!${NC}"
    echo ""
    echo "To get your API key:"
    echo "  1. Go to https://developer.nytimes.com/"
    echo "  2. Create an account and register an app"
    echo "  3. Get your API key"
    echo "  4. Edit .env and set NYTIMES_API_KEY=your_key"
    echo ""
    echo -e "${YELLOW}The learning DAGs will work, but the news aggregator won't.${NC}"
    echo ""
fi

echo ""
echo -e "${GREEN}Starting Airflow...${NC}"
echo ""
echo "📍 Airflow Home: $AIRFLOW_HOME"
echo "📁 DAGs Folder: $AIRFLOW__CORE__DAGS_FOLDER"
echo ""
echo -e "${BLUE}Web UI: http://localhost:8080${NC}"
echo ""
echo -e "${YELLOW}Credentials will be displayed below when Airflow starts.${NC}"
echo -e "${YELLOW}Look for 'Login with the following credentials'${NC}"
echo ""
echo "Press Ctrl+C to stop Airflow"
echo ""
echo "======================================"
echo ""

# Run Airflow standalone
# This starts scheduler, webserver, and triggerer together
airflow standalone
