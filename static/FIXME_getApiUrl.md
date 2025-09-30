# FIXME: getApiUrl() - Risk of /api/api Duplication

## Problem

`static/global-config.js:242` - `getApiUrl(endpoint, additionalParams)` can create duplicate `/api/api` URLs.

**Scenario:**
- `api_base_url` = `http://localhost:8000/api` (ends with `/api`)
- `endpoint` = `/api/risk/status` (starts with `/api`)
- **Result:** `http://localhost:8000/api/api/risk/status` ❌

## Current Code (Line 242-258)

```javascript
getApiUrl(endpoint, additionalParams = {}) {
  const base = this.settings.api_base_url;
  const url = new URL(endpoint, base.endsWith('/') ? base : base + '/');
  // ... adds params ...
  return url.toString();
}
```

## Proposed Fix

Add normalization before creating URL:

```javascript
getApiUrl(endpoint, additionalParams = {}) {
  const base = this.settings.api_base_url;

  // Normalize endpoint to avoid /api/api duplication
  let normalizedEndpoint = endpoint;
  if (base.endsWith('/api') && /^\/+api(\/|$)/i.test(endpoint)) {
    normalizedEndpoint = endpoint.replace(/^\/+api/, '');
    if (!normalizedEndpoint.startsWith('/')) {
      normalizedEndpoint = '/' + normalizedEndpoint;
    }
  }

  const url = new URL(normalizedEndpoint, base.endsWith('/') ? base : base + '/');

  const defaults = {
    source: this.settings.data_source,
    pricing: this.settings.pricing,
    min_usd: this.settings.min_usd_threshold
  };

  const all = { ...defaults, ...additionalParams };
  Object.entries(all).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
  });

  return url.toString();
}
```

## Test Cases

```javascript
// Test 1: Base with /api, endpoint with /api
base = "http://localhost:8000/api"
endpoint = "/api/risk/status"
expected = "http://localhost:8000/api/risk/status" ✅

// Test 2: Base with /api, endpoint without /api
base = "http://localhost:8000/api"
endpoint = "/risk/status"
expected = "http://localhost:8000/api/risk/status" ✅

// Test 3: Base without /api, endpoint with /api
base = "http://localhost:8000"
endpoint = "/api/risk/status"
expected = "http://localhost:8000/api/risk/status" ✅
```

## Why Not Fixed Yet

File is being continuously modified by a watcher/linter, making direct edits impossible.
Created this FIXME document instead for future reference.

## Related

- Commit 2de5a53: Removed duplicate simple getApiUrl() at line 157
- 6 active usages of getApiUrl() in: execution.html, risk-dashboard.html, saxo-dashboard.html