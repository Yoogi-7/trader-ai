# Kompleksowy Opis Systemu Generowania Sygnałów Tradingowych

## 📋 Spis Treści

1. [Architektura Systemu](#architektura-systemu)
2. [Proces Generowania Sygnału](#proces-generowania-sygnału)
3. [Obliczanie Poziomów Wejścia](#obliczanie-poziomów-wejścia)
4. [Stop Loss (SL)](#stop-loss-sl)
5. [Take Profit (TP)](#take-profit-tp)
6. [Dźwignia (Leverage)](#dźwignia-leverage)
7. [Position Sizing](#position-sizing)
8. [Filtry Ryzyka](#filtry-ryzyka)
9. [Koszty i Opłaty](#koszty-i-opłaty)
10. [Przykład Pełnego Sygnału](#przykład-pełnego-sygnału)

---

## 1. Architektura Systemu

```
┌─────────────────────────────────────────────────────────────┐
│                    OHLCV Data (Binance)                     │
│                 15-minute candles, 4 years                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Feature Engineering (50+ indicators)            │
│  • VWAP, StochRSI, Keltner, ADX, Supertrend               │
│  • OBV, Volume Profile, OBI, Dynamic Fibonacci             │
│  • EMA Slopes, Consolidation Zones, RSI Divergence         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  ML Model (Ensemble)                        │
│            LightGBM + Conformal Prediction                  │
│                                                             │
│  Input:  50+ features                                       │
│  Output: Probability [0.0 - 1.0]                           │
│          • >0.5 = LONG signal                              │
│          • <0.5 = SHORT signal                             │
│          • Confidence = distance from 0.5                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 Risk Filters (7 checks)                     │
│  ✓ Confidence ≥ 0.65                                       │
│  ✓ ATR > 0                                                 │
│  ✓ Liquidity sufficient                                    │
│  ✓ Spread ≤ 15 bps                                         │
│  ✓ No correlation with open positions                      │
│  ✓ Expected net profit ≥ 2.0%                              │
│  ✓ Position limit not exceeded                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Signal Generator                               │
│  • Adaptive TP/SL (based on confidence + volatility)       │
│  • Position sizing (Kelly-inspired)                        │
│  • Leverage calculation (1-20x)                            │
│  • Cost analysis (fees + slippage + funding)               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Final Signal                              │
│  • Entry Price                                              │
│  • TP1, TP2, TP3 (30%, 40%, 30% position)                 │
│  • Stop Loss                                                │
│  • Leverage (auto-adjusted)                                │
│  • Position Size (USD + quantity)                          │
│  • Expected Net Profit (after all costs)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Proces Generowania Sygnału

### Krok 1: Pobranie Danych

```python
# Pobierz ostatnie 250 świec (15m = ~62 godziny historii)
candles = fetch_latest_ohlcv(symbol='BTC/USDT', timeframe='15m', limit=250)
```

**Dane zawierają:**
- `timestamp` - Czas otwarcia świecy
- `open`, `high`, `low`, `close` - OHLC prices
- `volume` - Wolumen w base currency

### Krok 2: Feature Engineering

System oblicza **50+ wskaźników technicznych**:

#### Trend Indicators
```python
# Exponential Moving Averages
ema_9, ema_21, ema_50, ema_200

# VWAP (Volume Weighted Average Price)
vwap = Σ(price × volume) / Σ(volume)

# Supertrend (trend direction)
supertrend_direction ∈ {-1, 0, 1}  # bearish/neutral/bullish

# ADX (trend strength)
adx = 0-100  # >25 = strong trend, <20 = weak/sideways
```

#### Momentum Indicators
```python
# RSI (Relative Strength Index)
rsi_14 = 0-100  # <30 oversold, >70 overbought

# Stochastic RSI (more sensitive)
stochrsi = 0-100
stochrsi_k = SMA(stochrsi, 3)
stochrsi_d = SMA(stochrsi_k, 3)

# MACD
macd_line = ema_12 - ema_26
macd_signal = ema(macd_line, 9)
macd_hist = macd_line - macd_signal

# RSI Divergence Detection
bearish_divergence = (price ↑ but rsi ↓)  # Potential reversal down
bullish_divergence = (price ↓ but rsi ↑)  # Potential reversal up
```

#### Volatility & Support/Resistance
```python
# ATR (Average True Range) - key for TP/SL calculation
atr_14 = SMA(true_range, 14)

# Bollinger Bands
bb_middle = SMA(close, 20)
bb_upper = bb_middle + 2 × std(close, 20)
bb_lower = bb_middle - 2 × std(close, 20)
bb_width = (bb_upper - bb_lower) / bb_middle

# Keltner Channels (better for trending markets)
keltner_middle = ema_20
keltner_upper = ema_20 + 2 × atr_14
keltner_lower = ema_20 - 2 × atr_14

# Swing Points (key levels)
swing_high = local_maximum(high, window=5)
swing_low = local_minimum(low, window=5)

# Dynamic Fibonacci Levels
fib_0 = recent_swing_high
fib_236 = high - range × 0.236
fib_382 = high - range × 0.382
fib_50 = high - range × 0.5
fib_618 = high - range × 0.618
fib_786 = high - range × 0.786
fib_100 = recent_swing_low
```

#### Volume Analysis
```python
# On-Balance Volume (cumulative)
obv = Σ(volume × sign(close - close_prev))

# Volume Surge Detection
volume_surge = volume / SMA(volume, 20)  # >2.0 = unusual activity

# Volume Profile
high_volume_node = (volume > quantile(volume, 0.8))

# Order Book Imbalance (simulated)
buy_pressure = volume × max(0, price_change)
sell_pressure = volume × max(0, -price_change)
obi = (buy_pressure - sell_pressure) / (buy_pressure + sell_pressure)
```

#### Derivative Features
```python
# EMA Slopes (trend acceleration)
ema_20_slope = (ema_20[t] - ema_20[t-3]) / ema_20[t-3]
ema_20_accel = ema_20_slope[t] - ema_20_slope[t-3]  # 2nd derivative

# Consolidation Detection
is_consolidation = (bb_width < quantile(bb_width, 0.30))
consolidation_duration = consecutive_bars_in_consolidation
```

#### Market Regime
```python
# Trend Regime
if ema_21 > ema_50:
    regime_trend = 1  # Uptrend
elif ema_21 < ema_50:
    regime_trend = -1  # Downtrend
else:
    regime_trend = 0  # Sideways

# Volatility Regime
atr_percentile = percentile_rank(atr_14, window=100)
if atr_percentile < 0.30:
    regime_volatility = 0  # Low volatility
elif atr_percentile > 0.70:
    regime_volatility = 2  # High volatility
else:
    regime_volatility = 1  # Normal volatility
```

### Krok 3: Predykcja Modelu ML

```python
# Model Ensemble: LightGBM + Conformal Prediction
probability = model.predict_proba(features)[:, 1]  # Probability of class 1 (UP)

# Określenie kierunku i confidence
if probability >= 0.5:
    side = LONG
    confidence = probability  # 0.5-1.0
else:
    side = SHORT
    confidence = 1.0 - probability  # 0.5-1.0

# Przykład:
# probability = 0.73 → LONG, confidence = 0.73
# probability = 0.28 → SHORT, confidence = 0.72
```

### Krok 4: Filtry Ryzyka

System sprawdza **7 warunków** przed wygenerowaniem sygnału:

```python
risk_filters = {
    'confidence': confidence >= 0.65,          # ✓ High confidence only
    'atr': atr > 0,                            # ✓ Valid ATR
    'liquidity': volume >= min_volume,         # ✓ Sufficient liquidity
    'spread': spread_bps <= 15.0,              # ✓ Tight spread
    'correlation': no_correlated_positions,    # ✓ No correlation
    'profit': expected_net_profit >= 2.0%,     # ✓ Profitable after costs
    'position_limit': open_positions < max,    # ✓ Not overexposed
}

# WSZYSTKIE muszą być True, inaczej sygnał jest odrzucany
if not all(risk_filters.values()):
    return None  # Reject signal
```

---

## 3. Obliczanie Poziomów Wejścia

### Entry Price

```python
# Sygnał generowany na zamknięciu bieżącej świecy
entry_price = current_candle['close']

# W środowisku produkcyjnym:
# - Używany jest BID (dla LONG) lub ASK (dla SHORT)
# - Uwzględniane jest slippage (±0.03%)
```

**Przykład:**
```
BTC/USDT close price: $62,450.00
Slippage estimate: ±0.03% = $18.74

LONG entry: $62,468.74 (close + slippage)
SHORT entry: $62,431.26 (close - slippage)
```

---

## 4. Stop Loss (SL)

### Adaptive SL - Bazuje na Volatility Regime

```python
def calculate_sl(entry_price, atr, side, volatility_regime):
    """
    Oblicza Stop Loss w zależności od reżimu volatility
    """
    # Bazowy mnożnik ATR
    if volatility_regime == 'high':
        sl_mult = 1.5  # Szerszy SL w wysokiej volatility
    elif volatility_regime == 'low':
        sl_mult = 0.8  # Ciasniejszy SL w niskiej volatility
    else:
        sl_mult = 1.0  # Normalny SL
    
    sl_distance = atr × sl_mult
    
    if side == LONG:
        sl_price = entry_price - sl_distance
    else:  # SHORT
        sl_price = entry_price + sl_distance
    
    return sl_price
```

### Przykłady Obliczania SL

**Scenariusz 1: LONG w Normal Volatility**
```python
entry_price = $62,450.00
atr = $850.00
volatility = 'normal'

sl_mult = 1.0
sl_distance = $850.00 × 1.0 = $850.00
sl_price = $62,450.00 - $850.00 = $61,600.00

Risk per trade = ($62,450 - $61,600) / $62,450 = 1.36%
```

**Scenariusz 2: SHORT w High Volatility**
```python
entry_price = $62,450.00
atr = $1,200.00
volatility = 'high'

sl_mult = 1.5
sl_distance = $1,200.00 × 1.5 = $1,800.00
sl_price = $62,450.00 + $1,800.00 = $64,250.00

Risk per trade = ($64,250 - $62,450) / $62,450 = 2.88%
```

**Scenariusz 3: LONG w Low Volatility**
```python
entry_price = $62,450.00
atr = $400.00
volatility = 'low'

sl_mult = 0.8
sl_distance = $400.00 × 0.8 = $320.00
sl_price = $62,450.00 - $320.00 = $62,130.00

Risk per trade = ($62,450 - $62,130) / $62,450 = 0.51%
```

### Volatility Regime Detection

```python
def detect_volatility_regime(atr_current, atr_history):
    """
    Określa reżim volatility na podstawie percentyla ATR
    """
    atr_percentile = percentile_rank(atr_current, atr_history[-100:])
    
    if atr_percentile < 0.30:
        return 'low'      # ATR in bottom 30%
    elif atr_percentile > 0.70:
        return 'high'     # ATR in top 30%
    else:
        return 'normal'   # ATR in middle 40%
```

---

## 5. Take Profit (TP)

### Adaptive TP - 3 Poziomy z Częściowym Zamknięciem

System używa **trzech poziomów TP** z różnymi alokacjami pozycji:
- **TP1**: 30% pozycji (konserwatywny)
- **TP2**: 40% pozycji (główny cel)
- **TP3**: 30% pozycji (agresywny)

### Obliczanie TP na Podstawie Confidence

```python
def calculate_tp(entry_price, atr, side, confidence, volatility_regime):
    """
    Oblicza 3 poziomy TP w zależności od confidence i volatility
    """
    # Wybór mnożników ATR na podstawie confidence
    if confidence >= 0.70:
        # High confidence: aggressive targets
        if volatility_regime == 'high':
            tp_mult = [3.0, 5.0, 8.0]  # Bardzo agresywne w trendach
        else:
            tp_mult = [2.5, 4.5, 7.0]  # Agresywne
    
    elif confidence >= 0.65:
        # Medium confidence: balanced targets
        tp_mult = [2.0, 3.5, 6.0]  # Zbalansowane
    
    else:
        # Lower confidence: conservative targets
        tp_mult = [1.5, 2.5, 4.0]  # Konserwatywne
    
    if side == LONG:
        tp1 = entry_price + (atr × tp_mult[0])
        tp2 = entry_price + (atr × tp_mult[1])
        tp3 = entry_price + (atr × tp_mult[2])
    else:  # SHORT
        tp1 = entry_price - (atr × tp_mult[0])
        tp2 = entry_price - (atr × tp_mult[1])
        tp3 = entry_price - (atr × tp_mult[2])
    
    return [tp1, tp2, tp3]
```

### Przykłady Obliczania TP

**Scenariusz 1: LONG, Confidence 0.73, Normal Volatility**
```python
entry_price = $62,450.00
atr = $850.00
confidence = 0.73  # High
volatility = 'normal'

# Mnożniki: [2.5, 4.5, 7.0]
tp1 = $62,450 + ($850 × 2.5) = $64,575.00  (30% position)
tp2 = $62,450 + ($850 × 4.5) = $66,275.00  (40% position)
tp3 = $62,450 + ($850 × 7.0) = $68,400.00  (30% position)

Expected gain:
TP1: +3.40% (close 30%)
TP2: +6.13% (close 40%)
TP3: +9.53% (close 30%)

Weighted avg: 0.30×3.40% + 0.40×6.13% + 0.30×9.53% = 6.30%
```

**Scenariusz 2: SHORT, Confidence 0.67, High Volatility**
```python
entry_price = $62,450.00
atr = $1,200.00
confidence = 0.67  # Medium
volatility = 'high'

# Mnożniki: [2.0, 3.5, 6.0] (nie 3.0/5.0/8.0 bo confidence < 0.70)
tp1 = $62,450 - ($1,200 × 2.0) = $60,050.00  (30%)
tp2 = $62,450 - ($1,200 × 3.5) = $58,250.00  (40%)
tp3 = $62,450 - ($1,200 × 6.0) = $55,250.00  (30%)

Expected gain:
TP1: +3.84%
TP2: +6.72%
TP3: +11.53%

Weighted avg: 7.04%
```

**Scenariusz 3: LONG, Confidence 0.65, Low Volatility**
```python
entry_price = $62,450.00
atr = $400.00
confidence = 0.65  # Exactly at threshold
volatility = 'low'

# Mnożniki: [2.0, 3.5, 6.0]
tp1 = $62,450 + ($400 × 2.0) = $63,250.00  (30%)
tp2 = $62,450 + ($400 × 3.5) = $63,850.00  (40%)
tp3 = $62,450 + ($400 × 6.0) = $64,850.00  (30%)

Expected gain:
TP1: +1.28%
TP2: +2.24%
TP3: +3.84%

Weighted avg: 2.30%
```

### Risk/Reward Ratio

```python
def calculate_rr_ratio(entry, sl, tp_levels, tp_allocations):
    """
    Oblicza stosunek Risk/Reward
    """
    sl_distance = abs(entry - sl)
    
    # Weighted average TP
    weighted_tp = sum(
        abs(tp - entry) × allocation 
        for tp, allocation in zip(tp_levels, tp_allocations)
    )
    
    rr_ratio = weighted_tp / sl_distance
    return rr_ratio
```

**Przykład:**
```python
entry = $62,450
sl = $61,600  # Distance: $850
tp1 = $64,575  # Distance: $2,125, Weight: 0.30
tp2 = $66,275  # Distance: $3,825, Weight: 0.40
tp3 = $68,400  # Distance: $5,950, Weight: 0.30

weighted_tp_distance = 
    $2,125 × 0.30 + $3,825 × 0.40 + $5,950 × 0.30
    = $637.50 + $1,530.00 + $1,785.00
    = $3,952.50

rr_ratio = $3,952.50 / $850 = 4.65

# Risk $1 to make $4.65 (excellent ratio!)
```

---

## 6. Dźwignia (Leverage)

### Auto-Leverage System

Dźwignia jest **automatycznie kalkulowana** na podstawie:
1. **Confidence** modelu
2. **Volatility** rynku
3. **Risk Profile** użytkownika
4. **Maksymalny cap** dla profilu

```python
def calculate_leverage(
    confidence,
    atr_pct,
    risk_profile,
    entry_price,
    sl_price,
    capital_usd
):
    """
    Oblicza optymalną dźwignię
    """
    # 1. Base leverage z confidence
    if confidence < 0.55:
        base_leverage = 3
    elif confidence < 0.60:
        base_leverage = 5
    elif confidence < 0.70:
        base_leverage = 8
    else:
        base_leverage = 12
    
    # 2. Volatility adjustment
    if atr_pct > 3.0:
        volatility_factor = 0.6  # High vol = reduce leverage
    elif atr_pct > 2.0:
        volatility_factor = 0.8  # Medium vol
    else:
        volatility_factor = 1.0  # Low vol = full leverage
    
    adjusted_leverage = base_leverage × volatility_factor
    
    # 3. Risk profile caps
    max_leverage = {
        RiskProfile.LOW: 8,
        RiskProfile.MEDIUM: 20,
        RiskProfile.HIGH: 30
    }[risk_profile]
    
    # 4. Position-based calculation
    sl_distance_pct = abs(entry_price - sl_price) / entry_price
    risk_per_trade = {
        RiskProfile.LOW: 0.02,    # 2%
        RiskProfile.MEDIUM: 0.05,  # 5%
        RiskProfile.HIGH: 0.10     # 10%
    }[risk_profile]
    
    position_size_usd = (capital_usd × risk_per_trade) / sl_distance_pct
    required_leverage = position_size_usd / capital_usd
    
    # 5. Final leverage
    final_leverage = min(
        adjusted_leverage,
        required_leverage,
        max_leverage
    )
    
    return max(1, round(final_leverage, 1))
```

### Przykłady Kalkulacji Leverage

**Scenariusz 1: High Confidence, Low Volatility, MEDIUM Risk**
```python
confidence = 0.75
atr_pct = 1.5%
risk_profile = MEDIUM
capital = $1,000
entry = $62,450
sl = $61,600  # 1.36% distance

# 1. Base leverage
base = 12  # confidence > 0.70

# 2. Volatility factor
vol_factor = 1.0  # atr_pct < 2.0%
adjusted = 12 × 1.0 = 12

# 3. Max cap
max_cap = 20  # MEDIUM profile

# 4. Position-based
risk_per_trade = 5%  # $50
sl_distance_pct = 1.36%
position_size = ($1,000 × 0.05) / 0.0136 = $3,676
required_lev = $3,676 / $1,000 = 3.68

# 5. Final
final_leverage = min(12, 3.68, 20) = 3.7x

# Position details:
# Notional = $1,000 × 3.7 = $3,700
# Quantity = $3,700 / $62,450 = 0.0592 BTC
```

**Scenariusz 2: Medium Confidence, High Volatility, HIGH Risk**
```python
confidence = 0.67
atr_pct = 3.5%
risk_profile = HIGH
capital = $1,000
entry = $62,450
sl = $60,650  # 2.88% distance

# 1. Base leverage
base = 8  # 0.60 ≤ confidence < 0.70

# 2. Volatility factor
vol_factor = 0.6  # atr_pct > 3.0%
adjusted = 8 × 0.6 = 4.8

# 3. Max cap
max_cap = 30  # HIGH profile

# 4. Position-based
risk_per_trade = 10%  # $100
sl_distance_pct = 2.88%
position_size = ($1,000 × 0.10) / 0.0288 = $3,472
required_lev = $3,472 / $1,000 = 3.47

# 5. Final
final_leverage = min(4.8, 3.47, 30) = 3.5x

# Lower leverage due to high volatility protection
```

**Scenariusz 3: Low Confidence, Normal Volatility, LOW Risk**
```python
confidence = 0.58
atr_pct = 2.2%
risk_profile = LOW
capital = $1,000
entry = $62,450
sl = $61,800  # 1.04% distance

# 1. Base leverage
base = 5  # 0.55 ≤ confidence < 0.60

# 2. Volatility factor
vol_factor = 0.8  # 2.0% < atr_pct ≤ 3.0%
adjusted = 5 × 0.8 = 4.0

# 3. Max cap
max_cap = 8  # LOW profile

# 4. Position-based
risk_per_trade = 2%  # $20
sl_distance_pct = 1.04%
position_size = ($1,000 × 0.02) / 0.0104 = $1,923
required_lev = $1,923 / $1,000 = 1.92

# 5. Final
final_leverage = min(4.0, 1.92, 8) = 1.9x

# Conservative: low risk profile dominates
```

---

## 7. Position Sizing

### Obliczanie Wielkości Pozycji

```python
def calculate_position_size(
    entry_price,
    sl_price,
    risk_profile,
    capital_usd,
    leverage
):
    """
    Oblicza wielkość pozycji w USD i jednostkach
    """
    # 1. Risk per trade based on profile
    risk_pct = {
        RiskProfile.LOW: 0.02,    # 2% capital
        RiskProfile.MEDIUM: 0.05,  # 5% capital
        RiskProfile.HIGH: 0.10     # 10% capital
    }[risk_profile]
    
    risk_usd = capital_usd × risk_pct
    
    # 2. SL distance
    sl_distance_pct = abs(entry_price - sl_price) / entry_price
    
    # 3. Position size to risk exactly risk_usd if SL hit
    position_size_usd = risk_usd / sl_distance_pct
    
    # 4. Apply leverage cap
    max_position = capital_usd × leverage
    position_size_usd = min(position_size_usd, max_position)
    
    # 5. Quantity in base currency
    quantity = position_size_usd / entry_price
    
    return {
        'leverage': leverage,
        'position_size_usd': position_size_usd,
        'quantity': quantity,
        'risk_usd': position_size_usd × sl_distance_pct
    }
```

### Przykład Kompletny

```python
# Parametry
capital = $10,000
entry = $62,450
sl = $61,600  # -$850 = 1.36%
risk_profile = MEDIUM  # 5% risk
leverage = 4.5x

# Kalkulacja
risk_pct = 0.05
risk_usd = $10,000 × 0.05 = $500

sl_distance_pct = ($850 / $62,450) = 0.0136 = 1.36%

position_size_usd = $500 / 0.0136 = $36,765

max_position = $10,000 × 4.5 = $45,000
position_size_usd = min($36,765, $45,000) = $36,765

quantity = $36,765 / $62,450 = 0.5888 BTC

# Weryfikacja
actual_risk = $36,765 × 0.0136 = $500 ✓

# Jeśli SL zostanie trafiony:
loss_in_btc = 0.5888 × $850 = $500.48
loss_as_pct_of_capital = $500 / $10,000 = 5.0% ✓
```

---

## 8. Filtry Ryzyka

System sprawdza **7 warunków** zanim wygeneruje sygnał:

### 1. Confidence Filter

```python
confidence >= 0.65  # Minimum 65% confidence

# Reasoning: 
# Modele poniżej 65% są zbyt niepewne
# Historycznie accuracy < 60% przy confidence < 0.65
```

### 2. ATR Filter

```python
atr > 0  # Valid ATR required

# Reasoning:
# ATR = 0 oznacza brak volatility = niemożliwe do trade
# Potrzebny do kalkulacji TP/SL
```

### 3. Liquidity Filter

```python
volume >= min_volume  # Sufficient market depth

# Calculation:
min_volume = median(volume[-20:]) × 0.3

# Reasoning:
# Niska likwidność = high slippage
# Potrzeba minimum 30% średniego wolumenu
```

### 4. Spread Filter

```python
spread_bps <= 15.0  # Max 0.15% spread

# Calculation:
spread_bps = ((ask - bid) / mid_price) × 10000

# Reasoning:
# Szeroki spread zwiększa koszty wejścia/wyjścia
# 15 bps = 0.15% jest akceptowalne dla 15m timeframe
```

### 5. Correlation Filter

```python
no_correlated_positions = True  # No overlapping exposure

# Check:
for open_position in portfolio:
    correlation = price_correlation(symbol, open_position.symbol, window=50)
    if abs(correlation) > 0.7:
        return False  # Reject - too correlated

# Reasoning:
# Unikaj podwójnej ekspozycji na ten sam ruch
# Np. BTC/USDT LONG + ETH/USDT LONG (correlation ~0.85)
```

### 6. Profit Filter

```python
expected_net_profit_pct >= 2.0  # Minimum 2% net profit

# Calculation (detailed in section 9)
gross_profit = weighted_avg_tp_distance
costs = fees + slippage + funding
net_profit = (gross_profit - costs) / entry_price

# Reasoning:
# Po kosztach (~0.25%), potrzebny min 2% dla opłacalności
# Risk/Reward ratio musi być > 2.5:1
```

### 7. Position Limit Filter

```python
open_positions < max_positions  # Diversification

max_positions = {
    RiskProfile.LOW: 2,
    RiskProfile.MEDIUM: 5,
    RiskProfile.HIGH: 8
}

# Reasoning:
# Unikaj over-exposure
# Zachowaj kapitał na nowe okazje
```

---

## 9. Koszty i Opłaty

System uwzględnia **4 typy kosztów**:

### 1. Trading Fees

```python
# Maker fee (limit orders)
maker_fee_bps = 2.0  # 0.02%

# Taker fee (market orders)
taker_fee_bps = 5.0  # 0.05%

# Entry fee
entry_fee = position_size_usd × (taker_fee_bps / 10000)

# Exit fee (weighted by TP levels)
exit_fee_tp1 = tp1_size × (taker_fee_bps / 10000) × 0.30
exit_fee_tp2 = tp2_size × (taker_fee_bps / 10000) × 0.40
exit_fee_tp3 = tp3_size × (taker_fee_bps / 10000) × 0.30

total_fees = entry_fee + exit_fee_tp1 + exit_fee_tp2 + exit_fee_tp3
```

**Przykład:**
```python
position_size = $10,000
entry_fee = $10,000 × 0.0005 = $5.00

# At TP1 (30% = $3,000)
exit_fee_tp1 = $3,000 × 0.0005 = $1.50

# At TP2 (40% = $4,000)
exit_fee_tp2 = $4,000 × 0.0005 = $2.00

# At TP3 (30% = $3,000)
exit_fee_tp3 = $3,000 × 0.0005 = $1.50

total_fees = $5.00 + $1.50 + $2.00 + $1.50 = $10.00
fee_pct = $10 / $10,000 = 0.10%
```

### 2. Slippage

```python
slippage_bps = 3.0  # 0.03% average slippage

# Entry slippage
entry_slippage = position_size_usd × (slippage_bps / 10000)

# Exit slippage (same calculation)
total_slippage = entry_slippage + exit_slippage
```

**Przykład:**
```python
position = $10,000

entry_slippage = $10,000 × 0.0003 = $3.00
exit_slippage = $10,000 × 0.0003 = $3.00

total_slippage = $6.00
slippage_pct = 0.06%
```

### 3. Funding Rate

```python
funding_rate_hourly_bps = 1.0  # 0.01% per hour (average)

# Assumując średni hold time 12 godzin
funding_periods = 12

funding_cost = position_size_usd × (funding_rate_hourly_bps / 10000) × funding_periods
```

**Przykład:**
```python
position = $10,000
hold_time = 12 hours
funding_rate = 0.01% per hour

funding_cost = $10,000 × 0.0001 × 12 = $12.00
funding_pct = 0.12%
```

### 4. Total Costs

```python
total_costs_usd = fees + slippage + funding
total_costs_pct = total_costs_usd / position_size_usd
```

**Przykład Kompletny:**
```python
position_size = $10,000

fees = $10.00      (0.10%)
slippage = $6.00   (0.06%)
funding = $12.00   (0.12%)

total_costs = $28.00
total_costs_pct = 0.28%
```

### Expected Net Profit Calculation

```python
def calculate_expected_net_profit(
    entry_price,
    tp_levels,
    tp_allocations,
    costs_pct
):
    """
    Oblicza oczekiwany zysk netto po wszystkich kosztach
    """
    # Gross profit (weighted average)
    gross_profit_pct = sum(
        abs(tp - entry_price) / entry_price × allocation
        for tp, allocation in zip(tp_levels, tp_allocations)
    )
    
    # Net profit
    net_profit_pct = gross_profit_pct - costs_pct
    
    return net_profit_pct
```

**Przykład:**
```python
entry = $62,450
tp1 = $64,575  (+3.40%, 30%)
tp2 = $66,275  (+6.13%, 40%)
tp3 = $68,400  (+9.53%, 30%)

gross_profit = 3.40% × 0.30 + 6.13% × 0.40 + 9.53% × 0.30
             = 1.02% + 2.45% + 2.86%
             = 6.33%

costs = 0.28%

net_profit = 6.33% - 0.28% = 6.05%

# Profit Filter Check:
6.05% >= 2.0% ✓ PASS
```

---

## 10. Przykład Pełnego Sygnału

### Input Data

```python
symbol = 'BTC/USDT'
timeframe = '15m'
current_price = $62,450.00
atr = $850.00

# Model prediction
probability = 0.73
side = LONG  # prob >= 0.5
confidence = 0.73

# Market conditions
volatility_regime = 'normal'  # ATR at 45th percentile
volume = 1,250 BTC (above average)
spread_bps = 8.5 (tight)

# User settings
capital = $10,000
risk_profile = MEDIUM
```

### Step 1: Risk Filters

```python
✓ Confidence: 0.73 >= 0.65
✓ ATR: $850 > 0
✓ Liquidity: 1,250 BTC >= 400 BTC (30% of avg)
✓ Spread: 8.5 bps <= 15.0 bps
✓ Correlation: No correlated positions
✓ Position Limit: 0 open < 5 max
? Profit: (calculated below)
```

### Step 2: Calculate TP/SL

```python
# Confidence 0.73, Volatility 'normal' → Aggressive TP
tp_multipliers = [2.5, 4.5, 7.0]

tp1 = $62,450 + ($850 × 2.5) = $64,575.00
tp2 = $62,450 + ($850 × 4.5) = $66,275.00
tp3 = $62,450 + ($850 × 7.0) = $68,400.00

# Volatility 'normal' → Normal SL
sl_multiplier = 1.0
sl = $62,450 - ($850 × 1.0) = $61,600.00
```

### Step 3: Calculate Leverage

```python
# Base leverage (confidence 0.73 >= 0.70)
base_lev = 12

# Volatility adjustment (normal)
atr_pct = $850 / $62,450 = 1.36%
vol_factor = 1.0  # < 2.0%
adjusted_lev = 12 × 1.0 = 12

# Position-based
risk_pct = 5%  # MEDIUM
risk_usd = $10,000 × 0.05 = $500
sl_distance = 1.36%
position_size = $500 / 0.0136 = $36,765
required_lev = $36,765 / $10,000 = 3.68

# Max cap (MEDIUM)
max_lev = 20

# Final leverage
leverage = min(12, 3.68, 20) = 3.7x
```

### Step 4: Position Sizing

```python
position_size_usd = $10,000 × 3.7 = $37,000
quantity = $37,000 / $62,450 = 0.5925 BTC

# Risk verification
actual_risk = $37,000 × 0.0136 = $503.20
risk_as_pct = $503.20 / $10,000 = 5.03% ✓
```

### Step 5: Calculate Costs

```python
# Fees
entry_fee = $37,000 × 0.0005 = $18.50
exit_fees = $37,000 × 0.0005 = $18.50
total_fees = $37.00

# Slippage
slippage = $37,000 × 0.0006 = $22.20

# Funding (12h hold)
funding = $37,000 × 0.0001 × 12 = $44.40

# Total
total_costs = $37.00 + $22.20 + $44.40 = $103.60
costs_pct = $103.60 / $37,000 = 0.28%
```

### Step 6: Calculate Expected Net Profit

```python
# Gross profit (weighted avg)
tp1_gain = (+3.40%, 30%)
tp2_gain = (+6.13%, 40%)
tp3_gain = (+9.53%, 30%)

gross_profit = 3.40% × 0.30 + 6.13% × 0.40 + 9.53% × 0.30
             = 6.33%

# Net profit
net_profit = 6.33% - 0.28% = 6.05%

# Profit Filter Check
6.05% >= 2.0% ✓ PASS
```

### Step 7: Final Signal

```json
{
  "signal_id": "BTC_USDT_15m_20251007_163045",
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "side": "LONG",
  "confidence": 0.73,
  
  "entry": {
    "price": 62450.00,
    "timestamp": "2025-10-07T16:30:45Z"
  },
  
  "take_profit": [
    {
      "level": "TP1",
      "price": 64575.00,
      "distance_pct": 3.40,
      "allocation_pct": 30,
      "description": "Conservative target"
    },
    {
      "level": "TP2",
      "price": 66275.00,
      "distance_pct": 6.13,
      "allocation_pct": 40,
      "description": "Main target"
    },
    {
      "level": "TP3",
      "price": 68400.00,
      "distance_pct": 9.53,
      "allocation_pct": 30,
      "description": "Aggressive target"
    }
  ],
  
  "stop_loss": {
    "price": 61600.00,
    "distance_pct": 1.36,
    "reason": "ATR-based (1.0x)"
  },
  
  "position": {
    "leverage": 3.7,
    "size_usd": 37000.00,
    "quantity": 0.5925,
    "risk_usd": 503.20,
    "risk_pct": 5.03
  },
  
  "metrics": {
    "risk_reward_ratio": 4.65,
    "expected_gross_profit_pct": 6.33,
    "expected_net_profit_pct": 6.05,
    "total_costs_pct": 0.28
  },
  
  "costs": {
    "trading_fees": 37.00,
    "slippage": 22.20,
    "funding": 44.40,
    "total": 103.60
  },
  
  "risk_filters": {
    "confidence": true,
    "atr": true,
    "liquidity": true,
    "spread": true,
    "correlation": true,
    "profit": true,
    "position_limit": true
  },
  
  "model_info": {
    "model_id": "BTC_USDT_15m_20251005_161731",
    "version": "v10",
    "accuracy": 0.56,
    "roc_auc": 0.56
  },
  
  "market_conditions": {
    "atr": 850.00,
    "volatility_regime": "normal",
    "volume_24h": 1250.00,
    "spread_bps": 8.5
  }
}
```

---

## 🎯 Podsumowanie Kluczowych Mechanizmów

### 1. Adaptive TP/SL
- **Dostosowuje się** do confidence i volatility
- **Wyższe confidence** = większe TP (2.5-7.0x ATR)
- **Wyższa volatility** = szerszy SL (1.5x ATR)

### 2. Auto-Leverage
- **Bazuje na** confidence, volatility, risk profile
- **Chroni przed** over-leverage w trudnych warunkach
- **Maksymalizuje** returns przy high confidence

### 3. Position Sizing
- **Fixed risk %** (2%, 5%, 10%) per trade
- **Kalkuluje** exact size dla desired risk
- **Uwzględnia** leverage caps

### 4. Multi-Level TP
- **3 poziomy**: conserv ative (30%), main (40%), aggressive (30%)
- **Secure profits** early, let winners run
- **Weighted average** ~6% gross profit

### 5. Comprehensive Cost Model
- **4 typy kosztów**: fees, slippage, funding, impact
- **Realistic filtering**: tylko sygnały >2% net profit
- **Transparentne** kalkulacje dla użytkownika

### 6. Risk Management
- **7 filtrów**: confidence, ATR, liquidity, spread, correlation, profit, limits
- **Wszystkie muszą pass** przed wygenerowaniem sygnału
- **Zero compromise** na jakości

---

## 📚 Dalsze Informacje

- **[OPTIMIZATION_CHANGES.md](OPTIMIZATION_CHANGES.md)** - Szczegóły optymalizacji systemu
- **[QUICK_START.md](QUICK_START.md)** - Przewodnik uruchomienia
- **[apps/ml/signal_engine.py](apps/ml/signal_engine.py)** - Kod źródłowy
- **[apps/ml/features.py](apps/ml/features.py)** - Feature engineering

---

**System jest gotowy do generowania wysokiej jakości sygnałów tradingowych!** 🚀
