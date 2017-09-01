#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Verwendet python-gatt
# https://github.com/getsenic/gatt-python

import gatt, sys, struct
import threading

# GATT Device-Manager, um selektiv nach Spielzeug-Controllern zu suchen
class ToyDeviceManager(gatt.DeviceManager):
    def __init__(self, adapter_name='hci0'):
        super().__init__(adapter_name=adapter_name)
        self.connected_device = None

    def device_discovered(self, device):
        # teste auf TI-OID und passenden Gerätenamen für WeDo-Hub,
        # auf LNT-OID für fischertechnik und auf Lego-OID für Boost-
        # Controller
        if(((":".join(device.mac_address.split(':')[0:3]) == "a0:e6:f8") and
            (device.alias() == "LPF2 Smart Hub 2 I/O")) or
           ((":".join(device.mac_address.split(':')[0:3]) == "10:45:f8") and
            (device.alias() == "BT Smart Controller")) or
           ((":".join(device.mac_address.split(':')[0:3]) == "10:45:f8") and
            (device.alias() == "BT Control Receiver")) or
           ((":".join(device.mac_address.split(':')[0:3]) == "00:16:53") and
            (device.alias() == "LEGO Move Hub"))):

            self.stop_discovery()
            # verbinde, wenn noch nicht verbunden
            if not self.connected_device:
                print("Controller gefunden, verbinde ...")
                self.connected_device = device
                self.connected_device.connect()

        # teste auf LNT-OID und passenden Gerätenamen
            self.stop_discovery()

    def make_device(self, mac_address):
        return ToyDevice(mac_address=mac_address, manager=self)

    def run(self):
        try:
            super().run()
        except KeyboardInterrupt:
            print("CTRL-C erkannt")
            self.quit();
      
    def quit(self):
        super().stop()

class ToyDevice(gatt.Device):
    def __init__(self, mac_address, manager):
        super().__init__(mac_address, manager)
        self.m1 = None
        self.state = None
        self.outstanding_m1_value = None
        self.port = [ None, None ]
        self.output_in_progress = False
        self.output_queue = [ ]
    
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
            print("Service UUID", service.uuid)
            
            # Liste alle Charakteristiken
            for characteristic in service.characteristics:
                print("Charakteristik UUID", characteristic.uuid)

        self.disconnect();
                
# Hintergrund-Prozess starten, der den GATT-DBus bedient
manager = ToyDeviceManager(adapter_name='hci0')
thread = threading.Thread(target = manager.run)
thread.start()

if len(sys.argv) > 1:
    # teste, ob der Parameter einer MAC-Adresse entspricht
    if len(sys.argv[1].split(':')) != 6:
        print("Bitte eine gültige MAC-Adresse angeben.")
        print("z.B.:", sys.argv[0], "a0:e6:f8:1b:e1:b9");
        exit(1)

    # Parameter auf der Kommandozeile gegeben
    manager.connected_device = ToyDevice(mac_address=sys.argv[1], manager=manager)
    manager.connected_device.connect()

else:
    print("Suche nach Spielzeug-Controller ...")
    print("Bitte Taster am Controller drücken.")
    manager.start_discovery()

print("Beenden mit Ctrl-C")

# führe eigentliches Programm aus, solange im Hintergrund
# der Manager noch läuft
while True:
    # Teste, ob Manager noch läuft oder ob z.B. der Benutzer
    # ctrl-c gedrückt hat. Gleichzeitig sorgt der Timeout dafür, dass
    # die Hauptschleife 1 mal pro Sekunde durchlaufen wird
    thread.join(1)
    if not thread.isAlive():
        break
