#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Verwendet python-gatt
# https://github.com/getsenic/gatt-python

# Einfaches Python-Beispiel, um per GATT auf den fischertechnik
# BT-Smart-Controller zuzugreifen.

try:
    import gatt
except ModuleNotFoundError as e:
    print("Error loading gatt module:", e);
    print("You may install it via 'pip3 install gatt' ...");
    exit(-1);
    
import sys, struct
import threading

# GATT Device-Manager, um selektiv nach ft-Controllern zu suchen
class FtBtSmartDeviceManager(gatt.DeviceManager):
    def __init__(self, adapter_name='hci0'):
        super().__init__(adapter_name=adapter_name)
        self.connected_device = None

    def device_discovered(self, device):
        # teste auf LNT-OID und passenden Gerätenamen
        if((":".join(device.mac_address.split(':')[0:3]) == "10:45:f8") and
           (device.alias() == "BT Smart Controller")):
            self.stop_discovery()
            # verbinde, wenn noch nicht verbunden
            if not self.connected_device:
                print("Controller gefunden, verbinde ...")
                self.connected_device = device
                self.connected_device.connect()

    def make_device(self, mac_address):
        return FtBtSmartDevice(mac_address=mac_address, manager=self)

    def run(self):
        try:
            super().run()
        except KeyboardInterrupt:
            print("CTRL-C erkannt")
            self.quit();
      
    def quit(self):
        super().stop()

class FtBtSmartDevice(gatt.Device):
    def __init__(self, mac_address, manager):
        super().__init__(mac_address, manager)
        self.m1 = None
        self.state = None
        self.write_in_progress = False
        self.outstanding_m1_value = None
    
    def connect(self):
        super().connect()
        
    def connect_succeeded(self):
        super().connect_succeeded()
        print("Verbunden mit", self.mac_address)
        print("Taster an I1 drücken, um Karussell an M1 zu starten")

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
                if (service.uuid == "8ae87702-ad7d-11e6-80f5-76304dec7eb7" and
                    characteristic.uuid == "8ae87e32-ad7d-11e6-80f5-76304dec7eb7"):
                    characteristic.name = "Channel"
                    characteristic.write_value( bytes([1]) )
                    self.write_in_progress = True

                # Eingang I1 permanent abfragen
                if (service.uuid == "8ae8952a-ad7d-11e6-80f5-76304dec7eb7" and
                    characteristic.uuid == "8ae89a2a-ad7d-11e6-80f5-76304dec7eb7"):
                    characteristic.name = "I1"
                    characteristic.read_value()
                    characteristic.enable_notifications()

                # Charaketeristik von Ausgang M1 erfragen
                if (service.uuid == "8ae883b4-ad7d-11e6-80f5-76304dec7eb7" and
                    characteristic.uuid == "8ae8860c-ad7d-11e6-80f5-76304dec7eb7"):
                    characteristic.name = "M1"
                    self.m1 = characteristic
                
    def characteristic_enable_notification_succeeded(self, characteristic):
        super().characteristic_enable_notification_succeeded(characteristic)
        print("Charakteristik-Notifikation eingeschaltet")
        
    def characteristic_enable_notification_failed(self, characteristic):
        super().characteristic_enable_notification_failed(characteristic)
        print("Einschalten Charakteristik-Notifikation fehlgeschlagen")

    def characteristic_write_value_succeeded(self, characteristic):
        super().characteristic_write_value_succeeded(characteristic)
        if not self.outstanding_m1_value:
            self.write_in_progress = False
        else:
            self.m1.write_value(bytes([self.outstanding_m1_value]))
            self.outstanding_m1_value = None
        
        
    def characteristic_write_value_failed(self, characteristic, error):
        super().characteristic_write_value_failed(characteristic, error)
        print("Schreiben fehlgeschlagen", error)
    
    def characteristic_value_updated(self, characteristic, value):
        # Wert wird in zwei Bytes als 16-Bit-Wert geliefert
        value_int = struct.unpack('<H', value)[0]

        # Starten des Karussel wenn Taster gedrückt. Es wird der Widerstand des Tasters
        # gemessen und unter 100 Ohm wird der Taster als geschlossen anerkannt
        if value_int < 100 and not self.state:
            print("Taster wurde gedrückt, Karussell startet ...")
            self.state = "starten"
            self.counter = 0

    def run(self, value):
        # das Karussell soll drehen. Wenn das letzte Motorkommando noch nicht
        # bestätigt wurde, dann wird der Wert gespeichert und gesendet, sobald
        # das letzte Kommando bestätigt wurde
        
        # letzter Wert wurde noch nicht gesendet?
        if self.write_in_progress:
            self.outstanding_m1_value = value
        else:
            self.m1.write_value(bytes([value]))
            self.write_in_progress = True
        
# Hintergrund-Prozess starten, der den GATT-DBus bedient
manager = FtBtSmartDeviceManager(adapter_name='hci0')
thread = threading.Thread(target = manager.run)
thread.start()

if len(sys.argv) > 1:
    # teste, ob der Parameter einer MAC-Adresse entspricht
    if len(sys.argv[1].split(':')) != 6:
        print("Bitte eine gültige MAC-Adresse angeben.")
        print("z.B.:", sys.argv[0], "10:45:f8:7b:86:ed");
        exit(1)

    # Parameter auf der Kommandozeile gegeben
    manager.connected_device = FtBtSmartDevice(mac_address=sys.argv[1], manager=manager)
    manager.connected_device.connect()

else:
    print("Suche nach fischertechnik BT-Smart-Controller ...")
    print("Bitte Taster am Controller mehrere Sekunden drücken.")
    manager.start_discovery()

print("Beenden mit Ctrl-C")

# führe eigentliches Programm aus, solange im Hintergrund
# der Manager noch läuft
while True:
    karussell = manager.connected_device
    
    # karussel läuft
    if karussell and karussell.state:
        if karussell.state == "starten":
            karussell.run(karussell.counter)
            if karussell.counter < 100:
                # schneller werden bis 100
                karussell.counter += 1
            else:
                # volle Geschwindigkeit erreicht
                print("Karussell fährt ...")
                karussell.state = "fahren"
                karussell.counter = 0
                
        elif karussell.state == "fahren":
            # 30 Sekunden fahren
            if karussell.counter < 300:
                karussell.counter += 1
            else:
                print("Karussell bremst ...")
                karussell.state = "bremsen"
                karussell.counter = 100
                
        elif karussell.state == "bremsen":
            # bremsen bis zu Stillstand
            karussell.run(karussell.counter)
            if karussell.counter > 0:
                karussell.counter -= 1
            else:
                print("Fahrt beendet ...")
                karussell.state = None
    
    # Teste, ob Manager noch läuft oder ob z.B. der Benutzer
    # ctrl-c gedrückt hat. Gleichzeitig sorgt der Timeout dafür, dass
    # die Hauptschleife 10 mal pro Sekunde durchlaufen wird
    thread.join(.1)
    if not thread.isAlive():
        break

# versuche Geräteverbindung zum Abschluss zu trennen
if manager.connected_device:
    manager.connected_device.disconnect()
