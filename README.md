# Bluetooth construction toys BLE examples

This repository contains examples how to connect a
Raspberry Pi or any Linux PC with the fischertechnik
bluetooth controllers or the Lego Wedo 2.0, Boost or later
controllers.

Part of this was published in
[c't 18/2017 S. 144ff](https://www.heise.de/ct/ausgabe/2017-18-Spielzeug-Roboter-mit-dem-Raspberry-Pi-steuern-3798159.html).

## Shell scripts

The shell scripts don't require any further installations. They
run on any Raspbian Jessie standard installation and later or
any Debian or Ubuntu PC.

- [`batterie.sh`](batterie.sh) is a simple shell script that
  searches for BLE devicesm connects to them and tries to
  read the battery level.

- [`ft_bt_smart_led_blink.sh`](ft_bt_smart_led_blink.sh) is a bash
  shell script which searches for the fischertechnik BT-Smart-Controller,
  connects to it and toggles between the orange and blue interal
  LEDs of that controller. Root permissions are required for the
  automatic device detection. If a bluetooth MAC address is provided
  on the command line then regular permissions are sufficient.

- [`ft_bt_remote_led_blink.sh`](ft_bt_remote_led_blink.sh) is a bash
  shell script which searches for the fischertechnik BT-Control-Receiver,
  connects to it and toggles between the orange and blue interal
  LEDs of that controller. Root permissions are required for the
  automatic device detection. If a bluetooth MAC address is provided
  on the command line then regular permissions are sufficient.

- [`lego_wedo_led_blink.sh`](lego_wedo_led_blink.sh) toggles the
  LED of the WeDo2.0 Hub between orange and blue. If the script
  is being invoked without parameters it will automatically search
  for matching devices. This requires root permissions. If a bluetooth
  MAC address is given as a parameter then it will be used instead
  and no root permissions are required.

- [`lego_boost_led_blink.sh`](lego_boost_led_blink.sh) toggles the
  LED of the Lego Boost Hub between orange and blue. If the script
  is being invoked without parameters it will automatically search
  for matching devices. This requires root permissions. If a bluetooth
  MAC address is given as a parameter then it will be used instead
  and no root permissions are required.

## Python scripts

The pythons scripts need additional packages which are usually
not installed by default. The python gatt package is required
and can e.g. be installed like this:

```
$ pip3 search gatt
gatt (0.2.7)               - Bluetooth GATT SDK for Python
jumper-ble-logger (0.1.3)  - Jumper GATT proxy for logging BLE traffic
pygatt (4.0.3)             - Python Bluetooth LE (Low Energy) and GATT Library
vernierpygatt (3.2.0)      - Python Bluetooth LE (Low Energy) and GATT Library
$ pip3 install gatt
...

```

On older Linux version the script `[python-gatt-install.sh](python-gatt-install.sh)`
may help setting up bluetooth/python/gatt.

- [`ft_karussell.py`](ft_karussell.py) controls the caroussell
  model from the BT-Smart-Beginner-Set. On button press the
  caroussell starts, slowly speeds up, runs for 30 seconds
  and finally slows down.

- [`lego_wed_dino.py`](lego_wedo_dino.py) controls the dinosaur
  from the Lego WeDo 2.0 kit. The motions sensor is being evaluated
  to colorize the LED. Additionally if something is detected right
  in front of the sensor then the motor is being run.

- [`ft_rc_racer.py`](ft_rc_racer.py) controls the car from the
  fischertechnik BT-Racing-Set. The car speeds up 2 seconds,
  turns 2 seconds and slows down 2 seconds.

- [`lego_boost_color_echo.py`](lego_boost_color_echo.py) reads the
  value of the color sensor and "mirrors" the color onto the
  boosts internal LED.

- [`lego_hub_monitor.py`](lego_hub_monitor.py) processes all known
  signals and events of the Lego Boost, the Lego Hub NO.4, the
  Technic Hub or later.

  All known peripherals are supported incl. the sensors from
  the WeDo 2.0 set.
