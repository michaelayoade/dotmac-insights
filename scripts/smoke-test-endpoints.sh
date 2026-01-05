#!/bin/bash
#
# Smoke Test API Endpoints
# Fetches OpenAPI spec and tests GET endpoints with curl
#
# Usage: ./scripts/smoke-test-endpoints.sh [limit]
#   limit: max number of endpoints to test (default: 50)
#

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
LIMIT="${1:-50}"
TIMEOUT=5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  DotMac BOS - API Endpoint Smoke Test"
echo "=============================================="
echo "Base URL: $BASE_URL"
echo "Testing up to $LIMIT endpoints"
echo ""

# Check if API is up
echo -n "Checking API health... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" --max-time $TIMEOUT 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED (HTTP $HTTP_CODE)${NC}"
    echo "API is not responding. Make sure it's running."
    exit 1
fi

# Fetch OpenAPI spec
echo -n "Fetching OpenAPI spec... "
OPENAPI_JSON=$(curl -s "$BASE_URL/openapi.json" --max-time 30)
if [ -z "$OPENAPI_JSON" ]; then
    echo -e "${RED}FAILED${NC}"
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# Extract GET endpoints using Python (available in most systems)
ENDPOINTS=$(echo "$OPENAPI_JSON" | python3 -c "
import sys, json, re
data = json.load(sys.stdin)
paths = data.get('paths', {})
count = 0
for path, methods in paths.items():
    if 'get' in methods and count < $LIMIT:
        # Substitute path parameters with test values
        test_path = re.sub(r'\{[^}]+\}', '1', path)
        print(test_path)
        count += 1
")

TOTAL=$(echo "$ENDPOINTS" | wc -l)
echo "Testing $TOTAL GET endpoints..."
echo ""

# Save endpoints to temp file to avoid subshell issues
TEMP_FILE=$(mktemp)
echo "$ENDPOINTS" > "$TEMP_FILE"

# Test each endpoint
PASSED=0
FAILED=0
SKIPPED=0
FAILURES=""

while IFS= read -r endpoint; do
    [ -z "$endpoint" ] && continue

    URL="${BASE_URL}${endpoint}"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" --max-time $TIMEOUT 2>/dev/null || echo "000")

    case $HTTP_CODE in
        2*)
            echo -e "  ${GREEN}✓${NC} $endpoint -> $HTTP_CODE"
            PASSED=$((PASSED + 1))
            ;;
        401|403)
            echo -e "  ${YELLOW}○${NC} $endpoint -> $HTTP_CODE (auth required)"
            SKIPPED=$((SKIPPED + 1))
            ;;
        404)
            echo -e "  ${YELLOW}○${NC} $endpoint -> $HTTP_CODE (not found)"
            SKIPPED=$((SKIPPED + 1))
            ;;
        5*)
            echo -e "  ${RED}✗${NC} $endpoint -> $HTTP_CODE (server error)"
            FAILED=$((FAILED + 1))
            FAILURES="$FAILURES\n  $endpoint -> $HTTP_CODE"
            ;;
        000)
            echo -e "  ${RED}✗${NC} $endpoint -> timeout/connection error"
            FAILED=$((FAILED + 1))
            FAILURES="$FAILURES\n  $endpoint -> timeout"
            ;;
        *)
            echo -e "  ${YELLOW}?${NC} $endpoint -> $HTTP_CODE"
            SKIPPED=$((SKIPPED + 1))
            ;;
    esac
done < "$TEMP_FILE"

rm -f "$TEMP_FILE"

# Summary
echo ""
echo "=============================================="
echo "  Results"
echo "=============================================="
echo -e "  ${GREEN}Passed:${NC}  $PASSED"
echo -e "  ${YELLOW}Skipped:${NC} $SKIPPED (auth/404)"
echo -e "  ${RED}Failed:${NC}  $FAILED (5xx/timeout)"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failures:${NC}"
    echo -e "$FAILURES"
    echo ""
    exit 1
else
    echo -e "${GREEN}All endpoints responding correctly!${NC}"
    exit 0
fi
