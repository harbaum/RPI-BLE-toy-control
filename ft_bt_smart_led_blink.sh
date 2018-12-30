#!/bin/bash

# Teste ob eine MAC-Adresse als Parameter gegeben wurde
# Versuche andernfalls den Controller automatisch zu finden
if [ "$1" != "" ]; then
    if [ "${#1}" != "17" ]; then
	echo "Bitte eine gültige MAC-Adresse als Parameter angeben."
	echo "Beispiel: $0 10:45:F8:7B:86:ED"
	exit 1
    fi
    FTC=$1
else
    echo "Kein Gerät angegeben, suche nach fischertechnik-BT-Smart-Controller ..."

    if [ "$(id -u)" != "0" ]; then
	echo "Dieses Script muss vom Root-User oder per sudo gestartet werden wenn automatisch nach Controllern gesucht werden soll." 1>&2
	exit 1   
    fi

    # Sicherstellen, dass letztes Kommando der folgenden Pipe nicht in einer
    # Subshell läuft
    shopt -s lastpipe
    
    # hcitool per lescan nach bluetooth le-Geräten suchen lassen. Sämtliche Puffer unterdrücken, damit
    # Ergebnisse sofort ausgewertet werden
    stdbuf -i0 -o0 -e0 hcitool lescan | {
	while IFS= read -r line
	do
	    # MAC-Adresse aus Antwort extrahieren
	    MAC=`echo $line | cut -d " " -f1`
	    # erste drei Bytes einer MAC-Adresse ist die sog.
	    # OID, die den Hersteller kennzeichnet
	    OID=`echo $MAC | cut -d':' -f 1-3`
	    
	    # eine gültige MAC-Adresse ist 17 Zeichen lang
	    if [ "${#MAC}" == "17" ]; then
		# suche solange kein passender Controller gefunden wurde
		if [ "$FTC" == "" ]; then
		    
		    # Test, ob ein gültiger Gerätename erkannt wurde
		    NAME=`echo $line | cut -d " " -f2-`
		    
		    # erweitertes hcitool wird "NAME ..." liefern
		    if [ "$OID" == "10:45:F8" ] &&
		       ( [ "$NAME" == "NAME BT Smart Controller" ] ||
			 [ "$NAME" ==      "BT Smart Controller" ] ); then
			
			echo "fischertechnik-BT-Smart-Controller erkannt: $MAC"
			FTC=$MAC
			
			# Suche erfolgreich, beende hcitool
			killall -s SIGINT hcitool
		    fi
		fi
	    fi
	done
    }
fi

# ein ft-Controller wurde erkannt, starte gatttool
if [ "$FTC" == "" ]; then
    echo "Kein passender Controller gefunden!"
    exit 1
fi

# suche nach Kanal-Service
CH_SRV=`gatttool -b $FTC --primary -u 8ae87702-ad7d-11e6-80f5-76304dec7eb7`
if [ "$CH_SRV" != "" ]; then
    SH=`echo $CH_SRV | cut -d' ' -f3`
    EH=`echo $CH_SRV | cut -d' ' -f6`
    echo "Kanal-Service-Handles: $SH bis $EH"

    # erfrage Kanal-Charakteristik
    CH_CHAR=`gatttool -b $FTC --char-desc -s 0x$SH -e 0x$EH | grep 8ae87e32-ad7d-11e6-80f5-76304dec7eb7`
    
    CH_VALUE_HDL=`echo $CH_CHAR | cut -d',' -f1 | cut -d'=' -f2`
    if [ "$CH_VALUE_HDL" != "" ]; then
        echo "Kanel-Charakteristik-Handle: $CH_VALUE_HDL"

	# blinken ...
	while true; do
	    gatttool -b $FTC --char-write-req -a $CH_VALUE_HDL -n 01
	    sleep 1
	    gatttool -b $FTC --char-write-req -a $CH_VALUE_HDL -n 00
	    sleep 1
	done    
    fi
fi
 
