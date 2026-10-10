# PiHA Vaillant — uruchomienie

Ustaw `ebusd_host` na IP lub DNS serwera ebusd. Port TCP domyślnie 8888, obwód `bai`.
Włącz broker Mosquitto i integrację MQTT. Puste `mqtt_host` włącza pobieranie danych
brokera z Supervisora. Zapisz konfigurację i zrestartuj dodatek.

Otwórz panel przez Ingress. Encje powstają w urządzeniu Vaillant boiler.
Nieprawidłowe odczyty są niedostępne; ich powód znajdziesz w tabeli diagnostycznej.
Odczyty liczników aktualizują się co 5 minut. Pełna dokumentacja i dashboard:
README.md oraz examples/dashboard.yaml w repozytorium projektu.

Dodatek nie steruje kotłem ani nie resetuje błędów. Nie przelicza modulacji na kW.
