#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Verwendet python-gatt
# https://github.com/getsenic/gatt-python

# Einfaches Python-Beispiel, um per GATT auf den Lego
# Boost-Controller zuzugreifen.

try:
    import gatt
except ModuleNotFoundError as e:
    print("Error loading gatt module:", e);
    print("You may install it via 'pip3 install gatt' ...");
    exit(-1);
    
import sys, struct
import threading

print("Für dieses Programm muss der Farbsensor am Boost-Controller")
print("angeschlossen sein. Sobald die Farbe eines Objekts ca. 1cm")
print("vor dem Sensor erkannt wurde wird diese Farbe auf der LED")
print("des Controllers angezeigt.\n")

# GATT Device-Manager, um selektiv nach Lego-Boost-Controllern zu suchen
class BoostDeviceManager(gatt.DeviceManager):
    def __init__(self, adapter_name='hci0'):
        super().__init__(adapter_name=adapter_name)
        self.connected_device = None

    def device_discovered(self, device):
        # teste auf TI-OID und passenden Gerätenamen
        if((":".join(device.mac_address.split(':')[0:3]) == "00:16:53") and
           (device.alias() == "LEGO Move Hub")):
            self.stop_discovery()
            # verbinde, wenn noch nicht verbunden
            if not self.connected_device:
                print("Controller gefunden, verbinde ...")
                self.connected_device = device
                self.connected_device.connect()

    def make_device(self, mac_address):
        return BoostDevice(mac_address=mac_address, manager=self)

    def run(self):
        try:
            super().run()
        except KeyboardInterrupt:
            print("CTRL-C erkannt")
            self.quit();
      
    def quit(self):
        super().stop()

class BoostDevice(gatt.Device):
    
    # Farb-Indizes, wie sie Boost und WeDo 2.0 nutzen
    COLORS = { "schwarz": 0, "rosa": 1, "lila": 2, "blau": 3,
               "hellblau": 4, "hellgrün": 5, "grün": 6, "gelb": 7,
               "orange": 8, "rot": 9, "weiss": 10, "keine": 0xff }
                
    def __init__(self, mac_address, manager):
        super().__init__(mac_address, manager)
        self.device_on_port = { }
        self.ch = None
        self.state = None
        self.output_in_progress = False
        self.output_queue = [ ]
        self.color = None
    
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
                if (service.uuid == "00001623-1212-efde-1623-785feabcd123" and
                    characteristic.uuid == "00001624-1212-efde-1623-785feabcd123"):
                    characteristic.enable_notifications()
                    self.ch = characteristic
                    
                    self.led_set_color("schwarz")    # LED zunächst ausschalten
                    
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
            self.ch.write_value(data)
        
    def characteristic_write_value_failed(self, characteristic, error):
        super().characteristic_write_value_failed(characteristic, error)
        print("Schreiben fehlgeschlagen", error)

    def send_cmd(self, cmd, data):
        # sende Kommando + Daten inkl. vorangehendem Längenfeld
        cmd_seq = struct.pack(">bH", len(data)+3, cmd) + data
        
        if not self.output_in_progress:
            self.ch.write_value(cmd_seq)
            self.output_in_progress = True
        else:
            self.output_queue.append(cmd_seq)
        
    def button_set_config(self, code):
        # code 1 und 3 werden von der Tablet-App genutzt, haben aber unbekannte
        # Funktion. Code 2 schaltet die permanente Button-Abfrage ein
        self.send_cmd(1, bytes( [2, code] ))

    def led_set_color(self, color=0):
        if isinstance(color, int ):
            self.send_cmd(0x81, struct.pack(">bbbH", 0x32, 0x11, 0x51, color))
        elif color in self.COLORS:
            self.send_cmd(0x81, struct.pack(">bbbH", 0x32, 0x11, 0x51, self.COLORS[color]))
        else:
            print("Ignoriere unbekannten Farbcode")

    def enable_color_reading(self, port):
        self.send_cmd(0x41, struct.pack(">bbbL", port, 8, 1, 1))
        
    def color_name(self, id, ticks=""):
        # Farbname aus Farb-Index ableiten
        for name, lid in self.COLORS.items():
            if lid == id:
                return ticks + name + ticks
        return "<unknown>"
    
    def characteristic_value_updated(self, characteristic, value):
        # teste, ob Längenfeld stimmt, ignoriere die Meldung falls nicht
        if struct.unpack('b', value[0:1])[0] != len(value):
            return

        # extrahiere den Meldungstyp
        type = struct.unpack('>H', value[1:3])[0]
        
        if type == 4:  # Port-Konfigurations-Ereignis
            port, event = struct.unpack('bb', value[3:5])

            # Details zum Port-Konfigurations-Ereignis ausgeben
            if event == 0:
                # Event 0: Ein Gerät wurde vom Boost getrennt
                self.device_on_port[port] = None
            elif event == 1:
                # Event 1: Ein Gerät wurde vom Boost neu erkannt
                # Dieser Event wird auch initial für jedes verbundene Gerät
                # einmal geschickt
                dev = struct.unpack('b', value[5:6])[0]
                self.device_on_port[port] = dev

                # wenn ein farbsensor gefunden wurde, dann schalte ihn ein
                if dev == 0x25:
                    self.enable_color_reading(port)
                    
        elif type == 0x45:
            port = struct.unpack('b', value[3:4])[0]

            # Bearbeite je nach Sensor, der vorher an diesem Port erkannt wurde
            if self.device_on_port[port] == 0x25:
                # mindestens zwei Bytes werden erwartet
                if len(value[4:]) != 4:
                    pass
                else:
                    color = struct.unpack('BBxx', value[4:])[0]

                    # hat die erkannte Farbe sich geändert?
                    if color != self.color:
                        print("Erkannte Farbe:", self.color_name(color, '"'))
                        self.color = color

                        # 0xff (nichts erkannt) soll die LED ausschalten
                        if color == 0xff: color = 0
                        self.led_set_color(color)

# Hintergrund-Prozess starten, der den GATT-DBus bedient
manager = BoostDeviceManager(adapter_name='hci0')
thread = threading.Thread(target = manager.run)
thread.start()

if len(sys.argv) > 1:
    # teste, ob der Parameter einer MAC-Adresse entspricht
    if len(sys.argv[1].split(':')) != 6:
        print("Bitte eine gültige MAC-Adresse angeben.")
        print("z.B.:", sys.argv[0], "00:16:53:A4:DB:62");
        exit(1)

    # Parameter auf der Kommandozeile gegeben
    manager.connected_device = BoostDevice(mac_address=sys.argv[1], manager=manager)
    manager.connected_device.connect()

else:
    print("Suche nach Lego-Boost-Controller ...")
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
