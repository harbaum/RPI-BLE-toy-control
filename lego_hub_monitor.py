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
    NAMES = [ "LEGO Move Hub", "HUB NO.4", "Technic Hub", "Smart Hub" ]
    
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
    
    IMPACT = { "still": 0, "light hit": 1, "heavy hit/shake": 2, "shake": 3, "falling": 4 }

    # the ports have no special meanings, but we can name them from experience
    PORTS = { "A": 0x00, "B": 0x01, "C": 0x02, "D": 0x03, "A+B": 0x10,
              "LED": 0x32, "Int. tilt": 0x3a, "Current": 0x3b,
              "Voltage": 0x3c,
              "CPU": 0x3d,
              "Boost unknown internal port": 0x46,
              "Temperature": 0x60,                    # seen on technic hub
              "Accelerometer": 0x61,                  # seen on technic hub
              "Gyroscope": 0x62,                      # seen on technic hub
              "Angle": 0x63,                          # seen on technic hub
              "Impact sensor": 0x64 }                 # seen on technic hub

    # Klartextbezeichnungen der möglichen an den Boost angeschlossenen Geräte
    # (auch interne und WeDo-2.0-Geräte), der Boost hat keinen Speaker
    DEVICES = { "Motor M": 0x01, "Train Motor":0x02,
                "Turn":0x03, "Power":0x04, "Button":0x05,
                "Motor L": 0x06,"Motor X": 0x07,
                "Light": 0x08, "Light 1": 0x09, "Light 2": 0x0a,
                "Voltage sensor": 0x14, "Current sensor": 0x15,
                "Piezo": 0x16, "RGB LED": 0x17, "WeDo-2.0 tilt sensor": 0x22,
                "WeDo-2.0 motion sensor": 0x23, "WeDo-2.0 generic sensor": 0x24,
                "Vision sensor": 0x25,
                "Boost interactive motor": 0x26,
                "Boost builtin motor": 0x27,
                "Powered Up motor L": 0x2e,
                "Powered Up motor XL": 0x2f,
                "Impact sensor": 0x36,
                "Accelerometer": 0x39,
                "Gyroscope": 0x3a,
                "Tilt": 0x3b,
                "Thermometer": 0x3c,
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
                    
                    self.set_hub_property(2,2)    # button reports
                    self.led_set_color("orange") # LED auf orange schalten
                    self.set_hub_property(1,2)    # request name
                    
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
        
    def set_hub_property(self, property, operation):
        # properties  1=name, 2=button, ....
        # operations 2=enable updates
        self.send_cmd(0x01, bytes( [property, operation] ))

    def generic_set_mode(self, port, mode):
        self.send_cmd(0x41, struct.pack("<bbLb", port, mode, 1, 1))

    def color_dist_sensor_set_mode(self, port, mode):
        # mode = 0: Vier Bytes-Ergebnis, letztes Byte scheint Hindernis anzuzeigen
        # mode = 1/2: Sensor leuchtet grün
        # mode = 3: Sensor leuchtet rot
        # mode = 4: Sensor leuchtet blau
        # mode = 5: Sensor leuchtet nicht
        # mode = 6: Sensor liefert 3*2 Byte RGB-Werte
        # mode = 7: Sensor leuchtet nicht
        # mode = 8: Sensor liefert Distanz und Farb-Index
        self.send_cmd(0x41, struct.pack("<bbLb", port, mode, 1, 1))

    def tilt_sensor_set_mode(self, port, mode):
        # mode = 0: Neigung in zwei Winkeln
        # mode = 1: Unbekanntes 1-Byte-Format
        # mode = 2: grobe Neigung (links, rechts, vorwärts, ...)         
        self.send_cmd(0x41, struct.pack("<bbLb", port, mode, 1, 1))

    def wedo_tilt_sensor_set_mode(self, port, mode):
        # mode = 0: Neigung in zwei Winkeln
        # mode = 1: grobe Neigung (links, rechts, vorwärts, ...)         
        # mode = 2: Ereignis-Zähler
        self.send_cmd(0x41, struct.pack("<bbLb", port, mode, 1, 1))

    def wedo_motion_sensor_set_mode(self, port, mode):
        # mode 0: Distanz ungefähr in cm von 0 bis 10
        # mode 1: Ereigniszähler
        # mode 2: Unbekanntes 6-Byte-Resultat
        # >2: nicht erlaubt (Fehlercode 5)
        self.send_cmd(0x41, struct.pack("<bbLb", port, mode, 1, 1))

    def current_sensor_set_mode(self, port, mode):
        self.send_cmd(0x41, struct.pack("<bbLb", port, mode, 1000, 1))
        
    def voltage_sensor_set_mode(self, port, mode):
        self.send_cmd(0x41, struct.pack("<bbLb", port, mode, 1000, 1))

    def motor_report_rotation(self, port, mode):
        # mode = 0: Unbekannte Eregnisse für beide Motoren A+B
        # mode = 1: Winkel seit letztem Report melden
        # mode = 2: aufsummierten Winkel melden
        self.send_cmd(0x41, struct.pack("<bbLb", port, mode, 1, 1))
        
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
    
    def impact_name(self, id, ticks=""):
        for name, lid in self.IMPACT.items():
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

    def request_port_information(self,port):
        self.send_cmd(0x21, struct.pack("<BB", port, 0x01))    # request port mode information

    def request_port_mode_information(self,port,mode,type):
        self.send_cmd(0x22, struct.pack("<BBB", port, mode,type))
    
    def characteristic_value_updated(self, characteristic, value):
        # teste, ob Längenfeld stimmt, ignoriere die Meldung falls nicht
        if struct.unpack('b', value[0:1])[0] != len(value):
            return

        # extrahiere den Meldungstyp
        type = struct.unpack('>H', value[1:3])[0]

        if type == 0x01:  # Hub property event
            subtype = struct.unpack('b', value[3:4])[0]
            if subtype == 1:
                print("Hub property device name:", value[5:].decode("utf-8") )
            elif subtype == 2:
                status = struct.unpack('x?', value[4:6])[0]
                print("Hub property button status:", status)
            else:
                print("Hub property unknown:", hex(subtype))
            
        elif type == 0x04:  # Hub Attached I/O
            port, event = struct.unpack('bb', value[3:5])

            # Details zum Port-Konfigurations-Ereignis ausgeben
            print("Event: Port configuration, port name:", self.port_name(port, '"') + ", ", end="")
            if event == 0:
                # Event 0: Ein Gerät wurde vom Boost getrennt
                print("Device on port", hex(port), "disconnected")
                self.device_on_port[port] = None
            elif event == 1:
                # hub attach event
                dev = struct.unpack('b', value[5:6])[0]
                self.device_on_port[port] = dev
                print("Device connected:", self.device_name(dev, '"'))

                # request port information
                self.request_port_information(port)
                
                # set to true to trigger some default operation for many devices
                if dev == 0x05: # False: # True: # False:
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
                        self.wedo_motion_sensor_set_mode(port, 1)  # test in count mode
                
                    # wenn ein Farbsensor gefunden wurde, dann schalte ihn ein
                    if dev == 0x25:
                        self.color_dist_sensor_set_mode(port, 8)  # z.B. 6 ist RGB, 8 ist Farb-Index+Distanz
                    
                    # Wenn ein interaktiver Motor gefunden wurde: Drehe ihn einmal
                    # langsam 360°
                    if dev == 0x26 or dev == 0x2e or dev == 0x2f:
                        self.motor_report_rotation(port, 2)
                        self.motor_run_angle(port, 25, 360)  

                    if dev == 0x27:
                        self.motor_report_rotation(port, 1)
                    
                    # wenn ein Tiltsensor gefunden wurde, dann schalte ihn ein
                    if dev == 0x28:
                        self.tilt_sensor_set_mode(port, 0)
                    
                    # technic hub sensor "impact" sensor
                    if dev == 0x36:
                        self.generic_set_mode(port, 0)

                    # technic hub 3 axis accelerometer
                    if dev == 0x39:
                        self.generic_set_mode(port, 0)

                    # technic hub 3 axis gyroscope
                    if dev == 0x3a:
                        self.generic_set_mode(port, 0)

                    # technic hub 3 axis angle
                    if dev == 0x3b:
                        self.generic_set_mode(port, 0)
                
                    # temperature
                    if dev == 0x3c:
                        self.generic_set_mode(port, 0)
                
                    # unknown boost sensor
                    if dev == 0x42:
                        self.generic_set_mode(port, 0)
              
            elif event == 2:
                # setup of a virtual device complete
                dev, port1, port2 = struct.unpack('bxbb', value[5:9])
                print("Devices coupled:",  self.device_name(dev, '"'), "on ports",
                      self.port_name(port1, '"'), "and", self.port_name(port2, '"'))
            else:
                print("Unknown port event", event)

        elif type == 0x05:
            print("Error event", value[3:])
            
        elif type == 0x43:
            port,itype = struct.unpack('BB', value[3:5])
            print("Event: Port information: Port name:",  self.port_name(port,'"') + ", ", end="");
            if itype == 0x01:
                cap,count,imodes,omodes=struct.unpack('<BBHH', value[5:11])
                caps = ""
                if cap&1: caps += "Output,"
                if cap&2: caps += "Input,"
                if cap&4: caps += "Logical Combinable,"
                if cap&8: caps += "Logical Synchronizable,"
                print("mode info", caps, "#modes:", count, "input:", imodes, "output", omodes)

                # request info for all modes
                for i in range(count):
                    self.request_port_mode_information(port,i,0x00)   # 0x00 = name
                    self.request_port_mode_information(port,i,0x01)   # 0x01 = raw range
                    self.request_port_mode_information(port,i,0x02)   # 0x02 = pct range
                    self.request_port_mode_information(port,i,0x03)   # 0x03 = si range
                    self.request_port_mode_information(port,i,0x04)   # 0x04 = symbol
            else:
                print("unsupported info type", hex(itype));
            
        elif type == 0x44:
            port,mode,itype = struct.unpack('BBB', value[3:6])
            print("Event: Port mode information: Port name:",  self.port_name(port,'"') + ", ", end="");
            print("mode:", mode, ", ", end="");
            if itype == 0x00:
                print("name:", value[6:].decode('ascii'))
            elif itype == 0x01:
                min,max = struct.unpack('<ff', value[6:])
                print("raw min:", min, "max:", max);
            elif itype == 0x02:
                min,max = struct.unpack('<ff', value[6:])
                print("pct min:", min, "max:", max);
            elif itype == 0x03:
                min,max = struct.unpack('<ff', value[6:])
                print("si min:", min, "max:", max);
            elif itype == 0x04:
                print("symbol:", value[6:].decode('ascii'))
            else:
                print("unknown information type", hex(itype))
            
        elif type == 0x45:
            port = struct.unpack('B', value[3:4])[0]
            print("Port event: Port:", self.port_name(port,'"') + ", ", end="")

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
            elif (self.device_on_port[port] == 0x26 or self.device_on_port[port] == 0x27 or
                  self.device_on_port[port] == 0x2e or self.device_on_port[port] == 0x2f):
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

            # technic hub "impact" sensor
            elif self.device_on_port[port] == 0x36:
                if len(value[4:]) == 1:
                    i = struct.unpack('<B', value[4:])[0]
                    print("Impact:", self.impact_name(i))
                else:
                    print("Impact: unknown format", value[4:])
                    
            # technic hub accelerometer
            elif self.device_on_port[port] == 0x39:
                if len(value[4:]) == 6:
                    x, y, z = struct.unpack('<hhh', value[4:])
                    print("Acceleration X/Y/Z:",  x, y, z)
                else:
                    print("Acceleration: unknown format", value[4:])
                
            # technic hub gyroscope
            elif self.device_on_port[port] == 0x3a:
                if len(value[4:]) == 6:
                    x, y, z = struct.unpack('<hhh', value[4:])
                    print("Gyroscope X/Y/Z:",  x, y, z)
                else:
                    print("Gyroscope: unknown format", value[4:])
                    
            # technic hub tilt
            elif self.device_on_port[port] == 0x3b:
                if len(value[4:]) == 6:
                    x, y, z = struct.unpack('<hhh', value[4:])
                    print("Tilt X/Y/Z:",  x, y, z)
                else:
                    print("Tilt: unknown format", value[4:])
                    
            # technic hub temperature sensors
            elif self.device_on_port[port] == 0x3c:
                if len(value[4:]) == 2:
                    t = struct.unpack('<h', value[4:])[0] * 0.1
                    print("temperature: {:3.1f}°C".format(t))
                else:
                    print("temperature: unknown format", value[4:])
                    
            # unknown boost sensor, always returns one single 00 byte
            elif self.device_on_port[port] == 0x42:
                if len(value[4:]) == 1:
                    b = struct.unpack('<B', value[4:])[0]
                    print("boost: ", b)
                    if b!= 0:
                        print("!= 0!!!")
                        exit(-1)
                else:
                    print("boost: unknown format", value[4:])
                    exit(-1)
                    
            else:
                print("unbekannter Sensor: ", self.device_on_port[port], ":", value[4:])
            
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
            print("Unknown event", hex(type), "data:", value[3:])
        
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
