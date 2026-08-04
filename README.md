# Bewässerungsautomatik

![Logo](images/logo_256.png)

Wetterabhängige Pflanzenbewässerung für Home Assistant. Version 1.0.3 ist auf ein **Blumenbeet mit sonnigem Standort und Mikrosprühern** abgestimmt.

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

## Manuelle Wasserentnahme

„Wasser manuell öffnen“ setzt die Gerätelaufzeit standardmäßig auf 240 Minuten. Bei aktiver Sicherheitsabschaltung wird nach Ablauf geschlossen. Ist die Sicherheitsabschaltung deaktiviert, bleibt das Ventil geöffnet, bis „Sofort stoppen“ gedrückt oder anderweitig geschlossen wird.

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
