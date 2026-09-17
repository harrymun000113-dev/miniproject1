import requests
 
api_url = "https://api.db.nomics.world/v22/"
 
try:
    response = requests.get(api_url, timeout=10)
    print("연결 성공! 상태 코드:", response.status_code)
except Exception as e:
    print("연결 실패:", e)