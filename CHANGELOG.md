# Changelog

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
