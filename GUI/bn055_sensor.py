"""
BN055 IMU Sensor Reader and CSV Logger
Handles serial communication with BN055 sensor and saves data to CSV file
"""

import serial
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class BN055Reader:
    """Reads data from BN055 IMU sensor connected via serial port and logs to CSV"""
    
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        """
        Initialize BN055 sensor reader
        
        Args:
            port: Serial port (e.g., 'COM3', '/dev/ttyUSB0')
            baudrate: Serial communication speed (default 115200)
            timeout: Serial read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn: Optional[serial.Serial] = None
        self.csv_file: Optional[str] = None
        self.csv_writer = None
        self.is_recording = False
    
    def connect(self) -> bool:
        """
        Establish connection to BN055 sensor
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"Connected to BN055 on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to {self.port}: {e}")
            return False
    
    def disconnect(self) -> None:
        """Close serial connection"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print("Disconnected from BN055")
    
    def start_recording(self, output_file: str = None) -> bool:
        """
        Start recording sensor data to CSV file
        
        Args:
            output_file: Path to output CSV file. If None, creates timestamped file
        
        Returns:
            True if recording started successfully, False otherwise
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("Serial connection not established")
            return False
        
        try:
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"bn055_data_{timestamp}.csv"
            
            self.csv_file = output_file
            
            # Create parent directories if needed
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            
            # Open CSV file and write header
            self.csv_file_handle = open(output_file, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file_handle)
            
            # Write header row (adjust based on your sensor output format)
            self.csv_writer.writerow([
                'Timestamp',
                'Accel_X', 'Accel_Y', 'Accel_Z',
                'Gyro_X', 'Gyro_Y', 'Gyro_Z',
                'Mag_X', 'Mag_Y', 'Mag_Z',
                'Temp'
            ])
            self.csv_file_handle.flush()
            
            self.is_recording = True
            print(f"Started recording to {output_file}")
            return True
        
        except IOError as e:
            print(f"Failed to open CSV file: {e}")
            return False
    
    def stop_recording(self) -> None:
        """Stop recording and close CSV file"""
        if self.csv_file_handle:
            self.csv_file_handle.close()
            self.is_recording = False
            print(f"Stopped recording. Data saved to {self.csv_file}")
    
    def read_sensor_data(self) -> Optional[str]:
        """
        Read one line of data from sensor
        
        Returns:
            Raw sensor data string, or None if read fails
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
        
        try:
            if self.serial_conn.in_waiting > 0:
                data = self.serial_conn.readline().decode('utf-8').strip()
                return data if data else None
        except (serial.SerialException, UnicodeDecodeError) as e:
            print(f"Error reading from sensor: {e}")
        
        return None
    
    def parse_sensor_data(self, raw_data: str) -> Optional[list]:
        """
        Parse raw sensor data string into list of values
        Adjust parsing based on your sensor's output format
        
        Args:
            raw_data: Raw string from sensor
        
        Returns:
            List of parsed values, or None if parsing fails
        """
        try:
            # Example parsing for comma-separated values
            # Adjust this based on your actual sensor output format
            values = raw_data.split(',')
            
            # Add timestamp at the beginning
            parsed = [datetime.now().isoformat()] + values
            return parsed
        except Exception as e:
            print(f"Error parsing sensor data: {e}")
            return None
    
    def log_data_point(self, data: list) -> None:
        """
        Write a data point to CSV file
        
        Args:
            data: List of values to write
        """
        if self.is_recording and self.csv_writer:
            try:
                self.csv_writer.writerow(data)
                self.csv_file_handle.flush()
            except IOError as e:
                print(f"Error writing to CSV: {e}")
    
    def read_and_log_continuous(self, duration: float = None) -> None:
        """
        Continuously read from sensor and log to CSV
        
        Args:
            duration: How long to read in seconds. If None, reads indefinitely
        """
        if not self.is_recording:
            print("Recording not started. Call start_recording() first.")
            return
        
        start_time = time.time()
        
        try:
            while True:
                if duration and (time.time() - start_time) > duration:
                    break
                
                raw_data = self.read_sensor_data()
                if raw_data:
                    parsed_data = self.parse_sensor_data(raw_data)
                    if parsed_data:
                        self.log_data_point(parsed_data)
                
                time.sleep(0.01)  # Small delay to prevent CPU spinning
        
        except KeyboardInterrupt:
            print("Recording interrupted by user")
        finally:
            self.stop_recording()


def main_example():
    """Example usage of BN055Reader"""
    # Create sensor reader instance
    reader = BN055Reader(port='COM3', baudrate=115200)  # Adjust port as needed
    
    # Connect to sensor
    if not reader.connect():
        return
    
    # Start recording to CSV
    if not reader.start_recording('sensor_data.csv'):
        reader.disconnect()
        return
    
    # Read and log data for 60 seconds
    try:
        reader.read_and_log_continuous(duration=60)
    finally:
        reader.disconnect()


if __name__ == "__main__":
    main_example()
