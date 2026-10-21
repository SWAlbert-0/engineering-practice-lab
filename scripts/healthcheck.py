"""Container readiness probe, using only Python's standard library."""
import json
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=3) as response:
    result = json.load(response)
    if response.status != 200 or result != {'status': 'ok', 'projects': 5}:
        raise SystemExit('Service is not ready')
