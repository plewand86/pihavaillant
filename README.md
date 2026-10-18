# PiHA Vaillant

**Wersja 0.6.0:** sterownik pokojowy CTLV2 w panelu z możliwością czasowej zmiany nastawy Quick Veto.
W HA odśwież repozytoria w sklepie dodatków, otwórz PiHA Vaillant i wybierz
**Aktualizuj**. Zachowano slug i identyfikatory encji; nie trzeba dodawać
integracji ponownie. Nowa historia zaczyna być zbierana po aktualizacji.

Dodatek Home Assistant do wizualizacji Vaillant ecoTEC plus przez działający **ebusd**.
Odczytuje dane z portu TCP ebusd i tworzy encje MQTT Discovery. Zawiera polski
panel Ingress ze schematem kotła, pomp i zasobnika, trwałą historię palnika,
wykres temperatur, diagnostykę oraz dashboard Lovelace bez dodatkowych kart HACS.

Panel pozwala zmienić tylko temperaturę Quick Veto strefy 1 i czas jej obowiązywania.
Nie udostępnia dowolnych poleceń eBUS ani sterowania przez MQTT. Aktywne zapytania
`read` oraz ograniczone zapisy Quick Veto wysyłają żądania na magistralę eBUS.

## Architektura i pochodzenie

Wzorzec: lokalne repo `pihaalpr` i https://github.com/plewand86/pihaalpr.
Zachowano układ repozytorium dodatków (`repository.json`, katalog aplikacji,
`config.yaml`, Dockerfile), FastAPI, Ingress, `/data/options.json` i pobieranie
parametrów MQTT z Supervisora. Kod napisano osobno; nie skopiowano funkcji LPR,
wywoływania usług HA, danych kamer ani historii Git.

Panel jest lekkim HTML/CSS/JS, bez procesu budowania React/Vite. Od wersji 0.2.0
historia palnika i temperatur jest zapisywana w SQLite w `/data/<device_id>.sqlite3`
z retencją 90 dni; przetrwa restart i aktualizację dodatku. HA Recorder niezależnie
zapisuje historię encji MQTT.
To **dodatek + integracja MQTT**, nie `custom_components` ani integracja HACS.

```
Vaillant ← zapytania read ← ebusd:8888 ← PiHA Vaillant → MQTT → encje HA
                                                └→ panel Ingress
```

## Instalacja lokalna w Home Assistant OS

1. Potrzebny jest działający ebusd ze zgodnymi definicjami Vaillant, osiągalny
   z sieci dodatków. Sprawdź na jego hoście: `ebusctl read -V -f -c bai FlowTemp`.
   TCP 8888 to port ebusd, nie port adaptera eBUS ani HTTP ebusd.
2. Zainstaluj i uruchom Mosquitto Broker oraz skonfiguruj integrację **MQTT** w HA.
3. Skopiuj **wewnętrzny katalog `pihavaillant/`**, zawierający `config.yaml` i Dockerfile,
   do `/addons/pihavaillant` na hoście HA. Nie kopiuj tam całego repozytorium.
4. W sklepie dodatków wybierz sprawdzenie aktualizacji/odświeżenie. W sekcji
   lokalnych dodatków zainstaluj **PiHA Vaillant**. Budowanie wymaga internetu.
5. W konfiguracji wpisz `ebusd_host` (IP/DNS serwera ebusd) oraz właściwy port.
   `127.0.0.1` wskazuje kontener dodatku, a nie maszynę z ebusd.
6. Przy Mosquitto zarządzanym przez HA zostaw `mqtt_host` puste. Dane dostępowe
   zostaną odczytane z Supervisora. Przy zewnętrznym brokerze wpisz host, port,
   użytkownika i hasło. Włącz `mqtt_tls` tylko gdy broker obsługuje TLS;
   certyfikat musi być zaufany przez system.
7. Uruchom dodatek, otwórz interfejs webowy i sprawdź diagnostykę. Pierwszy cykl
   może trwać do około 3 minut przy timeoutach. Encje pojawią się pod urządzeniem
   **Vaillant boiler** w integracji MQTT. Włącz automatyczny start dodatku.

## Instalacja z GitHub

W sklepie dodatków HA otwórz menu → Repozytoria i dodaj:

```
https://github.com/plewand86/pihavaillant
```

Odśwież sklep, wybierz **PiHA Vaillant**, zainstaluj i skonfiguruj zgodnie
z krokami 5–7 powyżej. Repozytorium zawiera Dockerfile, więc HA buduje obraz
podczas instalacji. Jeśli tworzysz własny fork, popraw adresy w `repository.json`
i `pihavaillant/config.yaml`.

## Konfiguracja

| Pole | Domyślnie | Znaczenie |
|---|---|---|
| ebusd_host | puste | Adres działającego ebusd; wymagany do odczytów |
| ebusd_port | 8888 | Port TCP protokołu poleceń ebusd |
| circuit | bai | Obwód z wiadomościami kotła |
| poll_interval | 30 s | Cykl 15–300 s; odczyty sekwencyjne, bez nakładania cykli |
| timeout | 5 s | Limit pojedynczego odczytu (1–15 s) |
| device_id | boiler | Stabilny identyfikator urządzenia: małe litery, cyfry, `_` |
| mqtt_host | puste | Puste = automatyczna konfiguracja Supervisor |
| mqtt_port | 1883 | Port brokera; zwykle 8883 dla TLS |
| mqtt_username/password | puste | Dane brokera zewnętrznego |
| mqtt_tls | false | TLS z weryfikacją certyfikatu |

Po zmianie opcji zrestartuj dodatek. Nie zmieniaj `device_id` bez potrzeby:
zmieni to identyfikatory i tematy Discovery. Każda równoległa instancja musi mieć
inny identyfikator. Prefiks Discovery to standardowe `homeassistant`.

## Odczyty i jakość danych

Temperatury: zasilanie, powrót, różnica temperatur, zasobnik CWU, czujnik CWU,
zewnętrzna, zadana zasilania i zasobnika. Ponadto: ciśnienie, płomień,
zapotrzebowanie CWU, blokada, pompa cyrkulacyjna, stan i tryb pompy, wentylator
(obroty, zadane i minimalne), modulacja zadana, surowe wysterowanie pompy,
przepływ obiegu, godziny i starty CO/CWU/wentylatora/pompy.
Diagnostyka: bieżące kody błędów, liczba niedostępnych odczytów i czas zakończenia cyklu.

- `temp` i `press` są wybierane jawnie, pole `tempmirror` jest pomijane.
- `sensor` inne niż `ok`, `valid_for_metrics=false`, brak wartości, niewłaściwa
  jednostka, NaN, nieskończoność i wartości poza zakresami dają **unavailable**.
  Zakresy są filtrami wiarygodności danych, nie progami alarmów lub zaleceniami eksploatacyjnymi.
- Zero i `off` są poprawnymi wartościami; błąd nigdy nie staje się zerem.
- `Currenterror` z samymi `-` oznacza brak kodów; błędy odczytu oznaczają brak danych.
- `HwcTemp` w próbce ma `sensor=circuit`: jest niedostępny. Do wizualizacji CWU
  służy poprawny `StorageTemp=37.31 °C`. Nie zastępujemy po cichu jednego czujnika drugim.
- `PowerValue` i `PrEnergySum*` nie są publikowane: próbka zawiera błędy dekodowania.
  Nie wyliczamy energii, gazu ani mocy cieplnej z obrotów/modulacji.
- `PumpPower` nie ma potwierdzonej jednostki w eksporcie, dlatego pozostaje bez jednostki.
- Płomień jest odczytywany aktywnie (bez cache, `-m 0`) co około 5 sekund,
  między zapytaniami innych parametrów. Odczyty są sekwencyjne; timeout innego
  parametru może opóźnić kolejny odczyt płomienia. Nie wysyłamy równoległych zapytań.
- Liczniki i minimalne obroty są pobierane co 5 minut. Pozostałe odczyty co cykl,
  z przerwą 150 ms między zapytaniami. ebusd może zwrócić cache młodszy niż cykl
  (liczniki: 300 s). Błędy dekodowania są ponawiane po 5 minutach, timeouty co cykl.
- Publikacja MQTT ma LWT, dostępność dla każdej encji i `expire_after` zależne od
  maksymalnego czasu cyklu. Zerwane połączenie lub zawieszony proces nie zachowuje
  w HA starej wartości jako bezterminowo aktualnej. Data cyklu oznacza odczyt z
  ebusd, nie dokładny czas pomiaru na magistrali.
- Reconnect MQTT ponawia Discovery. Stany nie są retained; HA po restarcie czeka
  na następny cykl. Pomyślne wcześniejsze odczyty liczników mogą mieć do 5 min wieku.

## Dashboard

Panel Ingress zawiera schemat kotła, pompy obiegowej, ogrzewania i zasobnika.
Płomień i animacja pompy wynikają z odczytów, a przy braku danych są wygaszane.
Schemat jest poglądowy — nie dokumentuje rzeczywistego przebiegu rur ani
nie potwierdza jednoczesnego przepływu przez oba obiegi.

**Historia palnika:** wybierz 6 h, 24 h, 7 dni lub własny przedział dat.
Pomarańczowe odcinki oznaczają pracę, niebieskie wyłączenie, kreskowane brak danych.
Kliknięcie odcinka pokazuje godziny i czas pracy. Tabela poniżej rozróżnia pełne
cykle, odcinki niepełne i pracę w toku. Podsumowanie pokazuje czas pracy w zakresie,
liczbę wykrytych zapłonów, pokrycie odczytami i czas bez danych.

Są to **czasy wykrycia z dokładnością ograniczoną częstotliwością odczytów**,
nie dokładne znaczniki zdarzeń z elektroniki kotła. Historia nie odtwarza się wstecz
z liczników HcHours/HwcHours. Szczegóły obliczeń: [docs/HISTORY.md](docs/HISTORY.md).

W HA utwórz pusty dashboard, przejdź do edytora surowej konfiguracji i wklej
`examples/dashboard.yaml`. Karty używają standardowych komponentów HA.
Przykład zakłada `device_id: boiler` i identyfikatory utworzone przez Discovery.
Sprawdź identyfikatory w Narzędziach deweloperskich → Stany: HA może zachować
wcześniejszą nazwę lub dodać sufiks przy kolizji. Dostosuj YAML w takim przypadku.
Historia wymaga aktywnego Recorder bez wykluczenia tych encji.

## Testy i uruchomienie bez HA

Python 3.12 lub nowszy:

```sh
python -m venv .venv
# Aktywuj środowisko zgodnie z systemem operacyjnym.
python -m pip install -r pihavaillant/requirements.txt httpx==0.28.1
python -m unittest discover -s tests -v
python tools/replay.py
```

`tools/replay.py [ścieżka-do-JSON]` analizuje format załączonego eksportu
`messages[].fields[]`. Działa offline i niczego nie publikuje. Snapshot testowy
jest rzeczywistym dostarczonym eksportem; nie jest używany przez działającą integrację.

Do pracy na komputerze skopiuj `examples/options.local.example.json` do
`options.local.json`, uzupełnij adresy, ustaw zmienną `PIH_OPTIONS` na bezwzględną
ścieżkę tego pliku, a następnie:

```sh
cd pihavaillant
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8090 --no-proxy-headers
```

Otwórz http://127.0.0.1:8090. Bez Supervisora panel akceptuje tylko localhost;
w HA tylko rzeczywisty adres proxy Ingress. Nagłówki proxy nie mogą podmienić IP.
Panel udostępnia wyłącznie odczytowe endpointy i zasoby, bez sekretów.
`/api/history` i `/api/burner` przyjmują `start`/`end` jako sekundy Unix UTC,
maksymalnie 7 dni na zapytanie. Lokalny katalog danych można zmienić zmienną
`PIH_DATA_DIR` (domyślnie `./data` bez Supervisora).
Dodatek nie wystawia portu na hoście i nie potrzebuje uprawnień do usług HA.

## Rozwiązywanie problemów

**Brak encji:** sprawdź MQTT, włączone Discovery i status połączenia w panelu.
**Encje unavailable:** tabela diagnostyki pokazuje błędy czujnika, dekodowania lub timeout.
**Brak połączenia ebusd:** sprawdź host, port, firewall i nasłuch ebusd na interfejsie
dostępnym dla dodatków. Nie wystawiaj portu sterowania ebusd do internetu.
**Nieobsługiwany parametr:** dopasuj definicje ebusd do modelu kotła; nie zmieniaj
wartości błędnych na zera. Nie każda wersja ecoTEC udostępnia wszystkie wiadomości.
**Usunięcie:** zatrzymaj dodatek i usuń urządzenie MQTT. Jeśli konfiguracje wracają,
usuń retained wiadomości Discovery danego urządzenia (pusty payload retained na
`homeassistant/<sensor lub binary_sensor>/pihavaillant_<device_id>/<key>/config`).

## Weryfikacja i źródła

Zakres lokalnych testów i ograniczenia: [docs/VALIDATION.md](docs/VALIDATION.md).
Analiza konkretnego eksportu: [docs/DATA.md](docs/DATA.md).
Protokół: https://github.com/john30/ebusd/wiki/3.1.-TCP-client-commands
Discovery: https://www.home-assistant.io/integrations/mqtt/
Ingress: https://developers.home-assistant.io/docs/apps/presentation/

## Temperatura pokojowa CTLV2 (od 0.3.0)

Dodatek odczytuje rzeczywistą temperaturę strefy 1 z `ctlv2 Z1RoomTemp`.
W dostarczonej liście eBUS sterownik CTLV2 udostępniał 24,1°C.
To pomiar pokojowy, nie temperatura zadana. Odczyt korzysta z tego samego
hosta i portu ebusd co kocioł, ale zawsze z obiegu `ctlv2`. Pozostaw `circuit: bai`
dla kotła. Nie trzeba dodawać kolejnego połączenia ani zmieniać konfiguracji.

Po aktualizacji i uruchomieniu dodatku MQTT Discovery dodaje sensor
`sensor.pihavaillant_boiler_room_temp` (dla domyślnego `device_id: boiler`; HA
może nadać inną nazwę przy konflikcie). Panel pokazuje kafelek i osobny wykres
pokojowy z tym samym zakresem czasu co palnik. Archiwum 90 dni zaczyna się
od pierwszego odczytu po aktualizacji; istniejąca historia kotła pozostaje.
Brak odpowiedzi, błędne dekodowanie, niedostępny czujnik lub wartość poza
zakresem -30…60°C daje niedostępność, nigdy zastępcze 0°C.

W razie braku pomiaru sprawdź `ebusctl read -V -f -c ctlv2 Z1RoomTemp`.
Oczekiwane pole w konfiguracji CTLV2 to `value`, np. `value=24.1 °C`.
Strefy 2 i 3 oraz temperatura zadana miały w dostarczonej liście `no data stored`;
nie są automatycznie traktowane jako aktywne czujniki.
Źródło definicji: https://ebus.github.io/en/vaillant/15.ctlv2.csv.

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


## Sterownik pokojowy w panelu (0.6.0)

Panel pokazuje temperaturę zmierzoną, aktywną nastawę i Quick Veto dla CTLV2 strefy 1.
Formularz pozwala ustawić `Z1QuickVetoTemp` (5–30°C co 0,5°C) oraz
`Z1QuickVetoDuration` (0,5–12 godzin co 0,5 h). Wysłanie czasu włącza Quick Veto;
po upływie sterownik wraca do zwykłego programu. Panel wykonuje odczyt zwrotny
`Z1ActualRoomTempDesired`, temperatury override i czasu. Jeśli weryfikacja nie powiedzie
się, pokaże błąd i zaleci sprawdzić sterownik przed ponowieniem. Zmiana może uruchomić
ogrzewanie. Nie wpisuj `Z1ActualRoomTempDesired` ani innych wiadomości; tylko dwa
parametry Quick Veto są udostępnione do zapisu.
