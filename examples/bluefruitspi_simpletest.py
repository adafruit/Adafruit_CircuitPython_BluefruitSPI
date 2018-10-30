import busio
import digitalio
import board

from adafruit_bluefruitspi import BluefruitSPI, MsgType

spi_bus = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.A5)
irq = digitalio.DigitalInOut(board.A4)
bluefruit = BluefruitSPI(spi_bus, cs, irq, debug=True)

# Send the ATI command
try:
    msgtype, msgid, rsp = bluefruit.cmd("ATI\n")
    if msgtype == MsgType.ERROR:
        print("Error (id:{0})".format(hex(msgid)))
    if msgtype == MsgType.RESPONSE:
        print("Response:")
        print(rsp)
except RuntimeError as error:
    print("AT command failure: " + repr(error))
    exit()
