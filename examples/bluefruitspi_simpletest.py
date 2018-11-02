import busio
from digitalio import DigitalInOut, Direction
import board
import time
from adafruit_bluefruitspi import BluefruitSPI, MsgType

spi_bus = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = DigitalInOut(board.D8)
irq = DigitalInOut(board.D7)
rst = DigitalInOut(board.D4)
bluefruit = BluefruitSPI(spi_bus, cs, irq, rst, debug=False)

def send_command(string):
    try:
        msgtype, msgid, rsp = bluefruit.cmd(string+"\n")
        if msgtype == MsgType.ERROR:
            raise RuntimeError("Error (id:{0})".format(hex(msgid)))
        if msgtype == MsgType.RESPONSE:
            return rsp
    except RuntimeError as error:
        raise RuntimeError("AT command failure: " + repr(error))

def command_check_OK(string):
    ret = send_command(string)
    if not ret or not ret[-4:]:
        raise RuntimeError("Not OK")
    if ret[-4:] != b'OK\r\n':
        raise RuntimeError("Not OK")
    if ret[:-4]:
        return str(ret[:-4], 'utf-8')

def uarttx(string):
    try:
        msgtype, msgid, rsp = bluefruit.uarttx(string)
        if msgtype == MsgType.ERROR:
            raise RuntimeError("Error (id:{0})".format(hex(msgid)))
    except RuntimeError as error:
        raise RuntimeError("UARTTX command failure: " + repr(error))
    if not rsp or not rsp[-4:]:
        raise RuntimeError("Not OK")
    if rsp[-4:] != b'OK\r\n':
        raise RuntimeError("Not OK")
    if rsp[:-4]:
        return str(ret[:-4], 'utf-8')

def uartrx():
    try:
        msgtype, msgid, rsp = bluefruit.uartrx()
        if msgtype == MsgType.ERROR:
            raise RuntimeError("Error (id:{0})".format(hex(msgid)))
    except RuntimeError as error:
        raise RuntimeError("UARTRX command failure: " + repr(error))
    if not rsp or not rsp[-4:]:
        raise RuntimeError("Not OK")
    if rsp[-4:] != b'OK\r\n':
        raise RuntimeError("Not OK")
    if rsp[:-4]:
        return str(ret[:-4], 'utf-8')

# Send the ATI command
print(command_check_OK("AT+FACTORYRESET"))
time.sleep(1)
print(command_check_OK("ATI"))
#print(command_check_OK("AT+GAPDEVNAME=ColorLamp"))

while True:
    # our main loop, if not connected, wait till we are
    connected = False
    dotcount = 0
    print("Waiting for a connection to Bluefruit LE Connect ...")
    while not connected:
        connected = int(command_check_OK("AT+GAPGETCONN")) == 1
        dotcount += 1
        if dotcount == 79:
            print(".")
            dotcount = 0
        else:
            print(".", end="")
        time.sleep(0.5)
    # Yay!
    print("\nConnected!")
    while connected:
        uarttx("1")
        connected = int(command_check_OK("AT+GAPGETCONN")) == 1
    print("Connection lost.")
