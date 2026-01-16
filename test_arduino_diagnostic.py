#!/usr/bin/env python3
"""
Diagnostic tool to test Arduino serial connection and data flow.
Run this to verify the Arduino is sending data correctly.
"""

import sys
import time
from pathlib import Path

# Add GUI directory to path
gui_path = Path(__file__).parent / "GUI"
sys.path.insert(0, str(gui_path))

try:
    from Arduino import ArduinoReader
    import serial
    import serial.tools.list_ports
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure pyserial is installed: pip install pyserial")
    sys.exit(1)

def find_arduino_port():
    """Find Arduino serial port."""
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    
    print("Available serial ports:")
    for p in ports:
        desc = p.description or "Unknown"
        print(f"  {p.device}: {desc}")
    
    # Try common Arduino ports
    for p in ports:
        desc = (p.description or "").lower()
        if "arduino" in desc or "usb" in desc or "cp210x" in desc or "ch340" in desc:
            print(f"\nSelected port: {p.device}")
            return p.device
    
    # Fallback to first port
    if ports:
        print(f"\nSelected port (first available): {ports[0].device}")
        return ports[0].device
    
    return None

def test_arduino_connection():
    """Test Arduino serial connection and data reception."""
    port = find_arduino_port()
    if not port:
        print("ERROR: No Arduino port found!")
        return False
    
    print(f"\nTesting connection to {port}...")
    
    # Test 1: Can we open the port?
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        print("✓ Successfully opened serial port")
        ser.close()
    except Exception as e:
        print(f"✗ Failed to open serial port: {e}")
        return False
    
    # Test 2: Can we create an ArduinoReader?
    try:
        lines_received = []
        quaternions_received = []
        
        def on_line(line):
            lines_received.append(line)
            print(f"  Line: {line}")
        
        def on_quat(quat):
            quaternions_received.append(quat)
            w, x, y, z = quat
            print(f"  Quaternion: w={w:.4f}, x={x:.4f}, y={y:.4f}, z={z:.4f}")
        
        reader = ArduinoReader(port=port, callback=on_quat, line_callback=on_line, auto_connect=False)
        print("✓ Successfully created ArduinoReader")
        
        # Test 3: Can we connect?
        try:
            reader.connect()
            print("✓ Successfully connected")
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
        
        # Test 4: Start background thread and wait for data
        try:
            reader.start_background()
            print("✓ Started background thread")
        except Exception as e:
            print(f"✗ Failed to start background thread: {e}")
            return False
        
        # Test 5: Wait for data
        print("\nWaiting for data (10 seconds)...")
        start_time = time.time()
        while time.time() - start_time < 10:
            if lines_received:
                print(f"\n✓ Received {len(lines_received)} lines and {len(quaternions_received)} quaternions")
                print("\nSample data received:")
                for i, line in enumerate(lines_received[:5]):
                    print(f"  {i+1}. {line}")
                if len(lines_received) > 5:
                    print(f"  ... and {len(lines_received) - 5} more lines")
                break
            time.sleep(0.1)
        else:
            print("✗ No data received after 10 seconds")
            print("  Check that:")
            print("  1. Arduino is powered and connected")
            print("  2. Arduino sketch is uploading data on the selected port")
            print("  3. Baud rate (115200) matches Arduino sketch")
            reader.close()
            return False
        
        # Cleanup
        reader.close()
        return True
        
    except Exception as e:
        print(f"✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Arduino Connection Diagnostic Tool")
    print("=" * 60)
    
    success = test_arduino_connection()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ Arduino connection test PASSED")
        print("  The Arduino is properly connected and sending data.")
    else:
        print("✗ Arduino connection test FAILED")
        print("  See above for details on what went wrong.")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
