# Bewässerungsautomatik

![Logo](images/logo_256.png)

Wetterabhängige Pflanzenbewässerung für Home Assistant. Version 1.0 ist auf ein **Blumenbeet mit sonnigem Standort und Mikrosprühern** abgestimmt.

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

Die Regen- und Temperaturhistorie wird ab Installation aufgebaut. In den ersten Tagen ist die Datenqualität daher als Fallback gekennzeichnet. Die Startzeit ist in Version 1.0 auf 05:00 Uhr festgelegt. Änderungen an der Startzeit sind für eine spätere Options-Flow-Version vorgesehen.
