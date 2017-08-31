#!/bin/bash
if [ "$(id -u)" != "0" ]; then
   echo "Dieses Script muss vom Root-User oder per sudo gestartet werden!" 1>&2
   exit 1
fi

# Sicherstellen, dass letztes Kommando der folgenden Pipe nicht in einer
# Subshell läuft
shopt -s lastpipe

# Liste aller erkannten Geräte führen, damit das gleiche Gerät nicht mehrfach
# abgefragt wird
ALLMACS=()

while true; do  
    echo "Suche nach Bluetooth-LE-Geräten ..."

    # hcitool per lescan nach bluetooth le-Geräten suchen lassen
    stdbuf -i0 -o0 -e0 hcitool lescan | {
	while IFS= read -r line
	do
	    # MAC-Adresse aus Antwort extrahieren
	    MAC=`echo $line | cut -d " " -f1`
	
            # eine gültige MAC-Adresse ist 17 Zeichen lang
            if [ "${#MAC}" == "17" ]; then
 
		# erste drei Bytes einer MAC-Adresse ist die sog.
		# OID, die den Hersteller kennzeichnet
		OID=`echo $MAC | cut -d':' -f 1-3`
	    
		# check, ob dieses Gerät schon einmal erkannt wurde
		if ! [[ ${ALLMACS[*]} =~ $MAC ]]; then
		    echo "Neues Gerät erkannt: $MAC"
		
		    # Neues Gerät an Liste der bisher erkannten Geräte
		    # anhängen
		    ALLMACS+=($MAC)
		
		    # Neues Gerät erkannt, beende Suche
		    killall -INT hcitool
		fi
            fi
	done
    }

    # Gerät(e) erkannt -> untersuche es

    # Finde "Battery Service"
    BATT_SRV=`gatttool -b $MAC --primary -u 0000180f-0000-1000-8000-00805f9b34fb`
    if [ "$BATT_SRV" != "" ]; then
	SH=`echo $BATT_SRV | cut -d' ' -f3`
	EH=`echo $BATT_SRV | cut -d' ' -f6`
	echo "Batterie-Service-Handles: $SH bis $EH"
	
	# Hole alle Charakteristiken dieses Dienstes
	BATT_LVL_CHAR=`gatttool -b $MAC --char-desc -s 0x$SH -e 0x$EH | grep 00002a19-0000-1000-8000-00805f9b34fb`
	
	# Die Charakteristik-Beschreibung ist Komma-separiert
	BATT_LVL_VALUE_HDL=`echo $BATT_LVL_CHAR | cut -d',' -f1 | cut -d'=' -f2`
	if [ "$BATT_LVL_VALUE_HDL" != "" ]; then
	    echo "Batterie-Level-Charakteristik-Handle: $BATT_LVL_VALUE_HDL"
	    BATT_LVL=`gatttool -b $MAC --char-read -a $BATT_LVL_VALUE_HDL | cut -d':' -f2- | tr -d '[:space:]'`
	    if [ "$BATT_LVL" != "" ]; then
		echo "Batterie-Level: $((16#$BATT_LVL))%"
	    fi
	fi
    else
	echo "Kein Batterie-Service vorhanden"
    fi
done		
