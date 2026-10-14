# LogiAndes – Panel BI, versión comité (Taller Práctico 3)

Parte del dashboard de la semana 2 (mismos filtros, mismos cinco KPIs y mismo `kpis.py`) y agrega dos pestañas: **Hallazgos** (las mismas vistas de las láminas 5 a 8: comercial, operativo, financiero y atención al cliente, cada una con resultado técnico, hallazgo analítico e implicación) y **Comité directivo**:

- Semáforo por ciudad con los umbrales del comité y la nota de interpretabilidad.
- Solidez de la evidencia (hallazgo robusto, señal o hipótesis) según volumen y estabilidad mensual.
- Índice de Prioridad Operativa (IPO) con pesos ajustables.
- Seguimiento de decisiones (línea base, meta del II trimestre, responsable).
- Reporte agregado que oculta celdas con menos de 30 pedidos o 5 reclamos.

Por privacidad, la tabla de detalle ya no muestra `pedido_id`.

- `app.py`: dashboard.
- `kpis.py`: KPIs de la semana 2 + funciones de la semana 3 (ciudad, SLA, nivel de atención, IPO, supresión).
- Datos: usa `logiandes.csv` si está junto a `app.py`; si no, descarga la hoja de cálculo de la fuente.

```
pip install -r requirements.txt
streamlit run app.py
```
