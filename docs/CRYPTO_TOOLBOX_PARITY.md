# Crypto-Toolbox Parsing Parity Checklist

## Objective

Ensure **100% parity** between Flask (legacy) and FastAPI (new) implementations.

---

## Parsing Logic Comparison

### ✅ Ported Functions

| Function | Flask | FastAPI | Status |
|----------|-------|---------|--------|
| `parse_comparison()` | ✅ | ✅ | **Identical** |
| BMO special handling | ✅ | ✅ | **Identical** |
| Regex value extraction | ✅ | ✅ | **Identical** |
| Operator evaluation | ✅ | ✅ | **Identical** |
| Newline stripping | ✅ | ✅ | **Identical** |

---

## JSON Contract Validation

### Required Fields (Each Indicator)

- [x] `name` (string)
- [x] `value` (string, cleaned)
- [x] `value_numeric` (float)
- [x] `threshold` (string, cleaned)
- [x] `threshold_numeric` (float)
- [x] `threshold_operator` (string: ">=", "<=", ">", "<")
- [x] `in_critical_zone` (boolean)
- [x] `raw_value` (string, original)
- [x] `raw_threshold` (string, original)

### Response Structure

```json
{
    "success": true,
    "indicators": [...],
    "total_count": <int>,
    "critical_count": <int>,
    "scraped_at": "<ISO timestamp>",
    "source": "crypto-toolbox.vercel.app",
    "cached": <bool>,
    "cache_age_seconds": <int>
}
```

---

## Special Cases

### BMO (par Prof. Chaîne)

**Flask behavior**:
- Splits into multiple indicators with labels
- Format: `"BMO (par Prof. Chaîne) (Short-Term)"`
- Each sub-indicator has own threshold

**FastAPI behavior**:
- ✅ **Identical** (line 247-266)
- Regex: `r'(>=?\s*[\d.]+)\s*\(([^)]+)\)'`
- Uses `zip(vals, thrs)` to match values/thresholds

### Comparison Operators

**Flask regex**: `r'(>=|<=|>|<)\s*([\d.,]+)'`

**FastAPI regex**: `r'(>=|<=|>|<)\s*([\d.,]+)'`

**Status**: ✅ **Identical**

### Numeric Extraction

**Flask**: `re.search(r'[\d.,]+', val_raw.replace(',', ''))`

**FastAPI**: `re.search(r'[\d.,]+', val_raw.replace(',', ''))`

**Status**: ✅ **Identical**

---

## Test Cases

### Manual A/B Testing

**Prerequisites**:
1. Flask server running on port 8001
2. FastAPI server running on port 8000 (with router enabled, Commit 4+)
3. `jq` installed (optional, for JSON diff)

**Commands**:

```bash
# Capture Flask output
curl -s http://localhost:8001/api/crypto-toolbox > flask_output.json

# Capture FastAPI output (Commit 4+, flag ON)
curl -s http://localhost:8000/api/crypto-toolbox > fastapi_output.json

# Compare (visual)
diff flask_output.json fastapi_output.json

# Compare (structured, with jq)
jq -S '.indicators | sort_by(.name)' flask_output.json > flask_sorted.json
jq -S '.indicators | sort_by(.name)' fastapi_output.json > fastapi_sorted.json
diff flask_sorted.json fastapi_sorted.json
```

**Expected**:
- Same `total_count`
- Same `critical_count`
- Same indicator names (order may differ)
- Same `value_numeric` values (float precision: 2 decimals)
- Same `threshold_numeric` values
- Same `in_critical_zone` booleans

**Acceptable differences**:
- `scraped_at` timestamps (different scrape times)
- `cached` field (Flask always `false` or absent, FastAPI has TTL)
- `cache_age_seconds` (FastAPI only)

---

## Automated Tests (Future)

### Unit Test (Offline)

Simulate a DOM structure and verify parsing logic:

```python
# tests/unit/test_crypto_toolbox_parsing.py
import pytest
from api.crypto_toolbox_endpoints import _parse_comparison

def test_parse_comparison_greater_or_equal():
    op, val = _parse_comparison(">=80 (critical)")
    assert op == ">="
    assert val == 80.0

def test_parse_comparison_less_than():
    op, val = _parse_comparison("<0.5 (fear)")
    assert op == "<"
    assert val == 0.5

def test_parse_comparison_no_match():
    op, val = _parse_comparison("N/A")
    assert op is None
    assert val is None
```

### Integration Test (Live)

Compare Flask vs FastAPI responses:

```python
# tests/integration/test_crypto_toolbox_parity.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_parity_total_count():
    """Flask and FastAPI should return same total_count"""
    async with httpx.AsyncClient() as client:
        flask_resp = await client.get("http://localhost:8001/api/crypto-toolbox")
        fastapi_resp = await client.get("http://localhost:8000/api/crypto-toolbox?force=true")

        flask_data = flask_resp.json()
        fastapi_data = fastapi_resp.json()

        assert flask_data["total_count"] == fastapi_data["total_count"]
        assert flask_data["critical_count"] == fastapi_data["critical_count"]
```

---

## Validation Checklist (Before Commit 7)

Before switching default to FastAPI (`CRYPTO_TOOLBOX_NEW=1`), validate:

- [ ] Flask output captured (baseline)
- [ ] FastAPI output captured (with flag ON)
- [ ] `total_count` matches
- [ ] `critical_count` matches
- [ ] All indicator names present (both sides)
- [ ] BMO sub-indicators correctly split
- [ ] `value_numeric` values match (±0.01 tolerance)
- [ ] `in_critical_zone` booleans match
- [ ] No parsing errors in logs
- [ ] Response time <5 seconds (cache miss)
- [ ] Response time <50ms (cache hit)

---

## Known Differences (Expected)

| Field | Flask | FastAPI | Reason |
|-------|-------|---------|--------|
| `cached` | ❌ Absent or `false` | ✅ `true`/`false` | FastAPI has cache |
| `cache_age_seconds` | ❌ Absent | ✅ Present | FastAPI feature |
| `scraped_at` | Timestamp A | Timestamp B | Different scrape times |

---

## Rollback Criteria

If any of these fail, **rollback to Flask** (`CRYPTO_TOOLBOX_NEW=0`):

- ❌ `total_count` mismatch (>1 indicator difference)
- ❌ `critical_count` mismatch
- ❌ Missing indicators (name not found)
- ❌ Parsing errors in logs (>5% of requests)
- ❌ Response time >10 seconds (timeout)

---

**Last updated**: 2025-10-02
**Status**: Parsing logic ported (Commit 3)
**Next**: A/B testing (Commit 6)
