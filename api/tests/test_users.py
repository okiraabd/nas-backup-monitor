"""User management endpoint tests."""


class TestUserList:
    def test_admin_list_users(self, client, admin_headers):
        resp = client.get("/api/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 3  # admin, nas-wd, collector from seed

    def test_service_cannot_list_users(self, client, service_headers):
        resp = client.get("/api/users", headers=service_headers)
        assert resp.status_code == 403

    def test_collector_cannot_list_users(self, client, collector_headers):
        resp = client.get("/api/users", headers=collector_headers)
        assert resp.status_code == 403


class TestUserCRUD:
    def test_create_user(self, client, admin_headers):
        resp = client.post(
            "/api/users",
            json={
                "username": "test-user-crud",
                "password": "testpass123",
                "display_name": "Test User",
                "role": "service",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "test-user-crud"
        assert data["role"] == "service"
        assert data["is_active"] is True

    def test_create_duplicate_user(self, client, admin_headers):
        resp = client.post(
            "/api/users",
            json={
                "username": "admin",
                "password": "testpass123",
                "display_name": "Dup",
                "role": "admin",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_get_user(self, client, admin_headers):
        users = client.get("/api/users", headers=admin_headers).json()
        user_id = users[0]["id"]
        resp = client.get(f"/api/users/{user_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == user_id

    def test_update_user(self, client, admin_headers):
        users = client.get("/api/users", headers=admin_headers).json()
        target = [u for u in users if u["username"] == "test-user-crud"]
        if target:
            uid = target[0]["id"]
            resp = client.patch(
                f"/api/users/{uid}",
                json={"display_name": "Updated Name"},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["display_name"] == "Updated Name"

    def test_soft_delete_user(self, client, admin_headers):
        users = client.get("/api/users", headers=admin_headers).json()
        target = [u for u in users if u["username"] == "test-user-crud"]
        if target:
            uid = target[0]["id"]
            resp = client.delete(f"/api/users/{uid}", headers=admin_headers)
            assert resp.status_code == 204

    def test_admin_cannot_demote_self(self, client, admin_headers):
        me = client.get("/api/auth/me", headers=admin_headers).json()
        resp = client.patch(
            f"/api/users/{me['id']}",
            json={"role": "operator"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_admin_cannot_disable_self_via_patch(self, client, admin_headers):
        me = client.get("/api/auth/me", headers=admin_headers).json()
        resp = client.patch(
            f"/api/users/{me['id']}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert resp.status_code == 400


class TestPasswordAndToken:
    def test_reset_password(self, client, admin_headers):
        users = client.get("/api/users", headers=admin_headers).json()
        target = [u for u in users if u["username"] == "nas-wd"]
        if target:
            uid = target[0]["id"]
            resp = client.patch(
                f"/api/users/{uid}/password",
                json={"new_password": "newpass123"},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            # Restore original password
            client.patch(
                f"/api/users/{uid}/password",
                json={"new_password": "wd123"},
                headers=admin_headers,
            )

    def test_generate_password_service_account(self, client, admin_headers):
        created = client.post(
            "/api/users",
            json={
                "username": "generate-service-test",
                "password": "oldpass123",
                "display_name": "Generate Service Test",
                "role": "service",
            },
            headers=admin_headers,
        )
        assert created.status_code == 201
        uid = created.json()["id"]

        try:
            resp = client.post(f"/api/users/{uid}/password/generate", headers=admin_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "new_password" in data
            assert data["message"]  # "Store this password now..."

            old_login = client.post(
                "/api/auth/login",
                json={"username": "generate-service-test", "password": "oldpass123"},
            )
            assert old_login.status_code == 401

            new_login = client.post(
                "/api/auth/login",
                json={"username": "generate-service-test", "password": data["new_password"]},
            )
            assert new_login.status_code == 200
        finally:
            client.delete(f"/api/users/{uid}", headers=admin_headers)

    def test_generate_password_admin_allowed(self, client, admin_headers):
        created = client.post(
            "/api/users",
            json={
                "username": "rotate-admin-test",
                "password": "oldpass123",
                "display_name": "Rotate Admin Test",
                "role": "admin",
            },
            headers=admin_headers,
        )
        assert created.status_code == 201
        uid = created.json()["id"]

        try:
            resp = client.post(f"/api/users/{uid}/password/generate", headers=admin_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["username"] == "rotate-admin-test"

            new_login = client.post(
                "/api/auth/login",
                json={"username": "rotate-admin-test", "password": data["new_password"]},
            )
            assert new_login.status_code == 200
        finally:
            client.delete(f"/api/users/{uid}", headers=admin_headers)
