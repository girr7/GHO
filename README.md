# Binance Trading Bot

Bot de trading automatizado que se conecta a Binance usando la API oficial. Implementa estrategias técnicas basadas en RSI y cruce de medias móviles (EMA).

## Características

- Conexión a Binance (mainnet y testnet)
- Tres estrategias configurables: `rsi`, `ma_crossover`, `combined`
- Gestión de riesgo: stop-loss y take-profit automáticos
- Persistencia del estado del portfolio en disco
- Logs en consola (con colores) y en archivo `bot.log`
- Señal SIGINT/SIGTERM para apagado limpio

## Arquitectura

```
bot.py          — Loop principal, orquesta todo
strategy.py     — Lógica de señales (RSI + EMA crossover)
exchange.py     — Wrapper de python-binance con manejo de errores
portfolio.py    — Seguimiento de trades abiertos/cerrados
config.py       — Configuración vía variables de entorno
logger.py       — Logger con colores y archivo
```

## Instalación

```bash
pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus credenciales de Binance
```

## Configuración (`.env`)

| Variable | Descripción | Default |
|----------|-------------|---------|
| `BINANCE_API_KEY` | API Key de Binance | — |
| `BINANCE_API_SECRET` | API Secret de Binance | — |
| `USE_TESTNET` | Usar testnet de Binance | `true` |
| `TRADING_PAIR` | Par de trading (ej. BTCUSDT) | `BTCUSDT` |
| `QUOTE_ASSET` | Asset de cotización | `USDT` |
| `TRADE_AMOUNT` | Cantidad por trade en quote asset | `50` |
| `STRATEGY` | Estrategia: `rsi`, `ma_crossover`, `combined` | `combined` |
| `STOP_LOSS_PERCENT` | % de stop-loss | `2.0` |
| `TAKE_PROFIT_PERCENT` | % de take-profit | `4.0` |
| `MAX_OPEN_TRADES` | Máximo de trades abiertos simultáneos | `3` |
| `KLINE_INTERVAL` | Intervalo de velas (1m, 5m, 15m, 1h…) | `15m` |
| `LOG_LEVEL` | Nivel de log | `INFO` |

## Uso

```bash
python bot.py
```

El bot ejecuta una comprobación inmediatamente y luego a cada intervalo de vela configurado.

## Estrategias

### RSI
- **BUY** cuando RSI ≤ 30 (sobreventa)
- **SELL** cuando RSI ≥ 70 (sobrecompra)

### MA Crossover (EMA 9/21)
- **BUY** en cruce alcista (EMA rápida cruza por encima de la lenta)
- **SELL** en cruce bajista (EMA rápida cruza por debajo de la lenta)

### Combined (recomendada)
Ambas señales deben coincidir para ejecutar una orden. Reduce falsos positivos.

## Gestión de riesgo

Cada trade abierto monitorea en tiempo real:
- **Stop-Loss**: cierra automáticamente si el precio cae X% desde la entrada
- **Take-Profit**: cierra automáticamente si el precio sube X% desde la entrada

## Advertencia

Este bot es educativo. Úsalo en testnet antes de operar con fondos reales. El trading de criptomonedas conlleva riesgos significativos de pérdida de capital.
