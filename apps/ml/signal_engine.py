import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
import uuid
from apps.api.db.models import RiskProfile, Side
from apps.api.config import settings

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Signal generation with TP/SL calculation, position sizing, and cost-based filtering.
    Ensures minimum 2% net profit after all costs.
    """

    def __init__(
        self,
        maker_fee_bps: float = None,
        taker_fee_bps: float = None,
        slippage_bps: float = None,
        funding_rate_hourly_bps: float = None
    ):
        self.maker_fee_bps = maker_fee_bps or settings.MAKER_FEE_BPS
        self.taker_fee_bps = taker_fee_bps or settings.TAKER_FEE_BPS
        self.slippage_bps = slippage_bps or settings.SLIPPAGE_BPS
        self.funding_rate_hourly_bps = funding_rate_hourly_bps or settings.FUNDING_RATE_HOURLY_BPS

    def generate_signal(
        self,
        symbol: str,
        side: Side,
        entry_price: float,
        atr: float,
        risk_profile: RiskProfile,
        capital_usd: float,
        confidence: float,
        timestamp: datetime,
        leverage_cap: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Generate a complete trading signal with TP/SL, sizing, and profit validation.

        Args:
            symbol: Trading pair
            side: LONG or SHORT
            entry_price: Entry price
            atr: Current ATR value (for dynamic SL)
            risk_profile: LOW, MEDIUM, or HIGH
            capital_usd: Available capital
            confidence: Model confidence score
            timestamp: Signal timestamp
            leverage_cap: Optional leverage cap

        Returns:
            Signal dict or None if doesn't meet profit threshold
        """
        # Calculate TP/SL using ATR
        tp_levels, sl_price = self._calculate_tp_sl(entry_price, atr, side)

        # Position sizing based on risk profile
        leverage, position_size_usd, quantity = self._calculate_position_size(
            entry_price=entry_price,
            sl_price=sl_price,
            risk_profile=risk_profile,
            capital_usd=capital_usd,
            leverage_cap=leverage_cap
        )

        # Calculate expected profit after costs
        expected_net_profit_pct, expected_net_profit_usd = self._calculate_expected_profit(
            entry_price=entry_price,
            tp_prices=tp_levels,
            tp_pcts=[30, 40, 30],
            sl_price=sl_price,
            position_size_usd=position_size_usd,
            leverage=leverage,
            side=side
        )

        # CRITICAL FILTER: Minimum 2% net profit
        if expected_net_profit_pct < settings.MIN_NET_PROFIT_PCT:
            logger.info(
                f"Signal rejected for {symbol}: Expected net profit {expected_net_profit_pct:.2f}% "
                f"< minimum {settings.MIN_NET_PROFIT_PCT}%"
            )
            return None

        # Calculate liquidation price
        liquidation_price = self._calculate_liquidation_price(
            entry_price=entry_price,
            leverage=leverage,
            side=side
        )

        # Validate liquidation is sufficiently far from SL
        if not self._validate_liquidation(sl_price, liquidation_price, side):
            logger.warning(f"Signal rejected for {symbol}: Liquidation price too close to SL")
            return None

        # Risk/Reward ratio
        risk_distance = abs(entry_price - sl_price)
        reward_distance = abs(tp_levels[1] - entry_price)  # Using TP2 as primary target
        rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 0

        # Construct signal
        signal = {
            'signal_id': f"signal_{symbol.replace('/', '_')}_{uuid.uuid4().hex[:8]}",
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'timestamp': timestamp,
            'tp1_price': tp_levels[0],
            'tp1_pct': 30.0,
            'tp2_price': tp_levels[1],
            'tp2_pct': 40.0,
            'tp3_price': tp_levels[2],
            'tp3_pct': 30.0,
            'sl_price': sl_price,
            'leverage': leverage,
            'margin_mode': 'ISOLATED',
            'position_size_usd': position_size_usd,
            'quantity': quantity,
            'risk_reward_ratio': rr_ratio,
            'estimated_liquidation': liquidation_price,
            'max_loss_usd': position_size_usd * (abs(entry_price - sl_price) / entry_price),
            'confidence': confidence,
            'expected_net_profit_pct': expected_net_profit_pct,
            'expected_net_profit_usd': expected_net_profit_usd,
            'valid_until': timestamp + timedelta(hours=4),
            'risk_profile': risk_profile,
            'passed_profit_filter': True
        }

        return signal

    def _calculate_tp_sl(
        self,
        entry_price: float,
        atr: float,
        side: Side
    ) -> Tuple[list, float]:
        """
        Calculate TP levels and SL using ATR-based approach.

        Returns:
            (tp_levels, sl_price)
        """
        atr_multiplier_sl = 1.5
        atr_multiplier_tp1 = 1.0
        atr_multiplier_tp2 = 2.0
        atr_multiplier_tp3 = 3.0

        if side == Side.LONG:
            sl_price = entry_price - (atr * atr_multiplier_sl)
            tp1 = entry_price + (atr * atr_multiplier_tp1)
            tp2 = entry_price + (atr * atr_multiplier_tp2)
            tp3 = entry_price + (atr * atr_multiplier_tp3)
        else:  # SHORT
            sl_price = entry_price + (atr * atr_multiplier_sl)
            tp1 = entry_price - (atr * atr_multiplier_tp1)
            tp2 = entry_price - (atr * atr_multiplier_tp2)
            tp3 = entry_price - (atr * atr_multiplier_tp3)

        return [tp1, tp2, tp3], sl_price

    def _calculate_position_size(
        self,
        entry_price: float,
        sl_price: float,
        risk_profile: RiskProfile,
        capital_usd: float,
        leverage_cap: Optional[int] = None
    ) -> Tuple[float, float, float]:
        """
        Calculate position sizing based on risk per trade.

        Returns:
            (leverage, position_size_usd, quantity)
        """
        # Risk parameters by profile
        risk_params = {
            RiskProfile.LOW: {
                'risk_per_trade': settings.LOW_RISK_PER_TRADE,
                'max_lev': settings.LOW_MAX_LEV
            },
            RiskProfile.MEDIUM: {
                'risk_per_trade': settings.MED_RISK_PER_TRADE,
                'max_lev': settings.MED_MAX_LEV
            },
            RiskProfile.HIGH: {
                'risk_per_trade': settings.HIGH_RISK_PER_TRADE,
                'max_lev': settings.HIGH_MAX_LEV
            }
        }

        params = risk_params[risk_profile]
        risk_per_trade = params['risk_per_trade']
        max_leverage = leverage_cap if leverage_cap else params['max_lev']

        # Calculate risk amount
        risk_usd = capital_usd * risk_per_trade

        # Calculate position size based on SL distance
        sl_distance_pct = abs(entry_price - sl_price) / entry_price

        if sl_distance_pct == 0:
            logger.error("SL distance is zero, cannot calculate position size")
            return 1.0, 100.0, 100.0 / entry_price

        # Position size such that hitting SL loses exactly risk_usd
        position_size_usd = risk_usd / sl_distance_pct

        # Apply leverage constraint
        max_position_size = capital_usd * max_leverage
        position_size_usd = min(position_size_usd, max_position_size)

        # Calculate actual leverage used
        leverage = position_size_usd / capital_usd
        leverage = min(leverage, max_leverage)

        # Calculate quantity
        quantity = position_size_usd / entry_price

        return leverage, position_size_usd, quantity

    def _calculate_expected_profit(
        self,
        entry_price: float,
        tp_prices: list,
        tp_pcts: list,
        sl_price: float,
        position_size_usd: float,
        leverage: float,
        side: Side
    ) -> Tuple[float, float]:
        """
        Calculate expected net profit after all costs (fees, slippage, funding).

        Assumes partial exits at TP1/TP2/TP3 with specified percentages.

        Returns:
            (expected_net_profit_pct, expected_net_profit_usd)
        """
        # Assume TP hit scenario (optimistic but realistic for filtering)
        # Weighted average of TP levels
        avg_exit_price = sum(tp * pct / 100 for tp, pct in zip(tp_prices, tp_pcts))

        # Gross profit
        if side == Side.LONG:
            gross_profit_pct = (avg_exit_price - entry_price) / entry_price
        else:
            gross_profit_pct = (entry_price - avg_exit_price) / entry_price

        gross_profit_usd = position_size_usd * gross_profit_pct

        # Entry cost (assume maker order = lower fee)
        entry_fee_usd = position_size_usd * (self.maker_fee_bps / 10000)
        entry_slippage_usd = position_size_usd * (self.slippage_bps / 10000) * 0.5  # Reduced for maker

        # Exit costs (assume 3 exits: TP1, TP2, TP3 - taker orders)
        exit_size_total = position_size_usd
        exit_fee_usd = exit_size_total * (self.taker_fee_bps / 10000)
        exit_slippage_usd = exit_size_total * (self.slippage_bps / 10000)

        # Funding cost (assume average hold time = 12 hours)
        avg_hold_hours = 12
        funding_cost_usd = position_size_usd * (self.funding_rate_hourly_bps / 10000) * avg_hold_hours

        # Total costs
        total_costs_usd = entry_fee_usd + entry_slippage_usd + exit_fee_usd + exit_slippage_usd + funding_cost_usd

        # Net profit
        net_profit_usd = gross_profit_usd - total_costs_usd
        net_profit_pct = (net_profit_usd / position_size_usd) * 100

        return net_profit_pct, net_profit_usd

    def _calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: float,
        side: Side
    ) -> float:
        """
        Calculate liquidation price (simplified formula).

        Liquidation occurs when loss = margin (1/leverage of position).
        """
        margin_ratio = 1 / leverage

        if side == Side.LONG:
            liq_price = entry_price * (1 - margin_ratio * 0.9)  # 90% of margin (maintenance margin buffer)
        else:
            liq_price = entry_price * (1 + margin_ratio * 0.9)

        return liq_price

    def _validate_liquidation(
        self,
        sl_price: float,
        liq_price: float,
        side: Side
    ) -> bool:
        """
        Validate that liquidation price is sufficiently far from SL.
        We want SL to trigger before liquidation.
        """
        if side == Side.LONG:
            # liq_price should be below sl_price
            return liq_price < sl_price * 0.95
        else:
            # liq_price should be above sl_price
            return liq_price > sl_price * 1.05

    def apply_trailing_stop(
        self,
        current_price: float,
        entry_price: float,
        current_sl: float,
        tp1_price: float,
        side: Side,
        atr: float
    ) -> float:
        """
        Apply trailing stop after TP1 is hit.

        Returns:
            New SL price
        """
        tp1_hit = (
            (side == Side.LONG and current_price >= tp1_price) or
            (side == Side.SHORT and current_price <= tp1_price)
        )

        if not tp1_hit:
            return current_sl

        # Move SL to breakeven + small buffer
        trailing_distance = atr * 0.5

        if side == Side.LONG:
            new_sl = max(current_sl, entry_price + trailing_distance)
            new_sl = max(new_sl, current_price - atr * 1.0)  # Trail below current price
        else:
            new_sl = min(current_sl, entry_price - trailing_distance)
            new_sl = min(new_sl, current_price + atr * 1.0)

        return new_sl
