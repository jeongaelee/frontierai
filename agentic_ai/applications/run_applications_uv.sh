#!/bin/bash
# Determine project root
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")

# Set paths relative to project root
MCP_DIR="$PROJECT_ROOT/mcp"
APP_DIR="$PROJECT_ROOT/agentic_ai/applications"
OUTPUT_LOG="$PROJECT_ROOT/logs/output.log"
ERROR_LOG="$PROJECT_ROOT/logs/error.log"

mkdir -p "$PROJECT_ROOT/logs"

# Function to add timestamps and service prefixes
log_with_prefix() {
    local service_name="$1"
    awk -v service="$service_name" '{print "[" strftime("%Y-%m-%d %H:%M:%S") "] [" service "] " $0; fflush()}'
}

# Start MCP server
echo "Starting MCP server..."
cd "$MCP_DIR"
uv run mcp_service.py 2>&1 | log_with_prefix "MCP" >> $OUTPUT_LOG &
MCP_PID=$!

sleep 5

# Start backend
echo "Starting backend..."
cd "$APP_DIR"
uv run backend.py 2>&1 | log_with_prefix "BACKEND" >> $OUTPUT_LOG &
BACKEND_PID=$!

sleep 5
uv run streamlit run frontend.py 2>&1 | log_with_prefix "FRONTEND" >> $OUTPUT_LOG &
FRONTEND_PID=$!

echo "MCP Server PID: $MCP_PID"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Project root: $PROJECT_ROOT"