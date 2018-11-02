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

# Initialize the device and perform a factory reset
print("Initializing the Bluefruit LE SPI Friend module")
bluefruit.init()
bluefruit.command_check_OK("AT+FACTORYRESET", 1.0)
print(bluefruit.command_check_OK("ATI"))
bluefruit.command_check_OK("AT+GAPDEVNAME=ColorLamp")

while True:
    connected = False
    dotcount = 0
    print("Waiting for a connection to Bluefruit LE Connect ...")
    # Wait for a connection ...
    while not connected:
        connected = int(bluefruit.command_check_OK("AT+GAPGETCONN")) == 1
        dotcount += 1
        if dotcount == 79:
            print(".")
            dotcount = 0
        else:
            print(".", end="")
        time.sleep(0.5)
    # Once connected, check for incoming BLE UART data
    print("\nConnected!")
    while connected:
        #bluefruit.command_check_OK("AT+BLEUARTTX=0123456789")
        resp = bluefruit.command_check_OK("AT+BLEUARTRX")
        if resp:
            print(resp)
        # Check connection status followed by a 500ms delay
        connected = int(bluefruit.command_check_OK("AT+GAPGETCONN", 0.5)) == 1
    print("Connection lost.")
