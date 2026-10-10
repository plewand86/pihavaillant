# Analiza dostarczonych danych

Źródło: załącznik `Wklejony tekst.txt` odzyskany z powiązanej rozmowy.
Eksport ma datę `2026-10-10T08:11:59.354686+02:00`, `force: true`,
167 wiadomości, 123 ze statusem `ok`, 44 ze statusem `error`.
Oryginał zapisano w `tests/fixtures/ebusd-export.json`.

| Odczyt | Wynik | Sposób obsługi |
|---|---|---|
| FlowTemp.temp | 45.69 °C, sensor=ok | Temperatura zasilania |
| ReturnTemp.temp | 42.12 °C, sensor=ok | Temperatura powrotu |
| ReturnTemp.tempmirror | 64861 °C | Pominięty, bez automatycznej naprawy |
| StorageTemp.temp | 37.31 °C, sensor=ok | Temperatura zasobnika |
| HwcTemp.temp | 116.06 °C, sensor=circuit | Niedostępny czujnik |
| Expertlevel_ReturnTemp | -1.81 °C, sensor=cutoff | Poza listą publikowanych parametrów |
| WaterPressure.press | 1.532 bar | Ciśnienie |
| Flame | off | Płomień wyłączony, poprawny stan |
| FanSpeed | 0 rpm | Poprawne zero |
| FanMinSpeedOperation | 2130 rpm | Diagnostyka, odczyt co 5 minut |
| ModulationDesired | 0 % | Zadana modulacja; nie pomiar mocy |
| PumpPower | 0, bez jednostki | Surowa wartość bez jednostki |
| HcHours / HwcHours | 4787 / 1653 h | Liczniki całkowite czasu pracy |
| HcStarts / HwcStarts | 1800 / 6600 | Liczniki startów zgodnie z dekodowaniem ebusd |
| Currenterror | pięć pól `-` | Brak kodów błędów; null w JSON rozstrzygany przez raw |
| PowerValue / PrEnergySum* | błędy dekodowania | Brak encji mocy/energii |

Wybór parametrów jest jawny. Integracja nie tworzy encji z wszystkich 167
rejestrów, ponieważ część reprezentuje ustawienia, wartości wewnętrzne lub
niepoprawne dekodowanie. Jedna próbka nie pozwala potwierdzić dokładności
liczników, przepełnień lub przeliczników dla każdego modelu ecoTEC.

Plik jest materiałem testowym, nie strumieniem danych. Panel produkcyjny
łączy się bezpośrednio z ebusd i nie odtwarza tej próbki jako bieżącej telemetrii.
