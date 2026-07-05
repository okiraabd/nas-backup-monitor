import requests
res = requests.post("http://localhost:8000/api/auth/login", json={"username": "admin", "password": "admin123"})
token = res.json()["access_token"]
logs = requests.get("http://localhost:8000/api/logs?date_from=2026-07-04T00:00:00Z&date_to=2026-07-04T23:59:59Z", headers={"Authorization": f"Bearer {token}"})
print(logs.json())
