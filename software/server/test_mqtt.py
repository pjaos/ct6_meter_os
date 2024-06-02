import network, utime, machine
import time
import ubinascii
from umqtt.simple import MQTTClient
import machine
import random

# Replace the following with your WIFI Credentials
#SSID = "airstorm11"
#SSID_PASSWORD = "train33sheep"

SSID = "BT-78AGMX"
SSID_PASSWORD = "fMcRbfY6GF6Ym6"

# Default  MQTT_BROKER to connect to
#MQTT_BROKER = "192.168.0.10"
MQTT_BROKER = "192.168.1.151"
CLIENT_ID = ubinascii.hexlify(machine.unique_id())
SUBSCRIBE_TOPIC = b"led"
PUBLISH_TOPIC = b"temperature"


def do_connect():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect(SSID, SSID_PASSWORD)
        while not sta_if.isconnected():
            print("Attempting to connect....")
            utime.sleep(1)
    print('Connected! Network config:', sta_if.ifconfig())

# Setup built in PICO LED as Output
led = machine.Pin("LED",machine.Pin.OUT)

# Publish MQTT messages after every set timeout
last_publish = time.time()
publish_interval = 1

# Received messages from subscriptions will be delivered to this callback
def sub_cb(topic, msg):
    print((topic, msg))
    if msg.decode() == "ON":
        led.value(1)
    else:
        led.value(0)


def reset():
    print("Resetting...")
    time.sleep(5)
    machine.reset()
    
# Generate dummy random temperature readings    
def get_temperature_reading():
    return random.randint(20, 50)
    
def main():
    
    print("Connecting to your wifi...")
    do_connect()

    print(f"Begin connection with MQTT Broker :: {MQTT_BROKER}")
    print(f"CLIENT_ID={CLIENT_ID}")
    mqttClient = MQTTClient(CLIENT_ID, MQTT_BROKER, keepalive=60)
    mqttClient.set_callback(sub_cb)
    mqttClient.connect()
    mqttClient.subscribe(SUBSCRIBE_TOPIC)
    print(f"Connected to MQTT  Broker :: {MQTT_BROKER}, and waiting for callback function to be called!")
    while True:
            # Non-blocking wait for message
            mqttClient.check_msg()
            global last_publish
            if (time.time() - last_publish) >= publish_interval:
                random_temp = get_temperature_reading()
                temperature = str(random_temp).encode()
                print(f"PUBLISH: {PUBLISH_TOPIC}={temperature}")
                mqttClient.publish(PUBLISH_TOPIC, temperature)
                
                last_publish = time.time()
            time.sleep(1)


if __name__ == "__main__":
    while True:
        try:
            main()
        except OSError as e:
            print("Error: " + str(e))
            reset()


