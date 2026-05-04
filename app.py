"""IMU BT50 Basketball Analyzer — Streamlit App."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.processor import load_csv, estimate_fs, compute_metrics, compute_session_summary
from src.detector import detect_all_events
from src.profiles import ProfileManager, DEFAULT_THRESHOLDS
from src.exporter import events_to_dataframe, to_csv_bytes, session_summary_to_csv_bytes

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Redline IMU Analyzer",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ────────────────────────────────────────────────────

for key, val in {
    "df_raw": None,
    "df": None,
    "fs": None,
    "events": None,
    "summary": None,
    "active_profile": None,
    "thresholds": DEFAULT_THRESHOLDS.copy(),
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

pm = ProfileManager()

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("🏀 Redline IMU")
    st.caption("Análisis de sensor IMU BT50 — Baloncesto Indoor")
    st.divider()

    # ── Upload CSV ──────────────────────────────────────────────────────────

    st.subheader("1. Importar sesión")
    uploaded = st.file_uploader(
        "Archivo CSV del sensor BT50",
        type="csv",
        help="Columnas requeridas: timestamp, ax, ay, az, gx, gy, gz, roll, pitch, yaw",
    )

    if uploaded:
        df_raw, err = load_csv(uploaded)
        if err:
            st.error(err)
        else:
            st.session_state.df_raw = df_raw
            fs = estimate_fs(df_raw)
            st.session_state.fs = fs
            st.success(f"{len(df_raw):,} muestras  |  ~{fs:.0f} Hz")

    # ── Player Profile ──────────────────────────────────────────────────────

    st.divider()
    st.subheader("2. Perfil de jugador")

    profiles = pm.list_profiles()
    profile_options = ["(sin perfil)"] + profiles

    selected = st.selectbox("Seleccionar perfil", profile_options)
    if selected != "(sin perfil)":
        st.session_state.active_profile = selected
        info = pm.get_info(selected)
        if info:
            st.caption(
                f"**Posición:** {info.get('posicion', '—')}  \n"
                f"**Peso:** {info.get('peso', '—')} kg  \n"
                f"**Notas:** {info.get('notas', '—')}"
            )
        # Load thresholds from profile
        st.session_state.thresholds = pm.get_thresholds(selected)
    else:
        st.session_state.active_profile = None

    with st.expander("Crear / editar perfil"):
        new_name = st.text_input("Nombre del jugador")
        posicion = st.selectbox("Posición", ["Base", "Escolta", "Alero", "Ala-pívot", "Pívot"])
        peso = st.number_input("Peso (kg)", 50, 150, 80)
        notas = st.text_input("Notas")

        if st.button("Guardar perfil", use_container_width=True):
            if new_name.strip():
                pm.create_profile(
                    new_name.strip(),
                    {"posicion": posicion, "peso": peso, "notas": notas},
                )
                st.success(f"Perfil '{new_name}' guardado.")
                st.rerun()
            else:
                st.warning("Escribe un nombre de jugador.")

        if selected != "(sin perfil)" and st.button(
            "Eliminar perfil seleccionado", type="secondary", use_container_width=True
        ):
            pm.delete(selected)
            st.session_state.active_profile = None
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════════════════════════════════════════════

st.title("Análisis de sesión IMU BT50")

if st.session_state.df_raw is None:
    st.info(
        "Importa un archivo CSV en la barra lateral para comenzar.\n\n"
        "Puedes generar datos de ejemplo con:\n```\npython data/generate_sample.py\n```"
    )
    st.stop()

tab_config, tab_analysis, tab_events, tab_export = st.tabs(
    ["⚙️ Umbrales", "📈 Análisis", "🏷️ Eventos", "💾 Exportar"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════════════

with tab_config:
    st.header("Configuración de umbrales")
    t = st.session_state.thresholds

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Aceleración (sprint)")
        t["acc_threshold"] = st.slider(
            "Umbral de aceleración horizontal (g)",
            0.5, 8.0, float(t["acc_threshold"]), 0.1,
            help="Aceleración horizontal mínima para detectar un sprint.",
        )
        t["acc_min_duration"] = st.slider(
            "Duración mínima (s)", 0.1, 2.0, float(t["acc_min_duration"]), 0.05)
        t["acc_min_gap"] = st.slider(
            "Separación mínima entre eventos (s)", 0.2, 3.0, float(t["acc_min_gap"]), 0.1)

        st.subheader("Salto")
        t["jump_threshold"] = st.slider(
            "Umbral az vertical (g)", 1.0, 10.0, float(t["jump_threshold"]), 0.1,
            help="Pico de aceleración vertical para detectar fase de despegue/aterrizaje.",
        )
        t["jump_min_duration"] = st.slider(
            "Duración mínima (s)", 0.05, 1.0, float(t["jump_min_duration"]), 0.05)
        t["jump_min_gap"] = st.slider(
            "Separación mínima entre eventos (s)", 0.2, 3.0, float(t["jump_min_gap"]), 0.1)

        st.subheader("Alta carga")
        t["load_threshold"] = st.slider(
            "Umbral de carga instantánea", 0.01, 0.5, float(t["load_threshold"]), 0.005,
            help="PlayerLoad instantáneo (unidades adimensionales).",
        )
        t["load_min_duration"] = st.slider(
            "Duración mínima (s)", 0.05, 1.0, float(t["load_min_duration"]), 0.05)
        t["load_min_gap"] = st.slider(
            "Separación mínima entre eventos (s)", 0.1, 2.0, float(t["load_min_gap"]), 0.1)

    with col_b:
        st.subheader("Deceleración")
        t["dec_threshold"] = st.slider(
            "Umbral derivada aceleración (g/s)", 1.0, 20.0, float(t["dec_threshold"]), 0.5,
            help="Magnitud del cambio brusco negativo de aceleración.",
        )
        t["dec_min_duration"] = st.slider(
            "Duración mínima (s)", 0.05, 1.0, float(t["dec_min_duration"]), 0.05)
        t["dec_min_gap"] = st.slider(
            "Separación mínima entre eventos (s)", 0.2, 3.0, float(t["dec_min_gap"]), 0.1)

        st.subheader("Cambio de dirección")
        t["dir_threshold"] = st.slider(
            "Umbral giroscopio (°/s)", 50.0, 600.0, float(t["dir_threshold"]), 10.0,
            help="Magnitud del vector de velocidad angular.",
        )
        t["dir_min_duration"] = st.slider(
            "Duración mínima (s)", 0.05, 1.0, float(t["dir_min_duration"]), 0.05)
        t["dir_min_gap"] = st.slider(
            "Separación mínima entre eventos (s)", 0.1, 2.0, float(t["dir_min_gap"]), 0.1)

    st.session_state.thresholds = t

    save_col, process_col = st.columns(2)
    with save_col:
        if st.session_state.active_profile and st.button(
            "Guardar umbrales en perfil", use_container_width=True
        ):
            pm.save_thresholds(st.session_state.active_profile, t)
            st.success("Umbrales guardados en el perfil.")

    with process_col:
        if st.button("Procesar sesión", type="primary", use_container_width=True):
            with st.spinner("Procesando señal y detectando eventos..."):
                df = compute_metrics(st.session_state.df_raw, st.session_state.fs)
                events = detect_all_events(df, t, st.session_state.fs)
                summary = compute_session_summary(df, events, st.session_state.fs)
                st.session_state.df = df
                st.session_state.events = events
                st.session_state.summary = summary
            st.success("Sesión procesada. Ve a la pestaña Análisis.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ANALYSIS CHARTS
# ═══════════════════════════════════════════════════════════════════════════════

with tab_analysis:
    if st.session_state.df is None:
        st.info("Pulsa **Procesar sesión** en la pestaña Umbrales para ver los gráficos.")
        st.stop()

    df = st.session_state.df
    events = st.session_state.events
    summary = st.session_state.summary
    t = st.session_state.thresholds

    # ── Summary cards ───────────────────────────────────────────────────────

    st.subheader("Resumen de sesión")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Duración", f"{summary['Duración (min)']} min")
    c2.metric("Player Load", f"{summary['Player Load total']:.1f}")
    c3.metric("Load / min", f"{summary['Player Load / min']:.2f}")
    c4.metric("Saltos", summary["Saltos detectados"])
    c5.metric("Aceleraciones", summary["Aceleraciones detectadas"])
    c6.metric("Deceleraciones", summary["Deceleraciones detectadas"])

    c7, c8, c9, c10 = st.columns(4)
    c7.metric("Cambios dirección", summary["Cambios de dirección detectados"])
    c8.metric("Ratio activo", f"{summary['Ratio activo (%)']:.1f}%")
    c9.metric("Acc. horiz. máx.", f"{summary['Aceleración horiz. máx. (g)']:.2f} g")
    c10.metric("Giroscopio máx.", f"{summary['Giroscopio máx. (°/s)']:.0f} °/s")

    st.divider()

    # ── Helper to add event shading ─────────────────────────────────────────

    EVENT_COLORS = {
        "accelerations": "rgba(0,200,100,0.18)",
        "decelerations": "rgba(255,80,80,0.18)",
        "jumps": "rgba(80,120,255,0.22)",
        "direction_changes": "rgba(255,180,0,0.22)",
        "high_load": "rgba(200,0,255,0.12)",
    }
    EVENT_LABELS = {
        "accelerations": "Aceleración",
        "decelerations": "Deceleración",
        "jumps": "Salto",
        "direction_changes": "Cambio dir.",
        "high_load": "Alta carga",
    }

    def add_event_shapes(fig, events_dict, categories=None, row=1):
        seen = set()
        shapes = []
        annotations = []
        cats = categories or list(events_dict.keys())
        for cat in cats:
            color = EVENT_COLORS.get(cat, "rgba(128,128,128,0.15)")
            for ev in events_dict.get(cat, []):
                shapes.append(
                    dict(
                        type="rect",
                        xref="x", yref="paper",
                        x0=ev["inicio_s"], x1=ev["fin_s"],
                        y0=0, y1=1,
                        fillcolor=color,
                        line_width=0,
                        layer="below",
                    )
                )
        return shapes

    # ── Chart 1: Horizontal acceleration with events ─────────────────────────

    st.subheader("Aceleración horizontal y eventos")
    fig_acc = go.Figure()

    fig_acc.add_trace(
        go.Scatter(
            x=df["time_s"], y=df["acc_horiz"],
            name="Acc. horizontal (g)",
            line=dict(color="#2196F3", width=1),
            opacity=0.8,
        )
    )
    fig_acc.add_hline(
        y=t["acc_threshold"], line_dash="dash", line_color="green",
        annotation_text=f"Umbral acc {t['acc_threshold']} g",
    )

    for ev in events.get("accelerations", []):
        fig_acc.add_vrect(
            x0=ev["inicio_s"], x1=ev["fin_s"],
            fillcolor=EVENT_COLORS["accelerations"], layer="below", line_width=0,
        )
    for ev in events.get("decelerations", []):
        fig_acc.add_vrect(
            x0=ev["inicio_s"], x1=ev["fin_s"],
            fillcolor=EVENT_COLORS["decelerations"], layer="below", line_width=0,
        )

    fig_acc.update_layout(
        height=300, margin=dict(t=10, b=30),
        xaxis_title="Tiempo (s)", yaxis_title="g",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig_acc, use_container_width=True)

    # ── Chart 2: Vertical acceleration (jumps) ───────────────────────────────

    st.subheader("Aceleración vertical — Saltos")
    fig_jmp = go.Figure()
    fig_jmp.add_trace(
        go.Scatter(
            x=df["time_s"], y=df["az"],
            name="az (g)", line=dict(color="#9C27B0", width=1), opacity=0.7,
        )
    )
    fig_jmp.add_trace(
        go.Scatter(
            x=df["time_s"], y=df["az_smooth"],
            name="az suavizado", line=dict(color="#E91E63", width=2),
        )
    )
    fig_jmp.add_hline(
        y=t["jump_threshold"], line_dash="dash", line_color="#3F51B5",
        annotation_text=f"Umbral salto {t['jump_threshold']} g",
    )
    for ev in events.get("jumps", []):
        fig_jmp.add_vrect(
            x0=ev["inicio_s"], x1=ev["fin_s"],
            fillcolor=EVENT_COLORS["jumps"], layer="below", line_width=0,
        )
    fig_jmp.update_layout(
        height=300, margin=dict(t=10, b=30),
        xaxis_title="Tiempo (s)", yaxis_title="g",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig_jmp, use_container_width=True)

    # ── Chart 3: Gyroscope magnitude (direction changes) ─────────────────────

    st.subheader("Magnitud del giroscopio — Cambios de dirección")
    fig_gyro = go.Figure()
    fig_gyro.add_trace(
        go.Scatter(
            x=df["time_s"], y=df["gyro_mag"],
            name="Giroscopio (°/s)", line=dict(color="#FF9800", width=1), opacity=0.8,
        )
    )
    fig_gyro.add_hline(
        y=t["dir_threshold"], line_dash="dash", line_color="#FF5722",
        annotation_text=f"Umbral dir. {t['dir_threshold']} °/s",
    )
    for ev in events.get("direction_changes", []):
        fig_gyro.add_vrect(
            x0=ev["inicio_s"], x1=ev["fin_s"],
            fillcolor=EVENT_COLORS["direction_changes"], layer="below", line_width=0,
        )
    fig_gyro.update_layout(
        height=300, margin=dict(t=10, b=30),
        xaxis_title="Tiempo (s)", yaxis_title="°/s",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig_gyro, use_container_width=True)

    # ── Chart 4: Player Load curve ───────────────────────────────────────────

    st.subheader("Carga acumulada del jugador (Player Load)")
    fig_load = make_subplots(specs=[[{"secondary_y": True}]])
    fig_load.add_trace(
        go.Scatter(
            x=df["time_s"], y=df["load_cumul"],
            name="Load acumulado", line=dict(color="#4CAF50", width=2),
        ),
        secondary_y=False,
    )
    fig_load.add_trace(
        go.Scatter(
            x=df["time_s"], y=df["load_instant"] * st.session_state.fs,  # per-second rate
            name="Load instantáneo (×fs)", line=dict(color="#8BC34A", width=1),
            opacity=0.5,
        ),
        secondary_y=True,
    )
    fig_load.update_layout(
        height=300, margin=dict(t=10, b=30),
        xaxis_title="Tiempo (s)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig_load.update_yaxes(title_text="Load acumulado", secondary_y=False)
    fig_load.update_yaxes(title_text="Tasa de carga", secondary_y=True)
    st.plotly_chart(fig_load, use_container_width=True)

    # ── Chart 5: Roll / Pitch / Yaw ──────────────────────────────────────────

    with st.expander("Orientación (Roll / Pitch / Yaw)"):
        fig_orient = go.Figure()
        for col, color, label in [
            ("roll", "#F44336", "Roll"),
            ("pitch", "#2196F3", "Pitch"),
            ("yaw", "#4CAF50", "Yaw"),
        ]:
            fig_orient.add_trace(
                go.Scatter(x=df["time_s"], y=df[col], name=label, line=dict(color=color, width=1))
            )
        fig_orient.update_layout(
            height=280, margin=dict(t=10, b=30),
            xaxis_title="Tiempo (s)", yaxis_title="°",
            hovermode="x unified",
        )
        st.plotly_chart(fig_orient, use_container_width=True)

    # ── Chart 6: Event timeline ──────────────────────────────────────────────

    st.subheader("Línea de tiempo de eventos")
    ev_df = events_to_dataframe(events)
    if not ev_df.empty:
        COLOR_MAP = {
            "Aceleración": "#4CAF50",
            "Deceleración": "#F44336",
            "Salto": "#2196F3",
            "Cambio de dirección": "#FF9800",
            "Alta carga": "#9C27B0",
        }
        fig_tl = go.Figure()
        for tipo, grp in ev_df.groupby("tipo"):
            fig_tl.add_trace(
                go.Bar(
                    x=grp["duracion_s"],
                    y=[tipo] * len(grp),
                    base=grp["inicio_s"],
                    orientation="h",
                    name=tipo,
                    marker_color=COLOR_MAP.get(tipo, "gray"),
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        "Inicio: %{base:.1f}s<br>"
                        "Duración: %{x:.2f}s<br>"
                        "Pico: %{customdata:.3f}<extra></extra>"
                    ),
                    customdata=grp["pico"].values,
                )
            )
        fig_tl.update_layout(
            height=280, barmode="overlay",
            xaxis_title="Tiempo (s)", yaxis_title="",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=10, b=30),
        )
        st.plotly_chart(fig_tl, use_container_width=True)
    else:
        st.warning("No se detectaron eventos con los umbrales actuales.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EVENTS TABLE
# ═══════════════════════════════════════════════════════════════════════════════

with tab_events:
    if st.session_state.events is None:
        st.info("Pulsa **Procesar sesión** en la pestaña Umbrales.")
        st.stop()

    events = st.session_state.events
    ev_df = events_to_dataframe(events)

    if ev_df.empty:
        st.warning("No se detectaron eventos con los umbrales actuales.")
        st.stop()

    st.subheader("Tabla de eventos detectados")

    # Filters
    col_f1, col_f2 = st.columns(2)
    tipos_disponibles = sorted(ev_df["tipo"].unique())
    tipos_sel = col_f1.multiselect("Filtrar por tipo", tipos_disponibles, default=tipos_disponibles)
    min_dur = col_f2.slider(
        "Duración mínima (s)", 0.0, float(ev_df["duracion_s"].max()), 0.0, 0.01
    )

    filtered = ev_df[ev_df["tipo"].isin(tipos_sel) & (ev_df["duracion_s"] >= min_dur)]

    st.dataframe(
        filtered.drop(columns=["inicio", "fin"], errors="ignore").rename(
            columns={
                "tipo": "Tipo",
                "inicio_s": "Inicio (s)",
                "fin_s": "Fin (s)",
                "duracion_s": "Duración (s)",
                "pico": "Pico",
                "media": "Media",
            }
        ),
        use_container_width=True,
        height=420,
    )

    # Per-type stats
    st.subheader("Estadísticas por tipo de evento")
    stats = (
        filtered.groupby("tipo")
        .agg(
            Cantidad=("tipo", "count"),
            Duración_media_s=("duracion_s", "mean"),
            Duración_total_s=("duracion_s", "sum"),
            Pico_máx=("pico", "max"),
            Pico_medio=("pico", "mean"),
        )
        .round(3)
        .reset_index()
        .rename(columns={"tipo": "Tipo"})
    )
    st.dataframe(stats, use_container_width=True)

    # Distribution chart
    st.subheader("Distribución de duraciones por tipo")
    fig_box = go.Figure()
    for tipo in tipos_sel:
        sub = filtered[filtered["tipo"] == tipo]
        if not sub.empty:
            fig_box.add_trace(
                go.Box(y=sub["duracion_s"], name=tipo, boxpoints="all", jitter=0.3, pointpos=-1.5)
            )
    fig_box.update_layout(
        height=320, margin=dict(t=10, b=30),
        yaxis_title="Duración (s)",
    )
    st.plotly_chart(fig_box, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

with tab_export:
    if st.session_state.events is None:
        st.info("Pulsa **Procesar sesión** en la pestaña Umbrales.")
        st.stop()

    events = st.session_state.events
    summary = st.session_state.summary
    ev_df = events_to_dataframe(events)

    st.subheader("Exportar datos de la sesión")

    col_e1, col_e2, col_e3 = st.columns(3)

    with col_e1:
        st.markdown("**Eventos detectados**")
        if not ev_df.empty:
            st.download_button(
                label="Descargar eventos (CSV)",
                data=to_csv_bytes(ev_df),
                file_name="eventos_imu.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.caption(f"{len(ev_df)} eventos en el archivo.")
        else:
            st.warning("Sin eventos para exportar.")

    with col_e2:
        st.markdown("**Resumen de sesión**")
        summary_df = pd.DataFrame(list(summary.items()), columns=["Métrica", "Valor"])
        st.download_button(
            label="Descargar resumen (CSV)",
            data=to_csv_bytes(summary_df),
            file_name="resumen_sesion.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_e3:
        st.markdown("**Señal procesada completa**")
        export_cols = [
            "timestamp", "time_s",
            "ax", "ay", "az",
            "gx", "gy", "gz",
            "roll", "pitch", "yaw",
            "acc_horiz", "acc_mag", "gyro_mag",
            "load_instant", "load_cumul",
        ]
        df_export = st.session_state.df[export_cols]
        st.download_button(
            label="Descargar señal (CSV)",
            data=to_csv_bytes(df_export),
            file_name="señal_procesada.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.caption(f"{len(df_export):,} muestras.")

    # Full summary table preview
    st.divider()
    st.subheader("Resumen completo")
    st.table(summary_df)
