import requests

url = "https://api.deepseek.com/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk-0abdc931ff8e4a24bc732ea6e3d4be65"
}
data = {
    "model": "deepseek-v4-flash",
    "messages": [
        {"role": "user", "content": "Hi"}
    ]
}

print("Sending request...")
try:
    response = requests.post(url, headers=headers, json=data, timeout=10)
    print("Status Code:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", repr(e))
