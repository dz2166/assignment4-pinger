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

        # Structure of the packet header: Type (8), Code (8), Checksum (16), ID (16), Sequence (16)
        icmpType, code, checksum, packetID, sequence = struct.unpack("bbHHh", icmpHeader)

        if icmpType == 0 and packetID == ID:
            byte_count = len(recPacket) - 28
            timeSent = struct.unpack("d", recPacket[28:28 + byte_count])[0]
            return timeReceived - timeSent

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

    # Calculate the checksum on the data and the dummy header
    myChecksum = checksum(header + data)

    # Get the right checksum and put in the header
    if sys.platform == 'darwin':
        myChecksum = htons(myChecksum) & 0xffff
    else:
        myChecksum = htons(myChecksum)

    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)

    packet = header + data
    sentTime = time.time()

    # send packet using socket
    mySocket.sendto(packet, (destAddr, 1))

    return sentTime



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

    response = pd.DataFrame(columns=['bytes', 'rtt', 'ttl'])

    delays = []  # Add this line to create an empty list to store delays

    for i in range(0, 4):
        delay, statistics = doOnePing(dest, timeout)  # delay and statistics are returned from doOnePing
        delays.append(delay)  # Add the delay value to the delays list
        response = response.append({'bytes': statistics[0], 'rtt': statistics[1], 'ttl': statistics[2]}, ignore_index=True)
        print(delay)
        time.sleep(1)

    packet_lost = 0
    packet_recv = 0

    for index, row in response.iterrows():
        if row['rtt'] == 0:  # Access the 'rtt' column of the response dataframe to determine if you received a packet or not
            packet_lost += 1
        else:
            packet_recv += 1

    vars = pd.DataFrame(columns=['min', 'avg', 'max', 'stddev'])
    vars = vars.append({'min': str(round(response['rtt'].min(), 2)), 'avg': str(round(response['rtt'].mean(), 2)),
                        'max': str(round(response['rtt'].max(), 2)), 'stddev': str(round(response['rtt'].std(), 2))},
                       ignore_index=True)
    print(vars)
    return vars


if __name__ == '__main__':
    ping("google.com")
