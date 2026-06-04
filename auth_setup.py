import requests

BACKEND_URL = "http://127.0.0.1:8000"

users_to_create = [
    {"username": "huzaif1a", "password": "password123"},
    {"username": "huzaifa", "password": "password123"}
]

for user in users_to_create:
    print(f"🔄 Registering account: {user['username']}...")
    # Form data is passed using the 'data' parameter to simulate an HTML form submission
    reg_resp = requests.post(f"{BACKEND_URL}/auth/register", data=user)
    print(f"   Status: {reg_resp.status_code}")
    
    print(f"🔑 Authenticating account: {user['username']}...")
    login_resp = requests.post(f"{BACKEND_URL}/auth/login", data=user)
    if login_resp.status_code == 200:
        token = login_resp.json()["access_token"]
        print(f"   ✅ Success! Token Generated:\nBearer {token}\n")
    else:
        print(f"   ❌ Authentication failed: {login_resp.text}\n")