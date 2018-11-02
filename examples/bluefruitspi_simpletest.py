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

def command_check_OK(string, delay=0.0):
    ret = send_command(string)
    time.sleep(delay)
    if not ret or not ret[-4:]:
        raise RuntimeError("Not OK")
    if ret[-4:] != b'OK\r\n':
        raise RuntimeError("Not OK")
    if ret[:-4]:
        return str(ret[:-4], 'utf-8')

# Initialize the device
bluefruit.init()
print(command_check_OK("AT+FACTORYRESET", 1.0))
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
        command_check_OK("AT+BLEUARTTX=*")
        resp = command_check_OK("AT+BLEUARTRX")
        if resp:
            print(resp)
        # Check connection status with a 1s delay
        connected = int(command_check_OK("AT+GAPGETCONN", 0.5)) == 1
    print("Connection lost.")
