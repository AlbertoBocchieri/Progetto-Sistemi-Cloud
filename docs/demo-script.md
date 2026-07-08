# Demo Script

1. Avvia:

```bash
docker compose up --build
```

2. Apri:

```text
http://localhost:8080
```

3. Mostra la mappa con zone colorate.

4. Cambia posizione demo: `Stesicoro`, `Borgo`, `Sanzio`, `Europa`.

5. Mostra live session, zona corrente, parcheggiabilita, trend, confidence e migliori zone vicine.

6. Clicca `Zona piena`: lo score della zona corrente peggiora.

7. Clicca `Ho trovato posto`: lo score migliora.

8. Lancia uno scenario demo: gli eventi passano da ingestion-service a RabbitMQ e aggiornano Redis.

9. Mostra `Dashboard admin`: DB, Redis, RabbitMQ e ultimi eventi consumati.

10. Apri RabbitMQ:

```text
http://localhost:15672
```

Credenziali: `parcheggia` / `parcheggia`.

11. Esegui smoke test:

```bash
scripts/smoke_test.sh
scripts/e2e_demo_test.sh
```

Quality gate completo:

```bash
scripts/run_checks.sh
```

12. Apri API docs:

```text
http://localhost:8001/docs
http://localhost:8002/docs
http://localhost:8003/docs
```
