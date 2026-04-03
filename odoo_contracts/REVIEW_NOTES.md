# Vertragsverwaltung Review

Stand: 2026-04-03

## Gesamtbild

Das Modul ist bereits deutlich naeher an einer echten Vertragsverwaltung als ein reines CRUD-Modul.
Positiv sind vor allem:

- Vertragsnummern, Status, Laufzeiten und Verlaengerung
- Erinnerungen und Aktivitaeten
- Dokumente mit OCR-Ansatz
- Timeline/Chatter fuer Nachvollziehbarkeit

## Priorisierte Verbesserungen

1. Kritisch: `ocr_text_combined` verweist auf eine fehlende Compute-Methode.
2. Hoch: Erinnerungen sind nicht per SQL eindeutig abgesichert.
3. Hoch: Automatische Verlaengerung rollt ueberfaellige Vertraege nur um eine Periode weiter.
4. Hoch: Berechtigungen sind fuer eine echte Vertragsverwaltung noch zu breit.
5. Mittel: Die Formularansicht zeigt effektiv nur ein sichtbares Vertragsdokument, obwohl Versionierung vorhanden ist.

## Fachliche Empfehlungen

- Vertragswert, Kostenstelle, Waehrung und Zahlungsintervall ergaenzen
- Kuendigungsart, Mindestlaufzeit und Verlaengerungslogik fachlich genauer modellieren
- Record Rules nach Abteilung, Verantwortlichem oder Gesellschaft einfuehren
- Freigabeprozess fuer neue oder geaenderte Vertraege ergaenzen
- Dokumentversionen getrennt von "im Vertrag sichtbar" modellieren
- Tests fuer Cronjobs, Erinnerungen und Statuswechsel nachziehen
