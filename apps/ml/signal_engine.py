import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Callable, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from apps.api.db.models import (
    RiskProfile,
    Side,
    OHLCV,
    MarketMetrics,
    Signal,
    SignalStatus,
    TimeFrame,
    ModelRegistry as ModelRecord,
)
from apps.api.config import settings
from apps.ml.features import FeatureEngineering
from apps.ml.model_registry import ModelRegistry
from apps.ml.models import EnsembleModel
from apps.ml.performance_tracker import PerformanceTracker
from apps.ml.auto_trainer import AutoTrainer

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Signal generation with TP/SL calculation, position sizing, and cost-based filtering.
    Ensures minimum 2% net profit after all costs.
    Includes Kelly Criterion for optimal leverage calculation.
    """

    def __init__(
        self,
        maker_fee_bps: float = None,
        taker_fee_bps: float = None,
        slippage_bps: float = None,
        funding_rate_hourly_bps: float = None,
        use_kelly_criterion: bool = True
    ):
        self.maker_fee_bps = maker_fee_bps or settings.MAKER_FEE_BPS
        self.taker_fee_bps = taker_fee_bps or settings.TAKER_FEE_BPS
        self.slippage_bps = slippage_bps or settings.SLIPPAGE_BPS
        self.funding_rate_hourly_bps = funding_rate_hourly_bps or settings.FUNDING_RATE_HOURLY_BPS
        self.use_kelly_criterion = use_kelly_criterion

    def _calculate_kelly_leverage(
        self,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        probability: float,
        max_leverage: float
    ) -> float:
        """
        Calculate optimal leverage using Kelly Criterion.

        Kelly formula: f* = (p * b - (1 - p)) / b
        Where:
            p = probability of winning
            b = ratio of TP to SL (reward/risk ratio)
            f* = optimal fraction of capital to risk

        Args:
            entry_price: Entry price
            sl_price: Stop loss price
            tp_price: Take profit price (main target)
            probability: Probability of success (0.0-1.0)
            max_leverage: Maximum allowed leverage

        Returns:
            Optimal leverage (capped at max_leverage)
        """
        # Calculate TP and SL percentages
        sl_pct = abs(entry_price - sl_price) / entry_price
        tp_pct = abs(tp_price - entry_price) / entry_price

        if sl_pct == 0:
            logger.warning("SL distance is zero, returning minimum leverage")
            return 1.0

        # Calculate b (reward/risk ratio)
        b = tp_pct / sl_pct

        # Kelly Criterion formula
        # f_star = (p * b - (1 - p)) / b
        p = probability
        f_star = (p * b - (1.0 - p)) / b

        # Convert to leverage
        # f_star is the fraction of capital to risk, but we need to be conservative
        # Apply Kelly fraction (typically use half-Kelly or quarter-Kelly)
        kelly_fraction = 0.25  # Conservative: use quarter-Kelly
        optimal_fraction = max(0.0, f_star * kelly_fraction)

        # Convert fraction to leverage
        if sl_pct > 0:
            kelly_leverage = optimal_fraction / sl_pct
        else:
            kelly_leverage = 1.0

        # Ensure minimum of 1x and cap at max_leverage
        kelly_leverage = max(1.0, min(kelly_leverage, max_leverage))

        return kelly_leverage

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
        leverage_cap: Optional[int] = None,
        enforce_risk_filters: bool = True,
        volatility_regime: str = 'normal',
        volume_high: bool = False,
        atr_rising: bool = False,
        atr_falling: bool = False,
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
            volatility_regime: 'low', 'normal', or 'high' volatility

        Returns:
            Signal dict or None if doesn't meet profit threshold
        """
        # Calculate TP/SL using ATR with adaptive parameters including volume/ATR trends
        tp_levels, sl_price = self._calculate_tp_sl(
            entry_price, atr, side, confidence, volatility_regime,
            volume_high, atr_rising, atr_falling
        )

        # Position sizing based on risk profile with Kelly Criterion
        leverage, position_size_usd, quantity = self._calculate_position_size(
            entry_price=entry_price,
            sl_price=sl_price,
            risk_profile=risk_profile,
            capital_usd=capital_usd,
            leverage_cap=leverage_cap,
            confidence=confidence,
            tp_levels=tp_levels,
            use_kelly=self.use_kelly_criterion
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

        # CRITICAL FILTER: Minimum 2% net profit + TP/SL ratio requirement
        if enforce_risk_filters:
            # Calculate TP/SL ratio (using weighted average TP)
            tp_avg = sum(tp * pct / 100 for tp, pct in zip(tp_levels, [30, 40, 30]))
            tp_distance = abs(tp_avg - entry_price)
            sl_distance = abs(entry_price - sl_price)
            tp_sl_ratio = tp_distance / sl_distance if sl_distance > 0 else 0

            # Dynamic TP/SL ratio requirement based on confidence
            min_tp_sl_ratio = 2.5 if confidence < 0.7 else 2.0

            # Check both net profit and TP/SL ratio
            if expected_net_profit_pct < settings.MIN_NET_PROFIT_PCT:
                logger.info(
                    f"Signal rejected for {symbol}: Expected net profit {expected_net_profit_pct:.2f}% "
                    f"< minimum {settings.MIN_NET_PROFIT_PCT}%"
                )
                return None

            if tp_sl_ratio < min_tp_sl_ratio:
                logger.info(
                    f"Signal rejected for {symbol}: TP/SL ratio {tp_sl_ratio:.2f} "
                    f"< minimum {min_tp_sl_ratio:.2f} (confidence={confidence:.2f})"
                )
                return None

        # Calculate liquidation price
        liquidation_price = self._calculate_liquidation_price(
            entry_price=entry_price,
            leverage=leverage,
            side=side
        )

        # Validate liquidation is sufficiently far from SL
        if enforce_risk_filters and not self._validate_liquidation(sl_price, liquidation_price, side):
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
            'passed_profit_filter': True,
            'atr': atr
        }

        return signal

    def _calculate_tp_sl(
        self,
        entry_price: float,
        atr: float,
        side: Side,
        confidence: float = 0.7,
        volatility_regime: str = 'normal',
        volume_high: bool = False,
        atr_rising: bool = False,
        atr_falling: bool = False
    ) -> Tuple[list, float]:
        """
        Calculate adaptive TP levels and SL based on market conditions.

        Args:
            entry_price: Entry price
            atr: Current ATR value
            side: LONG or SHORT
            confidence: Model confidence (0.0-1.0)
            volatility_regime: 'low', 'normal', or 'high'
            volume_high: Whether volume is high relative to average
            atr_rising: Whether ATR is rising (trending market)
            atr_falling: Whether ATR is falling (consolidating market)

        Returns:
            (tp_levels, sl_price)
        """
        # Adaptive SL based on volatility
        if volatility_regime == 'high':
            atr_multiplier_sl = 1.5  # Wider SL in high volatility
        elif volatility_regime == 'low':
            atr_multiplier_sl = 0.8  # Tighter SL in low volatility
        else:
            atr_multiplier_sl = 1.0  # Normal SL

        # Adaptive TP based on confidence and volatility
        # Higher confidence = aim for TP2/TP3, lower confidence = focus on TP1
        if confidence >= 0.7:
            # High confidence: aggressive targets
            if volatility_regime == 'high':
                tp_mult = [3.0, 5.0, 8.0]  # Higher multiples in trending volatile markets
            else:
                tp_mult = [2.5, 4.5, 7.0]  # Normal aggressive targets
        elif confidence >= 0.65:
            # Medium-high confidence: balanced targets
            tp_mult = [2.0, 3.5, 6.0]  # Standard multipliers
        else:
            # Lower confidence: conservative targets
            tp_mult = [1.5, 2.5, 4.0]  # Quick profits, lower risk

        # Volume-based TP adjustment
        # High volume + rising ATR = trending market, increase TP targets
        if volume_high and atr_rising:
            tp_mult = [min(m * 1.3, 6.0) for m in tp_mult]  # Increase by 30%, cap at 6.0
            logger.debug(f"Volume-based TP adjustment: high volume + rising ATR -> increased targets")
        # ATR falling + high confidence = tighter targets for quick profits
        elif atr_falling and confidence >= 0.7:
            tp_mult = [max(m * 0.7, 2.0) for m in tp_mult]  # Decrease by 30%, minimum 2.0
            logger.debug(f"Volume-based TP adjustment: falling ATR + high confidence -> tighter targets")

        if side == Side.LONG:
            sl_price = entry_price - (atr * atr_multiplier_sl)
            tp1 = entry_price + (atr * tp_mult[0])
            tp2 = entry_price + (atr * tp_mult[1])
            tp3 = entry_price + (atr * tp_mult[2])
        else:  # SHORT
            sl_price = entry_price + (atr * atr_multiplier_sl)
            tp1 = entry_price - (atr * tp_mult[0])
            tp2 = entry_price - (atr * tp_mult[1])
            tp3 = entry_price - (atr * tp_mult[2])

        return [tp1, tp2, tp3], sl_price

    def _calculate_position_size(
        self,
        entry_price: float,
        sl_price: float,
        risk_profile: RiskProfile,
        capital_usd: float,
        leverage_cap: Optional[int] = None,
        confidence: float = 0.7,
        tp_levels: Optional[list] = None,
        use_kelly: bool = True
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

        # Calculate Kelly Criterion optimal leverage if enabled
        if use_kelly and tp_levels and len(tp_levels) >= 2:
            kelly_leverage = self._calculate_kelly_leverage(
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_levels[1],  # Use TP2 as main target
                probability=confidence,
                max_leverage=max_leverage
            )
            # Use Kelly as additional constraint
            max_leverage = min(max_leverage, kelly_leverage)
            logger.debug(f"Kelly Criterion leverage: {kelly_leverage:.2f}x (capped at {max_leverage:.2f}x)")

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
        trailing_distance = atr * 0.3  # Tighter trailing (was 0.5)

        if side == Side.LONG:
            new_sl = max(current_sl, entry_price + trailing_distance)
            new_sl = max(new_sl, current_price - atr * 1.0)  # Trail below current price
        else:
            new_sl = min(current_sl, entry_price - trailing_distance)
            new_sl = min(new_sl, current_price + atr * 1.0)

        return new_sl


@dataclass
class SignalInferenceResult:
    """Container holding signal inference outputs and metadata."""

    signal: Optional[Dict]
    model_info: Dict[str, Any]
    risk_filters: Dict[str, bool]
    inference_metadata: Dict[str, Any]
    accepted: bool
    rejection_reasons: Optional[List[str]] = None


class SignalEngine:
    """
    High level signal generation pipeline that
    1. Loads the currently deployed model from the registry
    2. Prepares latest OHLCV features + ATR
    3. Runs inference and applies risk filters before producing a trading signal.
    """

    def __init__(
        self,
        db: Session,
        registry: Optional[ModelRegistry] = None,
        signal_generator: Optional[SignalGenerator] = None,
        model_factory: Optional[Callable[[], Any]] = None,
        performance_tracker: Optional[PerformanceTracker] = None,
        lookback_bars: int = 250,
        max_spread_bps: float = 15.0,
        min_volume: float = 1.0
    ):
        self.db = db
        self.registry = registry or ModelRegistry(registry_dir=settings.MODEL_REGISTRY_DIR)
        self.signal_generator = signal_generator or SignalGenerator()
        self.model_factory = model_factory or EnsembleModel
        self.lookback_bars = lookback_bars
        self.max_spread_bps = max_spread_bps
        self.min_volume = min_volume
        self.feature_engineering = FeatureEngineering()
        self.performance_tracker = performance_tracker or PerformanceTracker(
            tracking_dir=settings.PERFORMANCE_TRACKING_DIR
        )

    def generate_for_deployment(
        self,
        symbol: str,
        timeframe: str,
        environment: str = "production",
        risk_profile: RiskProfile = RiskProfile.MEDIUM,
        capital_usd: float = 1000.0
    ) -> Optional[SignalInferenceResult]:
        """Generate signal for the current deployed model of a symbol/timeframe."""

        deployment = self.registry.get_deployed_model(symbol, timeframe, environment)

        if not deployment:
            logger.warning(
                "No deployed model found for %s %s in %s environment",
                symbol,
                timeframe,
                environment
            )
            return None

        timeframe_value = timeframe.value if isinstance(timeframe, Enum) else str(timeframe)

        try:
            timeframe_enum = TimeFrame(timeframe_value)
        except ValueError:
            logger.warning(
                "Unable to resolve timeframe enum for %s; duplicate-signal guard will fallback to symbol-level check",
                timeframe_value
            )
            timeframe_enum = None

        try:
            latest_snapshot = self._prepare_latest_snapshot(symbol, timeframe)
        except ValueError as exc:
            logger.error("Signal generation aborted: %s", exc)
            return None

        model = self._load_model(deployment)

        feature_columns = self._determine_feature_columns(model, latest_snapshot['features'])
        if not feature_columns:
            raise ValueError("No numeric features available for inference")
        inference_values = []
        for column in feature_columns:
            value = latest_snapshot['features'].get(column)
            try:
                inference_values.append(float(value))
            except (TypeError, ValueError):
                inference_values.append(0.0)

        inference_df = pd.DataFrame([inference_values], columns=feature_columns)

        probabilities = model.predict_proba(inference_df)
        probability = float(probabilities[0]) if isinstance(probabilities, (list, np.ndarray, pd.Series)) else float(probabilities)

        side = Side.LONG if probability >= 0.5 else Side.SHORT
        confidence = probability if side == Side.LONG else 1.0 - probability

        atr = float(latest_snapshot['atr'])
        entry_price = float(latest_snapshot['close'])
        volume = float(latest_snapshot['volume'])
        spread_bps = float(latest_snapshot.get('spread_bps', 0.0))

        # Extract volume and ATR trend indicators from features
        features = latest_snapshot['features']
        volume_high = bool(features.get('volume_quantile_90', 0))
        atr_rising = bool(features.get('atr_rising', 0))
        atr_falling = bool(features.get('atr_falling', 0))

        risk_filters = {
            'confidence': confidence >= settings.MIN_CONFIDENCE_THRESHOLD,
            'atr': atr > 0,
            'liquidity': volume >= self.min_volume,
            'spread': spread_bps <= self.max_spread_bps,
            'correlation': True,
            'profit': True,
            'position_limit': True,
            'duplicate': True
        }

        inference_metadata = {
            'probability': probability,
            'confidence': confidence,
            'side': side.value,
            'environment': environment,
            'timestamp': latest_snapshot['timestamp'],
            'timeframe': timeframe_value
        }

        prediction_record = inference_df.copy()
        prediction_record['probability'] = probability
        prediction_record['confidence'] = confidence
        prediction_record['prediction'] = 1 if side == Side.LONG else 0
        prediction_record['side'] = side.value
        prediction_record['timestamp'] = pd.to_datetime(latest_snapshot['timestamp'])

        tracking_metadata = {
            **inference_metadata,
            'risk_profile': risk_profile.value,
            'capital_usd': capital_usd,
            'model_version': deployment.get('version')
        }

        model_id = deployment.get('model_id')

        try:
            self.performance_tracker.log_prediction_batch(
                model_id=model_id or "unknown",
                symbol=symbol,
                timeframe=timeframe,
                predictions=prediction_record,
                metadata=tracking_metadata
            )
        except Exception:
            logger.exception(
                "Failed to log prediction batch for %s %s in %s",
                symbol,
                timeframe,
                environment
            )

        if not all(risk_filters[key] for key in ['confidence', 'atr', 'liquidity', 'spread']):
            failed_filters = [k for k, v in risk_filters.items() if not v]
            logger.info(
                "Signal for %s %s rejected by pre-signal risk filters: %s",
                symbol,
                timeframe,
                {k: v for k, v in risk_filters.items() if not v}
            )
            return SignalInferenceResult(
                signal=None,
                model_info=self._build_model_info(deployment),
                risk_filters=risk_filters,
                inference_metadata=inference_metadata,
                accepted=False,
                rejection_reasons=failed_filters
            )

        duplicate_query = (
            self.db.query(Signal)
            .filter(
                Signal.symbol == symbol,
                Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE]),
                Signal.valid_until > datetime.utcnow()
            )
        )

        if timeframe_enum is not None:
            duplicate_query = duplicate_query.join(
                ModelRecord,
                Signal.model_id == ModelRecord.model_id,
                isouter=True
            ).filter(ModelRecord.timeframe == timeframe_enum)

        existing_active_signal = duplicate_query.order_by(Signal.timestamp.desc()).first()

        if existing_active_signal:
            risk_filters['duplicate'] = False
            failed_filters = [k for k, v in risk_filters.items() if not v]
            logger.info(
                "Signal for %s %s rejected due to existing active signal (%s)",
                symbol,
                timeframe_value,
                existing_active_signal.signal_id
            )
            return SignalInferenceResult(
                signal=None,
                model_info=self._build_model_info(deployment),
                risk_filters=risk_filters,
                inference_metadata=inference_metadata,
                accepted=False,
                rejection_reasons=failed_filters
            )

        max_positions_map = {
            RiskProfile.LOW: settings.LOW_MAX_POSITIONS,
            RiskProfile.MEDIUM: settings.MED_MAX_POSITIONS,
            RiskProfile.HIGH: settings.HIGH_MAX_POSITIONS
        }

        active_positions_query = self.db.query(func.count(Signal.id)).filter(
            Signal.risk_profile == risk_profile,
            Signal.status == SignalStatus.ACTIVE,
            Signal.valid_until > datetime.utcnow()
        )

        if symbol:
            active_positions_query = active_positions_query.filter(Signal.symbol == symbol)

        active_positions = active_positions_query.scalar() or 0
        max_positions_allowed = max_positions_map.get(risk_profile, 0)

        if max_positions_allowed and active_positions >= max_positions_allowed:
            risk_filters['position_limit'] = False
            failed_filters = [k for k, v in risk_filters.items() if not v]
            logger.info(
                "Signal for %s %s rejected due to position limit (%s >= %s) for profile %s",
                symbol,
                timeframe,
                active_positions,
                max_positions_allowed,
                risk_profile.value
            )
            return SignalInferenceResult(
                signal=None,
                model_info=self._build_model_info(deployment),
                risk_filters=risk_filters,
                inference_metadata=inference_metadata,
                accepted=False,
                rejection_reasons=failed_filters
            )

        # Automatic leverage adjustment if enabled
        if settings.AUTO_LEVERAGE:
            try:
                trainer = AutoTrainer(self.db)
                optimal_leverage = trainer.get_optimal_leverage(
                    symbol=symbol,
                    atr=atr,
                    confidence=confidence
                )
                leverage_cap = optimal_leverage
                logger.info(
                    f"Auto-leverage for {symbol}: {leverage_cap}x "
                    f"(confidence={confidence:.3f}, atr={atr:.4f})"
                )
            except Exception as exc:
                logger.warning(f"Auto-leverage calculation failed, using defaults: {exc}")
                leverage_cap = {
                    RiskProfile.LOW: settings.LOW_MAX_LEV,
                    RiskProfile.MEDIUM: settings.MED_MAX_LEV,
                    RiskProfile.HIGH: settings.HIGH_MAX_LEV
                }[risk_profile]
        else:
            leverage_cap = {
                RiskProfile.LOW: settings.LOW_MAX_LEV,
                RiskProfile.MEDIUM: settings.MED_MAX_LEV,
                RiskProfile.HIGH: settings.HIGH_MAX_LEV
            }[risk_profile]

        # Detect volatility regime from features
        # Create a DataFrame from features for regime detection
        features_df = pd.DataFrame([latest_snapshot['features']])
        volatility_regime = self._detect_volatility_regime(features_df)

        signal = self.signal_generator.generate_signal(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            atr=atr,
            risk_profile=risk_profile,
            capital_usd=capital_usd,
            confidence=confidence,
            timestamp=latest_snapshot['timestamp'],
            leverage_cap=leverage_cap,
            volatility_regime=volatility_regime,
            volume_high=volume_high,
            atr_rising=atr_rising,
            atr_falling=atr_falling
        )

        if not signal:
            risk_filters['profit'] = False
            failed_filters = [k for k, v in risk_filters.items() if not v]
            logger.info("Signal for %s %s rejected by profit filter", symbol, timeframe)
            return SignalInferenceResult(
                signal=None,
                model_info=self._build_model_info(deployment),
                risk_filters=risk_filters,
                inference_metadata=inference_metadata,
                accepted=False,
                rejection_reasons=failed_filters
            )

        risk_filters['profit'] = True

        signal['model_id'] = deployment.get('model_id')
        signal['model_version'] = deployment.get('version')
        signal['timeframe'] = timeframe_value

        return SignalInferenceResult(
            signal=signal,
            model_info=self._build_model_info(deployment),
            risk_filters=risk_filters,
            inference_metadata=inference_metadata,
            accepted=True
        )

    # ------------------------------------------------------------------
    # Historical helpers
    # ------------------------------------------------------------------

    def generate_signals_for_period(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Generate signals for each bar between the supplied dates."""

        timeframe_value = timeframe.value if isinstance(timeframe, Enum) else str(timeframe)

        ohlcv_rows = (
            self.db.query(OHLCV)
            .filter(
                and_(
                    OHLCV.symbol == symbol,
                    OHLCV.timeframe == timeframe_value,
                    OHLCV.timestamp >= start_date,
                    OHLCV.timestamp <= end_date,
                )
            )
            .order_by(OHLCV.timestamp.asc())
            .all()
        )

        if not ohlcv_rows:
            logger.warning(
                "No OHLCV rows available for %s %s between %s and %s",
                symbol,
                timeframe_value,
                start_date,
                end_date,
            )
            return []

        df = pd.DataFrame(
            [
                {
                    'timestamp': row.timestamp,
                    'open': row.open,
                    'high': row.high,
                    'low': row.low,
                    'close': row.close,
                    'volume': row.volume,
                }
                for row in ohlcv_rows
            ]
        )

        features_df = self.feature_engineering.compute_all_features(df)

        # Try to get deployed model first, fallback to best model
        registry_entry = self.registry.get_deployed_model(symbol, timeframe_value, 'production')
        if not registry_entry:
            logger.info("No deployed model for %s %s, using best available model", symbol, timeframe_value)
            registry_entry = self.registry.get_best_model(symbol, timeframe_value)

        if not registry_entry:
            logger.warning("No registered models for %s %s", symbol, timeframe_value)
            return []

        model = self._load_model(registry_entry)
        feature_columns = self._determine_feature_columns(model, features_df.iloc[-1])

        if not feature_columns:
            logger.warning("Model lacks feature metadata; falling back to numeric columns")
            feature_columns = [
                col for col in features_df.columns
                if pd.api.types.is_numeric_dtype(features_df[col]) and col != 'timestamp'
            ]

        feature_matrix = features_df[feature_columns].copy()
        feature_matrix = feature_matrix.ffill().bfill().fillna(0)

        raw_probabilities = model.predict_proba(feature_matrix)
        prob_array = np.asarray(raw_probabilities)
        if prob_array.ndim == 2:
            prob_array = prob_array[:, -1]
        elif prob_array.ndim == 0:
            prob_array = np.full(len(feature_matrix), float(prob_array))

        result_signals: List[Dict[str, Any]] = []
        for idx, row in features_df.iterrows():
            if idx >= len(prob_array):
                break
            probability = float(prob_array[idx])
            side = Side.LONG if probability >= 0.5 else Side.SHORT
            confidence = probability if side == Side.LONG else 1.0 - probability

            entry_price = float(row['close'])
            atr_value = float(row.get('atr_14') or 0.0)

            # For historical signals, use normal volatility regime (can be enhanced later)
            volatility_regime = 'normal'

            signal_payload = self.signal_generator.generate_signal(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                atr=atr_value,
                risk_profile=RiskProfile.MEDIUM,
                capital_usd=100.0,
                confidence=confidence,
                timestamp=row['timestamp'],
                leverage_cap=settings.MED_MAX_LEV,
                enforce_risk_filters=False,
                volatility_regime=volatility_regime
            )

            if not signal_payload:
                continue

            signal_payload['probability'] = probability
            signal_payload['confidence'] = confidence
            signal_payload['model_id'] = registry_entry.get('model_id')
            signal_payload['model_version'] = registry_entry.get('version')
            signal_payload['timeframe'] = timeframe_value

            result_signals.append(signal_payload)

        return result_signals

    def _prepare_latest_snapshot(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Fetch latest OHLCV data and compute features/ATR."""

        timeframe_value = timeframe.value if isinstance(timeframe, Enum) else str(timeframe)

        ohlcv_rows = (
            self.db.query(OHLCV)
            .filter(
                and_(
                    OHLCV.symbol == symbol,
                    OHLCV.timeframe == timeframe_value,
                    OHLCV.timestamp != None
                )
            )
            .order_by(OHLCV.timestamp.desc())
            .limit(self.lookback_bars)
            .all()
        )

        if not ohlcv_rows:
            raise ValueError(f"No OHLCV data available for {symbol} {timeframe}")

        ohlcv_rows = list(reversed(ohlcv_rows))

        df = pd.DataFrame([
            {
                'timestamp': row.timestamp,
                'open': row.open,
                'high': row.high,
                'low': row.low,
                'close': row.close,
                'volume': row.volume
            }
            for row in ohlcv_rows
        ])

        market_metrics_row = (
            self.db.query(MarketMetrics)
            .filter(MarketMetrics.symbol == symbol)
            .order_by(MarketMetrics.timestamp.desc())
            .first()
        )

        market_metrics_df = pd.DataFrame([
            {
                'timestamp': market_metrics_row.timestamp,
                'funding_rate': market_metrics_row.funding_rate,
                'open_interest': market_metrics_row.open_interest,
                'spread_bps': market_metrics_row.spread_bps,
                'depth_imbalance': market_metrics_row.depth_imbalance,
                'realized_volatility': market_metrics_row.realized_volatility
            }
        ]) if market_metrics_row else pd.DataFrame()

        features_df = self.feature_engineering.compute_all_features(df, market_metrics=market_metrics_df)
        features_df = features_df.ffill().bfill()

        latest_row = features_df.iloc[-1]

        atr = latest_row.get('atr_14')
        if pd.isna(atr):
            raise ValueError("ATR calculation returned NaN")

        snapshot = {
            'features': latest_row,
            'atr': atr,
            'close': latest_row.get('close'),
            'volume': latest_row.get('volume', 0.0),
            'spread_bps': latest_row.get('spread_bps', market_metrics_row.spread_bps if market_metrics_row else 0.0),
            'timestamp': latest_row.get('timestamp') or df['timestamp'].iloc[-1]
        }

        if snapshot['close'] is None:
            snapshot['close'] = df['close'].iloc[-1]

        return snapshot

    def _load_model(self, deployment: Dict[str, Any]):
        """Instantiate and load model from deployment path."""

        model_path = deployment.get('path')
        if not model_path:
            raise ValueError("Deployment missing model path")

        model = self.model_factory()
        model.load(model_path)
        return model

    @staticmethod
    def _build_model_info(deployment: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'model_id': deployment.get('model_id'),
            'version': deployment.get('version'),
            'path': deployment.get('path'),
            'symbol': deployment.get('symbol'),
            'timeframe': deployment.get('timeframe')
        }

    @staticmethod
    def _determine_feature_columns(model: Any, latest_row: pd.Series) -> list:
        """Determine feature columns expected by the model."""

        if hasattr(model, 'feature_names') and model.feature_names:
            return list(model.feature_names)

        excluded_columns = {
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'symbol', 'timeframe'
        }

        numeric_columns = []
        for col in latest_row.index:
            if col in excluded_columns:
                continue
            value = latest_row[col]
            if isinstance(value, (int, float, np.number)) and not pd.isna(value):
                numeric_columns.append(col)

        return numeric_columns

    def _calculate_kelly_leverage(
        self,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        probability: float,
        max_leverage: float
    ) -> float:
        """
        Calculate optimal leverage using Kelly Criterion.

        Kelly formula: f* = (p * b - (1 - p)) / b
        Where:
            p = probability of winning
            b = ratio of TP to SL (reward/risk ratio)
            f* = optimal fraction of capital to risk

        Args:
            entry_price: Entry price
            sl_price: Stop loss price
            tp_price: Take profit price (main target)
            probability: Probability of success (0.0-1.0)
            max_leverage: Maximum allowed leverage

        Returns:
            Optimal leverage (capped at max_leverage)
        """
        # Calculate TP and SL percentages
        sl_pct = abs(entry_price - sl_price) / entry_price
        tp_pct = abs(tp_price - entry_price) / entry_price

        if sl_pct == 0:
            logger.warning("SL distance is zero, returning minimum leverage")
            return 1.0

        # Calculate b (reward/risk ratio)
        b = tp_pct / sl_pct

        # Kelly Criterion formula
        # f_star = (p * b - (1 - p)) / b
        p = probability
        f_star = (p * b - (1.0 - p)) / b

        # Convert to leverage
        # f_star is the fraction of capital to risk, but we need to be conservative
        # Apply Kelly fraction (typically use half-Kelly or quarter-Kelly)
        kelly_fraction = 0.25  # Conservative: use quarter-Kelly
        optimal_fraction = max(0.0, f_star * kelly_fraction)

        # Convert fraction to leverage
        if sl_pct > 0:
            kelly_leverage = optimal_fraction / sl_pct
        else:
            kelly_leverage = 1.0

        # Ensure minimum of 1x and cap at max_leverage
        kelly_leverage = max(1.0, min(kelly_leverage, max_leverage))

        return kelly_leverage

    def _calculate_tp_sl(
        self,
        entry_price: float,
        atr: float,
        side: Side,
        confidence: float = 0.7,
        volatility_regime: str = 'normal',
        volume_high: bool = False,
        atr_rising: bool = False,
        atr_falling: bool = False
    ) -> Tuple[list, float]:
        """
        Calculate adaptive TP levels and SL based on market conditions.

        Args:
            entry_price: Entry price
            atr: Current ATR value
            side: LONG or SHORT
            confidence: Model confidence (0.0-1.0)
            volatility_regime: 'low', 'normal', or 'high'
            volume_high: Whether volume is high relative to average
            atr_rising: Whether ATR is rising (trending market)
            atr_falling: Whether ATR is falling (consolidating market)

        Returns:
            (tp_levels, sl_price)
        """
        # Adaptive SL based on volatility
        if volatility_regime == 'high':
            atr_multiplier_sl = 1.5  # Wider SL in high volatility
        elif volatility_regime == 'low':
            atr_multiplier_sl = 0.8  # Tighter SL in low volatility
        else:
            atr_multiplier_sl = 1.0  # Normal SL

        # Adaptive TP based on confidence and volatility
        # Higher confidence = aim for TP2/TP3, lower confidence = focus on TP1
        if confidence >= 0.7:
            # High confidence: aggressive targets
            if volatility_regime == 'high':
                tp_mult = [3.0, 5.0, 8.0]  # Higher multiples in trending volatile markets
            else:
                tp_mult = [2.5, 4.5, 7.0]  # Normal aggressive targets
        elif confidence >= 0.65:
            # Medium-high confidence: balanced targets
            tp_mult = [2.0, 3.5, 6.0]  # Standard multipliers
        else:
            # Lower confidence: conservative targets
            tp_mult = [1.5, 2.5, 4.0]  # Quick profits, lower risk

        # Volume-based TP adjustment
        # High volume + rising ATR = trending market, increase TP targets
        if volume_high and atr_rising:
            tp_mult = [min(m * 1.3, 6.0) for m in tp_mult]  # Increase by 30%, cap at 6.0
            logger.debug(f"Volume-based TP adjustment: high volume + rising ATR -> increased targets")
        # ATR falling + high confidence = tighter targets for quick profits
        elif atr_falling and confidence >= 0.7:
            tp_mult = [max(m * 0.7, 2.0) for m in tp_mult]  # Decrease by 30%, minimum 2.0
            logger.debug(f"Volume-based TP adjustment: falling ATR + high confidence -> tighter targets")

        if side == Side.LONG:
            sl_price = entry_price - (atr * atr_multiplier_sl)
            tp1 = entry_price + (atr * tp_mult[0])
            tp2 = entry_price + (atr * tp_mult[1])
            tp3 = entry_price + (atr * tp_mult[2])
        else:  # SHORT
            sl_price = entry_price + (atr * atr_multiplier_sl)
            tp1 = entry_price - (atr * tp_mult[0])
            tp2 = entry_price - (atr * tp_mult[1])
            tp3 = entry_price - (atr * tp_mult[2])

        return [tp1, tp2, tp3], sl_price

    def _calculate_position_size(
        self,
        entry_price: float,
        sl_price: float,
        risk_profile: RiskProfile,
        capital_usd: float,
        leverage_cap: Optional[int] = None,
        confidence: float = 0.7,
        tp_levels: Optional[list] = None,
        use_kelly: bool = True
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

        # Calculate Kelly Criterion optimal leverage if enabled
        if use_kelly and tp_levels and len(tp_levels) >= 2:
            kelly_leverage = self._calculate_kelly_leverage(
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_levels[1],  # Use TP2 as main target
                probability=confidence,
                max_leverage=max_leverage
            )
            # Use Kelly as additional constraint
            max_leverage = min(max_leverage, kelly_leverage)
            logger.debug(f"Kelly Criterion leverage: {kelly_leverage:.2f}x (capped at {max_leverage:.2f}x)")

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
        entry_fee_usd = position_size_usd * (self.signal_generator.maker_fee_bps / 10000)
        entry_slippage_usd = position_size_usd * (self.signal_generator.slippage_bps / 10000) * 0.5  # Reduced for maker

        # Exit costs (assume 3 exits: TP1, TP2, TP3 - taker orders)
        exit_size_total = position_size_usd
        exit_fee_usd = exit_size_total * (self.signal_generator.taker_fee_bps / 10000)
        exit_slippage_usd = exit_size_total * (self.signal_generator.slippage_bps / 10000)

        # Funding cost (assume average hold time = 12 hours)
        avg_hold_hours = 12
        funding_cost_usd = position_size_usd * (self.signal_generator.funding_rate_hourly_bps / 10000) * avg_hold_hours

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
        trailing_distance = atr * 0.3  # Tighter trailing (was 0.5)

        if side == Side.LONG:
            new_sl = max(current_sl, entry_price + trailing_distance)
            new_sl = max(new_sl, current_price - atr * 1.0)  # Trail below current price
        else:
            new_sl = min(current_sl, entry_price - trailing_distance)
            new_sl = min(new_sl, current_price + atr * 1.0)

        return new_sl

    def _detect_volatility_regime(self, df: pd.DataFrame) -> str:
        """
        Detect volatility regime from features.
        
        Returns:
            'low', 'normal', or 'high'
        """
        if 'regime_volatility' in df.columns:
            # Use existing regime detection from features
            regime_val = df['regime_volatility'].iloc[-1]
            if regime_val < 1:
                return 'low'
            elif regime_val > 2:
                return 'high'
            else:
                return 'normal'
        
        # Fallback: use ATR percentile
        if 'atr_14' in df.columns:
            atr = df['atr_14'].iloc[-1]
            atr_percentile = (df['atr_14'].tail(100) < atr).mean()
            
            if atr_percentile < 0.3:
                return 'low'
            elif atr_percentile > 0.7:
                return 'high'
            else:
                return 'normal'
        
        return 'normal'  # Default
