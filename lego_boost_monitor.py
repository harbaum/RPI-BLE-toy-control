#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Verwendet python-gatt
# https://github.com/getsenic/gatt-python

# Einfaches Python-Beispiel, um per GATT auf den Lego
# Boost-Controller zuzugreifen. Dieses Programm schaltet
# die Meldungen aller Sensoren ein und gibt kontinuerlich deren
# Zustand aus.

import sys, struct
import threading

try:
    import gatt
except ModuleNotFoundError as e:
    print("Error loading gatt module:", e);
    print("You may install it via 'pip3 install gatt' ...");
    exit(-1);

# GATT Device-Manager, um selektiv nach Lego-Boost-Controllern zu suchen
class BoostDeviceManager(gatt.DeviceManager):
    OIDS = [ "00:16:53", "90:84:2b" ] 
    NAMES = [ "LEGO Move Hub", "HUB NO.4" ]
    
    def __init__(self, adapter_name='hci0'):
        super().__init__(adapter_name=adapter_name)
        self.connected_device = None

    def device_discovered(self, device):
        # teste auf TI-OID und passenden Gerätenamen
        if((":".join(device.mac_address.split(':')[0:3]).lower() in self.OIDS) and
           (device.alias() in self.NAMES )):
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
    COLORS = { "black": 0, "off": 0, "pink": 1, "purple": 2, "blue": 3,
               "light blue": 4, "light green": 5, "green": 6, "yellow": 7,
               "orange": 8, "red": 9, "white": 10, "invalid": 0xff }

    TILT = { "flat": 0, "backward": 1, "forward": 2, "right": 3, "left": 4, "upside down": 5 }

    WEDO_TILT = { "flat": 0, "backward": 3, "right": 5, "left": 7, "forward": 9 }

    # Klartextbezeichnungen der Anschlüsse (auch interne)
    PORTS = { "A": 0x00, "B": 0x01, "C": 0x02, "D": 0x03, "A+B": 0x10,
              "LED": 0x32, "Int. tilt": 0x3a, "Current": 0x3b,
              "Voltage": 0x3c, "Boost unknown port": 0x46}

    # Klartextbezeichnungen der möglichen an den Boost angeschlossenen Geräte
    # (auch interne und WeDo-2.0-Geräte), der Boost hat keinen Speaker
    DEVICES = { "WeDo-2.0 motor": 0x01, "White LED pair": 0x08,
                "Voltage sensor": 0x14, "Current sensor": 0x15,
                "Speaker": 0x16, "RGB LED": 0x17, "WeDo-2.0 tilt sensor": 0x22,
                "WeDo-2.0 motion sensor": 0x23, "WeDo-2.0 generic sensor": 0x24,
                "Boost color and distance sensor": 0x25,
                "Boost interactive motor": 0x26,
                "Boost builtin motor": 0x27,
                "Boost builtin tilt sensor": 0x28,
                "Boost unknown device": 0x42 }
                
    def __init__(self, mac_address, manager):
        super().__init__(mac_address, manager)
        self.device_on_port = { }
        self.ch = None
        self.state = None
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
                if (service.uuid == "00001623-1212-efde-1623-785feabcd123" and
                    characteristic.uuid == "00001624-1212-efde-1623-785feabcd123"):
                    characteristic.enable_notifications()
                    self.ch = characteristic
                    
                    # self.button_set_config(3)  # keine erkennbare Reaktion
                    self.button_set_config(2)    # automatische Reports einschalten
                    # self.button_set_config(1)  # -> verursacht unbekannten Ereignis-Typ 5
        
                    self.led_set_color("orange") # LED auf orange schalten

                    self.request_device_name()
                    
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
        self.send_cmd(1, bytes( [2, code] ))   # die '2' scheint den Button zu beschreiben

    def request_device_name(self):
        self.send_cmd(0x01, struct.pack(">bbb", 1, 2, 0))  # die '1' adressiert den Gerätenamen (vgl. Button)

    def color_dist_sensor_set_mode(self, port, mode):
        # mode = 0: Vier Bytes-Ergebnis, letztes Byte scheint Hindernis anzuzeigen
        # mode = 1/2: Sensor leuchtet grün
        # mode = 3: Sensor leuchtet rot
        # mode = 4: Sensor leuchtet blau
        # mode = 5: Sensor leuchtet nicht
        # mode = 6: Sensor liefert 3*2 Byte RGB-Werte
        # mode = 7: Sensor leuchtet nicht
        # mode = 8: Sensor liefert Distanz und Farb-Index
        self.send_cmd(0x41, struct.pack(">bbbL", port, mode, 1, 1))

    def tilt_sensor_set_mode(self, port, mode):
        # mode = 0: Neigung in zwei Winkeln
        # mode = 1: Unbekanntes 1-Byte-Format
        # mode = 2: grobe Neigung (links, rechts, vorwärts, ...)         
        self.send_cmd(0x41, struct.pack(">bbbL", port, mode, 1, 1))

    def wedo_tilt_sensor_set_mode(self, port, mode):
        # mode = 0: Neigung in zwei Winkeln
        # mode = 1: grobe Neigung (links, rechts, vorwärts, ...)         
        # mode = 2: Ereignis-Zähler
        self.send_cmd(0x41, struct.pack(">bbbL", port, mode, 1, 1))

    def wedo_motion_sensor_set_mode(self, port, mode):
        # mode 0: Distanz ungefähr in cm von 0 bis 10
        # mode 1: Ereigniszähler
        # mode 2: Unbekanntes 6-Byte-Resultat
        # >2: nicht erlaubt (Fehlercode 5)
        self.send_cmd(0x41, struct.pack(">bbbL", port, mode, 1, 1))

    def current_sensor_set_mode(self, port, mode):
        self.send_cmd(0x41, struct.pack(">bbbL", port, mode, 1, 1))
        
    def voltage_sensor_set_mode(self, port, mode):
        self.send_cmd(0x41, struct.pack(">bbbL", port, mode, 1, 1))

    def motor_report_rotation(self, port, mode):
        # mode = 0: Unbekannte Eregnisse für beide Motoren A+B
        # mode = 1: Winkel seit letztem Report melden
        # mode = 2: aufsummierten Winkel melden
        self.send_cmd(0x41, struct.pack(">bbbL", port, mode, 1, 1))
        
    def led_set_color(self, color=0):
        if isinstance(color, int ):
            self.send_cmd(0x81, struct.pack(">bbbH", 0x32, 0x11, 0x51, color))
        elif color in self.COLORS:
            self.send_cmd(0x81, struct.pack(">bbbH", 0x32, 0x11, 0x51, self.COLORS[color]))
        else:
            print("Ignoriere unbekannten Farbcode")

    def motor_run(self, port, speed):
        self.send_cmd(0x81, struct.pack("<BBBb", port, 0x11, 1, speed))

    def motor_run_time(self, port, speed, time):
        self.send_cmd(0x81, struct.pack("<BbbHbBBB", port, 0x11, 9, int(time*1000), speed, 100, 0x7f, 0x03))

    def motors_run_time(self, speedA, speedB, time):
        # zwei Motoren synchron laufen lassen. Das geht nur für Port 0x39 (den Gruppenport der
        # Motoren A+B).
        self.send_cmd(0x81, struct.pack("<BbbHbBBBB", 0x39, 0x11, 10, int(time*1000), speedA, speedB, 100, 0x7f, 0x03))

    def motor_run_angle(self, port, speed, angle):
        self.send_cmd(0x81, struct.pack("<BbblbBBB", port, 0x11, 11, angle, speed, 100, 0x7f, 0x03))
        
    def motors_run_angle(self, speedA, speedB, angle):
        self.send_cmd(0x81, struct.pack("<BbblbBBBB", 0x39, 0x11, 12, angle, speedA, speedB, 100, 0x7f, 0x03))

    # -----------------------------------------------------------------------------
    # Routinen, um die diversen Port-/Farb-,...Konstanten im Klartext zu wandeln
    # -----------------------------------------------------------------------------
        
    def color_name(self, id, ticks=""):
        # Farbname aus Farb-Index ableiten
        for name, lid in self.COLORS.items():
            if lid == id:
                return ticks + name + ticks
        return "<unknown>"
    
    def tilt_name(self, id, ticks=""):
        # Neigungsname aus Neigungs-Index ableiten
        for name, lid in self.TILT.items():
            if lid == id:
                return ticks + name + ticks
        return "<unknown>"
    
    def wedo_tilt_name(self, id, ticks=""):
        # WeDo-Sensor Neigungsname aus Neigungs-Index ableiten
        for name, lid in self.WEDO_TILT.items():
            if lid == id:
                return ticks + name + ticks
        return "<unknown>"
    
    def port_name(self, id, ticks=""):
        # Portname aus Port-Index ableiten
        for name, lid in self.PORTS.items():
            if lid == id:
                return ticks + name + ticks
        return "<unknown port id: "+str(id)+">"
    
    def device_name(self, id, ticks=""):
        # Gerätename aus Geräte-Index ableiten
        for name, lid in self.DEVICES.items():
            if lid == id:
                return ticks + name + ticks
        return "<unknown device id: "+str(id)+">"
        
    def characteristic_value_updated(self, characteristic, value):
        # teste, ob Längenfeld stimmt, ignoriere die Meldung falls nicht
        if struct.unpack('b', value[0:1])[0] != len(value):
            return

        # extrahiere den Meldungstyp
        type = struct.unpack('>H', value[1:3])[0]

        if type == 1:  # Button-/Name-Ereignis
            # Byte value[4] scheint immer 6 zu sein ...

            subtype = struct.unpack('b', value[3:4])[0]
            if subtype == 1:
                print("Ereignis: Gerätename:", value[5:].decode("utf-8") )
            elif subtype == 2:
                status = struct.unpack('x?', value[4:6])[0]
                print("Ereignis: Button, Status:", status)
            else:
                print("Ereignis: unbekanntes Ereignis", subtype)
            
        elif type == 4:  # Port-Konfigurations-Ereignis
            port, event = struct.unpack('bb', value[3:5])

            # Details zum Port-Konfigurations-Ereignis ausgeben
            print("Ereignis: Port-Konfiguration, Port-Name:", self.port_name(port, '"') + ", ", end="")
            if event == 0:
                # Event 0: Ein Gerät wurde vom Boost getrennt
                print("Gerät getrennt")
                self.device_on_port[port] = None
            elif event == 1:
                # Event 1: Ein Gerät wurde vom Boost neu erkannt
                # Dieser Event wird auch initial für jedes verbundene Gerät
                # einmal geschickt
                dev = struct.unpack('b', value[5:6])[0]
                self.device_on_port[port] = dev
                print("Gerät verbunden:", self.device_name(dev, '"'))

                if dev == 0x01:
                    self.motor_run(port, 25)
                      
                if dev == 0x08:
                    self.motor_run(port, 100)   # the LED pair uses the same command as the simple motor
                    
                if dev == 0x14:
                    self.voltage_sensor_set_mode(port, 0)

                if dev == 0x15:
                    self.current_sensor_set_mode(port, 0)

                if dev == 0x22:
                    self.wedo_tilt_sensor_set_mode(port, 0)
                    
                if dev == 0x23:
                    self.wedo_motion_sensor_set_mode(port, 1)
                    
                # wenn ein Farbsensor gefunden wurde, dann schalte ihn ein
                if dev == 0x25:
                    self.color_dist_sensor_set_mode(port, 8)  # z.B. 6 ist RGB, 8 ist Farb-Index+Distanz
                    
                # Wenn ein interaktiver Motor gefunden wurde: Drehe ihn einmal
                # langsam 360°
                if dev == 0x26:
                    self.motor_report_rotation(port, 2)
                    self.motor_run_angle(port, 25, 360)  

                if dev == 0x27:
                    self.motor_report_rotation(port, 1)
                    
                # wenn ein Tiltsensor gefunden wurde, dann schalte ihn ein
                if dev == 0x28:
                    self.tilt_sensor_set_mode(port, 0)
        
            elif event == 2:
                # Event 2: Eine Verbindung zwischen zwei Ports wird angezeigt.
                # Dies wird vom Boost genutzt, um die beiden internen Motoren
                # mit einem Kommando gemeinsam schalten zu können
                dev, port1, port2 = struct.unpack('bxbb', value[5:9])
                print("Geräte gekoppelt:",  self.device_name(dev, '"'), "an Ports",
                      self.port_name(port1, '"'), "und", self.port_name(port2, '"'))
            else:
                print("unbekanntes Port-Ereignis", event)

        elif type == 5:  # anscheinend Fehler-Eregnis, Inhalt bisher weigehend unbekannt
            print("Ereignis: FEHLER", value[3:])
            
        elif type == 0x45:
            port = struct.unpack('b', value[3:4])[0]
            print("Port-Ereignis: Port:", self.port_name(port,'"') + ", ", end="")

            # Bearbeite je nach Sensor, der vorher an diesem Port erkannt wurde

            if self.device_on_port[port] == 0x14:
                voltage = struct.unpack('<H', value[4:])[0]
                print("Spannung:", voltage)
                
            elif self.device_on_port[port] == 0x15:
                current = struct.unpack('<H', value[4:])[0]
                print("Strom:", current)

                # WeDo-Neigungssensor
            elif self.device_on_port[port] == 0x22:
                if len(value[4:]) == 1:
                    tilt = struct.unpack('B', value[4:])[0]
                    print("Neigung:",  self.wedo_tilt_name(tilt))
                elif len(value[4:]) == 2:
                    # WeDo-Winkel sind in 2°-Schritten
                    x, y = struct.unpack('bb', value[4:6])
                    print("WeDo-Neigung X°/Y°:",  2*x, 2*y)
                elif len(value[4:]) == 3:
                    c = struct.unpack('bbb', value[4:])
                    print("Zähler x/y/z:",  c[0], c[1], c[2])
                else:
                    print("WeDo-Neigung: unbekanntes Format:", value[4:])

            elif self.device_on_port[port] == 0x23:
                if len(value[4:]) == 1:
                    dist = struct.unpack('B', value[4:])[0]
                    print("WeDo-Distanz:",  dist)
                elif len(value[4:]) == 4:
                    events = struct.unpack('<L', value[4:])[0]
                    print("WeDo-Bewegungsereignisse:",  events)
                else:
                    print("WeDo-Distanz: unbekanntes Format:", value[4:])
                
                # Farbsensor
            elif self.device_on_port[port] == 0x25:
                # vier Bytes werden erwartet
                if len(value[4:]) == 4:
                    color, dist = struct.unpack('BBxx', value[4:])
                    print("Farbe:", self.color_name(color, '"') + ",", "Distanz:", dist)
                elif len(value[4:]) == 6:
                    r, g, b = struct.unpack('<HHH', value[4:])
                    print("Farbe RGB:", r, g, b)
                else:
                    print("unerwartete Farbsensorantwort:", value[4:])

            # Motor als Winkelsensor
            elif self.device_on_port[port] == 0x26 or self.device_on_port[port] == 0x27:
                if len(value[4:]) == 1:
                    angle = struct.unpack('<b', value[4:])[0]
                    print("Motorwinkel seit letztem Report:", angle)                    
                elif len(value[4:]) == 4:
                    angle = struct.unpack('<l', value[4:])[0]
                    print("Summierter Motorwinkel:", angle)
                else:
                    print("Motordrehung: unbekanntes Format:", value[4:])
                
            # Neigungssensor
            elif self.device_on_port[port] == 0x28:
                if len(value[4:]) == 1:
                    tilt = struct.unpack('B', value[4:])[0]
                    print("Neigung:",  self.tilt_name(tilt))
                elif len(value[4:]) == 2:
                    x, y = struct.unpack('bb', value[4:6])
                    print("Neigung X°/Y°:",  x, y)
                else:
                    print("Neigung: unbekanntes Format:", value[4:])
                
            else:
                print("unbekannter Sensor!!")
            
        elif type == 0x47:
            # Diese Antwort erfolgt auf Sensor-Konfigurationen
            port = struct.unpack('b', value[3:4])[0]
            print("Sensor-Bestätigung auf Port", self.port_name(port, '"'))
        
        elif type == 0x82:
            # Diese Antwort erfolgt auf alle 0x81-Kommandos
            port, code = struct.unpack('BB', value[3:5])
            
            # Port = Sensor-/Aktorport
            # Code 1: Kommando wird gestartet
            # Code 5: Kommando wird bereits ausgeführt
            # Code 10: Kommando beendet

            print("Ereignis: Bestätigung für Port", self.port_name(port, '"') + ", ", end="")
            if code == 1:
                print("Kommando wird gestartet")
            elif code == 5:
                print("Kommando wurde bereits ausgeführt")
            elif code == 10:
                print("Kommando beendet")
            else:
                print("Unbekannter Code:", code)
            
        else:
            print("Unbekanntes Ereignis", type, "Daten:", value[3:])
        
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
