# Changelog

## 1.2.0 – 2026-10-19

- Neuer HA-Reconfigure-Dialog zum Wechsel der Sensor-, Wetter-, Ventil- und Laufzeit-Zuordnungen.
- Bestehender Integrationseintrag, Unique IDs, Einstellungen und Winterfreigabe bleiben erhalten; HA lädt die Integration nach dem Speichern neu.
- Quellenprüfung mit Feldfehlermeldungen und optionaler, einmaliger Rücksetzung ausschließlich der Wetterhistorie.
- Laufender Betrieb wird vor Übernahme beendet; neue Starts bleiben während des Wechsels gesperrt. Kein unnötiger Reload bei unveränderten Daten.
- Letzten Bewässerungslauf und gespeichertes Tagesmaximum persistent gemacht; Mindestabstand überlebt Neustart und Neukonfiguration. Migration aus älteren Laufprotokollen.
- Veraltete, ungültige oder fehlende Vorhersagedaten werden nicht mehr als gültige Regenfreiheit bewertet. Fehlende Regenmessung sperrt die Automatik und wird nicht als trockener Tag archiviert.
- Umrechnung von Sensor- und Prognosewerten nach °C und mm; Prozent-Einheit mit neuem HA-Enum und Import-Fallback aktualisiert.
- Funktionstests für Erstkonfiguration, Quellenwechsel, Einheiten, Fehlerfälle, Wiederherstellung und Wintermodus ergänzt.

## 1.1.0 – 2026-10-19 (in 1.2.0 enthalten)

- Neuer dauerhafter Hauptschalter „Bewässerung freigeben“ für Winterpausen.
- Aus stoppt laufende automatische und manuelle Bewässerung und sperrt jeden neuen Start sowie das Wiederöffnen nach einer Versickerungspause.
- Wetterauswertung, Historie und Berechnungen laufen weiter. Einschalten startet keinen Lauf.
- Gespeicherte Sperre wird beim Laden und bei gemeldeter Ventilöffnung erneut durchgesetzt; Schließfehler werden sichtbar.
- Start/Stop-Abläufe gegen zeitgleiches Ausschalten abgesichert; abgebrochene Aufgaben werden vor dem nächsten Start abgewartet.
- Dashboard um Freigabeschalter und Winterhinweis ergänzt; Tests für Sperre und laufende Aufgaben hinzugefügt.

## 1.0.3

- Ereignisgesteuerte Neuberechnung bei Temperaturänderungen ab 2 °C.
- Neuberechnung bei Niederschlagsänderungen ab 0,1 mm.
- Neuberechnung bei Aktualisierungen der Wetter-Entität.
- Neuberechnung nach dem täglichen Archivieren der Messwerte.
- Änderungen an Einstellungen berechnen die Empfehlung weiterhin sofort neu.
- Fünf Sekunden Entprellung verhindert unnötige Mehrfachberechnungen.


## 1.0.2 - 2026-08-04

- Korrigiert die Erstinstallation ohne vorhandene Regenhistorie.
- Ein trockener aktueller Tag wird nun zunächst als ein trockener Tag bewertet, statt den Trockenheitsfaktor fälschlich auf 0 zu setzen.
- Dadurch kann die Automatik bereits vor dem ersten gespeicherten Tageswechsel eine sinnvolle Laufzeit berechnen.

## 1.0.1 - 2026-08-04

- Einstellbare Startzeit als native Home-Assistant-Time-Entität, Standard 05:00 Uhr.
- Automatische Vorberechnung zehn Minuten vor der Startzeit, Standard 04:50 Uhr.
- Vollständige Schlussprüfung direkt zur Startzeit vor dem Öffnen des Ventils.
- Neue Sensoren für nächste Aktion, geplanten Start und letzte Vorberechnung.
- Laufende Aktualisierung der verbleibenden Minuten.
- Optionales Benachrichtigungssystem mit frei eintragbarem Home-Assistant-Dienst.
- Dashboard um Startzeit, nächste Aktion, Restlaufzeit und Benachrichtigungen erweitert.
- Migration vorhandener 1.0.0-Einstellungen auf das neue Startzeitformat.

## 1.0.0 - 2026-08-04

- Erste vollständige Version der Bewässerungsautomatik.
- Blumenbeet/Sonnig als Standardprofil.
- Wetter-, Regen-, Temperatur-, Sicherheits- und manueller 4-Stunden-Modus.
