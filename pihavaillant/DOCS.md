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
