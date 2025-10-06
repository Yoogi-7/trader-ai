#!/usr/bin/env python3
"""
Symulacja wzrostu kapitału na podstawie parametrów backtestingowych.
Pokazuje jak kapitał początkowy 100$ może się zmieniać w ciągu 30 dni.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import matplotlib.pyplot as plt
from dataclasses import dataclass


@dataclass
class TradingStats:
    """Statystyki tradingowe z backtestów"""
    win_rate: float  # np. 0.65 = 65%
    avg_win_pct: float  # średni zysk w % (np. 3.5)
    avg_loss_pct: float  # średnia strata w % (np. -1.2)
    trades_per_day: float  # średnia liczba tradów dziennie
    profit_factor: float  # stosunek zysków do strat
    max_drawdown_pct: float  # maksymalny drawdown w %


def simulate_capital_growth(
    initial_capital: float,
    days: int,
    stats: TradingStats,
    risk_per_trade: float = 0.02,  # 2% kapitału na trade
    compound: bool = True,
    num_simulations: int = 1000
) -> Dict:
    """
    Symulacja Monte Carlo wzrostu kapitału.

    Args:
        initial_capital: Kapitał początkowy (np. 100 USD)
        days: Liczba dni symulacji (np. 30)
        stats: Statystyki tradingowe
        risk_per_trade: Procent kapitału ryzykowany na trade
        compound: Czy kapitalizować zyski
        num_simulations: Liczba symulacji Monte Carlo

    Returns:
        Dict z wynikami symulacji
    """

    all_paths = []
    final_capitals = []

    for sim in range(num_simulations):
        capital = initial_capital
        daily_capitals = [capital]

        for day in range(days):
            # Liczba tradów tego dnia (rozkład Poissona)
            num_trades = np.random.poisson(stats.trades_per_day)

            day_start_capital = capital

            for trade in range(num_trades):
                # Czy trade wygrywa?
                is_winner = np.random.random() < stats.win_rate

                if compound:
                    position_size = capital * risk_per_trade
                else:
                    position_size = initial_capital * risk_per_trade

                if is_winner:
                    # Zysk z rozkładu normalnego wokół średniego zysku
                    win_pct = np.random.normal(stats.avg_win_pct, stats.avg_win_pct * 0.3)
                    win_pct = max(0, win_pct)  # nie może być ujemny
                    profit = position_size * (win_pct / 100)
                    capital += profit
                else:
                    # Strata z rozkładu normalnego wokół średniej straty
                    loss_pct = np.random.normal(abs(stats.avg_loss_pct), abs(stats.avg_loss_pct) * 0.3)
                    loss_pct = max(0, loss_pct)  # wartość bezwzględna
                    loss = position_size * (loss_pct / 100)
                    capital -= loss

                # Zabezpieczenie przed ujemnym kapitałem
                capital = max(0.01, capital)

            daily_capitals.append(capital)

        all_paths.append(daily_capitals)
        final_capitals.append(capital)

    # Konwersja do DataFrame
    paths_df = pd.DataFrame(all_paths).T

    # Statystyki
    results = {
        'initial_capital': initial_capital,
        'days': days,
        'num_simulations': num_simulations,
        'paths': paths_df,
        'final_capitals': final_capitals,
        'mean_final': np.mean(final_capitals),
        'median_final': np.median(final_capitals),
        'std_final': np.std(final_capitals),
        'min_final': np.min(final_capitals),
        'max_final': np.max(final_capitals),
        'percentile_10': np.percentile(final_capitals, 10),
        'percentile_25': np.percentile(final_capitals, 25),
        'percentile_75': np.percentile(final_capitals, 75),
        'percentile_90': np.percentile(final_capitals, 90),
        'probability_profit': np.mean(np.array(final_capitals) > initial_capital) * 100,
        'probability_loss': np.mean(np.array(final_capitals) < initial_capital) * 100,
        'mean_return_pct': ((np.mean(final_capitals) - initial_capital) / initial_capital) * 100,
        'median_return_pct': ((np.median(final_capitals) - initial_capital) / initial_capital) * 100,
    }

    return results


def plot_simulation(results: Dict, save_path: str = None):
    """Wizualizacja wyników symulacji"""

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # 1. Wszystkie ścieżki kapitału
    ax1 = axes[0, 0]
    paths_df = results['paths']

    # Rysuj próbkę ścieżek (nie wszystkie, żeby było czytelne)
    sample_size = min(100, paths_df.shape[1])
    sample_cols = np.random.choice(paths_df.columns, sample_size, replace=False)

    for col in sample_cols:
        ax1.plot(paths_df[col], alpha=0.1, color='blue')

    # Dodaj średnią, medianę i percentyle
    ax1.plot(paths_df.mean(axis=1), color='red', linewidth=2, label='Średnia')
    ax1.plot(paths_df.median(axis=1), color='green', linewidth=2, label='Mediana')
    ax1.fill_between(
        range(len(paths_df)),
        paths_df.quantile(0.1, axis=1),
        paths_df.quantile(0.9, axis=1),
        alpha=0.2,
        color='orange',
        label='10-90 percentyl'
    )

    ax1.axhline(y=results['initial_capital'], color='black', linestyle='--', label='Kapitał początkowy')
    ax1.set_xlabel('Dzień')
    ax1.set_ylabel('Kapitał (USD)')
    ax1.set_title('Symulacja wzrostu kapitału (Monte Carlo)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Histogram końcowych kapitałów
    ax2 = axes[0, 1]
    final_capitals = results['final_capitals']
    ax2.hist(final_capitals, bins=50, alpha=0.7, color='blue', edgecolor='black')
    ax2.axvline(results['mean_final'], color='red', linestyle='--', linewidth=2, label=f"Średnia: ${results['mean_final']:.2f}")
    ax2.axvline(results['median_final'], color='green', linestyle='--', linewidth=2, label=f"Mediana: ${results['median_final']:.2f}")
    ax2.axvline(results['initial_capital'], color='black', linestyle='--', linewidth=2, label=f"Początek: ${results['initial_capital']:.2f}")
    ax2.set_xlabel('Końcowy kapitał (USD)')
    ax2.set_ylabel('Liczba symulacji')
    ax2.set_title('Rozkład końcowych kapitałów')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. Box plot dzień po dniu
    ax3 = axes[1, 0]

    # Wybierz co 5 dzień dla czytelności
    days_to_plot = range(0, len(paths_df), max(1, len(paths_df) // 10))
    box_data = [paths_df.iloc[day].values for day in days_to_plot]

    bp = ax3.boxplot(box_data, positions=list(days_to_plot), widths=2)
    ax3.axhline(y=results['initial_capital'], color='black', linestyle='--', label='Kapitał początkowy')
    ax3.set_xlabel('Dzień')
    ax3.set_ylabel('Kapitał (USD)')
    ax3.set_title('Rozkład kapitału w czasie (Box plot)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. Tabela statystyk
    ax4 = axes[1, 1]
    ax4.axis('off')

    stats_text = f"""
    STATYSTYKI SYMULACJI
    {'='*40}

    Kapitał początkowy: ${results['initial_capital']:.2f}
    Liczba dni: {results['days']}
    Liczba symulacji: {results['num_simulations']}

    WYNIKI KOŃCOWE:
    Średnia: ${results['mean_final']:.2f} ({results['mean_return_pct']:+.2f}%)
    Mediana: ${results['median_final']:.2f} ({results['median_return_pct']:+.2f}%)
    Odch. std: ${results['std_final']:.2f}

    ZAKRES:
    Minimum: ${results['min_final']:.2f}
    10 percentyl: ${results['percentile_10']:.2f}
    25 percentyl: ${results['percentile_25']:.2f}
    75 percentyl: ${results['percentile_75']:.2f}
    90 percentyl: ${results['percentile_90']:.2f}
    Maximum: ${results['max_final']:.2f}

    PRAWDOPODOBIEŃSTWA:
    Zysk: {results['probability_profit']:.1f}%
    Strata: {results['probability_loss']:.1f}%
    """

    ax4.text(0.1, 0.9, stats_text, fontfamily='monospace', fontsize=10, verticalalignment='top')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Wykres zapisany: {save_path}")

    return fig


def print_daily_projection(results: Dict):
    """Wyświetl projekcję dzień po dniu"""

    paths_df = results['paths']

    print("\n" + "="*80)
    print(f"PROJEKCJA KAPITAŁU - DZIEŃ PO DNIU (Kapitał początkowy: ${results['initial_capital']:.2f})")
    print("="*80)
    print(f"{'Dzień':<6} {'Średnia':<10} {'Mediana':<10} {'10%':<10} {'90%':<10} {'Min':<10} {'Max':<10}")
    print("-"*80)

    for day in range(0, len(paths_df), max(1, len(paths_df) // 15)):  # co 2 dni jeśli 30 dni
        row = paths_df.iloc[day]
        print(f"{day:<6} "
              f"${row.mean():>8.2f}  "
              f"${row.median():>8.2f}  "
              f"${row.quantile(0.1):>8.2f}  "
              f"${row.quantile(0.9):>8.2f}  "
              f"${row.min():>8.2f}  "
              f"${row.max():>8.2f}")

    print("="*80)


def main():
    """Przykład użycia"""

    # Przykładowe statystyki (dostosuj do swoich wyników z backtestów)
    stats = TradingStats(
        win_rate=0.65,  # 65% wygranych tradów
        avg_win_pct=3.5,  # średni zysk 3.5%
        avg_loss_pct=1.2,  # średnia strata 1.2%
        trades_per_day=2.5,  # ~2-3 trady dziennie
        profit_factor=2.5,  # profit factor
        max_drawdown_pct=15.0  # max drawdown 15%
    )

    print("\nParametry symulacji:")
    print(f"  Win rate: {stats.win_rate*100:.1f}%")
    print(f"  Średni zysk: {stats.avg_win_pct:.2f}%")
    print(f"  Średnia strata: {stats.avg_loss_pct:.2f}%")
    print(f"  Trady dziennie: {stats.trades_per_day:.1f}")
    print(f"  Profit factor: {stats.profit_factor:.2f}")

    # Scenariusz 1: Kapitalizacja zysków
    print("\n" + "="*80)
    print("SCENARIUSZ 1: Z KAPITALIZACJĄ ZYSKÓW")
    print("="*80)

    results_compound = simulate_capital_growth(
        initial_capital=100.0,
        days=30,
        stats=stats,
        risk_per_trade=0.02,  # 2% na trade
        compound=True,
        num_simulations=1000
    )

    print(f"\nPo 30 dniach (z kapitalizacją):")
    print(f"  Średni kapitał: ${results_compound['mean_final']:.2f} ({results_compound['mean_return_pct']:+.2f}%)")
    print(f"  Mediana: ${results_compound['median_final']:.2f} ({results_compound['median_return_pct']:+.2f}%)")
    print(f"  Zakres: ${results_compound['min_final']:.2f} - ${results_compound['max_final']:.2f}")
    print(f"  Prawdopodobieństwo zysku: {results_compound['probability_profit']:.1f}%")

    print_daily_projection(results_compound)

    # Scenariusz 2: Bez kapitalizacji
    print("\n" + "="*80)
    print("SCENARIUSZ 2: BEZ KAPITALIZACJI ZYSKÓW")
    print("="*80)

    results_no_compound = simulate_capital_growth(
        initial_capital=100.0,
        days=30,
        stats=stats,
        risk_per_trade=0.02,
        compound=False,
        num_simulations=1000
    )

    print(f"\nPo 30 dniach (bez kapitalizacji):")
    print(f"  Średni kapitał: ${results_no_compound['mean_final']:.2f} ({results_no_compound['mean_return_pct']:+.2f}%)")
    print(f"  Mediana: ${results_no_compound['median_final']:.2f} ({results_no_compound['median_return_pct']:+.2f}%)")
    print(f"  Zakres: ${results_no_compound['min_final']:.2f} - ${results_no_compound['max_final']:.2f}")
    print(f"  Prawdopodobieństwo zysku: {results_no_compound['probability_profit']:.1f}%")

    # Wizualizacja
    print("\nGeneruję wykresy...")
    plot_simulation(results_compound, save_path='capital_simulation_compound.png')
    plot_simulation(results_no_compound, save_path='capital_simulation_no_compound.png')

    print("\n✅ Symulacja zakończona!")
    print("Zapisano wykresy:")
    print("  - capital_simulation_compound.png")
    print("  - capital_simulation_no_compound.png")

    # Porównanie
    print("\n" + "="*80)
    print("PORÓWNANIE SCENARIUSZY")
    print("="*80)
    print(f"{'Metryka':<30} {'Z kapitalizacją':<20} {'Bez kapitalizacji':<20}")
    print("-"*80)
    print(f"{'Średni zwrot':<30} {results_compound['mean_return_pct']:>18.2f}% {results_no_compound['mean_return_pct']:>18.2f}%")
    print(f"{'Mediana zwrotu':<30} {results_compound['median_return_pct']:>18.2f}% {results_no_compound['median_return_pct']:>18.2f}%")
    print(f"{'Prawdop. zysku':<30} {results_compound['probability_profit']:>18.1f}% {results_no_compound['probability_profit']:>18.1f}%")
    print(f"{'90 percentyl':<30} ${results_compound['percentile_90']:>17.2f} ${results_no_compound['percentile_90']:>17.2f}")
    print(f"{'10 percentyl':<30} ${results_compound['percentile_10']:>17.2f} ${results_no_compound['percentile_10']:>17.2f}")
    print("="*80)


if __name__ == "__main__":
    main()
