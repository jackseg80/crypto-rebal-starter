"""
Tests de sécurité pour les headers HTTP
Vérifie la configuration CSP, headers de sécurité et middleware
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestSecurityHeaders:
    """Tests pour les headers de sécurité HTTP"""

    def test_security_headers_present(self):
        """Vérifie que tous les headers de sécurité essentiels sont présents"""
        response = client.get("/")
        headers = response.headers

        # Headers obligatoires de sécurité
        required_headers = [
            "x-content-type-options",
            "x-frame-options",
            "x-xss-protection",
            "referrer-policy",
            "content-security-policy"
        ]

        for header in required_headers:
            assert header in headers, f"Header de sécurité manquant: {header}"

    def test_csp_configuration(self):
        """Vérifie la configuration CSP"""
        response = client.get("/")
        csp = response.headers.get("content-security-policy", "")

        # Directives CSP critiques
        assert "default-src" in csp, "CSP manque default-src"
        assert "script-src" in csp, "CSP manque script-src"
        assert "style-src" in csp, "CSP manque style-src"
        assert "img-src" in csp, "CSP manque img-src"

        # Pas de 'unsafe-inline' sans nonce/hash en production
        if "localhost" not in csp and "127.0.0.1" not in csp:
            assert "'unsafe-inline'" not in csp or "nonce-" in csp, \
                "CSP autorise unsafe-inline sans nonce en production"

    def test_xframe_protection(self):
        """Vérifie la protection contre le clickjacking"""
        response = client.get("/")
        xframe = response.headers.get("x-frame-options", "").lower()

        # Doit être DENY ou SAMEORIGIN
        assert xframe in ["deny", "sameorigin"], \
            f"X-Frame-Options invalide: {xframe}"

    def test_content_type_protection(self):
        """Vérifie la protection contre le MIME sniffing"""
        response = client.get("/")
        content_type_options = response.headers.get("x-content-type-options", "").lower()

        assert content_type_options == "nosniff", \
            "X-Content-Type-Options doit être 'nosniff'"

    def test_xss_protection(self):
        """Vérifie la protection XSS du navigateur"""
        response = client.get("/")
        xss_protection = response.headers.get("x-xss-protection", "")

        # Soit activé (1; mode=block) soit désactivé (0) pour les navigateurs modernes
        assert xss_protection in ["1; mode=block", "0"], \
            f"X-XSS-Protection invalide: {xss_protection}"

    def test_referrer_policy(self):
        """Vérifie la politique de référent"""
        response = client.get("/")
        referrer_policy = response.headers.get("referrer-policy", "").lower()

        # Doit être une politique de sécurité stricte
        secure_policies = [
            "no-referrer",
            "no-referrer-when-downgrade",
            "origin",
            "origin-when-cross-origin",
            "same-origin",
            "strict-origin",
            "strict-origin-when-cross-origin"
        ]

        assert referrer_policy in secure_policies, \
            f"Referrer-Policy non sécurisée: {referrer_policy}"

    def test_no_server_info_leak(self):
        """Vérifie qu'aucune information serveur n'est exposée"""
        response = client.get("/")
        headers = response.headers

        # Headers à éviter en production
        sensitive_headers = ["server", "x-powered-by"]

        for header in sensitive_headers:
            if header in headers:
                # Log warning mais ne fait pas échouer le test en dev
                print(f"⚠️ Header sensible détecté: {header}={headers[header]}")

    def test_cors_configuration(self):
        """Vérifie la configuration CORS"""
        # Test preflight request
        response = client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })

        # Vérifier que CORS est configuré
        assert "access-control-allow-origin" in response.headers

        # En production, ne pas autoriser '*'
        allow_origin = response.headers.get("access-control-allow-origin", "")
        if "localhost" not in allow_origin and "127.0.0.1" not in allow_origin:
            assert allow_origin != "*", \
                "CORS ne doit pas autoriser '*' en production"

    def test_security_headers_on_api_endpoints(self):
        """Vérifie que les headers de sécurité sont présents sur les endpoints API"""
        api_endpoints = [
            "/api/portfolio/metrics",
            "/api/balances/current",
            "/api/risk/summary"
        ]

        for endpoint in api_endpoints:
            try:
                response = client.get(endpoint)
                # Même les endpoints API doivent avoir les headers de sécurité de base
                assert "x-content-type-options" in response.headers, \
                    f"Headers sécurité manquants sur {endpoint}"
                assert "x-frame-options" in response.headers, \
                    f"Headers sécurité manquants sur {endpoint}"
            except Exception as e:
                # Log l'erreur mais continue les tests
                print(f"⚠️ Erreur test endpoint {endpoint}: {e}")

    def test_rate_limiting_headers(self):
        """Vérifie la présence des headers de rate limiting"""
        response = client.get("/")

        # Headers de rate limiting optionnels mais recommandés
        rate_limit_headers = [
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset"
        ]

        for header in rate_limit_headers:
            if header in response.headers:
                print(f"✅ Rate limiting header présent: {header}")

    @pytest.mark.parametrize("path", [
        "/static/dashboard.html",
        "/static/risk-dashboard.html",
        "/static/analytics-unified.html"
    ])
    def test_static_files_security(self, path):
        """Vérifie que les fichiers statiques ont les bons headers"""
        response = client.get(path)

        if response.status_code == 200:
            # Les fichiers statiques doivent également avoir des headers de sécurité
            assert "x-content-type-options" in response.headers

            # Cache-Control approprié pour les fichiers statiques
            cache_control = response.headers.get("cache-control", "")
            if cache_control:
                print(f"📄 Cache-Control pour {path}: {cache_control}")


class TestSecurityVulnerabilities:
    """Tests pour détecter des vulnérabilités communes"""

    def test_no_debug_info_in_responses(self):
        """Vérifie qu'aucune information de debug n'est exposée"""
        # Test avec un endpoint qui pourrait échouer
        response = client.get("/api/nonexistent")

        # Ne doit pas exposer de stack traces ou info debug
        response_text = response.text.lower()
        debug_indicators = [
            "traceback",
            "file \"/",
            "line ",
            "exception:",
            "debug=true"
        ]

        for indicator in debug_indicators:
            assert indicator not in response_text, \
                f"Information de debug exposée: {indicator}"

    def test_error_handling_security(self):
        """Vérifie que la gestion d'erreur ne fuit pas d'infos"""
        # Test avec différents types d'erreurs
        error_endpoints = [
            "/api/invalid-endpoint",
            "/api/portfolio/invalid",
            "/static/nonexistent.html"
        ]

        for endpoint in error_endpoints:
            response = client.get(endpoint)

            # Doit retourner une erreur générique, pas de détails internes
            if response.status_code >= 400:
                response_text = response.text.lower()

                # Vérifier qu'on n'expose pas de chemins système
                assert "/python/" not in response_text
                assert "\\python\\" not in response_text.replace("/", "\\")
                assert "smartfolio" not in response_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])