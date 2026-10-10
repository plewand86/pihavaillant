# Weryfikacja wydania 0.3.0 — 2026-10-10

## Wykonane lokalnie

- CTLV2: odczyt pokojowy 24,1°C, walidacja błędnych wartości, rozdzielenie
  obiegów sterownika i kotła, awaria sterownika bez utraty odczytów kotła.
- Historia pokojowa zachowuje poprzednie rekordy bez nowego pola i przerwy w danych.
- Panel 0.3.0: kafelek 24,1°C i osobny wykres w zakresie 6 h; brak błędów JavaScript.

- 23 testy unittest: wszystkie zakończone poprawnie na Pythonie 3.12.14.
- Testy historii obejmują pełny cykl, timeout, długą przerwę, restart podczas
  pracy, przycinanie do zakresu, brak dopisywania czasu po ostatniej próbce,
  cofnięcie zegara, retencję i ograniczenie liczby próbek temperatur.
- Parser sprawdzony na rzeczywistym załączniku (167 wiadomości, 123 poprawne,
  44 błędy). Porównano wynik importu JSON z parsowaniem surowych odpowiedzi ebusd.
- Sprawdzono błędny czujnik, wartości spoza zakresu, niezgodne jednostki, braki,
  zera, `off`, kody błędów i brak kodów.
- Lokalny serwer TCP sprawdził polecenie read, fragmentowaną odpowiedź,
  timeout i odrzucenie nazwy zawierającej dodatkowe polecenie.
- Sprawdzono niezależność odczytów, wyliczanie różnicy temperatur i wolniejszy
  harmonogram liczników, a także unieważnienie temperatur po awarii transportu.
- Testy MQTT objęły strukturę Discovery, unikalność identyfikatorów,
  brak command_topic oraz niedostępność i odzyskanie poprawnego odczytu.
  Publikację sprawdzano za pomocą obiektu testowego, bez rzeczywistego brokera.
- Testy HTTP: odczyt panelu i API, odrzucenie POST oraz połączeń spoza Ingress,
  brak danych dostępowych w odpowiedzi.
- Panel sprawdzono w przeglądarce z lokalnym serwerem demonstracyjnym i
  syntetycznymi cyklami palnika. Sprawdzono zakres 6 h, własny przedział 04:00–05:00,
  wybór cyklu i jego opis, brak błędów JavaScript, szerokości 1360 i 390 px.
  Strona nie przepełnia ekranu telefonu; szeroki schemat i tabele przewijają się
  we własnych kontenerach. Zrzuty pokazują dane demonstracyjne, nie odczyt kotła.
- Parsowanie plików YAML zakończone poprawnie.

## Wymaga sprawdzenia na docelowym środowisku

Nie było dostępu do Home Assistant, rzeczywistego brokera MQTT, kotła ani silnika
Docker. Nie przeprowadzono budowania obrazu ani instalacji w HA. Szablon `docs/github-actions-test.yml` zawiera testy i budowanie Docker. Aby
włączyć GitHub Actions, skopiuj go do `.github/workflows/test.yml` z użyciem
dostępu z uprawnieniem Workflows. Automatyzacja nie jest obecnie aktywna.

Po instalacji sprawdź:

1. Panel Ingress i utworzenie urządzenia z encjami w integracji MQTT.
2. Zgodność temperatur i stanów z `ebusctl read -V -f -c bai ...`.
3. Przejście encji w unavailable po przerwaniu połączenia i powrót po przywróceniu.
4. Ponowne wykrycie encji po restarcie brokera/HA i brak duplikatów po restarcie dodatku.
5. Dashboard oraz historię zapisującą się przez kilka cykli pracy kotła.

Wersja jest gotowa do instalacji próbnej, ale powyższe testy lokalne nie stanowią
potwierdzenia działania na konkretnej instalacji HA.
