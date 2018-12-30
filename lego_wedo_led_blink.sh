#!/bin/bash

# Teste ob eine MAC-Adresse als Parameter gegeben wurde
# Versuche andernfalls den Controller automatisch zu finden
if [ "$1" != "" ]; then
    if [ "${#1}" != "17" ]; then
	echo "Bitte eine gültige MAC-Adresse als Parameter angeben."
	echo "Beispiel: $0 A0:E6:F8:1B:E1:B9"
	exit 1
    fi
    LWH=$1
else
    echo "Kein Gerät angegeben, suche nach Lego WeDo-2.0-Controller ..."

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
	    
	    # eine gültige MAC-Adresse ist 17 Zeichen lang
	    if [ "${#MAC}" == "17" ]; then
		# suche solange kein passender Controller gefunden wurde
		if [ "$LWH" == "" ]; then
		    
		    # Test, ob ein gültiger Gerätename erkannt wurde
		    NAME=`echo $line | cut -d " " -f2-`
		    
		    # erweitertes hcitool wird "UUID128 ..." liefern, das originale
		    # hcitool lediglich den Namen. Unverändert ist dieser "LPF2 Smart Hub 2 I/O"
		    # Ein WeDo-Hub mit verändertem Naman kann daher mit dem originalen hcitool nicht
		    # erkannt werden.
		    if ( [ "$NAME" == "UUID128 00001523-1212-EFDE-1523-785FEABCD123" ] ||
		         [ "$NAME" == "LPF2 Smart Hub 2 I/O" ] ); then
			
			echo "Lego WeDo-2.0-Controller erkannt: $MAC"
			LWH=$MAC
			
			# Suche erfolgreich, beende hcitool
			killall -s SIGINT hcitool
		    fi
		fi
	    fi
	done
    }
fi

# ein Lego-Controller wurde erkannt, starte gatttool
if [ "$LWH" == "" ]; then
    echo "Kein passender Controller gefunden!"
    exit 1
fi

# suche nach Lego-Service
LEGO_SRV=`gatttool -b $LWH --primary -u 00004f0e-1212-efde-1523-785feabcd123`
if [ "$LEGO_SRV" != "" ]; then
    SH=`echo $LEGO_SRV | cut -d' ' -f3`
    EH=`echo $LEGO_SRV | cut -d' ' -f6`
    echo "Lego-Service-Handles: $SH bis $EH"

    # erfrage Lego-Output-Charakteristik
    LEGO_OUT_CHAR=`gatttool -b $LWH --char-desc -s 0x$SH -e 0x$EH | grep 00001565-1212-efde-1523-785feabcd123`
    
    LEGO_OUT_HDL=`echo $LEGO_OUT_CHAR | cut -d',' -f1 | cut -d'=' -f2`
    if [ "LEGO_OUT_HDL" != "" ]; then
        echo "Lego-Output-Charakteristik-Handle: $LEGO_OUT_HDL"

	# blinken ...
	while true; do
	    # setze LED-Farbe auf Orange
	    gatttool -b $LWH --char-write-req -a $LEGO_OUT_HDL -n 06040108
	    sleep 1
	    # setze LED-Farbe auf Blau
	    gatttool -b $LWH --char-write-req -a $LEGO_OUT_HDL -n 06040103
	    sleep 1
	done    
    fi
fi
 
