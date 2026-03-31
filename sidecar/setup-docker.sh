#!/usr/bin/env bash
# ============================================================================
# WebAxon Docker Sidecar — Build & Run Script
# ============================================================================
#
# This script builds and runs the WebAxon browser agent sidecar inside Docker,
# integrated with the OpenClaw gateway.
#
# Prerequisites:
#   1. Docker Desktop running
#   2. atlas slauth server running on localhost:5000:
#        atlas slauth server
#   3. Atlassian internal PyPI token (for atlassian-ai-gateway-sdk):
#        Your pip.conf should have packages.atlassian.com credentials
#   4. OpenClaw dist directory at the expected location
#
# Usage:
#   ./setup-docker.sh                    # Build and start
#   ./setup-docker.sh --build-only       # Build image only
#   ./setup-docker.sh --start-only       # Start without rebuilding
#   ./setup-docker.sh --test             # Build, start, and run test query
#   ./setup-docker.sh --stop             # Stop the service
#   ./setup-docker.sh --logs             # Show service logs
#   ./setup-docker.sh --backend selenium # Use selenium backend (default: selenium)
#   ./setup-docker.sh --backend playwright # Use playwright backend
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBAXON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CORE_PROJECTS_DIR="$(cd "$WEBAXON_DIR/.." && pwd)"
OPENCLAW_DIST_DIR="${OPENCLAW_DIST_DIR:-$CORE_PROJECTS_DIR/../atlassian_packages/openclaw-dist}"

# If openclaw-dist not found at default, try alternate location
if [[ ! -d "$OPENCLAW_DIST_DIR" ]]; then
  OPENCLAW_DIST_DIR="$CORE_PROJECTS_DIR/atlassian-packages/openclaw-dist"
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
ACTION="build-and-start"
BACKEND="selenium"
TEST_QUERY=""

# Parse args
for arg in "$@"; do
  case "$arg" in
    --build-only)    ACTION="build" ;;
    --start-only)    ACTION="start" ;;
    --test)          ACTION="test" ;;
    --stop)          ACTION="stop" ;;
    --logs)          ACTION="logs" ;;
    --backend)       shift_next=true ;;
    selenium|playwright)
      if [[ "${shift_next:-}" == "true" ]]; then
        BACKEND="$arg"
        shift_next=false
      fi
      ;;
    *)
      if [[ "${shift_next:-}" == "true" ]]; then
        BACKEND="$arg"
        shift_next=false
      fi
      ;;
  esac
done

# ── Helper Functions ──────────────────────────────────────────────────────────

info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
fail()  { echo -e "${RED}✗${NC}  $*"; exit 1; }

check_prerequisites() {
  info "Checking prerequisites..."

  # Docker
  if ! command -v docker &>/dev/null; then
    fail "Docker not found. Please install Docker Desktop."
  fi
  if ! docker info &>/dev/null 2>&1; then
    fail "Docker daemon not running. Please start Docker Desktop."
  fi
  ok "Docker is running"

  # SLAUTH server
  if curl -s http://localhost:5000/ &>/dev/null; then
    ok "SLAUTH server is running on port 5000"
  else
    warn "SLAUTH server not detected on port 5000"
    warn "  Run: atlas slauth server"
    warn "  The AG Claude inferencer needs SLAUTH for AI Gateway authentication"
  fi

  # Packages token (for atlassian-ai-gateway-sdk)
  if [[ -z "${PACKAGES_TOKEN:-}" ]]; then
    # Try to extract from pip.conf
    PIP_CONF="${HOME}/.config/pip/pip.conf"
    if [[ -f "$PIP_CONF" ]]; then
      PACKAGES_TOKEN=$(grep "packages.atlassian.com" "$PIP_CONF" | sed 's|.*//||;s|@.*||' | head -1)
      if [[ -n "$PACKAGES_TOKEN" ]]; then
        export PACKAGES_TOKEN
        ok "Packages token extracted from pip.conf"
      fi
    fi
    if [[ -z "${PACKAGES_TOKEN:-}" ]]; then
      warn "PACKAGES_TOKEN not set. Build may fail for atlassian-ai-gateway-sdk."
      warn "  Set it in openclaw-dist/.env or export PACKAGES_TOKEN=username:token"
    fi
  else
    ok "PACKAGES_TOKEN is set"
  fi

  # OpenClaw dist directory
  if [[ -d "$OPENCLAW_DIST_DIR" ]]; then
    ok "OpenClaw dist found at: $OPENCLAW_DIST_DIR"
  else
    fail "OpenClaw dist not found at: $OPENCLAW_DIST_DIR"
  fi

  # Source directories
  for dir in WebAxon RichPythonUtils AgentFoundation; do
    if [[ -d "$CORE_PROJECTS_DIR/$dir" ]]; then
      ok "Found $dir at $CORE_PROJECTS_DIR/$dir"
    else
      fail "Missing $dir at $CORE_PROJECTS_DIR/$dir"
    fi
  done
}

build_image() {
  info "Building WebAxon Docker image..."
  info "  Backend: $BACKEND"
  info "  Build context: $CORE_PROJECTS_DIR"

  cd "$OPENCLAW_DIST_DIR"

  # Set backend in env for docker-compose
  export WEBAXON_BACKEND="$BACKEND"

  docker compose build webaxon-agent 2>&1 | while IFS= read -r line; do
    if [[ "$line" == *"ERROR"* ]] || [[ "$line" == *"error"* ]]; then
      echo -e "${RED}  $line${NC}"
    elif [[ "$line" == *"Built"* ]] || [[ "$line" == *"DONE"* ]]; then
      echo -e "${GREEN}  $line${NC}"
    else
      echo "  $line"
    fi
  done

  ok "WebAxon Docker image built successfully"
}

start_service() {
  info "Starting WebAxon sidecar (backend: $BACKEND)..."

  cd "$OPENCLAW_DIST_DIR"
  export WEBAXON_BACKEND="$BACKEND"

  docker compose up webaxon-agent -d --force-recreate 2>&1 | grep -v "WARN\|variable"

  info "Waiting for service to become healthy..."
  for i in $(seq 1 30); do
    if curl -s http://localhost:18800/health &>/dev/null; then
      ok "WebAxon sidecar is healthy (http://localhost:18800)"
      return
    fi
    sleep 2
  done

  fail "Service did not become healthy within 60 seconds. Check: docker compose logs webaxon-agent"
}

stop_service() {
  info "Stopping WebAxon sidecar..."
  cd "$OPENCLAW_DIST_DIR"
  docker compose stop webaxon-agent 2>&1 | grep -v "WARN\|variable"
  ok "WebAxon sidecar stopped"
}

show_logs() {
  cd "$OPENCLAW_DIST_DIR"
  docker compose logs webaxon-agent --tail 100 -f 2>&1 | grep -v "WARN\|variable"
}

run_test() {
  info "Running test query..."

  echo ""
  info "Test 1: Health check"
  HEALTH=$(curl -s http://localhost:18800/health)
  if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('ok')" 2>/dev/null; then
    ok "Health check passed: $HEALTH"
  else
    fail "Health check failed: $HEALTH"
  fi

  echo ""
  info "Test 2: Navigate to example.com"
  NAV_RESULT=$(curl -s -X POST http://localhost:18800/navigate \
    -H "Content-Type: application/json" \
    -d '{"url": "https://www.example.com"}' 2>&1)
  if echo "$NAV_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('ok')" 2>/dev/null; then
    ok "Navigation succeeded"
  else
    warn "Navigation result: $NAV_RESULT"
  fi

  echo ""
  info "Test 3: Snapshot"
  SNAP_RESULT=$(curl -s -X POST http://localhost:18800/snapshot \
    -H "Content-Type: application/json" \
    -d '{}' 2>&1)
  if echo "$SNAP_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Title:', d.get('data',{}).get('title','N/A'))" 2>/dev/null; then
    ok "Snapshot succeeded"
  else
    warn "Snapshot result: $(echo $SNAP_RESULT | head -c 200)"
  fi

  echo ""
  info "Test 4: Agent query (this takes 1-5 minutes)..."
  QUERY_RESULT=$(curl -s --max-time 300 -X POST http://localhost:18800/query \
    -H "Content-Type: application/json" \
    -d '{"query": "Go to https://www.example.com and tell me what text is on the page"}' 2>&1)
  if echo "$QUERY_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('ok'); print('Response:', d.get('response','N/A'))" 2>/dev/null; then
    ok "Agent query completed successfully"
  else
    warn "Agent query result: $(echo $QUERY_RESULT | head -c 300)"
  fi

  echo ""
  ok "Tests complete!"
}

# ── Main ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       WebAxon Docker Sidecar Setup                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

case "$ACTION" in
  build)
    check_prerequisites
    build_image
    ;;
  start)
    start_service
    ;;
  stop)
    stop_service
    ;;
  logs)
    show_logs
    ;;
  build-and-start)
    check_prerequisites
    build_image
    start_service
    echo ""
    info "Service is running. Useful commands:"
    info "  Health:     curl http://localhost:18800/health"
    info "  Navigate:   curl -X POST http://localhost:18800/navigate -H 'Content-Type: application/json' -d '{\"url\": \"https://example.com\"}'"
    info "  Query:      curl -X POST http://localhost:18800/query -H 'Content-Type: application/json' -d '{\"query\": \"Go to example.com and describe what you see\"}'"
    info "  Logs:       $0 --logs"
    info "  Stop:       $0 --stop"
    ;;
  test)
    check_prerequisites
    build_image
    start_service
    run_test
    ;;
esac

echo ""
