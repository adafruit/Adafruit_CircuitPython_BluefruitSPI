# The MIT License (MIT)
#
# Copyright (c) 2018 Kevin Townsend for Adafruit_Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
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

# imports

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_BluefruitSPI.git"

import time
import digitalio
from adafruit_bus_device.spi_device import SPIDevice
from micropython import const
try:
    from struct import pack_into, unpack
except ImportError:
    from ustruct import pack_into, unpack


class MsgType:  #pylint: disable=too-few-public-methods,bad-whitespace
    """An enum-like class representing the possible message types.
    Possible values are:
    - ``MsgType.COMMAND``
    - ``MsgType.RESPONSE``
    - ``MsgType.ALERT``
    - ``MsgType.ERROR``
    """
    COMMAND   = const(0x10)  # Command message
    RESPONSE  = const(0x20)  # Response message
    ALERT     = const(0x40)  # Alert message
    ERROR     = const(0x80)  # Error message


class SDEPCommand:  #pylint: disable=too-few-public-methods,bad-whitespace
    """An enum-like class representing the possible SDEP commands.
    Possible values are:
    - ``SDEPCommand.INITIALIZE``
    - ``SDEPCommand.ATCOMMAND``
    - ``SDEPCommand.BLEUART_TX``
    - ``SDEPCommand.BLEUART_RX``
    """
    INITIALIZE = const(0xBEEF) # Resets the Bluefruit device
    ATCOMMAND  = const(0x0A00) # AT command wrapper
    BLEUART_TX = const(0x0A01) # BLE UART transmit data
    BLEUART_RX = const(0x0A02) # BLE UART read data


class ArgType:  #pylint: disable=too-few-public-methods,bad-whitespace
    """An enum-like class representing the possible argument types.
    Possible values are
    - ``ArgType.STRING``
    - ``ArgType.BYTEARRAY``
    - ``ArgType.INT32``
    - ``ArgType.UINT32``
    - ``ArgType.INT16``
    - ``ArgType.UINT16``
    - ``ArgType.INT8``
    - ``ArgType.UINT8``
    """
    STRING    = const(0x0100) # String data type
    BYTEARRAY = const(0x0200) # Byte array data type
    INT32     = const(0x0300) # Signed 32-bit integer data type
    UINT32    = const(0x0400) # Unsigned 32-bit integer data type
    INT16     = const(0x0500) # Signed 16-bit integer data type
    UINT16    = const(0x0600) # Unsigned 16-bit integer data type
    INT8      = const(0x0700) # Signed 8-bit integer data type
    UINT8     = const(0x0800) # Unsigned 8-bit integer data type


class ErrorCode:  #pylint: disable=too-few-public-methods,bad-whitespace
    """An enum-like class representing possible error codes.
    Possible values are
    - ``ErrorCode.``
    """
    INVALIDMSGTYPE = const(0x8021) # SDEP: Unexpected SDEP MsgType
    INVALIDCMDID   = const(0x8022) # SDEP: Unknown command ID
    INVALIDPAYLOAD = const(0x8023) # SDEP: Payload problem
    INVALIDLEN     = const(0x8024) # SDEP: Indicated len too large
    INVALIDINPUT   = const(0x8060) # AT: Invalid data
    UNKNOWNCMD     = const(0x8061) # AT: Unknown command name
    INVALIDPARAM   = const(0x8062) # AT: Invalid param value
    UNSUPPORTED    = const(0x8063) # AT: Unsupported command


class BluefruitSPI:
    """Helper for the Bluefruit LE SPI Friend"""

    def __init__(self, spi, cs, irq, debug=False):
        self._cs = cs
        self._irq = irq
        self._spi = spi
        self._ble = SPIDevice(self._spi, self._cs)
        self._buf_tx = bytearray(20)
        self._buf_rx = bytearray(20)
        self._debug = debug

        # CS is an active low output, so set pullup
        self._cs.switch_to_output(value=True,
                                  drive_mode=digitalio.DriveMode.PUSH_PULL)

        # irq line is active high input, so set a pulldown as a precaution
        self._irq.switch_to_input(pull=digitalio.Pull.DOWN)

        # Check out the SPI bus
        while not self._spi.try_lock():
            pass

        # Configure SPI for 4MHz
        self._spi.configure(baudrate=4000000, phase=0, polarity=0)

        self._spi.unlock()

    def cmd(self, cmd):
        """
        Executes the supplied AT command, which must be terminated with
        a new-line (\n) character.
        Returns msgtype, rspid, rsp, which are 8-bit int, 16-bit int and a
        bytearray.
        :param cmd: The new-line (\n) terminated AT command to execute.
        """
        # Make sure we stay within the 20 byte limit
        if len(cmd) > 16:
            # TODO: Split command into multiple packets
            if self._debug:
                print("ERROR: Command too long.")
            raise ValueError('Command too long.')

        # Check out the SPI bus
        while not self._spi.try_lock():
            pass

        # Send the packet across the SPI bus
        pack_into("<BHB16s", self._buf_tx, 0,
                  MsgType.COMMAND, SDEPCommand.ATCOMMAND,
                  len(cmd), cmd)
        if self._debug:
            print("Writing: ", [hex(b) for b in self._buf_tx])
        self._cs.value = False
        self._spi.write(self._buf_tx, end=len(cmd) + 4)
        self._cs.value = True

        # Wait up to 200ms for a response
        timeout = 0.2
        while timeout > 0.0 and self._irq is False:
            time.sleep(0.005)
            timeout -= 0.005
        if timeout <= 0:
            if self._debug:
                print("ERROR: Timed out waiting for a response.")
            raise RuntimeError('Timed out waiting for a response.')

        # Retrieve the response message
        msgtype = 0
        rspid = 0
        rsplen = 0
        rsp = b""
        while self._irq.value is True:
            # Read the current response packet
            time.sleep(0.01)
            self._cs.value = False
            self._spi.readinto(self._buf_rx)
            self._cs.value = True

            # Read the message envelope and contents
            msgtype, rspid, rsplen = unpack('>BHB', self._buf_rx)
            if rsplen >= 16:
                rsp += self._buf_rx[4:20]
            else:
                rsp += self._buf_rx[4:rsplen+4]
            if self._debug:
                print("Reading: ", [hex(b) for b in self._buf_rx])

        # Release the SPI bus
        self._spi.unlock()

        # Clean up the response buffer
        if self._debug:
            print(rsp)

        return msgtype, rspid, rsp
