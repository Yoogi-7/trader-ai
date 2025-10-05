import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Iterable
from datetime import datetime, timedelta
import logging
from collections import defaultdict
from sqlalchemy import and_

from apps.api.db.models import Side, RiskProfile, SignalStatus, OHLCV, TimeFrame
from apps.api.config import settings

logger = logging.getLogger(__name__)


class Backtester:
    """
    Comprehensive backtester with realistic cost modeling.
    Simulates partial TP exits, trailing SL, funding fees.
    """

    def __init__(
        self,
        initial_capital: float = 100.0,
        maker_fee_bps: float = None,
        taker_fee_bps: float = None,
        slippage_bps: float = None,
        funding_rate_hourly_bps: float = None
    ):
        self.initial_capital = initial_capital
        self.maker_fee_bps = maker_fee_bps or settings.MAKER_FEE_BPS
        self.taker_fee_bps = taker_fee_bps or settings.TAKER_FEE_BPS
        self.slippage_bps = slippage_bps or settings.SLIPPAGE_BPS
        self.funding_rate_hourly_bps = funding_rate_hourly_bps or settings.FUNDING_RATE_HOURLY_BPS

        self.reset()

    def reset(self):
        """Reset backtest state"""
        self.capital = self.initial_capital
        self.equity_curve = []
        self.trades = []
        self.open_positions = []
        self.peak_equity = self.initial_capital
        self.max_drawdown = 0.0

    def run(
        self,
        signals: List[Dict],
        market_data: pd.DataFrame
    ) -> Dict:
        """
        Run backtest on a list of signals.

        Args:
            signals: List of signal dicts
            market_data: OHLCV data for simulation

        Returns:
            Backtest results dict
        """
        self.reset()

        # Sort signals by timestamp
        signals = sorted(signals, key=lambda x: x['timestamp'])

        # Sort market data by timestamp
        market_data = market_data.sort_values('timestamp').reset_index(drop=True)

        for signal in signals:
            self._process_signal(signal, market_data)

        # Close any remaining open positions at end
        self._close_all_positions(market_data)

        # Calculate metrics
        results = self._calculate_metrics()

        return results

    def _process_signal(self, signal: Dict, market_data: pd.DataFrame):
        """Process a single signal"""
        # Check if we have capital and position limits
        if not self._can_open_position(signal):
            return

        # Simulate entry
        entry_result = self._simulate_entry(signal, market_data)

        if not entry_result:
            return

        # Track position
        position = {
            'signal': signal,
            'entry': entry_result,
            'remaining_quantity': signal['quantity'],
            'exits': [],
            'status': 'open'
        }

        self.open_positions.append(position)

        # Simulate position lifecycle
        self._simulate_position_lifecycle(position, market_data)

    def _simulate_entry(self, signal: Dict, market_data: pd.DataFrame) -> Optional[Dict]:
        """Simulate entry execution"""
        # Find market data at signal timestamp
        entry_bar = market_data[market_data['timestamp'] >= signal['timestamp']].head(1)

        if entry_bar.empty:
            return None

        entry_price = signal['entry_price']

        # Apply slippage (assume taker order for safety)
        slippage_factor = 1 + (self.slippage_bps / 10000) * (1 if signal['side'] == Side.LONG else -1)
        filled_price = entry_price * slippage_factor

        # Calculate fees
        entry_fee = signal['position_size_usd'] * (self.maker_fee_bps / 10000)

        # Deduct margin from capital
        margin_required = signal['position_size_usd'] / signal['leverage']

        if margin_required > self.capital:
            logger.debug(f"Insufficient capital: {self.capital} < {margin_required}")
            return None

        self.capital -= margin_required

        return {
            'timestamp': entry_bar.iloc[0]['timestamp'],
            'price': filled_price,
            'fee': entry_fee,
            'margin': margin_required
        }

    def _simulate_position_lifecycle(self, position: Dict, market_data: pd.DataFrame):
        """Simulate position from entry to exit(s)"""
        signal = position['signal']
        entry_ts = position['entry']['timestamp']

        # Get market data after entry
        future_data = market_data[market_data['timestamp'] > entry_ts].copy()

        tp_levels = [
            (signal['tp1_price'], signal['tp1_pct'], 'TP1'),
            (signal['tp2_price'], signal['tp2_pct'], 'TP2'),
            (signal['tp3_price'], signal['tp3_pct'], 'TP3')
        ]

        sl_price = signal['sl_price']
        current_sl = sl_price
        trailing_activated = False

        for i, row in future_data.iterrows():
            timestamp = row['timestamp']
            high = row['high']
            low = row['low']
            close = row['close']

            # Check SL hit
            sl_hit = (
                (signal['side'] == Side.LONG and low <= current_sl) or
                (signal['side'] == Side.SHORT and high >= current_sl)
            )

            if sl_hit:
                self._execute_exit(position, current_sl, timestamp, 'SL', remaining=True)
                position['status'] = 'closed_sl'
                break

            # Check TP levels
            for tp_price, tp_pct, tp_name in tp_levels:
                if position['remaining_quantity'] <= 0:
                    break

                tp_hit = (
                    (signal['side'] == Side.LONG and high >= tp_price) or
                    (signal['side'] == Side.SHORT and low <= tp_price)
                )

                if tp_hit and not any(e['type'] == tp_name for e in position['exits']):
                    # Partial exit
                    exit_qty_pct = tp_pct
                    self._execute_exit(position, tp_price, timestamp, tp_name, pct=exit_qty_pct)

                    if tp_name == 'TP1':
                        trailing_activated = True

            # Apply trailing stop after TP1
            if trailing_activated and 'atr' in signal:
                atr = signal.get('atr', signal['entry_price'] * 0.02)  # Default 2% if no ATR
                new_sl = self._calculate_trailing_sl(
                    current_price=close,
                    entry_price=signal['entry_price'],
                    current_sl=current_sl,
                    side=signal['side'],
                    atr=atr
                )
                current_sl = max(current_sl, new_sl) if signal['side'] == Side.LONG else min(current_sl, new_sl)

            # Time stop (max 48 hours)
            duration = timestamp - entry_ts
            if duration > timedelta(hours=48):
                self._execute_exit(position, close, timestamp, 'TIME', remaining=True)
                position['status'] = 'closed_time'
                break

        # If still open, close at last price
        if position['status'] == 'open' and position['remaining_quantity'] > 0:
            last_price = future_data.iloc[-1]['close'] if not future_data.empty else signal['entry_price']
            last_ts = future_data.iloc[-1]['timestamp'] if not future_data.empty else entry_ts
            self._execute_exit(position, last_price, last_ts, 'END', remaining=True)
            position['status'] = 'closed_end'

        # Finalize trade
        self._finalize_trade(position)

    def _execute_exit(
        self,
        position: Dict,
        price: float,
        timestamp: datetime,
        exit_type: str,
        pct: float = None,
        remaining: bool = False
    ):
        """Execute a (partial) exit"""
        signal = position['signal']

        if remaining:
            exit_qty_pct = 100.0
        else:
            exit_qty_pct = pct

        exit_qty = signal['quantity'] * (exit_qty_pct / 100)
        exit_size_usd = exit_qty * price

        # Fees and slippage (taker)
        exit_fee = exit_size_usd * (self.taker_fee_bps / 10000)
        slippage_cost = exit_size_usd * (self.slippage_bps / 10000)

        position['exits'].append({
            'timestamp': timestamp,
            'price': price,
            'quantity': exit_qty,
            'pct': exit_qty_pct,
            'type': exit_type,
            'fee': exit_fee,
            'slippage': slippage_cost
        })

        position['remaining_quantity'] -= exit_qty

    def _finalize_trade(self, position: Dict):
        """Finalize trade and update capital"""
        signal = position['signal']
        entry = position['entry']
        exits = position['exits']

        # Calculate gross PnL
        gross_pnl = 0.0

        for exit in exits:
            exit_value = exit['quantity'] * exit['price']
            entry_value = exit['quantity'] * entry['price']

            if signal['side'] == Side.LONG:
                gross_pnl += (exit_value - entry_value)
            else:
                gross_pnl += (entry_value - exit_value)

        # Total fees
        total_fees = entry['fee'] + sum(e['fee'] + e.get('slippage', 0) for e in exits)

        # Funding fees (estimate based on duration)
        duration_hours = (exits[-1]['timestamp'] - entry['timestamp']).total_seconds() / 3600 if exits else 0
        funding_fees = signal['position_size_usd'] * (self.funding_rate_hourly_bps / 10000) * duration_hours

        # Net PnL
        net_pnl = gross_pnl - total_fees - funding_fees

        # Return margin and PnL to capital
        self.capital += entry['margin'] + net_pnl

        # Update equity curve
        self.equity_curve.append({
            'timestamp': exits[-1]['timestamp'] if exits else entry['timestamp'],
            'equity': self.capital
        })

        # Update max drawdown
        if self.capital > self.peak_equity:
            self.peak_equity = self.capital
        else:
            dd = (self.peak_equity - self.capital) / self.peak_equity
            if dd > self.max_drawdown:
                self.max_drawdown = dd

        # Record trade
        trade_result = {
            'signal_id': signal['signal_id'],
            'symbol': signal['symbol'],
            'side': signal['side'].value if isinstance(signal['side'], Side) else signal['side'],
            'entry_price': entry['price'],
            'entry_timestamp': entry['timestamp'],
            'exits': exits,
            'gross_pnl': gross_pnl,
            'total_fees': total_fees,
            'funding_fees': funding_fees,
            'net_pnl': net_pnl,
            'net_pnl_pct': (net_pnl / signal['position_size_usd']) * 100,
            'duration_hours': duration_hours,
            'status': position['status']
        }

        self.trades.append(trade_result)

    def _can_open_position(self, signal: Dict) -> bool:
        """Check if we can open a new position"""
        margin_required = signal['position_size_usd'] / signal['leverage']
        return self.capital >= margin_required

    def _calculate_trailing_sl(
        self,
        current_price: float,
        entry_price: float,
        current_sl: float,
        side: Side,
        atr: float
    ) -> float:
        """Calculate trailing SL"""
        trailing_distance = atr * 0.5

        if side == Side.LONG:
            new_sl = max(current_sl, entry_price + trailing_distance)
            new_sl = max(new_sl, current_price - atr * 1.0)
        else:
            new_sl = min(current_sl, entry_price - trailing_distance)
            new_sl = min(new_sl, current_price + atr * 1.0)

        return new_sl

    def _close_all_positions(self, market_data: pd.DataFrame):
        """Force close all open positions at end of backtest"""
        for position in self.open_positions:
            if position['status'] == 'open' and position['remaining_quantity'] > 0:
                last_price = market_data.iloc[-1]['close']
                last_ts = market_data.iloc[-1]['timestamp']
                self._execute_exit(position, last_price, last_ts, 'FORCED', remaining=True)
                self._finalize_trade(position)

    def _calculate_metrics(self) -> Dict:
        """Calculate backtest performance metrics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'final_equity': self.capital,
                'total_return_pct': 0.0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'max_drawdown_pct': 0.0,
                'sharpe_ratio': 0.0
            }

        trades_df = pd.DataFrame(self.trades)

        total_trades = len(trades_df)
        winners = trades_df[trades_df['net_pnl'] > 0]
        losers = trades_df[trades_df['net_pnl'] <= 0]

        win_rate = len(winners) / total_trades if total_trades > 0 else 0.0
        avg_win = winners['net_pnl'].mean() if len(winners) > 0 else 0.0
        avg_loss = abs(losers['net_pnl'].mean()) if len(losers) > 0 else 0.0

        total_wins = winners['net_pnl'].sum() if len(winners) > 0 else 0.0
        total_losses = abs(losers['net_pnl'].sum()) if len(losers) > 0 else 0.0

        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        total_return_pct = ((self.capital - self.initial_capital) / self.initial_capital) * 100

        # Sharpe ratio (simplified)
        if len(self.equity_curve) > 1:
            equity_df = pd.DataFrame(self.equity_curve)
            returns = equity_df['equity'].pct_change().dropna()
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
        else:
            sharpe = 0.0

        # Hit rate by TP level
        tp1_hits = len(trades_df[trades_df.apply(lambda x: any(e['type'] == 'TP1' for e in x['exits']), axis=1)])
        hit_rate_tp1 = (tp1_hits / total_trades) * 100 if total_trades > 0 else 0.0

        return {
            'total_trades': total_trades,
            'initial_capital': self.initial_capital,
            'final_equity': self.capital,
            'total_return_pct': total_return_pct,
            'win_rate': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown_pct': self.max_drawdown * 100,
            'sharpe_ratio': sharpe,
            'hit_rate_tp1': hit_rate_tp1,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }


def _coerce_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle both naive and Z-suffixed ISO strings
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            logger.warning("Unrecognized timestamp format for value %s", value)
    return datetime.utcnow()


def _load_market_data(
    db,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Fetch OHLCV data for the requested window."""

    buffer = timedelta(days=2)
    query = (
        db.query(OHLCV)
        .filter(
            and_(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == TimeFrame(timeframe),
                OHLCV.timestamp >= start - buffer,
                OHLCV.timestamp <= end + buffer,
            )
        )
        .order_by(OHLCV.timestamp.asc())
    )

    rows = query.all()
    if not rows:
        logger.warning("No OHLCV rows available for %s %s between %s and %s", symbol, timeframe, start, end)
        return pd.DataFrame()

    return pd.DataFrame(
        [
            {
                'timestamp': row.timestamp,
                'open': row.open,
                'high': row.high,
                'low': row.low,
                'close': row.close,
                'volume': row.volume,
            }
            for row in rows
        ]
    )


def backtest_signals(db, signals: Iterable[Dict], default_timeframe: str = '15m') -> Dict:
    """
    Lightweight convenience wrapper used by the Celery worker to backtest freshly
    generated historical signals. Returns aggregated metrics so the API can report
    progress even if the comprehensive research backtester is not configured.
    """

    signals = list(signals or [])
    if not signals:
        logger.info("No historical signals supplied for backtest")
        return {
            'win_rate': 0.0,
            'avg_profit_pct': 0.0,
            'total_pnl_usd': 0.0,
            'total_trades': 0,
            'details': [],
        }

    grouped = defaultdict(list)
    for signal in signals:
        symbol = signal.get('symbol') or signal.get('pair') or 'BTC/USDT'
        ts = _coerce_timestamp(signal.get('timestamp'))
        signal['timestamp'] = ts
        timeframe = signal.get('timeframe', default_timeframe)
        signal['timeframe'] = timeframe

        side_val = signal.get('side')
        if isinstance(side_val, str):
            try:
                signal['side'] = Side(side_val.lower())
            except ValueError:
                signal['side'] = Side.LONG if side_val.upper() == 'LONG' else Side.SHORT

        grouped[(symbol, timeframe)].append(signal)

    aggregate_trades = 0
    aggregate_win_weight = 0.0
    aggregate_return_pct = 0.0
    aggregate_pnl = 0.0
    per_group_results = []
    all_trades: list[dict] = []

    for (symbol, timeframe), group_signals in grouped.items():
        timestamps = [sig['timestamp'] for sig in group_signals]
        start = min(timestamps)
        end = max(timestamps)

        market_df = _load_market_data(db, symbol, timeframe, start, end)
        if market_df.empty:
            continue

        tester = Backtester()
        metrics = tester.run(group_signals, market_df)
        metrics['symbol'] = symbol
        metrics['timeframe'] = timeframe
        per_group_results.append(metrics)
        all_trades.extend(metrics.get('trades', []))

        trades = metrics.get('total_trades', 0)
        aggregate_trades += trades
        aggregate_win_weight += metrics.get('win_rate', 0.0) * trades
        aggregate_return_pct += metrics.get('total_return_pct', 0.0)
        aggregate_pnl += metrics.get('final_equity', tester.initial_capital) - tester.initial_capital

    if not per_group_results or aggregate_trades == 0:
        logger.warning("Historical backtest could not be completed due to missing data")
        return {
            'win_rate': 0.0,
            'avg_profit_pct': 0.0,
            'total_pnl_usd': 0.0,
            'total_trades': aggregate_trades,
            'details': per_group_results,
            'trades': [],
        }

    win_rate = aggregate_win_weight / aggregate_trades if aggregate_trades else 0.0
    avg_return_pct = aggregate_return_pct / len(per_group_results)

    return {
        'win_rate': win_rate,
        'avg_profit_pct': avg_return_pct,
        'total_pnl_usd': aggregate_pnl,
        'total_trades': aggregate_trades,
        'details': per_group_results,
        'trades': all_trades,
    }


__all__ = ['Backtester', 'backtest_signals']
