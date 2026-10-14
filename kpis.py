import numpy as np
import pandas as pd

MESES = {1: "Enero", 2: "Febrero", 3: "Marzo"}
ORDEN_MES = list(MESES.values())

# Las metas y umbrales no vienen en la base. Nosotros las propusimos a partir del
# comportamiento observado del primer trimestre y las dejamos aquí para poder
# ajustarlas cuando las áreas de LogiAndes confirmen sus valores reales.
# En los cinco KPIs un valor más bajo es mejor.
METAS = {
    "tasa_reclamos": {"meta": 30.0, "umbral": 45.0},
    "mediana_entrega": {"meta": 130.0, "umbral": 150.0},
    "pct_tarde": {"meta": 2.0, "umbral": 5.0},
    "ventas_riesgo": {"meta": 3.0, "umbral": 5.0},
    "concentracion_top2": {"meta": 60.0, "umbral": 65.0},
}

UMBRAL_TARDE_MIN = 240   # definimos "entrega tardía" como más de 4 horas
MIN_PEDIDOS = 100        # por debajo de este tamaño de muestra advertimos al lector


def preparar(df):
    # Nosotros no limpiamos la base; solo tipamos la fecha y creamos columnas auxiliares.
    df = df.copy()
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"], errors="coerce")
    df["mes"] = pd.Categorical(df["fecha_pedido"].dt.month.map(MESES),
                               categories=ORDEN_MES, ordered=True)
    df["tarde"] = (df["tiempo_individual_entrega_min"] > UMBRAL_TARDE_MIN).astype(int)
    df["ventas_riesgo"] = df["ventas_asociadas_usd"] * df["reclamos_registrados"]
    return df


def wilson(k, n, z=1.96):
    # Intervalo de Wilson al 95% para la tasa de reclamos, expresado por 1.000 pedidos.
    # Lo usamos porque con pocos reclamos la tasa de un subgrupo es muy inestable.
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    p = k / n
    den = 1 + z ** 2 / n
    centro = (p + z ** 2 / (2 * n)) / den
    margen = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return (centro - margen) * 1000, (centro + margen) * 1000


def agrupar(df, claves):
    g = (df.groupby(claves, observed=True)
           .agg(pedidos=("pedido_id", "count"),
                reclamos=("reclamos_registrados", "sum"),
                ventas=("ventas_asociadas_usd", "sum"),
                ventas_riesgo=("ventas_riesgo", "sum"),
                mediana_entrega=("tiempo_individual_entrega_min", "median"),
                pct_tarde=("tarde", "mean"))
           .reset_index())
    g["tasa_reclamos"] = g["reclamos"] / g["pedidos"] * 1000
    g["pct_tarde"] = g["pct_tarde"] * 100
    g["ic_bajo"], g["ic_alto"] = wilson(g["reclamos"], g["pedidos"])
    return g


def calcular_kpis(df):
    ventas_prov = df.groupby("provincia")["ventas_asociadas_usd"].sum().sort_values(ascending=False)
    total = df["ventas_asociadas_usd"].sum()
    return {
        "tasa_reclamos": df["reclamos_registrados"].mean() * 1000,
        "mediana_entrega": df["tiempo_individual_entrega_min"].median(),
        "pct_tarde": df["tarde"].mean() * 100,
        "ventas_riesgo": df["ventas_riesgo"].sum() / total * 100,
        "concentracion_top2": ventas_prov.head(2).sum() / total * 100,
    }


def estado(clave, valor):
    m = METAS[clave]
    if valor <= m["meta"]:
        return "Verde"
    if valor <= m["umbral"]:
        return "Amarillo"
    return "Rojo"


ICONO = {"Verde": "🟢", "Amarillo": "🟡", "Rojo": "🔴"}

# Ficha técnica de cada KPI. Las metas se leen de METAS para que la ficha
# y el semáforo del dashboard siempre digan lo mismo.
FICHAS = [
    {
        "clave": "tasa_reclamos",
        "nombre": "Tasa de reclamos por 1.000 pedidos",
        "objetivo": "Medir la calidad percibida del servicio sin que el volumen distorsione la comparación.",
        "formula": "(Σ reclamos_registrados / nº de pedidos) × 1.000",
        "fuente": "logiandes.csv: reclamos_registrados, pedido_id",
        "frecuencia": "Mensual",
        "unidad": "reclamos por 1.000 pedidos",
        "interpretacion": "Menor es mejor. En subgrupos pequeños puede cambiar mucho con 1 o 2 casos, por eso mostramos el intervalo de confianza.",
        "audiencia": "Atención al cliente, gerencia general",
    },
    {
        "clave": "mediana_entrega",
        "nombre": "Mediana del tiempo de entrega",
        "objetivo": "Seguir la rapidez típica de la entrega sin que los valores extremos distorsionen el resultado.",
        "formula": "mediana(tiempo_individual_entrega_min)",
        "fuente": "logiandes.csv: tiempo_individual_entrega_min",
        "frecuencia": "Semanal",
        "unidad": "minutos",
        "interpretacion": "Menor es mejor. Depende del canal (Programado es lento a propósito) y de la distancia, así que se compara dentro de un mismo canal.",
        "audiencia": "Operaciones",
    },
    {
        "clave": "pct_tarde",
        "nombre": "% de entregas tardías (más de 240 min)",
        "objetivo": "Detectar la cola de entregas muy lentas que la mediana no muestra.",
        "formula": "(pedidos con tiempo_individual_entrega_min > 240 / nº de pedidos) × 100",
        "fuente": "logiandes.csv: tiempo_individual_entrega_min",
        "frecuencia": "Semanal",
        "unidad": "% de pedidos",
        "interpretacion": "Menor es mejor. El umbral de 240 min es una definición nuestra y Operaciones debería validarla.",
        "audiencia": "Operaciones, atención al cliente",
    },
    {
        "clave": "ventas_riesgo",
        "nombre": "% de ventas en riesgo por reclamo",
        "objetivo": "Dar a Finanzas una medida del dinero asociado a pedidos con reclamo, sin inventar rentabilidad.",
        "formula": "(Σ ventas_asociadas_usd de pedidos con reclamo / Σ ventas_asociadas_usd) × 100",
        "fuente": "logiandes.csv: ventas_asociadas_usd, reclamos_registrados",
        "frecuencia": "Mensual",
        "unidad": "% de las ventas",
        "interpretacion": "Menor es mejor. No es una pérdida real: es la venta de pedidos con reclamo. La base no trae costos ni devoluciones.",
        "audiencia": "Finanzas, gerencia general",
    },
    {
        "clave": "concentracion_top2",
        "nombre": "Concentración de ventas en las 2 provincias principales",
        "objetivo": "Medir cuánto depende el negocio de dos provincias.",
        "formula": "(ventas de las 2 provincias con más ventas / ventas totales) × 100",
        "fuente": "logiandes.csv: provincia, ventas_asociadas_usd",
        "frecuencia": "Trimestral",
        "unidad": "% de las ventas",
        "interpretacion": "Menor indica menos dependencia. Con una sola provincia filtrada vale 100% y no tiene sentido.",
        "audiencia": "Área comercial, gerencia general",
    },
]

for _f in FICHAS:
    _f["meta"] = f"≤ {METAS[_f['clave']]['meta']:g} {_f['unidad']}"
    _f["umbral"] = f"> {METAS[_f['clave']]['umbral']:g} {_f['unidad']} (rojo)"


def formatear(clave, valor):
    if clave == "tasa_reclamos":
        return f"{valor:.1f}"
    if clave == "mediana_entrega":
        return f"{valor:.0f} min"
    return f"{valor:.1f}%"


# =====================================================================
# Semana 3: comunicación de resultados al comité
# Todo lo de abajo se calcula con los mismos datos y funciones de arriba.
# =====================================================================

CIUDAD = {"Pichincha": "Quito", "Guayas": "Guayaquil", "Azuay": "Cuenca",
          "Manabí": "Manta", "Tungurahua": "Ambato", "Loja": "Loja"}

# Supuesto nuestro: la base no trae SLA. Operaciones debe validar estos valores.
SLA = {"Express": 120, "Estándar urbano": 180, "Programado": 210}

# Umbrales del comité (los mismos del cuaderno de la semana 3)
UMBRALES_COMITE = {"tasa_reclamos": 30.0, "a_tiempo": 90.0, "usd_por_km": 2.5, "t_atencion": 8.0}

# Reglas de agregación mínima para no exponer segmentos muy pequeños
MIN_PEDIDOS_PUBLICAR = 30
MIN_RECLAMOS_PUBLICAR = 5

PESOS_IPO = {"R": 0.35, "E": 0.30, "F": 0.20, "A": 0.15}


def preparar_comite(df):
    # Agrega a la base de la semana 2 las columnas que usamos para el comité.
    df = df.copy()
    df["ciudad"] = df["provincia"].map(CIUDAD)
    df["a_tiempo"] = df["tiempo_individual_entrega_min"] <= df["canal_entrega"].map(SLA)
    return df


def tabla_ciudades(df):
    g = (df.groupby("ciudad", observed=True)
           .agg(pedidos=("pedido_id", "count"),
                reclamos=("reclamos_registrados", "sum"),
                ventas=("ventas_asociadas_usd", "sum"),
                km=("distancia_km", "sum"),
                dist_media=("distancia_km", "mean"),
                a_tiempo=("a_tiempo", "mean"),
                t_atencion=("tiempo_atencion_min", "mean"))
           .reset_index())
    g["tasa_reclamos"] = g["reclamos"] / g["pedidos"] * 1000
    g["a_tiempo"] = g["a_tiempo"] * 100
    g["usd_por_km"] = g["ventas"] / g["km"]
    g["ticket"] = g["ventas"] / g["pedidos"]
    g["ic_bajo"], g["ic_alto"] = wilson(g["reclamos"], g["pedidos"])
    return g.set_index("ciudad")


def alertas_ciudad(t):
    # Cuenta de KPIs fuera de umbral por ciudad (misma regla del cuaderno).
    u = UMBRALES_COMITE
    a = pd.DataFrame(index=t.index)
    a["reclamos"] = t["tasa_reclamos"] > u["tasa_reclamos"]
    a["entregas"] = t["a_tiempo"] < u["a_tiempo"]
    a["eficiencia"] = t["usd_por_km"] < u["usd_por_km"]
    a["atencion"] = t["t_atencion"] > u["t_atencion"]
    a["n_alertas"] = a.sum(axis=1)
    a["nivel"] = pd.cut(a["n_alertas"], [-1, 1, 2, 4], labels=["Bajo", "Medio", "Alto"]).astype(str)
    return a


def robustez(t, a, prom_global, meses_sobre):
    # Hallazgo robusto / señal relevante / hipótesis preliminar, según el cuaderno.
    out = {}
    for c in t.index:
        n = t.loc[c, "pedidos"]
        if n < 500:
            out[c] = "Hipótesis preliminar"
        elif a.loc[c, "n_alertas"] == 0:
            out[c] = "Sin alerta relevante"
        elif n >= 1000 and meses_sobre.get(c, 0) == 3 and a.loc[c, "n_alertas"] >= 2:
            out[c] = "Hallazgo robusto"
        elif t.loc[c, "ic_bajo"] > prom_global:
            out[c] = "Señal relevante"
        else:
            out[c] = "Señal en seguimiento"
    return pd.Series(out)


def meses_sobre_promedio(df, prom_global):
    m = (df.groupby(["ciudad", "mes"], observed=True)["reclamos_registrados"].mean() * 1000)
    return (m > prom_global).groupby("ciudad").sum()


def _norm(s, invertir=False):
    s = -s if invertir else s
    rango = s.max() - s.min()
    return (s - s.min()) / rango if rango else s * 0


def calcular_ipo(t, pesos=None):
    # Índice de Prioridad Operativa 0-100: mayor = más prioridad de revisión.
    p = pesos or PESOS_IPO
    c = pd.DataFrame(index=t.index)
    c["R"] = _norm(t["tasa_reclamos"])
    c["E"] = _norm(100 - t["a_tiempo"])
    c["F"] = _norm(t["usd_por_km"], invertir=True)
    c["A"] = _norm(t["t_atencion"])
    total = sum(p.values())
    c["IPO"] = 100 * sum(p[k] * c[k] for k in p) / total
    c["confiabilidad"] = pd.cut(t["pedidos"], [-1, 499, 999, 10 ** 9],
                                labels=["Baja", "Media", "Alta"]).astype(str)
    return c


def reporte_agregado(df, por):
    # Tasa de reclamos con supresión de celdas pequeñas (protección de datos).
    g = (df.groupby(por, observed=True)
           .agg(pedidos=("pedido_id", "count"), reclamos=("reclamos_registrados", "sum"))
           .reset_index())
    g["tasa_reclamos"] = g["reclamos"] / g["pedidos"] * 1000
    oculto = (g["pedidos"] < MIN_PEDIDOS_PUBLICAR) | (g["reclamos"] < MIN_RECLAMOS_PUBLICAR)
    g.loc[oculto, ["reclamos", "tasa_reclamos"]] = np.nan
    return g


NOTA_INTERPRETABILIDAD = (
    "El nivel de atención es una **señal de priorización, no una sentencia**. Un nivel Alto indica "
    "que conviene analizar y actuar de forma proporcional; no demuestra un problema ni mala gestión "
    "local. Se lee junto con el volumen de pedidos, las rutas, la capacidad de atención, el "
    "inventario y las decisiones comerciales recientes. No ejecuta ninguna acción automática.")

# Seguimiento de decisiones: línea base = I trimestre (se calcula en la app), meta = II trimestre
SEGUIMIENTO = [
    {"ciudad": "Guayaquil", "decision": "Revisión logística de rutas", "kpi": "Entregas a tiempo (%)",
     "col": "a_tiempo", "meta": 90.0, "mejor": "mayor", "revision": "Semanal", "responsable": "Operaciones"},
    {"ciudad": "Guayaquil", "decision": "Revisión logística de rutas", "kpi": "Eficiencia (USD/km)",
     "col": "usd_por_km", "meta": 2.80, "mejor": "mayor", "revision": "Mensual", "responsable": "Finanzas"},
    {"ciudad": "Manta", "decision": "Plan de atención canal Express", "kpi": "Reclamos por 1.000",
     "col": "tasa_reclamos", "meta": 40.0, "mejor": "menor", "revision": "Semanal",
     "responsable": "Atención al cliente"},
    {"ciudad": "Loja", "decision": "Seguimiento cauteloso", "kpi": "Reclamos por 1.000",
     "col": "tasa_reclamos", "meta": 32.0, "mejor": "menor", "revision": "Mensual", "responsable": "Analítica"},
]
