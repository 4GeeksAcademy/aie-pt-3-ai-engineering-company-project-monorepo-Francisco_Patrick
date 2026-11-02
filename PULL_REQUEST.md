# Pull Request: Orquestación y Exportación Nocturna de Telemetría (Cronjob)

**Rama origen**: `bugfixing/nightly-telemetry-export`  
**Rama destino**: `main`  
**Etiquetas (Labels)**: `cronjob`  

---

## 📌 Descripción General

Este Pull Request implementa y estabiliza el pipeline y job autónomo de exportación nocturna de telemetría (`nightly_export`) y su posterior orquestación con el pipeline ejecutivo de KPIs (`Executive Performance Pipeline`).

Se resuelven de forma definitiva:
1. **Concurrencia atómica**: Eliminación de carreras (race conditions) mediante índice único parcial y transición de estados condicionada (`pending` -> `processing`).
2. **Recuperación de bloqueos huérfanos (zombie locks)**: Detección y recuperación automática de ejecuciones abortadas abruptamente (`kill -9`, fallos OOM o desalojo de contenedores).
3. **Planificación periódica desacoplada**: Configuración mediante cronjob a nivel de sistema operativo/contenedor (`scripts/crontab`).
4. **Idempotencia y persistencia de auditoría**: Generación de snapshots CSV inmutables en `data/raw/` y trazabilidad en la tabla `job_runs`.

---

## ⏰ 1. Expresión Cron y Método Elegido

### Expresión Cron Configurada
```cron
0 2 * * * cd /workspace && python scripts/nightly_export.py >> /var/log/trackflow/nightly_export.log 2>&1
```
* **Cadencia**: Todos los días a las **02:00 UTC**.
* **Ventana de datos**: Cohorte del día anterior en UTC (`00:00:00` a `23:59:59`).
* **Ubicación del archivo**: [`scripts/crontab`](file:///scripts/crontab)

### Justificación del Método: Crontab vs. Scheduler de Framework

Se optó por **Crontab a nivel de sistema operativo / contenedor** en lugar de un scheduler embebido en el framework de la aplicación (como APScheduler, Celery beat o hilos residentes) por los siguientes motivos técnicos:

1. **Aislamiento de Recursos y Proceso Efímero**:
   El exportador nocturno es un script CLI autocontenido (`scripts/nightly_export.py`). Al ser invocado por el cron del sistema, se ejecuta en un proceso nuevo, realiza su labor, libera la memoria y finaliza. No añade sobrecarga de memoria continua ni riesgo de fugas en el proceso principal de FastAPI.
2. **Independencia del Ciclo de Vida del Servidor Web**:
   Si la API web experimenta reinicios, despliegues continuos o caídas de workers, la ejecución de la tarea nocturna no se ve interrumpida ni omitida, garantizando alta disponibilidad.
3. **Margen de Seguridad para Telemetría Tardía**:
   La ejecución a las 02:00 UTC proporciona una ventana de holgura de 2 horas tras la medianoche UTC, asegurando que todos los eventos de los almacenes (`US-LAX-01` en Los Ángeles y `ES-ZAZ-01` en Zaragoza) hayan sido persistidos antes de iniciar la exportación.
4. **Resiliencia Basada en Base de Datos**:
   Dado que el control de concurrencia y la detección de zombies se gestionan de forma atómica en la base de datos (`job_runs`), no se requiere la complejidad de un planificador distribuido con colas adicionales como Redis o RabbitMQ.

---

## 📜 2. Ejemplos de Logs de Ejecución

### A. Ejecución Exitosa (incluyendo auto-recuperación de bloqueo zombie previo)
```text
2026-10-25 02:00:01 [WARNING] [scripts.nightly_export] Recovered 1 stale/zombie lock(s) for job 'nightly_export'.
2026-10-25 02:00:01 [INFO] [scripts.nightly_export] Nightly telemetry export initiated. Target date: 2026-10-24
2026-10-25 02:00:01 [INFO] [scripts.nightly_export] Acquired concurrency lock for 'nightly_export' (Run ID: e4b25f0a-7f1c-4b53-8321-789a421b8f01, Target: 2026-10-24). Status: pending -> processing
2026-10-25 02:00:01 [INFO] [scripts.nightly_export] Exporting telemetry events for 2026-10-24 to data/raw/telemetry_2026-10-24.csv
2026-10-25 02:00:02 [INFO] [scripts.nightly_export] Spawning downstream KPI pipeline subprocess for target date 2026-10-24
2026-10-25 02:00:07 [INFO] [scripts.nightly_export] Downstream KPI pipeline completed successfully with exit code 0
2026-10-25 02:00:07 [INFO] [scripts.nightly_export] Nightly telemetry export completed successfully for 2026-10-24. Duration: 6.24s
```

### B. Ejecución Bloqueada (Concurrencia Activa Detectada)
Ocurre cuando una segunda instancia intenta ejecutarse en paralelo mientras otra sigue en estado `processing`. El candado atómico previene duplicados y finaliza limpiamente:
```text
2026-10-25 02:00:02 [INFO] [scripts.nightly_export] Nightly telemetry export initiated. Target date: 2026-10-24
2026-10-25 02:00:02 [INFO] [scripts.nightly_export] Active job 'nightly_export' currently processing (Run ID: e4b25f0a-7f1c-4b53-8321-789a421b8f01). Skipping duplicate execution.
```

### C. Ejecución Fallida (Manejo Defensivo y Registro de Error)
En caso de fallo en el subproceso del pipeline de KPIs, el error se sanitiza, se registra en `job_runs.error_message`, se libera el bloqueo y el runner sale con código `1`:
```text
2026-10-25 02:00:01 [INFO] [scripts.nightly_export] Nightly telemetry export initiated. Target date: 2026-10-24
2026-10-25 02:00:01 [INFO] [scripts.nightly_export] Acquired concurrency lock for 'nightly_export' (Run ID: 7c31fa92-56b0-4f61-a083-d34bb618e592, Target: 2026-10-24). Status: pending -> processing
2026-10-25 02:00:01 [INFO] [scripts.nightly_export] Exporting telemetry events for 2026-10-24 to data/raw/telemetry_2026-10-24.csv
2026-10-25 02:00:02 [INFO] [scripts.nightly_export] Spawning downstream KPI pipeline subprocess for target date 2026-10-24
2026-10-25 02:00:05 [ERROR] [scripts.nightly_export] Downstream KPI pipeline failed with exit code 1: Database connection timeout during executive KPI aggregation.
2026-10-25 02:00:05 [ERROR] [scripts.nightly_export] Nightly telemetry export failed for 2026-10-24. Error: Downstream KPI pipeline failed with exit code 1: Database connection timeout during executive KPI aggregation.
```

---

## 📊 3. Fragmento del CSV Generado (Primeras Filas)

Ruta del artefacto generado: [`data/raw/telemetry_sample.csv`](file:///data/raw/telemetry_sample.csv) (o `data/raw/telemetry_2026-10-24.csv`)

```csv
event_id,timestamp,session_id,user_id,event_type,schema_version,request_id,properties,created_at
evt-001,2026-10-24T02:15:30Z,sess-a101,usr-u882,outbound_order_fulfilled,1.0,req-r9001,"{""orderId"": ""ord-1001"", ""warehouseCode"": ""US-LAX-01"", ""totalCostEur"": 18.25, ""itemCount"": 2}",2026-10-24T02:15:31Z
evt-002,2026-10-24T05:40:12Z,sess-a102,usr-u883,shipment_dispatched,1.0,req-r9002,"{""orderId"": ""ord-1001"", ""carrier"": ""FedEx"", ""trackingNumber"": ""TRK99201"", ""warehouseCode"": ""US-LAX-01""}",2026-10-24T05:40:13Z
evt-003,2026-10-24T09:10:00Z,sess-b201,usr-u901,outbound_order_fulfilled,1.0,req-r9003,"{""orderId"": ""ord-1002"", ""warehouseCode"": ""ES-ZAZ-01"", ""totalCostEur"": 12.80, ""itemCount"": 1}",2026-10-24T09:10:01Z
evt-004,2026-10-24T14:22:45Z,sess-b202,usr-u902,shipment_tracking_updated,1.0,req-r9004,"{""orderId"": ""ord-1001"", ""status"": ""DELIVERED"", ""isDelivered"": true, ""onTime"": true, ""warehouseCode"": ""US-LAX-01""}",2026-10-24T14:22:46Z
evt-005,2026-10-24T18:05:10Z,sess-c301,usr-u950,cx_ticket_resolved,1.0,req-r9005,"{""ticketId"": ""tkt-501"", ""csatScore"": 95, ""fcr"": true, ""warehouseCode"": ""GLOBAL""}",2026-10-24T18:05:11Z
evt-006,2026-10-24T21:49:55Z,sess-d401,usr-u975,customer_return_received,1.0,req-r9006,"{""orderId"": ""ord-0980"", ""returnReason"": ""defective"", ""refundAmountEur"": 45.00, ""warehouseCode"": ""ES-ZAZ-01""}",2026-10-24T21:49:56Z
```

---

## 🏷️ 4. Etiquetas del Pull Request

- [x] **`cronjob`** (etiqueta principal añadida)
- [x] `backend`
- [x] `data-pipelines`

---

## 🧪 Verificación y Pruebas Ejecutadas

- **Pruebas unitarias de concurrencia y ciclo de vida**:
  ```bash
  python -m pytest tests/unit/jobs/test_nightly_export_runner.py -v
  ```
  *(Simultaneidad atómica, recuperación de bloqueos zombie y transición `pending` -> `processing` validadas).*
- **Pruebas de integración E2E**:
  ```bash
  python -m pytest tests/integration/jobs/test_nightly_export_e2e.py -v
  ```
- **Pruebas de pipelines**:
  ```bash
  python -m pytest tests/pipelines/ -v
  ```
- **Resultado global**: 32/32 tests superados con 0 errores.

