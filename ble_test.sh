#!/bin/bash
if [ "$1" != "" ]; then
    HCI=$1
else
    HCI="hci0"
fi
    
echo -n "Teste $HCI auf Bluetooth-LE-Fähigkeiten: "
FEATURES=`hciconfig $HCI features | grep "<LE support>"`
if [ $? -ne 0 ]; then
    echo "Die Fähigkeiten von $HCI können nicht festgestellt werden."
else
    if [ "$FEATURES" == "" ]; then
	echo "nicht vorhanden"
	echo "Dieser Adapter eignet sich nicht zum Ansteuern der BLE-Spielzeugcontroller von Lego oder fischertechnik."
    else
	echo "vorhanden"
	echo "Dieser Adapter eignet sich zum Ansteuern der BLE-Spielzeugcontroller von Lego oder fischertechnik."
    fi
fi
