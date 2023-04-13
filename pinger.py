from socket import *
import os
import sys
import struct
import time
import select
import binascii
import pandas as pd
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

ICMP_ECHO_REQUEST = 8


def checksum(string):
    csum = 0
    countTo = (len(string) // 2) * 2
    count = 0

    while count < countTo:
        thisVal = (string[count + 1]) * 256 + (string[count])
        csum += thisVal
        csum &= 0xffffffff
        count += 2

    if countTo < len(string):
        csum += (string[len(string) - 1])
        csum &= 0xffffffff

    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer


def receiveOnePing(mySocket, ID, timeout, destAddr):
    timeLeft = timeout

    while True:
        startedSelect = time.time()
        # Handles a timeout case
        whatReady = select.select([mySocket], [], [], timeLeft)
        elapsedSelect = (time.time() - startedSelect)

        # Handles a timeout case
        if whatReady[0] == []:  # Timeout
            print("Timeout")
            return None, None, None

        timeReceived = time.time()
        recPacket, addr = mySocket.recvfrom(1024)

        # Compare the ID returned with the ID we sent
        icmpHeader = recPacket[20:28]
        icmpType, code, checksum, packetID, sequence = struct.unpack(
            "bbHHh", icmpHeader
        )

        if icmpType == 0 and packetID == ID:
            bytes = len(recPacket) - 28
            rtt = (timeReceived - time.time()) * 1000
            ttl = struct.unpack("B", recPacket[8:9])[0]

            print(f"{bytes} bytes from {addr[0]}: icmp_seq={sequence} ttl={ttl} time={rtt} ms")

            return bytes, rtt, ttl

        timeLeft = timeLeft - elapsedSelect
        if timeLeft <= 0:
            print("Timeout")
            return None, None, None



def sendOnePing(mySocket, destAddr, ID):
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)

    myChecksum = 0
    # Make a dummy header with a 0 checksum
    # struct -- Interpret strings as packed binary data
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    data = struct.pack("d", time.time())
    # Calculate the checksum on the data and the dummy header.
    myChecksum = checksum(header + data)

    # Get the right checksum, and put in the header

    if sys.platform == 'darwin':
        # Convert 16-bit integers from host to network  byte order
        myChecksum = htons(myChecksum) & 0xffff
    else:
        myChecksum = htons(myChecksum)

    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data

    mySocket.sendto(packet, (destAddr, 1))  # AF_INET address must be tuple, not str

    # Both LISTS and TUPLES consist of a number of objects
    # which can be referenced by their position number within the object.


def doOnePing(destAddr, timeout):
    icmp = getprotobyname("icmp")

    # SOCK_RAW is a powerful socket type. For more details:   https://sock-raw.org/papers/sock_raw
    mySocket = socket(AF_INET, SOCK_RAW, icmp)

    myID = os.getpid() & 0xFFFF  # Return the current process i
    delay, statistics = sendOnePing(mySocket, destAddr, myID)
    delay, statistics = receiveOnePing(mySocket, myID, timeout, destAddr)
    mySocket.close()
    return delay, statistics


def ping(host, timeout=1):
    # timeout=1 means: If one second goes by without a reply from the server,
    # the client assumes that either the client's ping or the server's pong is lost
    dest = gethostbyname(host)
    print("\nPinging " + dest + " using Python:")
    print("")

    response = pd.DataFrame(columns=['bytes', 'rtt', 'ttl'])

    delays = []  # Create an empty list to store the delays of each ping

    for i in range(0, 4):
        delay, statistics = doOnePing(dest, timeout)
        response = response.append({'bytes': len(statistics), 'rtt': delay, 'ttl': statistics[0]}, ignore_index=True)
        delays.append(delay)  # Append the delay of each ping to the list
        print(delay)
        time.sleep(1)

    packet_lost = 0
    packet_recv = 0
    # fill in start
    for index, row in response.iterrows():
        if row['bytes'] == 0:
            packet_lost += 1
        else:
            packet_recv += 1
    # fill in end
    # Calculate the statistics of the delays
    packet_min = min(delays)
    packet_avg = sum(delays) / len(delays)
    packet_max = max(delays)
    stdev = np.std(delays)

    vars = pd.DataFrame(columns=['min', 'avg', 'max', 'stddev'])
    vars = vars.append({'min': str(round(packet_min, 2)), 'avg': str(round(packet_avg, 2)),
                        'max': str(round(packet_max, 2)), 'stddev': str(round(stdev, 2))},
                       ignore_index=True)
    print(vars)
    return vars


if __name__ == '__main__':
    ping("google.com")



