import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="IQ Option Signal Bot", page_icon="📈", layout="wide")

st.title("📈 IQ Option Signal Bot")
st.caption("Prototipo de análisis técnico para velas de 1 minuto · Solo señales, sin ejecución de operaciones")

st.warning(
    "Este prototipo no está conectado a IQ Option ni recibe precios en vivo por sí solo. "
    "Carga un CSV de velas de 1 minuto obtenido de una fuente autorizada. "
    "Las señales son experimentales y no garantizan resultados."
)

REQUIRED = {"timestamp", "asset", "open", "high", "low", "close"}

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.sort_values("timestamp").copy()
    close = d["close"].astype(float)
    d["ema9"] = close.ewm(span=9, adjust=False).mean()
    d["ema21"] = close.ewm(span=21, adjust=False).mean()
    d["ema50"] = close.ewm(span=50, adjust=False).mean()
    d["rsi14"] = rsi(close)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    d["macd"] = ema12 - ema26
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["bb_mid"] = close.rolling(20).mean()
    d["bb_std"] = close.rolling(20).std(ddof=0)
    d["bb_upper"] = d["bb_mid"] + 2 * d["bb_std"]
    d["bb_lower"] = d["bb_mid"] - 2 * d["bb_std"]
    d["atr"] = pd.concat([
        d["high"] - d["low"],
        (d["high"] - d["close"].shift()).abs(),
        (d["low"] - d["close"].shift()).abs()
    ], axis=1).max(axis=1).rolling(14).mean()
    d["atr_pct"] = d["atr"] / close.replace(0, np.nan) * 100
    return d

def evaluate_latest(d: pd.DataFrame):
    x = d.iloc[-1]
    if pd.isna(x[["rsi14", "macd", "macd_signal", "bb_mid", "atr_pct"]]).any():
        return "WAIT", 0, ["Datos insuficientes para calcular todos los indicadores"]

    call_checks = {
        "EMA9 por encima de EMA21": x.ema9 > x.ema21,
        "EMA21 por encima de EMA50": x.ema21 > x.ema50,
        "RSI entre 52 y 68": 52 <= x.rsi14 <= 68,
        "MACD por encima de su señal": x.macd > x.macd_signal,
        "Cierre por encima de EMA9": x.close > x.ema9,
        "Precio no extendido sobre Bollinger": x.close <= x.bb_upper,
    }
    put_checks = {
        "EMA9 por debajo de EMA21": x.ema9 < x.ema21,
        "EMA21 por debajo de EMA50": x.ema21 < x.ema50,
        "RSI entre 32 y 48": 32 <= x.rsi14 <= 48,
        "MACD por debajo de su señal": x.macd < x.macd_signal,
        "Cierre por debajo de EMA9": x.close < x.ema9,
        "Precio no extendido bajo Bollinger": x.close >= x.bb_lower,
    }

    call_score = sum(bool(v) for v in call_checks.values())
    put_score = sum(bool(v) for v in put_checks.values())
    reasons = []
    # Filtro de volatilidad extrema: ATR relativo superior a 0.35% queda fuera.
    if x.atr_pct > 0.35:
        return "WAIT", max(call_score, put_score), ["Volatilidad relativa elevada: filtro de riesgo activado"]
    if call_score >= 5 and call_score - put_score >= 3:
        reasons = [k for k, v in call_checks.items() if v]
        return "CALL", call_score, reasons
    if put_score >= 5 and put_score - call_score >= 3:
        reasons = [k for k, v in put_checks.items() if v]
        return "PUT", put_score, reasons
    return "WAIT", max(call_score, put_score), ["No hay suficiente confluencia; el sistema conservador no emite señal"]

uploaded = st.file_uploader("Carga un CSV de velas de 1 minuto", type=["csv"])
st.markdown("""
**Formato requerido:** `timestamp, asset, open, high, low, close`  
Una fila por vela y activo. `timestamp` debe ser una fecha/hora reconocible; precios numéricos.
""")

if uploaded:
    try:
        raw = pd.read_csv(uploaded)
        raw.columns = [c.strip().lower() for c in raw.columns]
        missing = REQUIRED - set(raw.columns)
        if missing:
            st.error("Faltan columnas obligatorias: " + ", ".join(sorted(missing)))
            st.stop()

        raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce", utc=True)
        for c in ["open", "high", "low", "close"]:
            raw[c] = pd.to_numeric(raw[c], errors="coerce")
        raw["asset"] = raw["asset"].astype(str).str.strip()
        raw = raw.dropna(subset=["timestamp", "asset", "open", "high", "low", "close"])
        raw = raw[(raw["high"] >= raw[["open", "close", "low"]].max(axis=1)) &
                  (raw["low"] <= raw[["open", "close", "high"]].min(axis=1))]
        if raw.empty:
            st.error("El archivo no contiene velas válidas.")
            st.stop()

        # Duplicados por activo y marca temporal se reducen a la última fila.
        raw = raw.sort_values("timestamp").drop_duplicates(["asset", "timestamp"], keep="last")
        assets = sorted(raw["asset"].unique().tolist())
        selected = st.multiselect("Activos a analizar", assets, default=assets)
        min_candles = st.number_input("Mínimo de velas por activo", min_value=60, max_value=1000, value=100, step=10)

        results = []
        detail = {}
        for asset in selected:
            part = raw[raw.asset == asset].sort_values("timestamp")
            if len(part) < min_candles:
                results.append({"Activo": asset, "Señal": "WAIT", "Puntuación": "—",
                                "Última vela (UTC)": part.timestamp.iloc[-1].strftime("%Y-%m-%d %H:%M"),
                                "Motivo": f"Solo {len(part)} velas; se requieren al menos {int(min_candles)}"})
                continue
            calc = add_indicators(part)
            signal, score, reasons = evaluate_latest(calc)
            detail[asset] = calc
            results.append({
                "Activo": asset, "Señal": signal, "Puntuación": f"{score}/6",
                "Última vela (UTC)": calc.timestamp.iloc[-1].strftime("%Y-%m-%d %H:%M"),
                "Motivo": "; ".join(reasons)
            })

        st.subheader("Panel de señales")
        if results:
            res = pd.DataFrame(results)
            st.dataframe(res, use_container_width=True, hide_index=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Activos revisados", len(results))
            c2.metric("Señales CALL", int((res["Señal"] == "CALL").sum()))
            c3.metric("Señales PUT", int((res["Señal"] == "PUT").sum()))

            st.download_button("Descargar análisis CSV", res.to_csv(index=False).encode("utf-8"),
                               file_name="senales_iq_option.csv", mime="text/csv")

            if detail:
                chosen = st.selectbox("Ver indicadores de un activo", list(detail.keys()))
                view = detail[chosen].tail(30)
                st.line_chart(view.set_index("timestamp")[["close", "ema9", "ema21", "ema50"]])
                last = view.iloc[-1]
                st.write({
                    "Activo": chosen,
                    "RSI 14": round(float(last.rsi14), 2) if pd.notna(last.rsi14) else None,
                    "MACD": round(float(last.macd), 6) if pd.notna(last.macd) else None,
                    "ATR %": round(float(last.atr_pct), 4) if pd.notna(last.atr_pct) else None
                })
        else:
            st.info("Selecciona al menos un activo.")
    except Exception as exc:
        st.error(f"No se pudo procesar el archivo: {exc}")
else:
    st.info("Cuando cargues un CSV válido, aquí aparecerán las señales de todos los activos incluidos.")

with st.expander("Reglas y limitaciones del prototipo"):
    st.markdown("""
    - Señal CALL o PUT solo si se cumplen al menos 5 de 6 condiciones y la diferencia frente a la dirección contraria es de 3 puntos.
    - RSI, MACD, EMA y Bollinger son filtros técnicos, no probabilidades de ganar.
    - WAIT significa que no hay una configuración suficientemente clara.
    - El filtro ATR es un umbral inicial configurable en el código, no una regla universal.
    - No se calcula una tasa de acierto hasta comparar cada señal con el precio de expiración real.
    - Este prototipo asume que el CSV contiene velas de 1 minuto. No convierte automáticamente otras temporalidades.
    - Los datos OTC pueden tener características distintas a los mercados convencionales; deben validarse por separado.
    """)
