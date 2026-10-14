from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import kpis as K

st.set_page_config(page_title="LogiAndes - Panel BI", layout="wide")

URL = ("https://docs.google.com/spreadsheets/d/1z68Fjbvpb-SiFSJK_fnaN4dmljm0Yv-yZ3gunGizvb8/"
       "export?format=csv&gid=45425025")
LOCAL = Path(__file__).parent / "logiandes.csv"
ORDEN_CANAL = ["Estándar urbano", "Express", "Programado"]
COLOR_CANAL = ["#2a7f8f", "#d1603d", "#8c8c8c"]
COLOR_REGION = {"Costa": "#d1603d", "Sierra": "#2a7f8f"}
FUENTE = "Fuente: LogiAndes S.A., logiandes.csv (enero-marzo 2026)"


@st.cache_data
def cargar():
    # Si el csv está junto a la app lo usamos; si no, bajamos la hoja de cálculo original.
    df = pd.read_csv(LOCAL if LOCAL.exists() else URL)
    return K.preparar_comite(K.preparar(df))


df = cargar()

# ---------------- Filtros globales ----------------
st.sidebar.header("Filtros")
meses = st.sidebar.multiselect("Mes", K.ORDEN_MES, default=K.ORDEN_MES)
provincias_all = sorted(df["provincia"].unique())
provincias = st.sidebar.multiselect("Provincia", provincias_all, default=provincias_all)
canales = st.sidebar.multiselect("Canal de entrega", ORDEN_CANAL, default=ORDEN_CANAL)
tipos_all = sorted(df["tipo_cliente"].dropna().unique())
tipos = st.sidebar.multiselect("Tipo de cliente", tipos_all, default=tipos_all)
st.sidebar.caption("Los filtros afectan a todas las secciones. Las metas de los KPIs son "
                   "supuestos del grupo (ver pestaña Documentación).")

f = df[df["mes"].isin(meses) & df["provincia"].isin(provincias)
       & df["canal_entrega"].isin(canales) & df["tipo_cliente"].isin(tipos)]

st.title("LogiAndes: panel de servicio y ventas · versión comité")
st.caption(FUENTE)

if f.empty:
    st.warning("No hay pedidos con los filtros seleccionados.")
    st.stop()
if len(f) < K.MIN_PEDIDOS:
    st.info(f"Los filtros dejan solo {len(f)} pedidos. Los indicadores pueden ser poco estables.")

tab1, tab2, tab3, tab_hall, tab_com, tab4 = st.tabs(
    ["Vista ejecutiva", "Análisis territorial", "Detalle operativo", "Hallazgos", "Comité directivo",
     "Documentación"])

# =====================================================================
# 1. Vista ejecutiva
# =====================================================================
with tab1:
    valores = K.calcular_kpis(f)
    st.subheader("¿Cómo estamos frente a las metas?")
    cols = st.columns(5)
    for col, ficha in zip(cols, K.FICHAS):
        clave = ficha["clave"]
        est = K.estado(clave, valores[clave])
        col.metric(f"{K.ICONO[est]} {ficha['nombre']}", K.formatear(clave, valores[clave]))
        col.caption(f"Meta {ficha['meta']}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas (USD)", f"${f['ventas_asociadas_usd'].sum():,.0f}")
    c2.metric("Pedidos", f"{len(f):,}")
    c3.metric("Venta promedio por pedido (USD)", f"${f['ventas_asociadas_usd'].mean():,.2f}")

    # Evolución mensual: ventas en barras y tasa de reclamos en línea
    mensual = K.agrupar(f, ["mes"])
    fig_m = make_subplots(specs=[[{"secondary_y": True}]])
    fig_m.add_bar(x=mensual["mes"], y=mensual["ventas"], name="Ventas (USD)",
                  marker_color="#9db8d3")
    fig_m.add_scatter(x=mensual["mes"], y=mensual["tasa_reclamos"], name="Reclamos por 1.000",
                      mode="lines+markers", line_color="#d1603d", secondary_y=True)
    fig_m.update_yaxes(title_text="Ventas (USD)", rangemode="tozero", secondary_y=False)
    fig_m.update_yaxes(title_text="Reclamos por 1.000 pedidos", rangemode="tozero", secondary_y=True)
    fig_m.update_layout(title="Ventas y reclamos por mes", template="plotly_white",
                        legend=dict(orientation="h", y=-0.2))

    # Cada provincia: cuánto vende contra qué tan mal le va en reclamos
    prov = K.agrupar(f, ["provincia", "region"])
    tasa_global = valores["tasa_reclamos"]
    fig_b = px.scatter(prov, x="ventas", y="tasa_reclamos", size="pedidos", color="region",
                       text="provincia", color_discrete_map=COLOR_REGION,
                       labels={"ventas": "Ventas (USD)", "tasa_reclamos": "Reclamos por 1.000 pedidos",
                               "region": "Región"},
                       title="Peso de cada provincia en ventas frente a su tasa de reclamos",
                       template="plotly_white", size_max=45)
    fig_b.update_traces(textposition="top center")
    fig_b.add_hline(y=tasa_global, line_dash="dash", line_color="gray",
                    annotation_text=f"Promedio ({tasa_global:.1f})")
    fig_b.update_xaxes(rangemode="tozero")
    fig_b.update_yaxes(rangemode="tozero")

    g1, g2 = st.columns(2)
    g1.plotly_chart(fig_m, use_container_width=True)
    g2.plotly_chart(fig_b, use_container_width=True)
    st.caption("Tamaño del círculo: número de pedidos. " + FUENTE)

    peor = prov.sort_values("tasa_reclamos").iloc[-1]
    st.info(f"Lectura rápida: con los filtros actuales, {peor['provincia']} tiene la tasa de "
            f"reclamos más alta ({peor['tasa_reclamos']:.1f} por 1.000, sobre {int(peor['pedidos']):,} "
            f"pedidos). Es una asociación, no prueba la causa.")

# =====================================================================
# 2. Análisis territorial
# =====================================================================
with tab2:
    st.subheader("Comparación entre provincias")
    opciones = {
        "Reclamos por 1.000 pedidos": "tasa_reclamos",
        "Mediana de entrega (min)": "mediana_entrega",
        "% de entregas tardías": "pct_tarde",
        "Ventas (USD)": "ventas",
        "Ventas en riesgo (USD)": "ventas_riesgo",
    }
    etiqueta = st.selectbox("Indicador a comparar", list(opciones))
    col_m = opciones[etiqueta]

    t = K.agrupar(f, ["provincia", "region"]).sort_values(col_m)
    t["err_alto"] = t["ic_alto"] - t["tasa_reclamos"]
    t["err_bajo"] = t["tasa_reclamos"] - t["ic_bajo"]
    con_ic = col_m == "tasa_reclamos"
    fig_t = px.bar(t, x=col_m, y="provincia", orientation="h", color="region",
                   color_discrete_map=COLOR_REGION, text=col_m,
                   error_x="err_alto" if con_ic else None,
                   error_x_minus="err_bajo" if con_ic else None,
                   custom_data=["pedidos", "reclamos"],
                   labels={col_m: etiqueta, "provincia": "", "region": "Región"},
                   title=f"{etiqueta} por provincia", template="plotly_white")
    fig_t.update_traces(texttemplate="%{x:,.1f}", textposition="outside", cliponaxis=False,
                        hovertemplate="<b>%{y}</b><br>" + etiqueta + ": %{x:,.1f}"
                                      "<br>Pedidos: %{customdata[0]:,}<br>Reclamos: %{customdata[1]}"
                                      "<extra></extra>")
    if con_ic:
        st.caption("Las barras de error son el intervalo de confianza al 95% de la tasa.")
    tope = (t["ic_alto"].max() if con_ic else t[col_m].max()) * 1.3
    fig_t.update_layout(xaxis_range=[0, tope])
    st.plotly_chart(fig_t, use_container_width=True)

    st.subheader("Provincia por canal")
    min_n = st.slider("Mínimo de pedidos para mostrar una celda", 0, 300, K.MIN_PEDIDOS, step=10,
                      help="Las celdas con menos pedidos quedan en blanco porque su tasa no es confiable.")
    pc = K.agrupar(f, ["provincia", "canal_entrega"])
    pc_ok = pc[pc["pedidos"] >= min_n]
    if pc_ok.empty:
        st.warning("Ninguna combinación cumple ese mínimo de pedidos.")
    else:
        z = pc_ok.pivot(index="provincia", columns="canal_entrega", values="tasa_reclamos")
        n = pc.pivot(index="provincia", columns="canal_entrega", values="pedidos")
        z = z.reindex(index=sorted(f["provincia"].unique()),
                      columns=[c for c in ORDEN_CANAL if c in pc["canal_entrega"].unique()])
        n = n.reindex(index=z.index, columns=z.columns)
        texto = z.round(1).astype(str) + "<br>(n=" + n.fillna(0).astype(int).astype(str) + ")"
        texto = texto.where(z.notna(), "")
        fig_h = go.Figure(go.Heatmap(z=z.values, x=z.columns, y=z.index, text=texto.values,
                                     texttemplate="%{text}", colorscale="Oranges",
                                     colorbar_title="Por 1.000", hoverongaps=False))
        fig_h.update_layout(title="Reclamos por 1.000 pedidos (n = pedidos de la celda)",
                            template="plotly_white", yaxis_autorange="reversed")
        st.plotly_chart(fig_h, use_container_width=True)
    st.caption(FUENTE)

# =====================================================================
# 3. Detalle operativo
# =====================================================================
with tab3:
    st.subheader("Tiempos, distancia y reclamos")
    o1, o2 = st.columns(2)

    with o1:
        muestra = f.sample(min(len(f), 2000), random_state=1)
        fig_s = px.scatter(muestra, x="distancia_km", y="tiempo_individual_entrega_min",
                           color="canal_entrega", opacity=0.5,
                           category_orders={"canal_entrega": ORDEN_CANAL},
                           color_discrete_sequence=COLOR_CANAL,
                           labels={"distancia_km": "Distancia (km)",
                                   "tiempo_individual_entrega_min": "Tiempo de entrega (min)",
                                   "canal_entrega": "Canal"},
                           title="Distancia y tiempo de entrega", template="plotly_white")
        fig_s.add_hline(y=K.UMBRAL_TARDE_MIN, line_dash="dash", line_color="gray",
                        annotation_text="240 min")
        st.plotly_chart(fig_s, use_container_width=True)
        st.caption("Mostramos una muestra de hasta 2.000 pedidos para que el gráfico responda rápido.")

    with o2:
        fig_c = px.box(f, x="canal_entrega", y="tiempo_individual_entrega_min",
                       color="canal_entrega", category_orders={"canal_entrega": ORDEN_CANAL},
                       color_discrete_sequence=COLOR_CANAL,
                       labels={"canal_entrega": "", "tiempo_individual_entrega_min": "Minutos"},
                       title="Tiempo de entrega por canal", template="plotly_white")
        fig_c.update_layout(showlegend=False)
        st.plotly_chart(fig_c, use_container_width=True)

    o3, o4 = st.columns(2)
    with o3:
        rec = f[f["reclamos_registrados"] == 1]
        if rec.empty:
            st.info("No hay reclamos con los filtros actuales.")
        else:
            motivos = (rec["motivo_reclamo"].fillna("Sin motivo").value_counts()
                          .rename_axis("motivo").reset_index(name="reclamos")
                          .sort_values("reclamos"))
            fig_mo = px.bar(motivos, x="reclamos", y="motivo", orientation="h", text="reclamos",
                            color_discrete_sequence=["#2a7f8f"],
                            labels={"reclamos": "Reclamos", "motivo": ""},
                            title="Reclamos por motivo", template="plotly_white")
            fig_mo.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig_mo, use_container_width=True)
    with o4:
        resumen_canal = K.agrupar(f, ["canal_entrega"]).set_index("canal_entrega")
        resumen_canal = resumen_canal.reindex([c for c in ORDEN_CANAL if c in resumen_canal.index])
        st.markdown("**Resumen por canal**")
        st.dataframe(resumen_canal[["pedidos", "reclamos", "tasa_reclamos", "mediana_entrega",
                                    "pct_tarde"]].round(1), use_container_width=True)

    st.subheader("Pedidos")
    solo = st.radio("Mostrar", ["Todos", "Solo con reclamo", "Solo entregas tardías"], horizontal=True)
    tabla = f
    if solo == "Solo con reclamo":
        tabla = f[f["reclamos_registrados"] == 1]
    elif solo == "Solo entregas tardías":
        tabla = f[f["tarde"] == 1]
    cols_tabla = ["fecha_pedido", "provincia", "canal_entrega", "tipo_cliente",
                  "distancia_km", "tiempo_individual_entrega_min", "reclamos_registrados",
                  "motivo_reclamo", "ventas_asociadas_usd"]
    st.write(f"{len(tabla):,} pedidos")
    st.dataframe(tabla[cols_tabla].head(500), use_container_width=True, hide_index=True)
    st.download_button("Descargar pedidos filtrados (CSV)",
                       tabla[cols_tabla].to_csv(index=False).encode("utf-8"),
                       file_name="pedidos_filtrados.csv", mime="text/csv")
    st.caption("La tabla muestra los primeros 500 pedidos; la descarga trae todos los filtrados. "
               "Por privacidad no mostramos el identificador del pedido: ese detalle queda para los equipos autorizados.")

# =====================================================================
# 4b. Hallazgos (semana 3): las mismas vistas de las láminas 5 a 8 de la presentación
# =====================================================================
with tab_hall:
    st.subheader("Cuatro hallazgos para el comité")
    st.caption("Cada vista separa el resultado técnico, el hallazgo analítico y la implicación de gestión. "
               "Los gráficos usan el mismo orden y colores que la presentación.")
    th = K.tabla_ciudades(f)
    if len(th) < 6:
        st.info("Esta sección compara las seis ciudades. Restablece el filtro de provincia para verla completa.")
    else:
        ROJO, VERDE, AMBAR, AZUL, GRIS = "#c0392b", "#2e8b57", "#e0a100", "#1f4e79", "#8c8c8c"
        provincia_de = {c: p for p, c in K.CIUDAD.items()}
        u = K.UMBRALES_COMITE

        def etiqueta_solidez(texto, color):
            st.markdown(f"<span style='background:{color}22;border:1px solid {color};border-radius:14px;"
                        f"padding:3px 12px;font-weight:600'>{texto}</span>", unsafe_allow_html=True)

        def grafico(orden, col, titulo, colores, fmt, linea=None, etiqueta_linea=""):
            d = th.loc[orden].reset_index()
            d["ciudad_p"] = d["ciudad"].map(lambda c: f"{c} ({provincia_de[c]})")
            fig = go.Figure(go.Bar(x=d[col], y=d["ciudad_p"], orientation="h", marker_color=colores,
                                   text=d[col], texttemplate=fmt, textposition="outside", cliponaxis=False,
                                   customdata=d[["pedidos"]],
                                   hovertemplate="<b>%{y}</b><br>%{x:,.2f}<br>Pedidos: %{customdata[0]:,}<extra></extra>"))
            if linea is not None:
                fig.add_vline(x=linea, line_dash="dash", line_color="gray", annotation_text=etiqueta_linea)
            fig.update_yaxes(autorange="reversed")
            fig.update_xaxes(rangemode="tozero")
            fig.update_layout(title=titulo, template="plotly_white", height=420, margin=dict(r=60))
            return fig

        def bloques(tecnico, hallazgo, implicacion):
            c1, c2, c3 = st.columns(3)
            with c1.container(border=True):
                st.markdown("**RESULTADO TÉCNICO**")
                st.write(tecnico)
            with c2.container(border=True):
                st.markdown("**HALLAZGO ANALÍTICO**")
                st.write(hallazgo)
            with c3.container(border=True):
                st.markdown("**IMPLICACIÓN DE GESTIÓN**")
                st.write(implicacion)

        eleccion = st.radio("Hallazgo", ["Comercial", "Operativo", "Financiero", "Atención al cliente"],
                            horizontal=True)
        g = th.loc

        if eleccion == "Comercial":
            etiqueta_solidez("Hallazgo robusto", VERDE)
            orden = th.sort_values("ventas", ascending=False).index.tolist()
            col = [AZUL if c in ("Quito", "Guayaquil") else GRIS for c in orden]
            st.plotly_chart(grafico(orden, "ventas", "Ventas asociadas por ciudad (USD)", col, "$%{x:,.0f}"),
                            use_container_width=True)
            top2 = (g["Quito", "ventas"] + g["Guayaquil", "ventas"]) / th["ventas"].sum() * 100
            resto = th.drop(["Quito", "Guayaquil"])
            bloques(f"Quito ${g['Quito', 'ventas']:,.0f} y Guayaquil ${g['Guayaquil', 'ventas']:,.0f} suman el "
                    f"{top2:.1f} % de ${th['ventas'].sum():,.0f}. Ticket promedio ≈ USD "
                    f"{(g['Quito', 'ventas'] + g['Guayaquil', 'ventas']) / (g['Quito', 'pedidos'] + g['Guayaquil', 'pedidos']):.1f} "
                    f"en ambas, frente a ≈ USD {resto['ventas'].sum() / resto['pedidos'].sum():.0f} en el resto.",
                    "El crecimiento comercial depende de dos plazas, y son también las de mayor ticket.",
                    "Corregir rutas y servicio sin restringir el crecimiento. Cualquier medida en Guayaquil "
                    "debe proteger el volumen.")

        elif eleccion == "Operativo":
            etiqueta_solidez("Hallazgo robusto (Guayaquil) · señal relevante (Manta)", VERDE)
            orden = th.sort_values("a_tiempo").index.tolist()
            col = [ROJO if th.loc[c, "a_tiempo"] < u["a_tiempo"] else VERDE for c in orden]
            st.plotly_chart(grafico(orden, "a_tiempo", f"Entregas a tiempo según SLA del canal (%) · meta {u['a_tiempo']:g} %",
                                    col, "%{x:.1f} %", linea=u["a_tiempo"], etiqueta_linea="Meta"),
                            use_container_width=True)
            ex = f[(f["ciudad"] == "Guayaquil") & (f["canal_entrega"] == "Express")]["a_tiempo"].mean() * 100
            bloques(f"Loja {g['Loja', 'a_tiempo']:.1f} %, Manta {g['Manta', 'a_tiempo']:.1f} % y Guayaquil "
                    f"{g['Guayaquil', 'a_tiempo']:.1f} % frente a la meta de {u['a_tiempo']:g} %. Distancia media: "
                    f"{g['Loja', 'dist_media']:.1f} km (Loja) y {g['Manta', 'dist_media']:.1f} km (Manta). "
                    f"Express en Guayaquil: {ex:.0f} %.",
                    "El incumplimiento coincide con rutas largas: sugiere un componente estructural de ruta "
                    "antes que de gestión local.",
                    "Revisar rutas y ventanas de entrega, empezando por Guayaquil. "
                    "Cuenca, Ambato y Quito superan la meta.")
            st.caption("El SLA por canal (Express 120, Estándar urbano 180, Programado 210 min) es un supuesto "
                       "del grupo que Operaciones debe validar. Editable en `kpis.py` (SLA).")

        elif eleccion == "Financiero":
            etiqueta_solidez("Hallazgo robusto", VERDE)
            orden = th.sort_values("usd_por_km").index.tolist()
            col = [ROJO if th.loc[c, "usd_por_km"] < u["usd_por_km"] else VERDE for c in orden]
            st.plotly_chart(grafico(orden, "usd_por_km", f"Eficiencia logística: ventas por km recorrido (USD/km) · umbral {u['usd_por_km']:g}",
                                    col, "%{x:.2f}", linea=u["usd_por_km"], etiqueta_linea="Umbral"),
                            use_container_width=True)
            bloques(f"Guayaquil {g['Guayaquil', 'usd_por_km']:.2f} vs. Quito {g['Quito', 'usd_por_km']:.2f} USD/km "
                    f"con ticket similar. Recorre {g['Guayaquil', 'dist_media']:.1f} km por pedido frente a "
                    f"{g['Quito', 'dist_media']:.1f} km en Quito. Manta {g['Manta', 'usd_por_km']:.2f} y Loja {g['Loja', 'usd_por_km']:.2f}.",
                    "Cada dólar vendido en Guayaquil exige más recorrido: es consistente con la caída de margen "
                    "que reporta el panel.",
                    "Consolidar pedidos y optimizar rutas para llevar la eficiencia a 2,80. "
                    "Integrar costos reales para confirmar el efecto.")
            st.caption("La base no trae costos ni margen: USD por km es una aproximación de la presión logística, "
                       "no un margen.")

        else:
            etiqueta_solidez("Señal relevante", AMBAR)
            orden = th.sort_values("tasa_reclamos", ascending=False).index.tolist()
            col = [ROJO if th.loc[c, "tasa_reclamos"] > 50 else AMBAR if th.loc[c, "tasa_reclamos"] > u["tasa_reclamos"]
                   else VERDE for c in orden]
            fig_c = grafico(orden, "tasa_reclamos", f"Reclamos por mil pedidos (‰) · umbral {u['tasa_reclamos']:g}",
                            col, "%{x:.1f}", linea=u["tasa_reclamos"], etiqueta_linea="Umbral")
            fig_c.data[0].error_x = dict(type="data", symmetric=False, color="black", thickness=1,
                                         array=(th.loc[orden, "ic_alto"] - th.loc[orden, "tasa_reclamos"]).values,
                                         arrayminus=(th.loc[orden, "tasa_reclamos"] - th.loc[orden, "ic_bajo"]).values)
            fig_c.update_xaxes(range=[0, th["ic_alto"].max() * 1.15])
            st.plotly_chart(fig_c, use_container_width=True)
            st.caption("Las barras de error son el intervalo de confianza al 95 %.")

            ra = K.reporte_agregado(f, ["ciudad", "canal_entrega"])
            z = ra.pivot(index="ciudad", columns="canal_entrega", values="tasa_reclamos").reindex(index=orden)
            z = z[[c for c in ORDEN_CANAL if c in z.columns]]
            fig_h = go.Figure(go.Heatmap(z=z.values, x=z.columns, y=z.index, colorscale="Oranges",
                                         text=z.round(1).astype(str).where(z.notna(), "oculto"),
                                         texttemplate="%{text}", hoverongaps=False, colorbar_title="‰"))
            fig_h.update_layout(title="Reclamos por mil por ciudad y canal (celdas pequeñas ocultas)",
                                template="plotly_white", height=380, yaxis_autorange="reversed")
            st.plotly_chart(fig_h, use_container_width=True)
            mm = f[f["ciudad"] == "Manta"].groupby("mes", observed=True)["reclamos_registrados"].mean() * 1000
            manta_exp = z.loc["Manta", "Express"] if "Express" in z.columns else float("nan")
            bloques(f"Manta {g['Manta', 'tasa_reclamos']:.1f} ‰ (IC 95 %: {g['Manta', 'ic_bajo']:.0f}–"
                    f"{g['Manta', 'ic_alto']:.0f} ‰) frente a {f['reclamos_registrados'].mean() * 1000:.1f} ‰ de promedio. "
                    f"Canal Express de Manta: {manta_exp:.0f} ‰, la más alta de la red.",
                    "Los reclamos se concentran en Express, por demora en entrega e incumplimiento de horario. "
                    f"Rango mensual en Manta: {mm.min():.0f}–{mm.max():.0f} ‰.",
                    "Plan de atención y aviso proactivo en Express. Desagregar por canal antes de escalar la medida.")
    st.caption(FUENTE)

# =====================================================================
# 4c. Comité directivo (semana 3): del dashboard a la decisión
# =====================================================================
with tab_com:
    st.subheader("¿Qué hallazgos deben convertirse en decisiones el próximo trimestre?")
    st.caption("Esta vista usa los mismos filtros y la misma base que las demás. Solo muestra datos "
               "agregados por ciudad; el detalle por pedido y por cliente no se expone aquí.")

    tc = K.tabla_ciudades(f)
    al = K.alertas_ciudad(tc)
    prom = f["reclamos_registrados"].mean() * 1000
    rob = K.robustez(tc, al, prom, K.meses_sobre_promedio(f, prom))

    if len(tc) < 2:
        st.info("Selecciona al menos dos provincias para comparar ciudades.")

    # --- Semáforo por ciudad ---------------------------------------------
    st.markdown("#### 1. Desempeño por ciudad frente a los umbrales")
    u = K.UMBRALES_COMITE
    vista = pd.DataFrame({
        "Pedidos": tc["pedidos"],
        "Ventas (USD)": tc["ventas"].round(0),
        f"A tiempo % (≥{u['a_tiempo']:g})": tc["a_tiempo"].round(1),
        f"Reclamos ‰ (≤{u['tasa_reclamos']:g})": tc["tasa_reclamos"].round(1),
        f"USD/km (≥{u['usd_por_km']:g})": tc["usd_por_km"].round(2),
        f"Atención min (≤{u['t_atencion']:g})": tc["t_atencion"].round(1),
        "Nivel de atención": al["nivel"],
        "Solidez de la evidencia": rob,
    }).sort_values("Pedidos", ascending=False)

    def pinta(v, malo):
        return "background-color: #f6d5d0" if malo else "background-color: #d9eadf"

    estilo = vista.style.format({"Pedidos": "{:,.0f}", "Ventas (USD)": "{:,.0f}",
                                 vista.columns[2]: "{:.1f}", vista.columns[3]: "{:.1f}",
                                 vista.columns[4]: "{:.2f}", vista.columns[5]: "{:.1f}"})
    for col, malo in [(f"A tiempo % (≥{u['a_tiempo']:g})", lambda v: v < u["a_tiempo"]),
                      (f"Reclamos ‰ (≤{u['tasa_reclamos']:g})", lambda v: v > u["tasa_reclamos"]),
                      (f"USD/km (≥{u['usd_por_km']:g})", lambda v: v < u["usd_por_km"]),
                      (f"Atención min (≤{u['t_atencion']:g})", lambda v: v > u["t_atencion"])]:
        estilo = estilo.map(lambda v, m=malo: pinta(v, m(v)), subset=[col])
    st.dataframe(estilo, use_container_width=True)
    st.info(K.NOTA_INTERPRETABILIDAD)
    pequenas = tc.index[tc["pedidos"] < 500].tolist()
    if pequenas:
        st.warning("Volumen histórico bajo (menos de 500 pedidos): " + ", ".join(pequenas)
                   + ". Sus resultados se comunican con cautela y no se tratan como definitivos.")

    # --- IPO ---------------------------------------------------------------
    st.markdown("#### 2. Índice de Prioridad Operativa (IPO)")
    st.caption("Ordena la agenda del comité; no reemplaza su criterio. Los pesos son una propuesta "
               "inicial: ajústalos para ver cómo cambia la prioridad.")
    p1, p2, p3, p4 = st.columns(4)
    pesos = {"R": p1.slider("Reclamos", 0, 100, int(K.PESOS_IPO["R"] * 100), 5),
             "E": p2.slider("Incumplimiento de entregas", 0, 100, int(K.PESOS_IPO["E"] * 100), 5),
             "F": p3.slider("Ineficiencia logística", 0, 100, int(K.PESOS_IPO["F"] * 100), 5),
             "A": p4.slider("Tiempo de atención", 0, 100, int(K.PESOS_IPO["A"] * 100), 5)}
    if sum(pesos.values()) == 0:
        st.warning("Al menos un peso debe ser mayor que cero.")
    else:
        ipo = K.calcular_ipo(tc, pesos)
        d = tc.join(ipo[["IPO", "confiabilidad"]]).join(al["nivel"]).reset_index()
        fig_i = px.scatter(d, x="pedidos", y="IPO", size="ventas", color="nivel", text="ciudad",
                           color_discrete_map={"Alto": "#c0392b", "Medio": "#e0a100", "Bajo": "#2e8b57"},
                           labels={"pedidos": "Pedidos del periodo (volumen de evidencia)",
                                   "IPO": "IPO (0-100)", "nivel": "Nivel de atención"},
                           title="Dónde intervenir y dónde investigar primero",
                           template="plotly_white", size_max=45)
        fig_i.update_traces(textposition="top center")
        fig_i.add_hline(y=40, line_dash="dash", line_color="gray")
        fig_i.add_vline(x=1000, line_dash="dash", line_color="gray")
        fig_i.update_yaxes(range=[0, 115])
        st.plotly_chart(fig_i, use_container_width=True)
        st.caption("Arriba a la derecha (IPO alto y volumen alto): intervenir. Arriba a la izquierda "
                   "(IPO alto y volumen bajo): investigar antes de actuar a gran escala. "
                   "Tamaño del círculo: ventas.")
        st.dataframe(d[["ciudad", "IPO", "confiabilidad", "nivel"]].sort_values("IPO", ascending=False)
                     .rename(columns={"confiabilidad": "Confiabilidad (volumen)", "nivel": "Nivel de atención"})
                     .round(1), use_container_width=True, hide_index=True)

    # --- Seguimiento -------------------------------------------------------
    st.markdown("#### 3. Seguimiento de las decisiones")
    st.caption("Línea base: el periodo filtrado. Meta: segundo trimestre. Regla de escalamiento: "
               "un KPI fuera de umbral en dos revisiones seguidas sube al comité.")
    filas = []
    for s in K.SEGUIMIENTO:
        if s["ciudad"] not in tc.index:
            continue
        base = tc.loc[s["ciudad"], s["col"]]
        cumple = base >= s["meta"] if s["mejor"] == "mayor" else base <= s["meta"]
        filas.append({"Ciudad": s["ciudad"], "Decisión": s["decision"], "KPI": s["kpi"],
                      "Línea base": round(base, 2), "Meta T2": s["meta"],
                      "Estado hoy": "🟢 cumple" if cumple else "🔴 por mejorar",
                      "Revisión": s["revision"], "Responsable": s["responsable"]})
    filas.append({"Ciudad": "Cuenca", "Decisión": "Monitoreo de inventario",
                  "KPI": "Integrar fuente de inventario", "Línea base": None, "Meta T2": None,
                  "Estado hoy": "⚪ sin dato", "Revisión": "Mensual", "Responsable": "Operaciones / TI"})
    st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    # --- Privacidad --------------------------------------------------------
    st.markdown("#### 4. Reporte agregado con protección de datos")
    st.caption(f"Se oculta toda celda con menos de {K.MIN_PEDIDOS_PUBLICAR} pedidos o "
               f"{K.MIN_RECLAMOS_PUBLICAR} reclamos para evitar identificar clientes.")
    ra = K.reporte_agregado(f, ["ciudad", "canal_entrega"])
    ra["tasa_reclamos"] = ra["tasa_reclamos"].round(1)
    st.dataframe(ra.rename(columns={"ciudad": "Ciudad", "canal_entrega": "Canal", "pedidos": "Pedidos",
                                    "reclamos": "Reclamos", "tasa_reclamos": "Reclamos por 1.000"}),
                 use_container_width=True, hide_index=True)
    st.caption(FUENTE)

# =====================================================================
# 5. Documentación
# =====================================================================
with tab4:
    st.subheader("Fichas técnicas de los KPIs")
    ficha_df = pd.DataFrame(K.FICHAS).drop(columns=["clave", "unidad"])
    ficha_df.columns = ["KPI", "Objetivo", "Fórmula", "Fuente", "Frecuencia", "Interpretación",
                        "Audiencia", "Meta", "Umbral"]
    ficha_df = ficha_df[["KPI", "Objetivo", "Fórmula", "Fuente", "Frecuencia", "Meta", "Umbral",
                         "Interpretación", "Audiencia"]]
    st.dataframe(ficha_df, use_container_width=True, hide_index=True)
    st.caption("Semáforo: 🟢 cumple la meta, 🟡 entre la meta y el umbral, 🔴 pasa el umbral.")

    st.subheader("Supuestos")
    st.markdown(
        "- La base no trae metas: **nosotros** las propusimos a partir del primer trimestre y "
        "deben validarse con cada área.\n"
        "- No usamos rentabilidad porque la base no tiene costos. «Ventas en riesgo» es la venta "
        "de pedidos con reclamo, no una pérdida real.\n"
        "- No limpiamos la base; solo tipamos la fecha y creamos columnas auxiliares.\n"
        "- Con tres meses de datos no podemos hablar de tendencias.")

    st.subheader("Riesgos y límites de lectura")
    st.markdown(
        "- **Sobreinteractividad:** muchos filtros permiten llegar a subgrupos con pocos pedidos. "
        "Por eso avisamos cuando hay menos de 100 pedidos y ocultamos celdas con muestra pequeña.\n"
        "- **Sesgos visuales:** las barras parten de cero, los ejes se mantienen fijos entre "
        "provincias y la tasa se muestra por 1.000 pedidos para no premiar a las provincias grandes.\n"
        "- **Privacidad:** la base no tiene datos personales del cliente. Si se agregaran, "
        "habría que anonimizarlos antes de mostrarlos en la tabla de detalle.\n"
        "- **Gobernanza:** fuente única, fórmulas documentadas y metas con responsable. "
        "Los cálculos del notebook y del panel salen del mismo código (`kpis.py`).\n"
        "- **Límites interpretativos:** el análisis es exploratorio. Dos variables que se mueven "
        "juntas no demuestran causa, y no controlamos distancia, canal y cliente a la vez.")
