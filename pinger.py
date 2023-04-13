from socket import *
import os
import sys
import struct
import time
import select
import binascii
import pandas as pd
import warnings
import statistics

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

    while 1:
        startedSelect = time.time()
        whatReady = select.select([mySocket], [], [], timeLeft)
        howLongInSelect = (time.time() - startedSelect)
        if whatReady[0] == []:  # Timeout
            return "Request timed out."

        timeReceived = time.time()
        recPacket, addr = mySocket.recvfrom(1024)

        # Fetch the ICMP header from the IP packet
        icmpHeader = recPacket[20:28]

        # Unpack ICMP header
        type, code, checksum, packetID, sequence = struct.unpack(
            "bbHHh", icmpHeader
        )

        if packetID == ID:
            bytes = len(recPacket) - 28
            rtt = (timeReceived - time.time()) * 1000
            ttl = ord(struct.unpack("c", recPacket[8:9])[0])
            return bytes, rtt, ttl

        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return "Request timed out."


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
    sendOnePing(mySocket, destAddr, myID)
    delay = receiveOnePing(mySocket, myID, timeout, destAddr)
    mySocket.close()
    return delay


def ping(host, timeout=1):
    # timeout=1 means: If one second goes by without a reply from the server,
    # the client assumes that either the client's ping or the server's pong is lost
    dest = gethostbyname(host)
    print("\nPinging " + dest + " using Python:")
    print("")

    response = pd.DataFrame(columns=['bytes', 'rtt', 'ttl'])  # This creates an empty dataframe with 3 headers with the column specific names declared
    delays = []  # Add an empty list to collect delays of each ping

    # Send ping requests to a server separated by approximately one second
    for i in range(0, 4):  # Four pings will be sent (loop runs for i=0, 1, 2, 3)
        delay, statistics = doOnePing(dest, timeout)  # what is stored into delay and statistics?
        delays.append(delay)  # Append the delay to the list of delays
        response = response.append({'bytes': statistics[0], 'rtt': delay, 'ttl': statistics[1]}, ignore_index=True)  # Add the statistics to the response DataFrame
        print(delay)
        time.sleep(1)  # wait one second

    packet_lost = 0
    packet_recv = 0
    # Check if each packet was received or lost
    for index, row in response.iterrows():
        if row['rtt'] == '*':  # Check if the rtt value is '*'
            packet_lost += 1
        else:
            packet_recv += 1

    # Calculate packet statistics
    packet_min = response['rtt'].min()
    packet_avg = response['rtt'].mean()
    packet_max = response['rtt'].max()
    packet_stdev = response['rtt'].std()

    # Create a DataFrame with packet statistics
    vars = pd.DataFrame({'min': [packet_min], 'avg': [packet_avg], 'max': [packet_max], 'stddev': [packet_stdev]})

    print(vars)  # make sure your vars data you are returning resembles acceptance criteria
    return vars


if __name__ == '__main__':
    ping("google.com")

