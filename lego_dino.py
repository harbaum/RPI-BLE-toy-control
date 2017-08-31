#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Verwendet python-gatt
# https://github.com/getsenic/gatt-python

# Einfaches Python-Beispiel, um per GATT auf den Lego
# WeDo-Controller zuzugreifen.

# https://github.com/cpseager/WeDo2-BLE-Protocol

import gatt, sys, struct
import threading

# GATT Device-Manager, um selektiv nach Lego-Controllern zu suchen
class WeDoDeviceManager(gatt.DeviceManager):
    def __init__(self, adapter_name='hci0'):
        super().__init__(adapter_name=adapter_name)
        self.connected_device = None

    def device_discovered(self, device):
        # teste auf TI-OID und passenden Gerätenamen
        if((":".join(device.mac_address.split(':')[0:3]) == "a0:e6:f8") and
           (device.alias() == "LPF2 Smart Hub 2 I/O")):
            self.stop_discovery()
            # verbinde, wenn noch nicht verbunden
            if not self.connected_device:
                print("Controller gefunden, verbinde ...")
                self.connected_device = device
                self.connected_device.connect()

    def make_device(self, mac_address):
        return WeDoDevice(mac_address=mac_address, manager=self)

    def run(self):
        try:
            super().run()
        except KeyboardInterrupt:
            print("CTRL-C erkannt")
            self.quit();
      
    def quit(self):
        super().stop()

class WeDoDevice(gatt.Device):
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
            # Lese alle Charakteristiken aus, die wir benötigen
            for characteristic in service.characteristics:
                if (service.uuid == "00001523-1212-efde-1523-785feabcd123" and
                    characteristic.uuid == "00001527-1212-efde-1523-785feabcd123"):
                    characteristic.name = "plug_event"
                    characteristic.enable_notifications()

                if (service.uuid == "00004f0e-1212-efde-1523-785feabcd123" and
                    characteristic.uuid == "00001560-1212-efde-1523-785feabcd123"):
                    characteristic.name = "value_event"
                    characteristic.enable_notifications()

                if (service.uuid == "00004f0e-1212-efde-1523-785feabcd123" and
                    characteristic.uuid == "00001563-1212-efde-1523-785feabcd123"):
                    self.char_mode_set = characteristic
                    
                if (service.uuid == "00004f0e-1212-efde-1523-785feabcd123" and
                    characteristic.uuid == "00001565-1212-efde-1523-785feabcd123"):
                    self.char_output = characteristic

                    # erstmal nehmen wir an, dass das Hindernis weit weg ist
                    # und die LED ist grün
                    self.set_color(9)
                    
    def characteristic_enable_notification_succeeded(self, characteristic):
        super().characteristic_enable_notification_succeeded(characteristic)
        print("Charakteristik-Notifikation eingeschaltet")
        
    def characteristic_enable_notification_failed(self, characteristic):
        super().characteristic_enable_notification_failed(characteristic)
        print("Einschalten Charakteristik-Notifikation fehlgeschlagen")

    def characteristic_write_value_succeeded(self, characteristic):
        super().characteristic_write_value_succeeded(characteristic)
        # Daten erfolgreich gesendet. Stehen weitere zum Senden an?
        if len(self.output_queue) == 0:
            self.output_in_progress = False
        else:
            # sende ausstehende Daten
            data = self.output_queue.pop(0)
            self.char_output.write_value(data)
        
    def characteristic_write_value_failed(self, characteristic, error):
        super().characteristic_write_value_failed(characteristic, error)
        print("Schreiben fehlgeschlagen", error)
    
    def characteristic_value_updated(self, characteristic, value):
        if characteristic.name == "value_event":
            event, port = struct.unpack('bb', value[0:2])
            if port <= 2:
                if self.port[port-1] == "motion":
                    # die Distant ist ein IEEE float gespeichert
                    # in Byte 2 bis 5 der Antwort. Der Wertebereich ist 0..9
                    motion = struct.unpack('f', value[2:6])[0]
                    print("Distanz:", motion)

                    # wenn etwas in der Nähe ist Farbe von grün über gelb und
                    # orange nach rot wechseln und motor ein- und auschalten
                    self.set_color(int(motion))
                    if motion < 4:   self.set_motor(100)
                    elif motion > 8: self.set_motor(0)
            
        if characteristic.name == "plug_event":
            port, event = struct.unpack('bb', value[0:2])

            # nur Ports 1 und 2 interessieren
            if port <= 2:
                if event == 0:
                    self.port[port-1] = None
                elif event == 1:
                    type = struct.unpack('b', value[3:4])[0]
                    if type == 1:
                        self.port[port-1] = "motor"
                    elif type == 34:
                        self.port[port-1] = "tilt"
                    elif type == 35:
                        self.port[port-1] = "motion"
                        # ein Bewegungssensor wurde erkannt
                        # schalte ihn in den "Motion-Detect"-Modus
                        self.char_mode_set.write_value(
                            bytes([ 1, 2, port, type, 0, 1, 0, 0, 0, 2, 1 ]))
                    else:
                        self.port[port-1] = "unknown"
                
    def set_output(self, data):
        if self.output_in_progress:
            self.output_queue.append(data)
        else:
            self.char_output.write_value(data)
            self.output_in_progress = True
            
    def set_motor(self, speed):
        # alle angeschlossenen Motoren ansteuern, speed = -100 bis 100
        for p in range(1,2):
            if self.port[p-1] == "motor":
                self.set_output(bytes([p,1,1,speed]))
                
    def set_color(self, value):
        # value is die aktuelle Distanz von 9 (weit weg) bis 0 (diret davor)
        # Die Farben dafür reichen von grün über gelb und orange nach rot
        colors = [ 9, 9, 9, 9, 8, 8, 7, 7, 6, 6 ]
        
        # sende set_color-Kommando
        self.set_output(bytes([6,4,1,colors[value]]))
            
# Hintergrund-Prozess starten, der den GATT-DBus bedient
manager = WeDoDeviceManager(adapter_name='hci0')
thread = threading.Thread(target = manager.run)
thread.start()

if len(sys.argv) > 1:
    # teste, ob der Parameter einer MAC-Adresse entspricht
    if len(sys.argv[1].split(':')) != 6:
        print("Bitte eine gültige MAC-Adresse angeben.")
        print("z.B.:", sys.argv[0], "a0:e6:f8:1b:e1:b9");
        exit(1)

    # Parameter auf der Kommandozeile gegeben
    manager.connected_device = WeDoDevice(mac_address=sys.argv[1], manager=manager)
    manager.connected_device.connect()

else:
    print("Suche nach Lego WeDo-2.0-Controller ...")
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

# versuche Geräteverbindung zum Abschluss zu trennen
if manager.connected_device:
    manager.connected_device.disconnect()
