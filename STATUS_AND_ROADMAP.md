# 📊 Status Systemu i Roadmap

## Data: 2025-10-06 18:07

---

## 🔄 Obecny Status Treningu

### Aktywne treningi:

| Symbol | Status | Progress | Fold | Czas trwania |
|--------|--------|----------|------|--------------|
| **BTC/USDT** | ⏳ Training | 77.6% | 52/67 | ~22h |
| **ETH/USDT** | ⏳ Training | 73.8% | 48/65 | ~22h |
| **ADA/USDT** | ⏳ Training | 81.0% | 51/63 | ~22h |

### Estymowany czas zakończenia:
- **BTC/USDT**: ~6 godzin (dzisiaj ~00:00)
- **ETH/USDT**: ~8 godzin (dzisiaj ~02:00)
- **ADA/USDT**: ~4 godziny (dzisiaj ~22:00)

### Status modeli:
```bash
# Sprawdź:
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT COUNT(*) FROM model_registry;"
```
**Wynik**: 0 modeli wdrożonych (jeszcze)

---

## ✅ Co DZIAŁA obecnie

### 1. **Automatyczne generowanie sygnałów** ✅

**Lokalizacja**: `apps/ml/worker.py:422-700`

**Harmonogram**:
```python
'generate-signals-every-5-minutes': {
    'task': 'signals.generate',
    'schedule': 300.0,  # CO 5 MINUT
}
```

**Co się dzieje**:
1. **Co 5 minut** worker sprawdza wdrożone modele
2. Pobiera najnowsze dane rynkowe (OHLCV)
3. Generuje features (techniczne indykatory)
4. Uruchamia model ML (predict_proba)
5. Jeśli confidence > 52% → próbuje wygenerować sygnał
6. **Filtr 2%**: Sprawdza czy expected profit ≥ 2%
7. Jeśli PASS → zapisuje sygnał do bazy
8. Wysyła WebSocket broadcast do UI

**Status**: ✅ **GOTOWE** - uruchomi się automatycznie gdy model będzie wdrożony

---

### 2. **Automatyczna aktualizacja danych** ✅

```python
'update-latest-candles-every-15-minutes': {
    'task': 'backfill.update_latest',
    'schedule': 900.0,  # CO 15 MINUT
}
```

**Co się dzieje**:
- Co 15 minut pobiera najnowsze świece z Binance
- Aktualizuje OHLCV w bazie
- System zawsze ma świeże dane

**Status**: ✅ **DZIAŁA**

---

### 3. **Automatyczne wygaszanie sygnałów** ✅

```python
'expire-signals-every-5-minutes': {
    'task': 'signals.expire',
    'schedule': 300.0,  # CO 5 MINUT
}
```

**Co się dzieje**:
- Sprawdza sygnały które przekroczyły `valid_until` (4 godziny)
- Zmienia status na EXPIRED
- Utrzymuje czystość w bazie

**Status**: ✅ **DZIAŁA**

---

## ⏰ Kiedy pierwsze sygnały?

### Scenariusz 1: Automatyczne wdrożenie (najszybszy)

**Po zakończeniu treningu** (dzisiaj w nocy):
1. Model zapisuje się do `model_registry`
2. System automatycznie wdraża najlepszy model
3. **Co 5 minut** worker generuje sygnały
4. **Pierwsze sygnały**: Jutro rano ~6:00-8:00 ✅

### Scenariusz 2: Manualne wdrożenie

Jeśli automatyczne się nie uruchomi:
```bash
# Sprawdź dostępne modele
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT model_id, symbol, timeframe, roc_auc, created_at
   FROM model_registry ORDER BY created_at DESC LIMIT 10;"

# Wdróż model ręcznie (przez API lub kod)
```

---

## ❌ Co NIE działa - AUTO-TRADING

### Obecna sytuacja:
System **NIE MA** automatycznego wykonywania tradów na giełdzie.

**Co jest:**
- ✅ Generowanie sygnałów
- ✅ Zapis do bazy danych
- ✅ WebSocket broadcast do UI
- ❌ **BRAK** automatycznego składania orderów
- ❌ **BRAK** monitorowania pozycji
- ❌ **BRAK** modyfikacji SL/TP
- ❌ **BRAK** zamykania pozycji

**Co musisz zrobić ręcznie**:
1. Zobaczysz sygnał w UI/API
2. **Ręcznie** otworzysz trade na Binance
3. **Ręcznie** ustawisz TP/SL
4. **Ręcznie** będziesz monitorować

---

## 🚀 Roadmap: Auto-Trading System

### Co trzeba zaimplementować:

### Phase 1: Basic Order Execution (2-3 dni) ⭐

**Cel**: Automatyczne otwieranie pozycji

**Pliki do stworzenia**:
```
apps/ml/trading/
├── __init__.py
├── exchange_client.py      # Rozszerzenie CCXTClient o orders
├── position_manager.py     # Zarządzanie pozycjami
├── risk_manager.py         # Kontrola ryzyka
└── order_executor.py       # Wykonywanie orderów
```

**Funkcje**:
1. **Automatyczne otwieranie pozycji**:
   ```python
   def execute_signal(signal: Dict) -> Position:
       # 1. Sprawdź dostępny kapitał
       # 2. Oblicz wielkość pozycji
       # 3. Złóż market order (entry)
       # 4. Ustaw SL jako stop-loss order
       # 5. Ustaw TP1/TP2/TP3 jako take-profit orders
       # 6. Zapisz pozycję do bazy
   ```

2. **Tracking pozycji**:
   ```python
   @celery_task(schedule=60.0)  # Co minutę
   def monitor_positions():
       # 1. Pobierz open positions z Binance
       # 2. Sprawdź które TP zostały trafione
       # 3. Aktualizuj trailing SL po TP1
       # 4. Zapisz status do bazy
   ```

**Tabela w bazie**:
```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    signal_id VARCHAR,
    exchange_order_id VARCHAR,
    symbol VARCHAR,
    side VARCHAR,
    entry_price FLOAT,
    quantity FLOAT,
    leverage INT,
    sl_price FLOAT,
    tp1_price FLOAT,
    tp1_filled BOOLEAN,
    tp2_price FLOAT,
    tp2_filled BOOLEAN,
    tp3_price FLOAT,
    tp3_filled BOOLEAN,
    current_sl FLOAT,  -- dla trailing
    status VARCHAR,  -- OPEN, CLOSED, LIQUIDATED
    pnl_usd FLOAT,
    pnl_pct FLOAT,
    created_at TIMESTAMP,
    closed_at TIMESTAMP
);
```

**Risk Management**:
- Maksymalna liczba otwartych pozycji (5-8)
- Maksymalny drawdown (stop trading jeśli > 30%)
- Weryfikacja margin przed otwarciem
- Kill switch (emergency stop)

---

### Phase 2: Advanced Position Management (3-5 dni)

**Funkcje**:
1. **Trailing Stop** po TP1:
   ```python
   def update_trailing_sl(position: Position, current_price: float):
       if position.tp1_filled:
           new_sl = calculate_trailing_sl(current_price, atr)
           if new_sl > position.current_sl:  # LONG
               # Modyfikuj SL order na giełdzie
               exchange.edit_order(position.sl_order_id, new_sl)
   ```

2. **Partial TP exits**:
   - 30% @ TP1
   - 40% @ TP2
   - 30% @ TP3

3. **Emergency close**:
   - Jeśli model wykryje odwrócenie trendu
   - Jeśli confidence spada < 40%
   - Jeśli drawdown > 35%

---

### Phase 3: Smart Trade Management (5-7 dni)

**Funkcje**:
1. **Re-entry** po SL:
   - Jeśli nowy sygnał w tym samym kierunku
   - Ale z mniejszą pozycją (50%)

2. **Pyramiding**:
   - Dodawanie do winning pozycji
   - Tylko jeśli w zysku > 3%

3. **Portfolio balancing**:
   - Max 30% kapitału w jednym symbolu
   - Max 60% kapitału w jednym kierunku (LONG/SHORT)

4. **Correlation filter**:
   - Nie otwieraj BTC LONG + ETH LONG jednocześnie (korelacja 0.9)
   - Preferuj uncorrelated pairs

---

## 🛠️ Implementacja Auto-Trading

### Krok 1: Dodaj Exchange Trading Client

**Plik**: `apps/ml/trading/exchange_client.py`

```python
import ccxt
from typing import Dict, Optional
from apps.ml.ccxt_client import CCXTClient

class TradingExchangeClient(CCXTClient):
    """Extended CCXT client with trading capabilities"""

    def create_market_order(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        amount: float,
        leverage: int = 10,
        params: dict = None
    ) -> Dict:
        """
        Create market order with leverage

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Position size in base currency
            leverage: Leverage (1-125)
            params: Additional parameters
                - 'marginMode': 'isolated' or 'cross'
        """
        # Set leverage
        self.exchange.set_leverage(leverage, symbol)

        # Create order
        order = self.exchange.create_order(
            symbol=symbol,
            type='market',
            side=side,
            amount=amount,
            params=params or {'marginMode': 'isolated'}
        )

        return order

    def create_stop_loss_order(
        self,
        symbol: str,
        side: str,  # opposite of entry
        amount: float,
        stop_price: float,
        params: dict = None
    ) -> Dict:
        """Create stop-loss order"""
        order = self.exchange.create_order(
            symbol=symbol,
            type='stop_market',
            side=side,
            amount=amount,
            params={
                'stopPrice': stop_price,
                'reduceOnly': True,
                **(params or {})
            }
        )
        return order

    def create_take_profit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        take_profit_price: float,
        params: dict = None
    ) -> Dict:
        """Create take-profit order"""
        order = self.exchange.create_order(
            symbol=symbol,
            type='take_profit_market',
            side=side,
            amount=amount,
            params={
                'stopPrice': take_profit_price,
                'reduceOnly': True,
                **(params or {})
            }
        )
        return order

    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """Cancel order"""
        return self.exchange.cancel_order(order_id, symbol)

    def edit_order(
        self,
        order_id: str,
        symbol: str,
        new_price: float
    ) -> Dict:
        """Edit order (for trailing SL)"""
        return self.exchange.edit_order(
            order_id,
            symbol,
            params={'stopPrice': new_price}
        )

    def fetch_open_orders(self, symbol: str = None) -> list:
        """Fetch all open orders"""
        return self.exchange.fetch_open_orders(symbol)

    def fetch_positions(self, symbols: list = None) -> list:
        """Fetch all open positions"""
        return self.exchange.fetch_positions(symbols)

    def get_balance(self) -> Dict:
        """Get account balance"""
        balance = self.exchange.fetch_balance()
        return {
            'total': balance['total']['USDT'],
            'free': balance['free']['USDT'],
            'used': balance['used']['USDT']
        }
```

---

### Krok 2: Position Manager

**Plik**: `apps/ml/trading/position_manager.py`

```python
from typing import Dict, Optional
from apps.ml.trading.exchange_client import TradingExchangeClient
from apps.api.db.models import Side
import logging

logger = logging.getLogger(__name__)

class PositionManager:
    """Manages opening and monitoring trading positions"""

    def __init__(self, exchange_client: TradingExchangeClient):
        self.exchange = exchange_client

    def open_position(self, signal: Dict) -> Dict:
        """
        Open trading position based on signal

        Returns:
            position dict with order IDs
        """
        symbol = signal['symbol']
        side = signal['side']
        entry_price = signal['entry_price']
        quantity = signal['quantity']
        leverage = signal['leverage']

        # Determine order sides
        entry_side = 'buy' if side == Side.LONG else 'sell'
        exit_side = 'sell' if side == Side.LONG else 'buy'

        try:
            # 1. Open entry position (market order)
            logger.info(f"Opening {side.value} position for {symbol}: {quantity} @ {entry_price}")

            entry_order = self.exchange.create_market_order(
                symbol=symbol,
                side=entry_side,
                amount=quantity,
                leverage=leverage
            )

            # 2. Set Stop Loss
            sl_order = self.exchange.create_stop_loss_order(
                symbol=symbol,
                side=exit_side,
                amount=quantity,
                stop_price=signal['sl_price']
            )

            # 3. Set Take Profits
            tp1_qty = quantity * (signal['tp1_pct'] / 100)
            tp2_qty = quantity * (signal['tp2_pct'] / 100)
            tp3_qty = quantity * (signal['tp3_pct'] / 100)

            tp1_order = self.exchange.create_take_profit_order(
                symbol=symbol,
                side=exit_side,
                amount=tp1_qty,
                take_profit_price=signal['tp1_price']
            )

            tp2_order = self.exchange.create_take_profit_order(
                symbol=symbol,
                side=exit_side,
                amount=tp2_qty,
                take_profit_price=signal['tp2_price']
            )

            tp3_order = self.exchange.create_take_profit_order(
                symbol=symbol,
                side=exit_side,
                amount=tp3_qty,
                take_profit_price=signal['tp3_price']
            )

            position = {
                'signal_id': signal['signal_id'],
                'symbol': symbol,
                'side': side.value,
                'entry_order_id': entry_order['id'],
                'entry_price': entry_order['average'],
                'quantity': quantity,
                'leverage': leverage,
                'sl_order_id': sl_order['id'],
                'sl_price': signal['sl_price'],
                'tp1_order_id': tp1_order['id'],
                'tp1_price': signal['tp1_price'],
                'tp1_filled': False,
                'tp2_order_id': tp2_order['id'],
                'tp2_price': signal['tp2_price'],
                'tp2_filled': False,
                'tp3_order_id': tp3_order['id'],
                'tp3_price': signal['tp3_price'],
                'tp3_filled': False,
                'status': 'OPEN',
                'created_at': datetime.utcnow()
            }

            logger.info(f"✅ Position opened successfully: {position['entry_order_id']}")
            return position

        except Exception as e:
            logger.error(f"❌ Failed to open position for {symbol}: {e}")
            # TODO: Rollback any partially filled orders
            raise

    def monitor_position(self, position: Dict) -> Dict:
        """
        Monitor and update position status

        Returns:
            updated position dict
        """
        # Check which TP orders are filled
        open_orders = self.exchange.fetch_open_orders(position['symbol'])
        open_order_ids = {o['id'] for o in open_orders}

        # TP1 filled?
        if position['tp1_order_id'] not in open_order_ids and not position['tp1_filled']:
            position['tp1_filled'] = True
            logger.info(f"✅ TP1 hit for {position['symbol']}")

            # Activate trailing SL
            self.activate_trailing_sl(position)

        # TP2 filled?
        if position['tp2_order_id'] not in open_order_ids and not position['tp2_filled']:
            position['tp2_filled'] = True
            logger.info(f"✅ TP2 hit for {position['symbol']}")

        # TP3 filled?
        if position['tp3_order_id'] not in open_order_ids and not position['tp3_filled']:
            position['tp3_filled'] = True
            logger.info(f"✅ TP3 hit for {position['symbol']}")
            position['status'] = 'CLOSED'

        # SL hit?
        if position['sl_order_id'] not in open_orders:
            position['status'] = 'CLOSED'
            logger.info(f"⚠️  SL hit for {position['symbol']}")

        return position

    def activate_trailing_sl(self, position: Dict):
        """Activate trailing stop after TP1"""
        # TODO: Implement trailing logic
        pass
```

---

### Krok 3: Celery Task dla Auto-Trading

**Dodaj do**: `apps/ml/worker.py`

```python
@celery_app.task(name="trading.execute")
def execute_trading_signals():
    """
    Execute trading signals (runs every 1 minute)
    """
    db = SessionLocal()
    exchange = TradingExchangeClient()
    position_mgr = PositionManager(exchange)

    # Fetch pending signals
    pending_signals = db.query(Signal).filter(
        Signal.status == SignalStatus.ACTIVE,
        Signal.auto_trade_enabled == True,
        Signal.position_opened == False
    ).all()

    for signal in pending_signals:
        try:
            # Open position
            position = position_mgr.open_position(signal.to_dict())

            # Save to database
            db_position = Position(**position)
            db.add(db_position)

            # Mark signal as executed
            signal.position_opened = True
            signal.position_id = db_position.id

            db.commit()

        except Exception as e:
            logger.error(f"Failed to execute signal {signal.signal_id}: {e}")
            db.rollback()

    db.close()


@celery_app.task(name="trading.monitor")
def monitor_open_positions():
    """
    Monitor open positions (runs every 1 minute)
    """
    db = SessionLocal()
    exchange = TradingExchangeClient()
    position_mgr = PositionManager(exchange)

    # Fetch open positions
    open_positions = db.query(Position).filter(
        Position.status == 'OPEN'
    ).all()

    for pos in open_positions:
        try:
            # Update position status
            updated = position_mgr.monitor_position(pos.to_dict())

            # Update in database
            pos.tp1_filled = updated['tp1_filled']
            pos.tp2_filled = updated['tp2_filled']
            pos.tp3_filled = updated['tp3_filled']
            pos.status = updated['status']

            db.commit()

        except Exception as e:
            logger.error(f"Failed to monitor position {pos.id}: {e}")
            db.rollback()

    db.close()


# Add to beat schedule
celery_app.conf.beat_schedule.update({
    'execute-trades-every-minute': {
        'task': 'trading.execute',
        'schedule': 60.0,  # 1 minute
    },
    'monitor-positions-every-minute': {
        'task': 'trading.monitor',
        'schedule': 60.0,  # 1 minute
    },
})
```

---

## 📋 Implementacja - Checklist

### Phase 1: Basic (2-3 dni)
- [ ] Dodaj `TradingExchangeClient` z metodami order
- [ ] Dodaj `PositionManager` do otwierania pozycji
- [ ] Stwórz tabelę `positions` w bazie
- [ ] Dodaj Celery task `trading.execute`
- [ ] Dodaj Celery task `trading.monitor`
- [ ] Dodaj flag `auto_trade_enabled` do signals
- [ ] Testy na sandbox Binance

### Phase 2: Advanced (3-5 dni)
- [ ] Implementuj trailing SL
- [ ] Dodaj partial TP exits
- [ ] Risk management (max positions, drawdown)
- [ ] Emergency close mechanism
- [ ] Logging i monitoring

### Phase 3: Production (2-3 dni)
- [ ] Security audit
- [ ] API key encryption
- [ ] Rate limiting
- [ ] Error recovery
- [ ] Alerting (email/telegram)
- [ ] Dashboard dla live monitoring

---

## 🎯 Twoje Następne Kroki

### 1. **Poczekaj na zakończenie treningu** (dzisiaj w nocy)

### 2. **Sprawdź pierwsze sygnały** (jutro rano)
```bash
# Zobacz sygnały w bazie
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT signal_id, symbol, side, entry_price, expected_net_profit_pct, confidence
   FROM signals ORDER BY created_at DESC LIMIT 10;"
```

### 3. **Jeśli chcesz auto-trading**:
- Implementuj Phase 1 (2-3 dni pracy)
- Testuj na sandbox
- Deploy na production

### 4. **Lub traduj ręcznie**:
- Obserwuj UI/API
- Ręcznie otwieraj pozycje na Binance
- Monitoruj zyski

---

**Ostatnia aktualizacja**: 2025-10-06 18:07
**Status**: ✅ System gotowy do generowania sygnałów po zakończeniu treningu
