#!/bin/bash
# This requires that the docker mosquito MQTT server is running
# An example of subscribing to the CT6 topic. Used for testing
# the CT6 MQTT server support.
mosquitto_sub -v -t 'CT6'