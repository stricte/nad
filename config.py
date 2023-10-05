class AppConfig:
    def __init__(self):
        self.broker_ip = "127.0.0.1"
        self.broker_port = 1883
        self.broker_topic = "nad"
        self.logger_name = "mqtt_receive"
        self.logger_path = "/var/log/nad/mqtt_receive.log"
        self.serial = "/dev/ttyUSB0"
        self.daemon_pid = "/var/run/nad/mqtt_receive.pid"


config = AppConfig()
