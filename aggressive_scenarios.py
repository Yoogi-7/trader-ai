#!/usr/bin/env python3
"""
Agresywne scenariusze tradingowe - wyższe ryzyko, wyższe zyski.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from capital_simulation import (
    simulate_capital_growth,
    plot_simulation,
    print_daily_projection,
    TradingStats
)
import matplotlib.pyplot as plt


def scenario_aggressive_5pct_risk():
    """5% ryzyko na trade - agresywny trading"""
    print("\n" + "="*80)
    print("SCENARIUSZ AGRESYWNY: 5% RYZYKO NA TRADE")
    print("="*80)

    stats = TradingStats(
        win_rate=0.62,
        avg_win_pct=3.2,
        avg_loss_pct=1.25,
        trades_per_day=2.5,  # więcej tradów
        profit_factor=2.8,
        max_drawdown_pct=25.0
    )

    print("\nParametry:")
    print(f"  Win rate: {stats.win_rate*100:.1f}%")
    print(f"  Średni zysk: {stats.avg_win_pct:.2f}%")
    print(f"  Średnia strata: {stats.avg_loss_pct:.2f}%")
    print(f"  Trady dziennie: {stats.trades_per_day:.1f}")
    print(f"  Ryzyko na trade: 5% kapitału")
    print(f"  Max drawdown: {stats.max_drawdown_pct:.1f}%")

    results = simulate_capital_growth(
        initial_capital=100.0,
        days=30,
        stats=stats,
        risk_per_trade=0.05,  # 5% zamiast 2%
        compound=True,
        num_simulations=1000
    )

    print(f"\nPo 30 dniach:")
    print(f"  Średni kapitał: ${results['mean_final']:.2f} ({results['mean_return_pct']:+.2f}%)")
    print(f"  Mediana: ${results['median_final']:.2f} ({results['median_return_pct']:+.2f}%)")
    print(f"  Zakres: ${results['min_final']:.2f} - ${results['max_final']:.2f}")
    print(f"  Prawdopodobieństwo zysku: {results['probability_profit']:.1f}%")

    return results


def scenario_high_frequency():
    """Wysoka częstotliwość tradów - 5-8 tradów dziennie"""
    print("\n" + "="*80)
    print("SCENARIUSZ HIGH FREQUENCY: 5-8 TRADÓW DZIENNIE")
    print("="*80)

    stats = TradingStats(
        win_rate=0.58,  # niższy win rate przy więcej tradach
        avg_win_pct=2.8,  # mniejsze zyski ale częściej
        avg_loss_pct=1.3,
        trades_per_day=6.0,  # dużo więcej tradów!
        profit_factor=2.2,
        max_drawdown_pct=20.0
    )

    print("\nParametry:")
    print(f"  Win rate: {stats.win_rate*100:.1f}%")
    print(f"  Średni zysk: {stats.avg_win_pct:.2f}%")
    print(f"  Średnia strata: {stats.avg_loss_pct:.2f}%")
    print(f"  Trady dziennie: {stats.trades_per_day:.1f}")
    print(f"  Ryzyko na trade: 3% kapitału")

    results = simulate_capital_growth(
        initial_capital=100.0,
        days=30,
        stats=stats,
        risk_per_trade=0.03,
        compound=True,
        num_simulations=1000
    )

    print(f"\nPo 30 dniach:")
    print(f"  Średni kapitał: ${results['mean_final']:.2f} ({results['mean_return_pct']:+.2f}%)")
    print(f"  Mediana: ${results['median_final']:.2f} ({results['median_return_pct']:+.2f}%)")
    print(f"  Zakres: ${results['min_final']:.2f} - ${results['max_final']:.2f}")
    print(f"  Prawdopodobieństwo zysku: {results['probability_profit']:.1f}%")

    return results


def scenario_higher_leverage():
    """Wyższe zyski przez lepsze wykorzystanie leverage (20-30x)"""
    print("\n" + "="*80)
    print("SCENARIUSZ WYŻSZY LEVERAGE: 20-30x (Większe TP/SL)")
    print("="*80)

    stats = TradingStats(
        win_rate=0.60,
        avg_win_pct=5.5,  # wyższe zyski z większym leverage
        avg_loss_pct=2.2,  # wyższe straty też
        trades_per_day=2.0,
        profit_factor=2.5,
        max_drawdown_pct=30.0
    )

    print("\nParametry:")
    print(f"  Win rate: {stats.win_rate*100:.1f}%")
    print(f"  Średni zysk: {stats.avg_win_pct:.2f}%")
    print(f"  Średnia strata: {stats.avg_loss_pct:.2f}%")
    print(f"  Trady dziennie: {stats.trades_per_day:.1f}")
    print(f"  Ryzyko na trade: 3% kapitału")
    print(f"  Leverage: 20-30x")

    results = simulate_capital_growth(
        initial_capital=100.0,
        days=30,
        stats=stats,
        risk_per_trade=0.03,
        compound=True,
        num_simulations=1000
    )

    print(f"\nPo 30 dniach:")
    print(f"  Średni kapitał: ${results['mean_final']:.2f} ({results['mean_return_pct']:+.2f}%)")
    print(f"  Mediana: ${results['median_final']:.2f} ({results['median_return_pct']:+.2f}%)")
    print(f"  Zakres: ${results['min_final']:.2f} - ${results['max_final']:.2f}")
    print(f"  Prawdopodobieństwo zysku: {results['probability_profit']:.1f}%")

    return results


def scenario_best_realistic():
    """Najlepszy realistyczny scenariusz - zbalansowany"""
    print("\n" + "="*80)
    print("SCENARIUSZ OPTIMAL: Najlepszy balans ryzyko/zysk")
    print("="*80)

    stats = TradingStats(
        win_rate=0.65,  # dobry win rate
        avg_win_pct=4.5,  # przyzwoite zyski
        avg_loss_pct=1.8,  # kontrolowane straty
        trades_per_day=3.5,  # umiarkowanie dużo tradów
        profit_factor=3.2,
        max_drawdown_pct=22.0
    )

    print("\nParametry:")
    print(f"  Win rate: {stats.win_rate*100:.1f}%")
    print(f"  Średni zysk: {stats.avg_win_pct:.2f}%")
    print(f"  Średnia strata: {stats.avg_loss_pct:.2f}%")
    print(f"  Trady dziennie: {stats.trades_per_day:.1f}")
    print(f"  Ryzyko na trade: 3.5% kapitału")
    print(f"  Profit factor: {stats.profit_factor:.2f}")

    results = simulate_capital_growth(
        initial_capital=100.0,
        days=30,
        stats=stats,
        risk_per_trade=0.035,  # 3.5%
        compound=True,
        num_simulations=1000
    )

    print(f"\nPo 30 dniach:")
    print(f"  Średni kapitał: ${results['mean_final']:.2f} ({results['mean_return_pct']:+.2f}%)")
    print(f"  Mediana: ${results['median_final']:.2f} ({results['median_return_pct']:+.2f}%)")
    print(f"  Zakres: ${results['min_final']:.2f} - ${results['max_final']:.2f}")
    print(f"  Prawdopodobieństwo zysku: {results['probability_profit']:.1f}%")

    print_daily_projection(results)
    plot_simulation(results, save_path='capital_simulation_optimal.png')

    return results


def scenario_yolo():
    """YOLO mode - maksymalne ryzyko, maksymalne zyski"""
    print("\n" + "="*80)
    print("SCENARIUSZ YOLO: 10% RYZYKO NA TRADE 🚀")
    print("="*80)
    print("⚠️  BARDZO WYSOKIE RYZYKO - tylko dla doświadczonych")

    stats = TradingStats(
        win_rate=0.62,
        avg_win_pct=6.0,  # duże zyski
        avg_loss_pct=2.5,  # duże straty
        trades_per_day=3.0,
        profit_factor=2.8,
        max_drawdown_pct=40.0  # możliwy duży drawdown!
    )

    print("\nParametry:")
    print(f"  Win rate: {stats.win_rate*100:.1f}%")
    print(f"  Średni zysk: {stats.avg_win_pct:.2f}%")
    print(f"  Średnia strata: {stats.avg_loss_pct:.2f}%")
    print(f"  Trady dziennie: {stats.trades_per_day:.1f}")
    print(f"  Ryzyko na trade: 10% kapitału ⚠️")
    print(f"  Max drawdown: {stats.max_drawdown_pct:.1f}%")

    results = simulate_capital_growth(
        initial_capital=100.0,
        days=30,
        stats=stats,
        risk_per_trade=0.10,  # 10% - YOLO!
        compound=True,
        num_simulations=1000
    )

    print(f"\nPo 30 dniach:")
    print(f"  Średni kapitał: ${results['mean_final']:.2f} ({results['mean_return_pct']:+.2f}%)")
    print(f"  Mediana: ${results['median_final']:.2f} ({results['median_return_pct']:+.2f}%)")
    print(f"  Zakres: ${results['min_final']:.2f} - ${results['max_final']:.2f}")
    print(f"  Prawdopodobieństwo zysku: {results['probability_profit']:.1f}%")

    return results


def main():
    print("\n" + "="*80)
    print("AGRESYWNE SCENARIUSZE - WYŻSZE RYZYKO, WYŻSZE ZYSKI")
    print("="*80)

    conservative_2pct = {
        'name': 'Konserwatywny (2%)',
        'mean_return_pct': 1.65,
        'median_final': 101.63,
        'percentile_90': 102.21
    }

    aggressive_5pct = scenario_aggressive_5pct_risk()
    high_freq = scenario_high_frequency()
    higher_lev = scenario_higher_leverage()
    optimal = scenario_best_realistic()
    yolo = scenario_yolo()

    # Porównanie
    print("\n" + "="*80)
    print("PORÓWNANIE WSZYSTKICH SCENARIUSZY")
    print("="*80)
    print(f"{'Scenariusz':<30} {'Ryzyko/trade':<15} {'Średni zwrot':<15} {'90 percentyl':<15}")
    print("-"*80)
    print(f"{'Konserwatywny (baseline)':<30} {'2%':<15} {conservative_2pct['mean_return_pct']:>13.2f}% ${conservative_2pct['percentile_90']:>13.2f}")
    print(f"{'Agresywny 5%':<30} {'5%':<15} {aggressive_5pct['mean_return_pct']:>13.2f}% ${aggressive_5pct['percentile_90']:>13.2f}")
    print(f"{'High Frequency':<30} {'3%':<15} {high_freq['mean_return_pct']:>13.2f}% ${high_freq['percentile_90']:>13.2f}")
    print(f"{'Wyższy Leverage':<30} {'3%':<15} {higher_lev['mean_return_pct']:>13.2f}% ${higher_lev['percentile_90']:>13.2f}")
    print(f"{'Optimal (recommended)':<30} {'3.5%':<15} {optimal['mean_return_pct']:>13.2f}% ${optimal['percentile_90']:>13.2f}")
    print(f"{'YOLO 10%':<30} {'10%':<15} {yolo['mean_return_pct']:>13.2f}% ${yolo['percentile_90']:>13.2f}")
    print("="*80)

    # Rekomendacje
    print("\n" + "="*80)
    print("REKOMENDACJE")
    print("="*80)
    print(f"""
1. DLA POCZĄTKUJĄCYCH:
   - Ryzyko: 2-3% na trade
   - Oczekiwany zwrot: {conservative_2pct['mean_return_pct']:.1f}-{aggressive_5pct['mean_return_pct']:.1f}% miesięcznie
   - Max drawdown: ~15%

2. DLA ŚREDNIOZAAWANSOWANYCH (RECOMMENDED):
   - Ryzyko: 3-5% na trade
   - Oczekiwany zwrot: {optimal['mean_return_pct']:.1f}% miesięcznie
   - Max drawdown: ~22%
   - Leverage: 15-20x

   ⭐ OPTIMAL: {optimal['mean_return_pct']:.1f}% miesięcznie = {optimal['mean_return_pct']*12:.1f}% rocznie

3. DLA ZAAWANSOWANYCH:
   - Ryzyko: 5-10% na trade
   - Oczekiwany zwrot: {aggressive_5pct['mean_return_pct']:.1f}-{yolo['mean_return_pct']:.1f}% miesięcznie
   - Max drawdown: ~30-40%
   - Leverage: 20-50x

4. JAK POPRAWIĆ WYNIKI?

   a) ZWIĘKSZ RYZYKO NA TRADE:
      - 2% → 3.5% = +{optimal['mean_return_pct']-conservative_2pct['mean_return_pct']:.1f}% zwrotu
      - 2% → 5% = +{aggressive_5pct['mean_return_pct']-conservative_2pct['mean_return_pct']:.1f}% zwrotu

   b) ZWIĘKSZ LICZBĘ TRADÓW:
      - 1.8/dzień → 3.5/dzień = więcej okazji
      - Generuj sygnały dla większej liczby par
      - Użyj niższych timeframe'ów (5m, 15m)

   c) ZWIĘKSZ LEVERAGE:
      - 10x → 20-30x = większe TP (5-7% zamiast 3%)
      - Ostrożnie! Większe ryzyko likwidacji

   d) OPTYMALIZUJ TP/SL:
      - Zwiększ mnożniki ATR dla TP (2x, 3x, 5x)
      - Zmniejsz SL dla lepszego R:R

   e) DODAJ WIĘCEJ SYMBOLI:
      - BTC, ETH, BNB, SOL, DOGE, XRP, ADA, MATIC...
      - Więcej symboli = więcej sygnałów dziennie

5. SKALOWANIE KAPITAŁU (OPTIMAL {optimal['mean_return_pct']:.1f}%/miesiąc):

   Kapitał początkowy → Po 1 miesiącu → Po 3 miesiącach → Po 6 miesiącach → Po roku
   $100  → ${optimal['mean_final']:.0f}  → ${100 * ((optimal['mean_final']/100)**3):.0f}  → ${100 * ((optimal['mean_final']/100)**6):.0f}  → ${100 * ((optimal['mean_final']/100)**12):.0f}
   $1000 → ${optimal['mean_final']*10:.0f} → ${1000 * ((optimal['mean_final']/100)**3):.0f} → ${1000 * ((optimal['mean_final']/100)**6):.0f} → ${1000 * ((optimal['mean_final']/100)**12):.0f}

6. KLUCZOWE PARAMETRY DO ZMIANY W KODZIE:

   Plik: apps/api/config.py

   # Risk per trade
   MED_RISK_PER_TRADE = 0.035  # 3.5% zamiast 0.02
   HIGH_RISK_PER_TRADE = 0.05  # 5% zamiast 0.03

   # Leverage
   MED_MAX_LEV = 20  # zamiast 10
   HIGH_MAX_LEV = 30  # zamiast 15

   # TP multipliers (apps/ml/signal_engine.py:163-166)
   atr_multiplier_tp1 = 2.0  # zamiast 1.5
   atr_multiplier_tp2 = 3.5  # zamiast 2.5
   atr_multiplier_tp3 = 6.0  # zamiast 4.0

   # SL multiplier
   atr_multiplier_sl = 1.0  # zamiast 1.2 (ciasniejszy SL)

""")

    print("\n✅ Analiza zakończona!")
    print("Zapisano wykres: capital_simulation_optimal.png")
    print("="*80)


if __name__ == "__main__":
    main()
