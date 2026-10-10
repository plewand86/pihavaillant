# 0.2.0

- Nowy schemat kotła, pompy obiegowej, ogrzewania, cyrkulacji i zasobnika CWU.
- Trwała historia pracy palnika i temperatur w SQLite, retencja 90 dni.
- Oś czasu pracy, własny zakres dat, tabela cykli i podsumowanie czasu pracy.
- Odczyt płomienia co około 5 s bez cache, z osobną publikacją stanu MQTT.
- Rozróżnienie pełnych cykli, fragmentów pracy i luk, bez naliczania czasu przez awarie.

# 0.1.0

- Monitor ebusd z listą dozwolonych odczytów Vaillant.
- 32 encje MQTT Discovery z dostępnością i obsługą błędnych danych.
- Polski panel Ingress i przykładowy dashboard HA.
- Testy na dostarczonym eksporcie i symulatorze TCP.
