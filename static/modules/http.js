const __etagCache = new Map();

export async function safeFetch(url, options = {}) {
    const maxRetries = options.maxRetries ?? 3;
    const baseDelay = options.baseDelay ?? 1000; // 1s
    const timeout = options.timeout ?? 10000; // 10s
    const retryStatusCodes = options.retryStatusCodes ?? [408, 429, 500, 502, 503, 504];

    let lastError;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            // Ajouter X-User depuis le sélecteur global (comme nav.js)
            const currentUser = window.getCurrentUser ? window.getCurrentUser() : null;
            if (!currentUser) {
                console.warn('[http.js] No current user found, requests may use default user');
            }

            const res = await fetch(url, {
                cache: 'no-store',
                signal: controller.signal,
                ...options,
                headers: {
                    ...(options.headers || {}),
                    ...(__etagCache.has(url) ? { 'If-None-Match': __etagCache.get(url) } : {}),
                    ...(currentUser ? { 'X-User': currentUser } : {})
                }
            });

            clearTimeout(timeoutId);

            let data = null;
            try {
                data = await res.json();
            } catch {
                // Réponses vides ou non JSON
                data = null;
            }

            const etag = res.headers?.get?.('ETag');
            if (etag) __etagCache.set(url, etag);

            if (res.status === 304) {
                return {
                    ok: true,
                    status: 304,
                    data: null,
                    notModified: true,
                    error: null
                };
            }

            const ok = res.ok === true;

            // Retry sur certains status codes
            if (!ok && retryStatusCodes.includes(res.status) && attempt < maxRetries) {
                const delay = baseDelay * Math.pow(2, attempt); // Retry exponentiel
                console.warn(`[safeFetch] Retry ${attempt + 1}/${maxRetries} for ${url} (status ${res.status}), waiting ${delay}ms`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }

            return {
                ok,
                status: res.status,
                data,
                error: ok ? null : (data?.error ?? 'http_error'),
                retries: attempt
            };

        } catch (error) {
            clearTimeout(timeoutId);
            lastError = error;

            // Network errors ou timeouts - retry
            if (attempt < maxRetries) {
                const delay = baseDelay * Math.pow(2, attempt);
                console.warn(`[safeFetch] Retry ${attempt + 1}/${maxRetries} for ${url} (${error.name}), waiting ${delay}ms`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }
        }
    }

    console.error(`[safeFetch] All retries failed for ${url}`, lastError);
    return {
        ok: false,
        status: 0,
        data: null,
        error: 'network_error',
        retries: maxRetries,
        lastError: lastError?.message
    };
}

// Helper pour les appels API avec timeout et retry optimisés
export async function apiCall(endpoint, options = {}) {
    return safeFetch(endpoint, {
        timeout: 15000, // 15s pour les APIs
        maxRetries: 2,
        baseDelay: 2000, // 2s de base
        ...options
    });
}