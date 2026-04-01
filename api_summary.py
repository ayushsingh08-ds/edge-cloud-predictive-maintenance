#!/usr/bin/env python3
"""
API Summary - Display what the FastAPI backend can do
"""

import json
import requests

BASE_URL = "http://localhost:8000"

print("=" * 80)
print("🚀 FASTAPI BACKEND - EDGE-CLOUD PREDICTIVE MAINTENANCE SYSTEM")
print("=" * 80)
print()

# Test each endpoint category
endpoints = {
    "Machines": [
        ("GET", "/api/machines/", "List all machines"),
        ("GET", "/api/machines/0", "Get machine details"),
        ("GET", "/api/machines/0/health", "Get machine health"),
        ("GET", "/api/machines/0/sensors", "Get sensor readings"),
    ],
    "Jobs": [
        ("GET", "/api/jobs/queue", "Get job queue"),
        ("GET", "/api/jobs/1", "Get specific job"),
        ("GET", "/api/jobs/completed/recent", "Get completed jobs"),
        ("GET", "/api/jobs/statistics", "Get job statistics"),
    ],
    "Anomalies": [
        ("GET", "/api/anomalies/", "Get recent anomalies"),
        ("GET", "/api/anomalies/machine/0", "Get machine anomalies"),
        ("GET", "/api/anomalies/sensor/temperature", "Get sensor anomalies"),
        ("GET", "/api/anomalies/statistics", "Get anomaly stats"),
    ],
    "Simulation": [
        ("POST", "/api/simulation/run", "Run simulation"),
        ("POST", "/api/simulation/compare-policies", "Compare policies"),
        ("GET", "/api/simulation/history/recent", "Get simulation history"),
    ],
    "RL Training": [
        ("POST", "/api/rl-training/start", "Start training"),
        ("GET", "/api/rl-training/models/list", "List trained models"),
        ("POST", "/api/rl-training/model_id/evaluate", "Evaluate model"),
    ],
    "Analytics": [
        ("GET", "/api/analytics/metrics/current", "Get current metrics"),
        ("GET", "/api/analytics/metrics/history", "Get metric history"),
        ("GET", "/api/analytics/kpi/dashboard", "Get dashboard KPIs"),
        ("GET", "/api/analytics/report/system", "Generate system report"),
        ("GET", "/api/analytics/forecast/rul", "Get RUL forecasts"),
    ],
}

for category, routes in endpoints.items():
    print(f"📍 {category.upper()}")
    print("-" * 80)
    for method, route, description in routes:
        print(f"  {method:4} {route:40} → {description}")
    print()

# Test a sample endpoint
print("=" * 80)
print("🧪 SAMPLE API CALL - Fetching Machine Status")
print("=" * 80)

try:
    response = requests.get(f"{BASE_URL}/api/machines/")
    if response.status_code == 200:
        machines = response.json()
        print(f"\n✅ API Response (HTTP {response.status_code}):\n")
        
        for machine in machines:
            print(f"  Machine-{machine['machine_id']}:")
            print(f"    ├─ State: {machine['state']}")
            print(f"    ├─ Health: {machine['health']['health_index']*100:.0f}%")
            print(f"    ├─ RUL: {machine['health']['rul_hours']:.0f} hours")
            print(f"    ├─ Queue Length: {machine['queue_length']}")
            print(f"    └─ Temperature: {machine['latest_sensors']['temperature']}°C")
        
        print()
    else:
        print(f"❌ API Error: HTTP {response.status_code}")

except Exception as e:
    print(f"❌ Connection Error: {str(e)}")
    print("\n   Make sure the API server is running:")
    print("   python -m uvicorn api.main:app --host 0.0.0.0 --port 8000")

print()
print("=" * 80)
print("📚 DOCUMENTATION")
print("=" * 80)
print(f"""
✅ Interactive Swagger UI:  http://localhost:8000/api/docs
✅ Alternative ReDoc:       http://localhost:8000/api/redoc
✅ OpenAPI Schema:          http://localhost:8000/api/openapi.json
✅ Health Check:             http://localhost:8000/health

Full documentation: See API_DOCUMENTATION.md
""")

print("=" * 80)
print("🎯 NEXT STEPS - Frontend Integration")
print("=" * 80)
print("""
1. Install HTTP Client:
   npm install axios

2. Create API Service:
   // Example: src/api/client.js
   const API = axios.create({
     baseURL: 'http://localhost:8000/api'
   });

3. Use in Components:
   const machines = await API.get('/machines/');
   const queue = await API.get('/jobs/queue');
   const metrics = await API.get('/analytics/metrics/current');

4. Real-time Updates:
   // WebSocket (coming soon)
   const ws = new WebSocket('ws://localhost:8000/ws/machines/0');

See FRONTEND_GUIDE.md for detailed implementation examples.
""")

print("=" * 80)
print("✅ FastAPI Backend Ready for Frontend Development!")
print("=" * 80)
