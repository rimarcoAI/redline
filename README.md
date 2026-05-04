# Redline — IMU BT50 Basketball Analyzer

Aplicación local en Python/Streamlit para analizar datos del sensor IMU BT50 en sesiones de baloncesto indoor.

## Características

- Importación de CSV con 10 canales del sensor (timestamp, ax, ay, az, gx, gy, gz, roll, pitch, yaw)
- Gestión de perfiles de jugador con umbrales individuales persistidos en JSON
- Detección de eventos **agrupados** (no muestra a muestra):
  - Aceleraciones / sprints
  - Deceleraciones
  - Saltos
  - Cambios de dirección (via giroscopio)
  - Períodos de alta carga
- Gráficos interactivos con Plotly (señal + regiones de eventos coloreadas)
- Resumen de sesión con métricas clave (Player Load, ratio activo, picos)
- Exportación a CSV de eventos, resumen y señal procesada completa

## Instalación

```bash
# 1. Clonar / descargar el proyecto
cd redline

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate      # Linux / Mac
# .venv\Scripts\activate       # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

## Uso

### Generar datos de ejemplo

```bash
python data/generate_sample.py
# Crea: data/sample_session.csv  (5 min, 100 Hz, 30 000 muestras)
```

### Lanzar la aplicación

```bash
streamlit run app.py
```

La app abrirá en el navegador en `http://localhost:8501`.

### Flujo de trabajo

1. **Importar CSV** — sube el archivo en la barra lateral.
2. **Perfil de jugador** — selecciona uno existente o crea uno nuevo (posición, peso).
3. **Umbrales** (pestaña ⚙️) — ajusta los umbrales de cada tipo de evento; guárdalos en el perfil.
4. **Procesar sesión** — pulsa el botón para analizar la señal.
5. **Análisis** (pestaña 📈) — visualiza los gráficos interactivos con los eventos marcados.
6. **Eventos** (pestaña 🏷️) — tabla filtrable y estadísticas por tipo.
7. **Exportar** (pestaña 💾) — descarga los CSV de eventos, resumen o señal completa.

## Formato del CSV de entrada

| Columna    | Descripción                        | Unidades      |
|------------|------------------------------------|---------------|
| timestamp  | Fecha y hora de la muestra         | datetime      |
| ax         | Aceleración eje X                  | g             |
| ay         | Aceleración eje Y                  | g             |
| az         | Aceleración eje Z (vertical ↑)     | g             |
| gx         | Velocidad angular eje X            | °/s           |
| gy         | Velocidad angular eje Y            | °/s           |
| gz         | Velocidad angular eje Z            | °/s           |
| roll       | Ángulo de balanceo                 | °             |
| pitch      | Ángulo de cabeceo                  | °             |
| yaw        | Ángulo de guiñada                  | °             |

## Estructura del proyecto

```
redline/
├── app.py                    # Aplicación Streamlit principal
├── requirements.txt
├── src/
│   ├── detector.py           # Detección de eventos agrupados
│   ├── processor.py          # Procesado de señal y métricas
│   ├── profiles.py           # Gestión de perfiles (JSON)
│   └── exporter.py           # Exportación a CSV
└── data/
    ├── generate_sample.py    # Generador de datos de ejemplo
    ├── sample_session.csv    # Datos de ejemplo generados
    └── profiles/             # Perfiles de jugador (JSON)
```

## Algoritmo de detección

Los eventos se detectan en tres pasos para evitar el conteo muestra a muestra:

1. **Máscara binaria** — la señal supera el umbral configurado.
2. **Fusión de gaps** — regiones separadas por menos de `min_gap` segundos se fusionan en un único evento.
3. **Filtro de duración** — se eliminan eventos más cortos que `min_duration` segundos.

Cada evento reporta: tipo, tiempo de inicio/fin, duración, valor pico y valor medio.

## Métricas calculadas

| Métrica           | Fórmula                                                        |
|-------------------|----------------------------------------------------------------|
| Acc. horizontal   | √(ax² + ay²)                                                   |
| Acc. magnitud     | √(ax² + ay² + az²)                                            |
| Gyro magnitud     | √(gx² + gy² + gz²)                                            |
| Player Load inst. | √(Δax² + Δay² + Δaz²) / fs                                    |
| Player Load acum. | Σ load_instant                                                 |
