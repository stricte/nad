import serial
import time
import logging

class SerialDevice:
    def __init__(self, port_name, logger=None):
        self.port_name = port_name
        self.ser = None
        self.logger = logger or logging.getLogger(__name__)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def open(self):
        if not self.ser:
            self.ser = serial.Serial(self.port_name, baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=1)
            self.logger.info(f"Serial port '{self.port_name}' opened.")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
            self.logger.info(f"Serial port '{self.port_name}' closed.")

    def send_command(self, command):
        self.open()
        # Include <CR> at the beginning and end of the command string
        command_with_cr = f"\r{command}\r"
        self.ser.write(command_with_cr.encode())
        time.sleep(0.3)  # Allow some time for the device to respond
        self.logger.info(f"Sent command: {command}")

    def receive_response(self):
        if self.ser and self.ser.is_open:
            response = self.ser.read(1024).decode()
            self.logger.info(f"Received response: {response.strip()}")
            return response.strip()
        else:
            self.logger.error("Serial port is not open.")
            return "Serial port is not open."
