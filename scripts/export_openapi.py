# scripts/export_openapi.py
import json, requests, os
API_URL = os.getenv("API_URL","http://localhost:8000")
r = requests.get(f"{API_URL}/openapi.json", timeout=5)
r.raise_for_status()
spec = r.json()
with open("OpenAPI.json","w") as f:
    json.dump(spec, f, indent=2)
print("saved OpenAPI.json")
