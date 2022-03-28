# SPDX-FileCopyrightText: 2018 Kevin Townsend for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_bluefruitspi`
====================================================

Helper class to work with the Adafruit Bluefruit LE SPI friend breakout.

* Author(s): Kevin Townsend

Implementation Notes
--------------------

**Hardware:**

"* `Adafruit Bluefruit LE SPI Friend <https://www.adafruit.com/product/2633>`_"

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_BluefruitSPI.git"

import time
import struct

try:
    import binascii as ba
except ImportError:
    import adafruit_binascii as ba
from digitalio import Direction, Pull
from adafruit_bus_device.spi_device import SPIDevice
from micropython import const

_MSG_COMMAND = const(0x10)  # Command message
_MSG_RESPONSE = const(0x20)  # Response message
_MSG_ALERT = const(0x40)  # Alert message
_MSG_ERROR = const(0x80)  # Error message

_SDEP_INITIALIZE = const(0xBEEF)  # Resets the Bluefruit device
_SDEP_ATCOMMAND = const(0x0A00)  # AT command wrapper
_SDEP_BLEUART_TX = const(0x0A01)  # BLE UART transmit data
_SDEP_BLEUART_RX = const(0x0A02)  # BLE UART read data

_ARG_STRING = const(0x0100)  # String data type
_ARG_BYTEARRAY = const(0x0200)  # Byte array data type
_ARG_INT32 = const(0x0300)  # Signed 32-bit integer data type
_ARG_UINT32 = const(0x0400)  # Unsigned 32-bit integer data type
_ARG_INT16 = const(0x0500)  # Signed 16-bit integer data type
_ARG_UINT16 = const(0x0600)  # Unsigned 16-bit integer data type
_ARG_INT8 = const(0x0700)  # Signed 8-bit integer data type
_ARG_UINT8 = const(0x0800)  # Unsigned 8-bit integer data type

_ERROR_INVALIDMSGTYPE = const(0x8021)  # SDEP: Unexpected SDEP MsgType
_ERROR_INVALIDCMDID = const(0x8022)  # SDEP: Unknown command ID
_ERROR_INVALIDPAYLOAD = const(0x8023)  # SDEP: Payload problem
_ERROR_INVALIDLEN = const(0x8024)  # SDEP: Indicated len too large
_ERROR_INVALIDINPUT = const(0x8060)  # AT: Invalid data
_ERROR_UNKNOWNCMD = const(0x8061)  # AT: Unknown command name
_ERROR_INVALIDPARAM = const(0x8062)  # AT: Invalid param value
_ERROR_UNSUPPORTED = const(0x8063)  # AT: Unsupported command

# For the Bluefruit Connect packets
_PACKET_BUTTON_LEN = const(5)
_PACKET_COLOR_LEN = const(6)

_KEY_CODE_CMD = "AT+BLEKEYBOARDCODE=00-00-00-00-00-00-00-00\n"

# TODO: replace with collections.deque in CircuitPython 7
class FIFOBuffer:
    """FIFO buffer vaguely based on collections.deque.

    Uses a tuple internally to allow for O(1) enqueue and dequeue
    """

    def __init__(self, maxlen=20):
        self.maxlen = maxlen
        self._buf = (None,) * self.maxlen
        self._end_idx = 0
        self._front_idx = 0

    def enqueue(self, data):
        """Put an item at the end of the FIFO queue"""
        if self._buf[self._end_idx] is not None:
            raise IndexError("FIFOBuffer full")
        self._buf[self._end_idx] = data
        self._end_idx += 1
        if self._end_idx >= self.maxlen:
            self._end_idx = 0

    def dequeue(self):
        """Pop an item from the front of the FIFO queue"""
        data = self._buf[self._front_idx]
        if data is None:
            return None
        self._buf[self._front_idx] = None
        self._front_idx += 1
        if self._front_idx >= self.maxlen:
            self._front_idx = 0
        return data


class BluefruitSPI:
    """Helper for the Bluefruit LE SPI Friend"""

    def __init__(
        self, spi, cs, irq, reset, debug=False, fifo_len=20
    ):  # pylint: disable=too-many-arguments
        self._irq = irq
        self._buf_tx = bytearray(20)
        self._buf_rx = bytearray(20)
        self._keycode_template = [
            bytearray(20),
            bytearray(20),
            bytearray(20),
            bytearray(20),
        ]
        self._fifo_buffer = FIFOBuffer(maxlen=fifo_len)
        self._init_keycode_template()
        self._debug = debug

        # a cache of data, used for packet parsing
        self._buffer = []

        # Reset
        reset.direction = Direction.OUTPUT
        reset.value = False
        time.sleep(0.01)
        reset.value = True
        time.sleep(0.5)

        # CS is an active low output
        cs.direction = Direction.OUTPUT
        cs.value = True

        # irq line is active high input, so set a pulldown as a precaution
        self._irq.direction = Direction.INPUT
        self._irq.pull = Pull.DOWN

        self._spi_device = SPIDevice(spi, cs, baudrate=4000000, phase=0, polarity=0)

    def _init_keycode_template(self):
        """Prebuild SDEP packets for AT+BLEKEYBOARDCODE command"""
        self._create_sdep_raw(
            self._keycode_template[0], _KEY_CODE_CMD[:16], True  # AT+BLEKEYBOARDCO
        )
        self._create_sdep_raw(
            self._keycode_template[1], _KEY_CODE_CMD[16:32], True  #  DE=00-00-00-00-0
        )
        self._create_sdep_raw(
            self._keycode_template[2], _KEY_CODE_CMD[32:48], False  #  0-00-00-00\n
        )

    def send_keyboard_code(self, evt):
        """
        Put an AT+BLEKEYBOARDCODE command into the FIFO buffer.
        Call pop_keyboard_code() to send a single packet to the Bluefruit.

        :param evt: bytearray(8) representing keyboard code to send
        """
        evt = ba.hexlify(evt)
        self._keycode_template[1][7:9] = evt[0:2]
        # self._keycode_template[1][10:12] = evt[2:4]  # Should always be 0
        self._keycode_template[1][13:15] = evt[4:6]
        self._keycode_template[1][16:18] = evt[6:8]
        self._keycode_template[1][19] = evt[8]
        self._keycode_template[2][4] = evt[9]
        self._keycode_template[2][6:8] = evt[10:12]
        self._keycode_template[2][9:11] = evt[12:14]
        self._keycode_template[2][12:14] = evt[14:16]
        for k in self._keycode_template:
            self._fifo_buffer.enqueue(k)

    def pop_keyboard_code_queue(self):
        """Send an SDEP packet from the FIFO buffer to the Bluefruit"""
        data = self._fifo_buffer.dequeue()
        if data is not None:
            with self._spi_device as spi:
                spi.write(data, end=24)

    @staticmethod
    def _create_sdep_raw(dest, payload, more):
        """
        Create an SDEP packet

        :param dest: bytearray(20) to place SDEP packet in
        :param payload: iterable with length <= 16 containing the payload data
        :param more: True to set the more bit, False otherwise
        """
        _more = 0x80 if more else 0
        plen = len(payload)
        struct.pack_into(
            "<BHB16s",
            dest,
            0,
            _MSG_COMMAND,
            _SDEP_ATCOMMAND,
            plen | _more,
            payload,
        )

    def _cmd(self, cmd):  # pylint: disable=too-many-branches
        """
        Executes the supplied AT command, which must be terminated with
        a new-line character.
        Returns msgtype, rspid, rsp, which are 8-bit int, 16-bit int and a
        bytearray.

        :param cmd: The new-line terminated AT command to execute.
        """
        # Make sure we stay within the 255 byte limit
        if len(cmd) > 127:
            if self._debug:
                print("ERROR: Command too long.")
            raise ValueError("Command too long.")

        more = True
        pos = 0
        while len(cmd) - pos:
            # Construct the SDEP packet
            if len(cmd) - pos <= 16:
                # Last or sole packet
                more = False
            plen = len(cmd) - pos
            plen = min(plen, 16)
            self._create_sdep_raw(self._buf_tx, cmd[pos : pos + plen], more=more)
            if self._debug:
                print("Writing: ", [hex(b) for b in self._buf_tx])
            else:
                time.sleep(0.05)

            # Update the position if there is data remaining
            pos += plen

            # Send out the SPI bus
            with self._spi_device as spi:
                spi.write(self._buf_tx, end=len(cmd) + 4)  # pylint: disable=no-member

        # Wait up to 200ms for a response
        timeout = 0.2
        while timeout > 0 and not self._irq.value:
            time.sleep(0.01)
            timeout -= 0.01
        if timeout <= 0:
            if self._debug:
                print("ERROR: Timed out waiting for a response.")
            raise RuntimeError("Timed out waiting for a response.")

        # Retrieve the response message
        msgtype = 0
        rspid = 0
        rsplen = 0
        rsp = b""
        while self._irq.value is True:
            # Read the current response packet
            time.sleep(0.01)
            with self._spi_device as spi:
                spi.readinto(self._buf_rx)

            # Read the message envelope and contents
            msgtype, rspid, rsplen = struct.unpack(">BHB", self._buf_rx[0:4])
            if rsplen >= 16:
                rsp += self._buf_rx[4:20]
            else:
                rsp += self._buf_rx[4 : rsplen + 4]
            if self._debug:
                print("Reading: ", [hex(b) for b in self._buf_rx])
            else:
                time.sleep(0.05)
        # Clean up the response buffer
        if self._debug:
            print(rsp)

        return msgtype, rspid, rsp

    def init(self):
        """
        Sends the SDEP initialize command, which causes the board to reset.
        This command should complete in under 1s.
        """
        # Construct the SDEP packet
        struct.pack_into("<BHB", self._buf_tx, 0, _MSG_COMMAND, _SDEP_INITIALIZE, 0)
        if self._debug:
            print("Writing: ", [hex(b) for b in self._buf_tx])

        # Send out the SPI bus
        with self._spi_device as spi:
            spi.write(self._buf_tx, end=4)  # pylint: disable=no-member

        # Wait 1 second for the command to complete.
        time.sleep(1)

    @property
    def connected(self):
        """Whether the Bluefruit module is connected to the central"""
        return int(self.command_check_OK(b"AT+GAPGETCONN")) == 1

    def uart_tx(self, data):
        """
        Sends the specific bytestring out over BLE UART.

        :param data: The bytestring to send.
        """
        return self._cmd(b"AT+BLEUARTTX=" + data + b"\r\n")

    def uart_rx(self):
        """
        Reads byte data from the BLE UART FIFO.
        """
        data = self.command_check_OK(b"AT+BLEUARTRX")
        if data:
            # remove \r\n from ending
            return data[:-2]
        return None

    def command(self, string):
        """Send a command and check response code"""
        try:
            msgtype, msgid, rsp = self._cmd(string + "\n")
            if msgtype == _MSG_ERROR:
                raise RuntimeError("Error (id:{0})".format(hex(msgid)))
            if msgtype == _MSG_RESPONSE:
                return rsp
            raise RuntimeError("Unknown response (id:{0})".format(hex(msgid)))
        except RuntimeError as error:
            raise RuntimeError("AT command failure: " + repr(error)) from error

    def command_check_OK(self, command, delay=0.0):  # pylint: disable=invalid-name
        """Send a fully formed bytestring AT command, and check
        whether we got an 'OK' back. Returns payload bytes if there is any"""
        ret = self.command(command)
        time.sleep(delay)
        if not ret or not ret[-4:]:
            raise RuntimeError("Not OK")
        if ret[-4:] != b"OK\r\n":
            raise RuntimeError("Not OK")
        if ret[:-4]:
            return ret[:-4]
        return None

    def read_packet(self):  # pylint: disable=too-many-return-statements
        """
        Will read a Bluefruit Connect packet and return it in a parsed format.
        Currently supports Button and Color packets only
        """
        data = self.uart_rx()
        if not data:
            return None
        # convert to an array of character bytes
        self._buffer += [chr(b) for b in data]
        # Find beginning of new packet, starts with a '!'
        while self._buffer and self._buffer[0] != "!":
            self._buffer.pop(0)
        # we need at least 2 bytes in the buffer
        if len(self._buffer) < 2:
            return None

        # Packet beginning found
        if self._buffer[1] == "B":
            plen = _PACKET_BUTTON_LEN
        elif self._buffer[1] == "C":
            plen = _PACKET_COLOR_LEN
        else:
            # unknown packet type
            self._buffer.pop(0)
            return None

        # split packet off of buffer cache
        packet = self._buffer[0:plen]

        self._buffer = self._buffer[plen:]  # remove packet from buffer
        if sum([ord(x) for x in packet]) % 256 != 255:  # check sum
            return None

        # OK packet's good!
        if packet[1] == "B":  # buttons have 2 int args to parse
            # button number & True/False press
            return ("B", int(packet[2]), packet[3] == "1")
        if packet[1] == "C":  # colorpick has 3 int args to parse
            # red, green and blue
            return ("C", ord(packet[2]), ord(packet[3]), ord(packet[4]))
        # We don't nicely parse this yet
        return packet[1:-1]
