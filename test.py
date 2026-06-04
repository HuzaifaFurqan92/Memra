import requests

# 1. First, make sure your test message is attached to huzaifa's session
append_url = "http://127.0.0.1:8000/chat/append"
payload = {
    "user_id": "huzaifa",
    "session_id": "session_day_three", 
    "role": "user", 
    "content": "I completely crash when I look at a massive 30-day roadmap. It triggers major analysis paralysis."
}
requests.post(append_url, json=payload)

# 2. Trigger the Core Feature 1 Synthesis Pipeline to update the graph!
sync_url = "http://127.0.0.1:8000/memory/update?session_id=session_day_three&user_id=huzaifa"
response = requests.post(sync_url)

print("Status Code:", response.status_code)
print("Response JSON:", response.json())