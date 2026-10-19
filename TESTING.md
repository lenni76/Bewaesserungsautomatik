# Tests der Version 1.2.0

Stand: 19. Oktober 2026. Die Tests laufen lokal mit echten Home-Assistant-Python-APIs und simulierten Wetter-/Ventilaktionen. Ein physisches RainPoint-Ventil wird nicht angesprochen.

Getestete Umgebungen:

| Umgebung | Version | Ergebnis |
| --- | --- | --- |
| Python | 3.14.8 | Beide Umgebungen |
| Home Assistant stabil | 2026.10.2 | 91 bestanden, Prozessende erfolgreich (Exit 0) |
| Home Assistant Entwicklung | 2026.11.0.dev0, Commit `87604108eedfd953d71f339e91bca46fdafbc704` | 91 bestanden, Prozessende erfolgreich (Exit 0) |

Die beiden in 1.1.0 noch erwarteten Fehlschläge sind behoben und bestehen jetzt regulär: Wiederherstellung von `last_run` und Zurückweisung ausschließlich vergangener Vorhersagen. Es gibt keine erwarteten Fehlschläge mehr.

## Wiederholen

In einer separaten Python-3.14-Umgebung aus dem Repository-Verzeichnis:

```sh
python -m pip install -r requirements-test.txt homeassistant==2026.10.2
python -m pytest -q -rx
```

Für den genau geprüften Entwicklungsstand in einer zweiten Umgebung:

```sh
python -m pip install -r requirements-test.txt 'homeassistant @ git+https://github.com/home-assistant/core.git@87604108eedfd953d71f339e91bca46fdafbc704'
python -m pytest -q -rx
```

Die Python-Anforderung künftig gegen die Metadaten der jeweiligen HA-Version prüfen. Das vorhandene Ruff-Ziel `py313` ist eine Syntax-Untergrenze für den Integrationscode, keine Festlegung der HA-Laufzeit.

## Prüfumfang

- Alle Integrationsmodule importieren, Config-Flow-Formular mit echten HA-Selektoren validieren, sieben Entitätsplattformen erzeugen.
- Neue Freigabe über Switch-Entität, automatische und manuelle Starts, Ausschalten während Lauf/Versickerungspause sowie während wartender Geräteaktionen.
- Persistenz der Wintersperre mit echtem HA-Store und neu erzeugtem Koordinator.
- Schließfehler, Speicherfehler, fehlgeschlagene Laufzeiteinstellung und sichtbarer Fehlerstatus.
- Gemeldete externe Öffnung bei aktiver Sperre, Laden bei offenem Ventil und explizites Entladen eines laufenden Koordinators.
- Fortgesetzte Berechnung, Tagesarchivierung und Vorberechnung trotz Wintersperre.
- Zwölf Kalenderstände November 2026 bis Oktober 2027, jeweils mit und ohne Wintersperre; Referenzlaufzeiten über alle Jahreszeiten.
- Keine sofortige Bewässerung beim Wiedereinschalten; bestehender Automatik-Schalter bleibt unabhängig.
- Erstkonfiguration und HA-Reconfigure mit echten ConfigEntry-Objekten und HA-Update-/Reload-Helfer: gleicher Eintrag, Vorbelegung, keine Änderung bei Validierungsfehler, kein Reload bei unveränderten Werten.
- Prüfung neuer Quellen auf Zahlenwerte, Einheiten und Stundenforecast; °F/K sowie Zoll/cm werden in °C/mm umgerechnet. Fehlende Regenmessung wird nicht als trocken gespeichert.
- Laufendes Ventil vor Änderung schließen; bei fehlgeschlagenem Stop bleiben die Zuordnungen bestehen. Unveränderte offline Aktoren dürfen während der Winterpause weiter zugeordnet bleiben.
- Wetterhistorie wahlweise erhalten oder ausdrücklich einmalig zurücksetzen; Einstellungen, Wintersperre, Laufprotokoll und letzter Lauf bleiben bestehen. Alte Temperatur-Listener werden ersetzt.

Die Reconfigure-Tests starten HA nur teilweise. Deshalb sind das tatsächliche Laden der Aktorplattformen und der automatische Schreibauftrag des HA-eigenen ConfigEntry-Stores ersetzt. Die HA-Methoden zum Ändern des bestehenden Eintrags und Anfordern des Reloads werden real ausgeführt; Reload-Anforderungen werden aufgezeichnet. Die integrationseigene Store-Persistenz wird zusätzlich mit echten temporären Dateien getestet.

Während der Entwicklung gab es im unvollständigen Testaufbau beim Beenden des stabilen Core-Testprozesses einen nativen Python-Absturz, obwohl die Assertions bestanden. Mit ersetzt gehaltenem HA-internem ConfigEntry-Schreibauftrag in diesem Teilaufbau beendet sich die vollständige Suite sauber. Das ist eine Korrektur des Testaufbaus; die genaue native Absturzursache wurde nicht abschließend bestimmt. Im Integrationscode wurde dafür keine Umgehung eingebaut.

Die Tests ersetzen keinen Probelauf mit dem echten Ventil und keinen vollständigen HAOS-/Frontend-Test. Keine VM, kein Supervisor und kein Browser-Dashboard wurden dafür gestartet. Die zwölf Kalenderstände sind keine Tests von zwölf zukünftigen Softwareversionen.

In beiden HA-Umgebungen entsteht eine DeprecationWarning aus dem HA-eigenen HTTP-Modul (`HomeAssistantApplication`). Sie kommt nicht aus der Bewässerungsintegration.

Die geänderten Python-Dateien und alle Tests bestehen `ruff check`; `git diff --check` ist ebenfalls sauber. Ein vollständiges `ruff check .` findet weiterhin Bestandsmeldungen in unberührten Dateien, insbesondere kompakte Mehrfachanweisungen und Importreihenfolge. Diese sind separat zu bereinigen.

## Empfohlene laufende Kompatibilitätsprüfung

Als nächster Schritt bietet sich eine GitHub-Actions-Matrix für die jeweils aktuelle stabile HA-Version, die nächste Beta und den Entwicklungszweig an. Tests bei jedem Pull Request und wöchentlich ausführen; hassfest/HACS-Validierung ergänzen. Die behauptete Mindestversion aus `hacs.json` separat prüfen. Es wurde hier keine wiederkehrende Automation eingerichtet und keine CI-Datei veröffentlicht.
