"""BFF Specification and contract helper for automated security tests."""

def get_logout_endpoint_spec():
    return {
        "cookies_to_delete": [
            "platform_access_token",
            "platform_refresh_token",
            "platform_session",
            "oidc_code_verifier",
            "oidc_auth_state",
        ],
        "redirect_url": "http://localhost:8080/realms/platform/protocol/openid-connect/logout?post_logout_redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Flogin&client_id=platform-frontend",
    }
