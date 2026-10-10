# PiHA Vaillant — uruchomienie

Ustaw `ebusd_host` na IP lub DNS serwera ebusd. Port TCP domyślnie 8888, obwód `bai`.
Włącz broker Mosquitto i integrację MQTT. Puste `mqtt_host` włącza pobieranie danych
brokera z Supervisora. Zapisz konfigurację i zrestartuj dodatek.

Otwórz panel przez Ingress. Encje powstają w urządzeniu Vaillant boiler.
Nieprawidłowe odczyty są niedostępne; ich powód znajdziesz w tabeli diagnostycznej.
Odczyty liczników aktualizują się co 5 minut. Pełna dokumentacja i dashboard:
README.md oraz examples/dashboard.yaml w repozytorium projektu.

Od 0.2.0 panel pokazuje schemat instalacji i trwałą historię palnika.
Wybierz zakres 6 h / 24 h / 7 dni lub własne daty. Kliknij odcinek pracy,
aby sprawdzić wykryte godziny i czas. Archiwum 90 dni zaczyna się od aktualizacji;
nie odtwarza wcześniejszych cykli. Dane przetrwają restart dodatku.
Czasy są przybliżone do odczytów (około 5 s plus opóźnienia eBUS), a luki
w komunikacji nie są liczone jako praca. Aktualizuj dodatek bez odinstalowywania.

Dodatek nie steruje kotłem ani nie resetuje błędów. Nie przelicza modulacji na kW.

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
zakresem -30…60°C daje niedostępność, nigdy zastępcze 0°C. Odczyt jest read-only.

W razie braku pomiaru sprawdź `ebusctl read -V -f -c ctlv2 Z1RoomTemp`.
Oczekiwane pole w konfiguracji CTLV2 to `value`, np. `value=24.1 °C`.
Strefy 2 i 3 oraz temperatura zadana miały w dostarczonej liście `no data stored`;
nie są automatycznie traktowane jako aktywne czujniki.
Źródło definicji: https://ebus.github.io/en/vaillant/15.ctlv2.csv.
