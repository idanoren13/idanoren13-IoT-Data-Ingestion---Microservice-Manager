import random
import time
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Configuration
API_URL = "http://localhost:8000/api/v1/sensors/data"
NUM_REQUESTS = 100
SENSORS = ["sensor-001", "sensor-002", "sensor-003"]
MIN_DELAY_MS = 20
MAX_DELAY_MS = 100

def generate_payload(sensor_id: str) -> dict:
    """Generate a random payload for the given sensor."""
    return {
        "sensor_id": sensor_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "readings": {
            "temperature": round(random.uniform(20.0, 30.0), 2),
            "humidity": round(random.uniform(40.0, 80.0), 2)
        },
        "metadata": {
            "device_type": "simulated"
        }
    }

def main():
    print(f"Starting simulation of {NUM_REQUESTS} requests across {len(SENSORS)} sensors.")
    
    success_count = 0
    error_count = 0
    
    for i in range(1, NUM_REQUESTS + 1):
        # Pick a random sensor
        sensor_id = random.choice(SENSORS)
        
        # Generate payload
        payload = generate_payload(sensor_id)
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(API_URL, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        
        # Send POST request
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 201:
                    success_count += 1
                    if i % 10 == 0:
                        print(f"[{i}/{NUM_REQUESTS}] Sent request for {sensor_id} -> Success")
                else:
                    error_count += 1
                    print(f"[{i}/{NUM_REQUESTS}] Error for {sensor_id}: {response.status}")
        except urllib.error.URLError as e:
            error_count += 1
            print(f"[{i}/{NUM_REQUESTS}] Request failed for {sensor_id}: {e}")
            
        # Random sleep between MIN_DELAY_MS and MAX_DELAY_MS
        delay_ms = random.randint(MIN_DELAY_MS, MAX_DELAY_MS)
        time.sleep(delay_ms / 1000.0)
        
    print("\nSimulation completed.")
    print(f"Successful requests: {success_count}")
    print(f"Failed requests: {error_count}")

if __name__ == "__main__":
    main()
