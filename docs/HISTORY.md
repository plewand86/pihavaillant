# Historia palnika od wersji 0.2.0

## Co pokazuje panel

- Schemat kotła, pompy obiegowej, ogrzewania, cyrkulacji i zasobnika CWU.
- Temperatury na schemacie, modulację zadaną, wentylator i stan płomienia.
- Wykres pracy palnika z wyborem 6 godzin, 24 godzin, 7 dni lub własnych dat.
- Godziny wykrycia zapłonu i wyłączenia, czas pracy w wybranym przedziale,
  rozróżnienie kompletnych cykli, niepełnych odcinków i pracy w toku.
- Czas pracy łącznie, wykryte zapłony, pokrycie historii oraz czas bez danych.

## Jak liczymy czas

`Flame` jest odczytywany bez cache co około 5 s. Odczyty są wykonywane
sekwencyjnie wraz z innymi parametrami; czas odpowiedzi ebusd może wydłużyć odstęp.
Zmianę stanu zapisujemy przy odebraniu odpowiedzi, więc zapłon mógł wystąpić
między poprzednim a bieżącym odczytem. Cykl krótszy niż odstęp odczytów może
pozostać niezauważony. Czas pracy jest estymacją na podstawie tych obserwacji.

Przykład: OFF o 10:00:00, ON o 10:00:05, ON o 10:00:10, OFF o 10:00:15.
Panel pokaże wykryty start 10:00:05, wykryte wyłączenie 10:00:15 i 10 s pracy.
Między poprawnymi obserwacjami przyjmujemy utrzymanie poprzedniego stanu do
następnej obserwacji. Nie oznacza to gwarancji, że pomiędzy nimi nie było innych zmian.

Timeout, błąd odczytu, restart procesu albo zbyt długa przerwa kończy odcinek
na **ostatnim potwierdzonym odczycie**. Nie liczymy czasu przez taką lukę.
Granica ciągłości wynosi `5 + 2 × timeout + 2` sekund (domyślnie 17 s).
Trwający odcinek również liczymy wyłącznie do ostatniego odczytu, bez dopisywania
pracy do bieżącej godziny. Błędy nie oznaczają OFF.

Jeśli pierwszym odczytem po starcie/awarii jest ON, znamy tylko fragment pracy.
Nie dodajemy wtedy wykrytego zapłonu. Licznik zapłonów obejmuje wyłącznie
zaobserwowane przejścia OFF → ON bez luki w odczytach. Może różnić się od
fabrycznych liczników CO/CWU. Przy cofnięciu zegara próbki nie są doliczane,
dopóki zegar nie przekroczy ostatnio zapisanego czasu.

Cykl przecinający granicę wybranego zakresu jest przycinany do zakresu przy
sumowaniu czasu. Tabela zachowuje znane granice całego odcinka, a kolumna
„Czas w zakresie” pokazuje tylko pokrywającą się część.
Godziny wyświetlane są w strefie czasowej przeglądarki; obliczenia używają czasu UTC.

## Trwałość i ograniczenia

Baza `/data/<device_id>.sqlite3` (SQLite WAL) zawiera odcinki palnika i próbki
temperatur, automatycznie czyszczone z danych starszych niż 90 dni. Długotrwały
odcinek przecinający granicę retencji może zaczynać się wcześniej. Nie zmieniaj
device_id, jeśli chcesz zachować dostęp do tej samej bazy.
Backup dodatku powinien obejmować `/data`. Nie odinstalowuj dodatku w celu aktualizacji.
Nie kopiuj samego pliku SQLite podczas zapisu — zatrzymaj dodatek przed ręczną kopią,
albo użyj backupu HA.

Historia zaczyna się po instalacji wersji 0.2.0. Nie da się odtworzyć wcześniejszych
cykli z pojedynczego eksportu JSON czy licznika godzin. Dotychczasowe dane HA
Recorder pozostają dostępne w historii HA, ale nie są automatycznie importowane.

Jedno zapytanie obejmuje do 7 dni. Wykres palnika pokazuje maksymalnie 5000 ostatnich
odcinków, tabela 200 ostatnich odcinków ON; komunikat informuje o ograniczeniu.
Podsumowania SQL obejmują cały wybrany zakres. Wykres temperatur wybiera do około
800 rzeczywistych próbek (ostatnia próbka w każdym przedziale czasu). Jest wykresem
poglądowym; krótsze przerwy między wybranymi próbkami mogą być niewidoczne.
Sam wykres palnika nie jest uśredniany.

## Podział CO / CWU (0.4.0)

Podczas pracy płomienia odczytywany jest `bai PositionValveSet` bez pamięci podręcznej.
Według definicji dla BAI HW7603: 0 = CO, 100 = CWU, 40 = pozycja pośrednia.
Źródło: https://ebus.github.io/en/vaillant/bai.0010043897.inc.
Tylko 0 i 100 klasyfikują pracę; inne wartości i błędy oznaczają tryb nieustalony.
CO opisano jako podłogówkę zgodnie z instalacją użytkownika; pomiar nie rozdziela
wielu odbiorników CO. Żądanie CWU samo w sobie nie dowodzi grzania zasobnika.

Panel sumuje czas podłogówki, CWU i nieustalony do łącznego czasu palnika.
Zmiana zaworu podczas pracy dzieli odcinki bez naliczania kolejnego zapłonu.
Czasy są momentami wykrycia w kolejnych odczytach, a nie pomiarem fizycznego
przełączenia co do sekundy. Odczyty płomienia i zaworu są sekwencyjne.
Stare dane pozostają w bazie jako tryb nieustalony; nie są klasyfikowane wstecz.
W HA pojawia się sensor `sensor.pihavaillant_boiler_burner_mode`
(`heating`, `dhw`, `unknown`, `off`) i diagnostyka `valve_position`.
Aktualizacja dodatku zachowuje konfigurację i archiwum.
