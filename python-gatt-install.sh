#!/bin/bash
if [ "$(id -u)" != "0" ]; then
   echo "Dieses Script muss vom Root-User oder per sudo gestartet werden!" 1>&2
   exit 1
fi

echo "Installiere python-gatt und bluez-5.44 ..."
systemctl stop bluetooth
apt-get update
apt-get -y install python3-pip python3-dbus
pip3 install gatt
apt-get -y install libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev libdbus-glib-1-dev unzip
cd
mkdir bluez
cd bluez
wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.44.tar.xz
tar xf bluez-5.44.tar.xz
cd bluez-5.44
./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --enable-library
make
make install
ln -svf /usr/libexec/bluetooth/bluetoothd /usr/sbin/
systemctl daemon-reload
systemctl start bluetooth
hciconfig hci0 up

# check for corrent version
if [ "`bluetoothd --version`" == "5.44" ]; then
    echo "Installation erfolgreich";
else
    echo "Installation nicht erfolgreich";
fi
