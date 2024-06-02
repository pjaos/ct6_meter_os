import socket
import json
from datetime import datetime

IF_ADDRESS_ON_THIS_MCHINE = '192.168.0.10'

# Set up a TCP/IP server
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
 
# Bind the socket to server address and port 
server_address = (IF_ADDRESS_ON_THIS_MCHINE, 20000)
print(f"Bound to {server_address}")
tcp_socket.bind(server_address)
 
# Listen on the TCP port
tcp_socket.listen(1)
 
while True:
    print("Waiting for connection")
    connection, client = tcp_socket.accept()
 
    try:
        print("Connected to client IP: {}".format(client))
        
        jsonBuf = ""
        while True:
            now = datetime.now()
            data = connection.recv(256)
            nowStr = now.strftime("%m/%d/%Y, %H:%M:%S")
            rxStr = data.decode()
            try:
                print(f"\n{nowStr}: {rxStr}\n")
            except:
                pass
                
            if not data:
                break
 
    finally:
        connection.close()