# IQ Option Signal Bot — prototipo

## Qué incluye
- Panel Streamlit local.
- Lectura de CSV con velas de 1 minuto de múltiples activos.
- Indicadores EMA 9/21/50, RSI 14, MACD, Bollinger y ATR.
- Señales conservadoras CALL / PUT / WAIT.
- Exportación del resumen a CSV.

## Requisitos
Python 3.10 o superior.

## Instalación
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Abre la dirección local que Streamlit muestra en la terminal.

## CSV esperado
Columnas obligatorias:
`timestamp,asset,open,high,low,close`

Ejemplo de formato (valores ilustrativos, no son precios reales):
```csv
timestamp,asset,open,high,low,close
2026-11-14T12:00:00Z,EURUSD,1.0800,1.0810,1.0798,1.0807
2026-11-14T12:01:00Z,EURUSD,1.0807,1.0812,1.0804,1.0810
```
Se necesitan al menos 100 velas por activo por defecto para calcular indicadores con mayor estabilidad.

## Importante
Este proyecto NO se conecta a IQ Option, no inicia sesión, no coloca operaciones y no garantiza rentabilidad.
Debes obtener datos de una fuente autorizada y comprobar que sean velas de 1 minuto. No compartas contraseñas ni cookies con scripts de terceros.
Antes de usar dinero real, valida con datos históricos y observación en demo. La puntuación es una medida de confluencia técnica, no una probabilidad estadística.
