#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Verwendet python-gatt
# https://github.com/getsenic/gatt-python

# Einfaches Python-Beispiel, um per GATT auf den fischertechnik
# BT-Control-Receiver zuzugreifen.

import gatt, sys, struct
import threading

# GATT Device-Manager, um selektiv nach ft-Controllern zu suchen
class FtBtCtrlRcvDeviceManager(gatt.DeviceManager):
    def __init__(self, adapter_name='hci0'):
        super().__init__(adapter_name=adapter_name)
        self.connected_device = None

    def device_discovered(self, device):
        # teste auf LNT-OID und passenden Gerätenamen
        if((":".join(device.mac_address.split(':')[0:3]) == "10:45:f8") and
           (device.alias() == "BT Control Receiver")):
            self.stop_discovery()
            # verbinde, wenn noch nicht verbunden
            if not self.connected_device:
                print("Receiver gefunden, verbinde ...")
                self.connected_device = device
                self.connected_device.connect()

    def make_device(self, mac_address):
        return FtBtCtrlRcvDevice(mac_address=mac_address, manager=self)

    def run(self):
        try:
            super().run()
        except KeyboardInterrupt:
            print("CTRL-C erkannt")
            self.quit();
      
    def quit(self):
        super().stop()

class FtBtCtrlRcvDevice(gatt.Device):
    def __init__(self, mac_address, manager):
        super().__init__(mac_address, manager)
        self.m1 = None
        self.state = None
        self.write_in_progress = False
        self.outstanding_run = None
        self.outstanding_steer = None
        self.m1 = None
        self.servo = None
    
    def connect(self):
        super().connect()
        
    def connect_succeeded(self):
        super().connect_succeeded()
        print("Verbunden mit", self.mac_address)

    def connect_failed(self, error):
        super().connect_failed(error)
        print("Verbindung fehlgeschlagen:", str(error))
        self.manager.stop()

    def disconnect(self):
        if self.is_connected():
            super().disconnect()
            self.manager.stop()

    def disconnect_succeeded(self):
        super().disconnect_succeeded()
        print("getrennt")
        self.manager.stop()
        
    def services_resolved(self):
        super().services_resolved()

        for service in self.services:
            # Lese alle Charakteristiken aus, die wir benötigen
            for characteristic in service.characteristics:
                # Kanal-Service, setze LED auf orange, um anzuzeigen, dass wir
                # verbunden sind
                if (service.uuid == "2e582b3a-c5c5-11e6-9d9d-cec0c932ce01" and
                    characteristic.uuid == "2e582de2-c5c5-11e6-9d9d-cec0c932ce01"):
                    characteristic.name = "Channel"
                    characteristic.write_value( bytes([1]) )
                    self.write_in_progress = True

                # Charaketeristik von Ausgang M1 erfragen
                if (service.uuid == "2e58327e-c5c5-11e6-9d9d-cec0c932ce01" and
                    characteristic.uuid == "2e583378-c5c5-11e6-9d9d-cec0c932ce01"):
                    characteristic.name = "M1"
                    self.m1 = characteristic
                
                # Charaketeristik von Ausgang M4 (Servo) erfragen
                if (service.uuid == "2e58327e-c5c5-11e6-9d9d-cec0c932ce01" and
                    characteristic.uuid == "2e5837b0-c5c5-11e6-9d9d-cec0c932ce01"):
                    characteristic.name = "M4"
                    self.servo = characteristic

        # und nun fahre ...
        self.state = "starten"
        self.counter = 0
        
    def characteristic_enable_notification_succeeded(self, characteristic):
        super().characteristic_enable_notification_succeeded(characteristic)
        print("Charakteristik-Notifikation eingeschaltet")
        
    def characteristic_enable_notification_failed(self, characteristic):
        super().characteristic_enable_notification_failed(characteristic)
        print("Einschalten Charakteristik-Notifikation fehlgeschlagen")

    def characteristic_write_value_succeeded(self, characteristic):
        super().characteristic_write_value_succeeded(characteristic)
        if not self.outstanding_run and not self.outstanding_steer:
            self.write_in_progress = False
        elif self.outstanding_run:
            self.m1.write_value(bytes([self.outstanding_run]))
            self.outstanding_run = None
        else:
            self.servo.write_value(bytes([self.outstanding_steer]))
            self.outstanding_steer = None
        
        
    def characteristic_write_value_failed(self, characteristic, error):
        super().characteristic_write_value_failed(characteristic, error)
        print("Schreiben fehlgeschlagen", error)
    
    def run(self, value):
        # der Rennwagen soll dahren. Wenn das letzte Kommando noch nicht
        # bestätigt wurde, dann wird das Kommando gespeichert und gesendet, sobald
        # das letzte Kommando bestätigt wurde
        
        # letzter Wert wurde noch nicht gesendet?
        if self.write_in_progress:
            self.outstanding_run = value
        else:
            self.m1.write_value(bytes([value]))
            self.write_in_progress = True

    def steer(self, value):
        # der Rennwagen soll lenken. Wenn das letzte Kommando noch nicht
        # bestätigt wurde, dann wird das Kommando gespeichert und gesendet, sobald
        # das letzte Kommando bestätigt wurde
        
        # letzter Wert wurde noch nicht gesendet?
        if self.write_in_progress:
            self.outstanding_steer = value
        else:
            self.servo.write_value(bytes([value]))
            self.write_in_progress = True

# Hintergrund-Prozess starten, der den GATT-DBus bedient
manager = FtBtCtrlRcvDeviceManager(adapter_name='hci0')
thread = threading.Thread(target = manager.run)
thread.start()

if len(sys.argv) > 1:
    # teste, ob der Parameter einer MAC-Adresse entspricht
    if len(sys.argv[1].split(':')) != 6:
        print("Bitte eine gültige MAC-Adresse angeben.")
        print("z.B.:", sys.argv[0], "10:45:f8:7b:86:ed");
        exit(1)

    # Parameter auf der Kommandozeile gegeben
    manager.connected_device = FtBtCtrlRcvDevice(mac_address=sys.argv[1], manager=manager)
    manager.connected_device.connect()

else:
    print("Suche nach fischertechnik BT-Control-Receiver ...")
    print("Bitte Taster am Controller mehrere Sekunden drücken.")
    manager.start_discovery()

print("Beenden mit Ctrl-C")

# führe eigentliches Programm aus, solange im Hintergrund
# der Manager noch läuft
while True:
    rennwagen = manager.connected_device
    
    # Rennwagen fährt
    # - er beschleunigt sanft
    # - fährt 2 Sekunden gerade
    # - fährt 2 Sekunden um die Kurve
    # - er bremst sanft
    if rennwagen and rennwagen.state:
        if rennwagen.state == "starten":
            rennwagen.run(rennwagen.counter)
            if rennwagen.counter < 100:
                # schneller werden bis 100
                rennwagen.counter += 5
            else:
                # volle Geschwindigkeit erreicht
                print("Rennwagen fährt ...")
                rennwagen.state = "fahren"
                rennwagen.counter = 0
                
        elif rennwagen.state == "fahren":
            # 2 Sekunden fahren
            if rennwagen.counter < 20:
                rennwagen.counter += 1
            else:
                # lenken
                rennwagen.steer(80);
                
                print("Rennwagen lenkt ...")
                rennwagen.state = "kurve"
                rennwagen.counter = 0
                
        elif rennwagen.state == "kurve":
            # weitere 2 Sekunden fahren
            if rennwagen.counter < 20:
                rennwagen.counter += 1
            else:
                # nicht mehr lenken
                rennwagen.steer(0);
                
                print("Rennwagen bremst ...")
                rennwagen.state = "bremsen"
                rennwagen.counter = 100
                
        elif rennwagen.state == "bremsen":
            # bremsen bis zu Stillstand
            rennwagen.run(rennwagen.counter)
            if rennwagen.counter > 0:
                rennwagen.counter -= 5
            else:
                print("Fahrt beendet ...")
                rennwagen.state = None
                rennwagen.disconnect()
    
    # Teste, ob Manager noch läuft oder ob z.B. der Benutzer
    # ctrl-c gedrückt hat. Gleichzeitig sorgt der Timeout dafür, dass
    # die Hauptschleife 10 mal pro Sekunde durchlaufen wird
    thread.join(.1)
    if not thread.isAlive():
        break

# versuche Geräteverbindung zum Abschluss zu trennen
if manager.connected_device:
    manager.connected_device.disconnect()
