# Bewässerungsautomatik

![Logo](images/logo_256.png)

Wetterabhängige Pflanzenbewässerung für Home Assistant. Version 1.2.0 ist auf ein **Blumenbeet mit sonnigem Standort und Mikrosprühern** abgestimmt.

## Funktionen

- gemessene Tageshöchsttemperatur aus `sensor.icolog277_temperature`
- erwartete Temperatur und 12-Stunden-Regen aus `weather.koln_bonn`
- gewichtete Niederschlagshistorie aus `sensor.icolog277_precipitation_today`
- Trockenheits-, Temperatur-, Saison-, Regen- und Vorhersagefaktor
- automatische Laufzeit von 2 bis maximal 50 Minuten
- manueller Wasserbetrieb mit 240 Minuten
- separat deaktivierbare Sicherheitsabschaltung
- transparente Entscheidung, Datenqualität, Logbuch und Diagnose
- native Dashboard-Konfiguration ohne Pflicht zu Mushroom/HACS-Frontendkarten
- einstellbare Startzeit, standardmäßig 05:00 Uhr
- Vorberechnung automatisch zehn Minuten vor dem Start
- erneute Wetter- und Sicherheitsprüfung unmittelbar vor Ventilöffnung
- nächste Aktion, geplanter Start und verbleibende Laufzeit als Sensoren
- optionale Benachrichtigungen über einen frei wählbaren Home-Assistant-Dienst

## Installation

### Manuell

Kopiere `custom_components/bewaesserungsautomatik` nach `/config/custom_components/bewaesserungsautomatik` und starte Home Assistant neu. Danach unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach „Bewässerungsautomatik“ suchen.

### HACS (benutzerdefiniertes Repository)

Repository `https://github.com/lenni76/Bewaesserungsautomatik` als benutzerdefiniertes Integrations-Repository hinzufügen.

## Standard-Entitäten

- Temperatur: `sensor.icolog277_temperature`
- Regen heute: `sensor.icolog277_precipitation_today`
- Wetter: `weather.koln_bonn`
- Ventil: `valve.garten_wasseranschluss`
- Laufzeit: `number.wasseranschluss_laufzeit`

## Wetterstation und Entitäten später ändern

Unter **Einstellungen → Geräte & Dienste → Bewässerungsautomatik** am bestehenden Integrationseintrag das **Drei-Punkte-Menü → Neu konfigurieren** öffnen. Der Dialog enthält die bisherigen Zuordnungen. Temperatur, Niederschlag, stündliche Wettervorhersage, Ventil und Laufzeit-Entität können dort geändert werden. Die Integration muss dafür nicht gelöscht oder neu angelegt werden.

Beim Speichern werden die Datenquellen geprüft: Temperatur muss eine endliche Zahl in °C, °F oder K sein; Niederschlag muss die nicht negative Tagessumme in mm, cm, m oder in liefern. Eine Regenrate wie mm/h ist ungeeignet. Die Wetter-Entität muss Stundenprognosen unterstützen und verwendbare Temperatur- und Niederschlagswerte im kommenden Zwölfstundenfenster liefern. Es werden keine Ventile zur Prüfung geöffnet.

Ein laufender Betrieb wird vor der Übernahme beendet. Scheitert das Stoppen oder Speichern, bleiben die bisherigen Zuordnungen bestehen und der Dialog zeigt einen Fehler. Unveränderte, während der Winterpause abgeschaltete Ventil-/Laufzeit-Entitäten verhindern den Wechsel der Wetterstation nicht. Anschließend lädt HA nur die bestehende Integration neu. Ihre Unique IDs, Einstellungen, Startzeit, Winterfreigabe und der Mindestabstand bleiben erhalten. Speichern mit unveränderten Werten löst keinen Reload aus.

**Wetterhistorie zurücksetzen** ist optional und standardmäßig aus. Bei vergleichbaren Messungen am selben Standort kann die Historie erhalten bleiben. Beim Wechsel des Standorts oder nicht vergleichbaren Messwerten die Option ausdrücklich einschalten. Sie setzt nur die wetterbezogene Tageshistorie und das heutige gespeicherte Temperaturmaximum zurück; Bewässerungslogbuch, letzter Lauf und Einstellungen bleiben bestehen. Der Befehl gilt einmalig und löscht keine Recorder-Daten von Home Assistant.

Die Integration rechnet Sensor- und Vorhersagewerte intern in °C und mm um. Fehlende oder ungültige Regenmessung wird nicht mehr als 0 mm archiviert; die automatische Bewässerung pausiert dann. Bei allein ausgefallener Vorhersage und verwendbaren Messdaten bleibt der bisherige Messwert-Fallback möglich und wird als `fallback` angezeigt. Auch unvollständige oder veraltete Vorhersagen werden nicht als gültige Regenfreiheit dargestellt. Es wird mindestens ein brauchbarer Zeitpunkt im kommenden Zwölfstundenfenster geprüft; die Prognose muss nicht lückenlos zwölf Stunden abdecken.

Der letzte Lauf und das zuletzt gespeicherte Tagesmaximum werden mit Datum wiederhergestellt. Ältere Installationen übernehmen den letzten Lauf soweit möglich aus ihrem bisherigen Bewässerungslogbuch. Auch ein abgebrochener, bereits laufender Betrieb setzt den Mindestabstand. Das Tagesmaximum wird bei Speichern/Neuberechnung gesichert; ein harter Absturz zwischen Messwert und Speicherung kann den letzten noch nicht gespeicherten Höchstwert verlieren.

## Manuelle Wasserentnahme

„Wasser manuell öffnen“ setzt die Gerätelaufzeit standardmäßig auf 240 Minuten. Bei aktiver Sicherheitsabschaltung wird nach Ablauf geschlossen. Ist die Sicherheitsabschaltung deaktiviert, bleibt das Ventil geöffnet, bis „Sofort stoppen“ gedrückt oder anderweitig geschlossen wird.

## Winterpause / Bewässerung freigeben

Der zusätzliche Schalter **Bewässerung freigeben** ist der Hauptschalter für das konfigurierte Ventil. Bei bestehenden Installationen ist er zunächst eingeschaltet, damit das bisherige Verhalten erhalten bleibt.

- **Aus:** Automatische und manuelle Starts sind gesperrt. Ein laufender Betrieb wird abgebrochen, auch während der Versickerungspause und bei deaktivierter Sicherheitsabschaltung. Ein Schließbefehl wird an das Ventil gesendet.
- Wetterabfragen, Tagesarchivierung, Vorberechnung, Empfehlungen und Anzeigen laufen weiter. Eine empfohlene Laufzeit größer null ist während der Sperre deshalb normal.
- Der Zustand bleibt nach einem HA-Neustart oder Neuladen erhalten. Meldet das Ventil bei aktiver Sperre `open` oder `opening`, sendet die Integration erneut einen Schließbefehl. Das gilt auch für eine gemeldete Öffnung durch andere Steuerungen.
- **Ein:** Die Bewässerung ist wieder freigegeben. Es startet kein Lauf unmittelbar durch das Einschalten. Die normale Startzeit, Automatik-Einstellung und übrigen Bedingungen gelten weiterhin; manuelle Starts sind wieder möglich.
- **Automatik** bleibt ein eigener Schalter: Er steuert nur automatische Starts. Die Winterpause sperrt zusätzlich die manuelle Wasserentnahme.
- Bei fehlgeschlagenem Schließbefehl bleibt die Sperre gespeichert; Status `stop_failed` und „Nächste Aktion“ zeigen den Fehler. Erneutes Ausschalten oder **Sofort stoppen** wiederholt den Schließversuch.

Bedienung: **Einstellungen → Geräte & Dienste → Bewässerungsautomatik → Gerät → Bewässerung freigeben** ausschalten oder die neue Kachel im mitgelieferten Dashboard verwenden. Die erwartete Entity-ID ist `switch.bewasserungsautomatik_bewasserung_freigeben`; falls HA eine andere ID vergeben hat, die vollständige Dashboard-Datei entsprechend anpassen.

Die Sperre arbeitet in Home Assistant. Sie kann bei ausgeschaltetem HA, fehlender Verbindung oder unzutreffender Ventilrückmeldung keinen Wasserfluss verhindern. Das Ventil muss erreichbar sein; der Schließbefehl ist keine physische Bestätigung. Für eine dauerhaft stillgelegte Winterleitung den Wasseranschluss zusätzlich am Gerät beziehungsweise Absperrhahn sichern.

## Dashboard

`dashboard/bewässerungsautomatik.yaml` als manuelle Karte einfügen. Home Assistant kann Entity-IDs abhängig von Sprache und bereits vorhandenen Entitäten abweichend erzeugen; diese gegebenenfalls einmalig anpassen.

## Logo

Das Repository enthält SVG- und PNG-Dateien. Ein Logo in der Home-Assistant-Integrationsübersicht wird bei öffentlichen Integrationen über das separate Home-Assistant-Brands-Repository bereitgestellt; die Dateien hier sind dafür vorbereitet.

## Hinweise

Die Regen- und Temperaturhistorie wird ab Installation aufgebaut. In den ersten Tagen ist die Datenqualität daher als Fallback gekennzeichnet. Die Startzeit ist standardmäßig 05:00 Uhr und kann über die Time-Entität direkt im Dashboard geändert werden. Die Vorberechnung erfolgt automatisch zehn Minuten vorher. Für Benachrichtigungen wird der vollständige Dienstname eingetragen, zum Beispiel `notify.mobile_app_mein_handy`; anschließend wird der Schalter „Benachrichtigungen“ aktiviert.


## Ereignisgesteuerte Neuberechnung

Die empfohlene Bewässerungszeit wird zusätzlich zur täglichen Vorberechnung automatisch aktualisiert:

- bei einer Temperaturänderung von mindestens 2 °C,
- bei einer Niederschlagsänderung von mindestens 0,1 mm,
- bei einer Aktualisierung von `weather.koln_bonn`,
- nach dem täglichen Archivieren der Messwerte,
- sowie unmittelbar nach Änderungen an den Einstellungen.

Mehrere kurz aufeinanderfolgende Änderungen werden fünf Sekunden lang gesammelt und anschließend gemeinsam berechnet. Die automatische Bewässerung startet dadurch nicht zusätzlich; sie bleibt auf den eingestellten täglichen Startzeitpunkt begrenzt.
