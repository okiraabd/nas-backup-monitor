"""Auth endpoint tests."""
import pytest


class TestLogin:
    def test_login_admin_success(self, client):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        assert resp.status_code == 401


class TestProtectedEndpoints:
    def test_me_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code in (401, 403)

    def test_me_with_token(self, client, admin_headers):
        resp = client.get("/api/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401


class TestLogout:
    def test_logout_revokes_token(self, client):
        # Login to get a fresh token
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Token works before logout
        assert client.get("/api/auth/me", headers=headers).status_code == 200

        # Logout
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 200

        # Token is revoked after logout
        assert client.get("/api/auth/me", headers=headers).status_code == 401
