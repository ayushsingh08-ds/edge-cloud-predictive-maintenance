"""Entry point for data adapter service."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge.adapter import data_adapter

if __name__ == "__main__":
    print("[+] Data Adapter started")
    print("[+] Listening for sensor.raw messages...")
    
    # The module-level subscribe() call will be executed when imported
    # The adapter will process messages indefinitely
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n[X] Data Adapter stopped")
