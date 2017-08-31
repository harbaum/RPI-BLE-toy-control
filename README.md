# BLE-Beispiele

Dieses Repository enthält Beispiele zur Bluetooth-LE-Kopplung von
Raspberry-Pi3 und fischertechnik-BT-Smart-Controller
bzw. Lego-WeDo-2.0-Hub wie in [c't 18/2017 S. 144ff](https://www.heise.de/ct/ausgabe/2017-18-Spielzeug-Roboter-mit-dem-Raspberry-Pi-steuern-3798159.html) beschrieben.

## Shell-Skripte

Für die Shell-Scripte sind keine weiteren Installationen nötig. Sie
laufen auf einem Raspbian-Jessie-Lite-Standardinstallation.

- [`batterie.sh`](batterie.sh) ist ein einfaches Bash-Shellskript, das
  permanent nach BLE-Geräten sucht und für jedes gefundene Gerät
  versucht, den Batterielevel auszulesen.

- [`ft_bt_smart_led_blink.sh`](ft_bt_smart_led_blink.sh) ist eim
  einfaches Bash-Shellskript, das die orange und blaue LED des
  BT-Smakrt-Controller im Wechsel blinken lässt. Wird das Skript ohne
  Parameter aufgerufen, dann suche es selbsttätig nach einem passenden
  Controller. Dafür sind root-Rechte nötig. Wird eine
  Bluetooth-Adresse als Parameter übergeben, dann wird diese genutzt
  und es sind keine Root-Rechte nötig.

- [`lego_wedo_led_blink.sh`](lego_wedo_led_blink.sh) blinkt mit der
  LED des WeDo-Hub im Wechsel orange und blau. Wird das Skript ohne
  Parameter aufgerufen, dann suche es selbsttätig nach einem passenden
  Controller. Dafür sind root-Rechte nötig. Wird eine
  Bluetooth-Adresse als Parameter übergeben, dann wird diese genutzt
  und es sind keine Root-Rechte nötig.

## Python-Skripte

Die Python-Skripte benötigen neben der bereits bei der
Standardinstalltion eines Raspbian-Jessie-Lite zusätzliche Pakete. Vor
allem wird für python-gatt eine neuere Version des BlueZ-Stacks
benötigt als bei jessie mitgeliefert.

Das Script `[python-gatt-install.sh](python-gatt-install.sh)` nimmt
die nötgen Änderungen automatisch vor.

- [`ft_karussell.py`](ft_karussell.py) kontrolliert das
  Karussell-Modell aus dem BT-Smart-Beginner-Set.  Auf Tastendruck
  startet das Karussel, erhöht langsam seine Geschwindigkeit, läuft
  für 30 Sekunden und bremst langsam wieder ab.

- [`lego_dino.py`](lego_dino.py) steuert das Dinosaurier-Modell aus
  dem Lego-WeDo-2.0-Baukasten. Der Bewegungssensor wird ausgewertet,
  um die LED am Dino zu färben. Befindet sich ein Hindernis direkt vor
  dem Dino, dann wird zusätzlich der Motor eingeschaltet.
