Introduction
============

.. image:: https://readthedocs.org/projects/adafruit-circuitpython-bluefruitspi/badge/?version=latest
    :target: https://docs.circuitpython.org/projects/bluefruitspi/en/latest/
    :alt: Documentation Status

.. image:: https://img.shields.io/discord/327254708534116352.svg
    :target: https://adafru.it/discord
    :alt: Discord

.. image:: https://github.com/adafruit/Adafruit_CircuitPython_BluefruitSPI/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_CircuitPython_BluefruitSPI/actions/
    :alt: Build Status

Helper class to work with the Adafruit Bluefruit LE SPI Friend.

Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_
* `Bus Device <https://github.com/adafruit/Adafruit_CircuitPython_BusDevice>`_

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://github.com/adafruit/Adafruit_CircuitPython_Bundle>`_.

Installing from PyPI
====================

On supported GNU/Linux systems like the Raspberry Pi, you can install the driver locally `from
PyPI <https://pypi.org/project/adafruit-circuitpython-bluefruitspi/>`_. To install for current user:

.. code-block:: shell

    pip3 install adafruit-circuitpython-bluefruitspi

To install system-wide (this may be required in some cases):

.. code-block:: shell

    sudo pip3 install adafruit-circuitpython-bluefruitspi

To install in a virtual environment in your current project:

.. code-block:: shell

    mkdir project-name && cd project-name
    python3 -m venv .env
    source .env/bin/activate
    pip3 install adafruit-circuitpython-bluefruitspi

Usage Example
=============

.. code-block:: python

    # A simple echo test for the Feather M0 Bluefruit
    # Sets the name, then echo's all RX'd data with a reversed packet

    import time
    import busio
    import board
    from digitalio import DigitalInOut
    from adafruit_bluefruitspi import BluefruitSPI

    spi_bus = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    cs = DigitalInOut(board.D8)
    irq = DigitalInOut(board.D7)
    rst = DigitalInOut(board.D4)
    bluefruit = BluefruitSPI(spi_bus, cs, irq, rst, debug=False)

    # Initialize the device and perform a factory reset
    print("Initializing the Bluefruit LE SPI Friend module")
    bluefruit.init()
    bluefruit.command_check_OK(b'AT+FACTORYRESET', delay=1)

    # Print the response to 'ATI' (info request) as a string
    print(str(bluefruit.command_check_OK(b'ATI'), 'utf-8'))

    # Change advertised name
    bluefruit.command_check_OK(b'AT+GAPDEVNAME=BlinkaBLE')

    while True:
        print("Waiting for a connection to Bluefruit LE Connect ...")
        # Wait for a connection ...
        dotcount = 0
        while not bluefruit.connected:
            print(".", end="")
            dotcount = (dotcount + 1) % 80
            if dotcount == 79:
                print("")
            time.sleep(0.5)

        # Once connected, check for incoming BLE UART data
        print("\n *Connected!*")
        connection_timestamp = time.monotonic()
        while True:
            # Check our connection status every 3 seconds
            if time.monotonic() - connection_timestamp > 3:
                connection_timestamp = time.monotonic()
                if not bluefruit.connected:
                    break

            # OK we're still connected, see if we have any data waiting
            resp = bluefruit.uart_rx()
            if not resp:
                continue  # nothin'
            print("Read %d bytes: %s" % (len(resp), resp))
            # Now write it!
            print("Writing reverse...")
            send = []
            for i in range(len(resp), 0, -1):
                send.append(resp[i-1])
            print(bytes(send))
            bluefruit.uart_tx(bytes(send))

        print("Connection lost.")

Documentation
=============

API documentation for this library can be found on `Read the Docs <https://docs.circuitpython.org/projects/bluefruitspi/en/latest/>`_.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_BluefruitSPI/blob/main/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.

Documentation
=============

For information on building library documentation, please check out `this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.
