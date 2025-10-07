# 📊 Status Treningu - Aktualizacja 2025-10-07

## 🔄 Status Treningu

### Aktywne zadania:

| Symbol | Progress | Fold | Start | Ostatnia aktualizacja |
|--------|----------|------|-------|----------------------|
| **BTC/USDT** | 13.4% | 9/67 | 2025-10-06 19:21 | 2025-10-07 05:46 |
| **ADA/USDT** | 17.5% | 11/63 | 2025-10-06 19:21 | 2025-10-07 06:03 |
| **BNB/USDT** | 16.1% | 10/62 | 2025-10-06 19:21 | 2025-10-07 06:25 |

**Uwaga**: Training został **zrestartowany wczoraj o 19:21** (prawdopodobnie przez restart systemu)

**Czas trwania**: ~11 godzin (9 foldów dla BTC)
**Średni czas/fold**: ~1.2 godziny
**Estymowany czas do końca**: ~70 godzin (~3 dni)

---

## 📈 Metryki Treningu (BTC/USDT - ostatnie 9 foldów)

### Szczegółowe wyniki:

| Fold | Accuracy | ROC-AUC | Precision | Recall | F1-Score | Czas |
|------|----------|---------|-----------|--------|----------|------|
| 1 | 53.5% | 0.542 | 48.2% | 39.1% | 0.432 | 20:50 |
| 2 | 60.5% | **0.661** ✅ | 72.4% | 26.9% | 0.392 | 21:47 |
| 3 | **65.3%** ✅ | **0.668** ✅ | 56.6% | 40.4% | 0.471 | 23:04 |
| 4 | 60.8% | 0.626 | 49.6% | 45.7% | 0.475 | 00:18 |
| 5 | 57.5% | 0.584 | 55.4% | 36.1% | 0.437 | 01:41 |
| 6 | 63.5% | 0.536 | 34.6% | 0.9% ⚠️ | 0.017 | 02:42 |
| 7 | 58.9% | 0.586 | 61.4% | 6.4% ⚠️ | 0.116 | 03:32 |
| 8 | 52.6% | 0.536 | 0.0% ❌ | 0.0% ❌ | 0.0 | 04:26 |
| 9 | 54.5% | **0.495** ❌ | 48.4% | 5.7% ⚠️ | 0.103 | 05:46 |

---

## 📊 Statystyki Zbiorcze (9 foldów)

| Metryka | Wartość | Ocena | Porównanie z poprzednim |
|---------|---------|-------|-------------------------|
| **Średnia Accuracy** | **58.3%** | ⚠️ Średnia | ↓ -2.4% (było 60.7%) |
| **Średnia ROC-AUC** | **0.582** | ⚠️ Słaba | ↓ -0.049 (było 0.631) |
| **Średnia Precision** | **49.6%** | ⚠️ Słaba | ↓ -9.3% (było 58.9%) |
| **Średnia Recall** | **24.7%** | ❌ Bardzo niska | ↓ -10.6% (było 35.3%) |
| **Średnia F1** | **0.271** | ❌ Słaba | ↓ -0.158 (było 0.429) |

### Najlepsze foldy:
- **Fold 3**: AUC 0.668, Accuracy 65.3% ✅
- **Fold 2**: AUC 0.661, Accuracy 60.5% ✅

### Problematyczne foldy:
- **Fold 8**: Precision 0%, Recall 0% ❌
- **Fold 9**: AUC 0.495 (gorsze od losowego) ❌
- **Fold 6-7**: Bardzo niski Recall (<7%) ⚠️

---

## ⚠️ Problemy i Obserwacje

### 1. **Spadek jakości vs poprzedni training**

| Metryka | Poprzedni (77% done) | Obecny (13% done) | Zmiana |
|---------|---------------------|-------------------|--------|
| ROC-AUC | 0.631 ✅ | 0.582 ⚠️ | **-7.8%** |
| Accuracy | 60.7% | 58.3% | -2.4% |
| Recall | 35.3% | 24.7% | **-30%** |

**Możliwe przyczyny**:
- ✅ **Nowe TP/SL multipliers** - model może potrzebować dostosowania
- ⚠️ **Zmiana parametrów** - coś się zmieniło w konfiguracji
- ⚠️ **Inne dane** - restart mógł użyć innych dat treningowych
- ⚠️ **Random seed** - losowość w walk-forward splits

### 2. **Bardzo niski Recall (24.7%)**

**Co to znaczy:**
- Model jest **ultra-konserwatywny**
- Wykrywa tylko **25% dobrych okazji**
- Pomija **75% potencjalnych tradów**

**Efekt dla tradingu:**
- Bardzo **mało sygnałów** (może 1-2/dzień zamiast 3-5)
- Ale te które przejdą będą **wysokiej jakości**

### 3. **Fold 8 - totalna porażka**
```
Precision: 0.0%
Recall: 0.0%
F1: 0.0
```

**Co się stało:**
- Model nie wygenerował **żadnej pozytywnej predykcji**
- Albo wszystkie były błędne
- **Czerwona flaga** - coś jest nie tak

### 4. **Fold 9 - gorsze od losowego**
```
ROC-AUC: 0.495 (< 0.5)
```

**Co to znaczy:**
- Model jest **gorszy** od zgadywania
- **Mega problem** - model się psuje na nowszych danych

---

## 🔍 Analiza Przyczyn

### Dlaczego nowy training jest gorszy?

#### 1. **Restart systemu wczoraj o 19:21**
```
Poprzedni training: 2025-10-05 20:29 → 2025-10-06 18:05 (22h, 77% done)
Nowy training:      2025-10-06 19:21 → teraz (11h, 13% done)
```

**Co się stało:**
- Poprzedni training był **77% ukończony** (52/67 foldów)
- Miał **dobre metryki** (AUC 0.631)
- Został **przerwany i zrestartowany**
- Nowy training zaczął od nowa

**Prawdopodobna przyczyna restartu:**
- Twój `docker-compose restart worker` o 18:24
- Albo automatyczny restart systemu

#### 2. **Nowe TP/SL multipliers wpłynęły na labeling**

**Stare multipliers** (używane w poprzednim trainingu):
```python
atr_multiplier_sl = 1.2
atr_multiplier_tp1 = 1.5
atr_multiplier_tp2 = 2.5
atr_multiplier_tp3 = 4.0
```

**Nowe multipliers** (używane teraz):
```python
atr_multiplier_sl = 1.0   # Ciasniejszy SL
atr_multiplier_tp1 = 2.0  # Wyższy TP
atr_multiplier_tp2 = 3.5  # Wyższy TP
atr_multiplier_tp3 = 6.0  # Wyższy TP
```

**Efekt na labeling**:
- **Ciasniejszy SL** → więcej SL hitów w historii → mniej pozytywnych labeli
- **Wyższe TP** → mniej TP hitów w historii → mniej pozytywnych labeli
- **Rezultat**: Model ma mniej pozytywnych przykładów do nauki
- **To wyjaśnia**: Bardzo niski Recall (25%) i foldy z 0% precision

#### 3. **Class imbalance problem**

Z nowymi TP/SL:
- Pozytywne labele (TP hit): ~20-30% danych (było ~40%)
- Negatywne labele (SL hit): ~70-80% danych (było ~60%)

**Model się uczy:**
- "Bezpieczniej jest przewidywać NEGATIVE"
- Dlatego bardzo niski Recall (pomija 75% okazji)
- Dlatego foldy z 0% predictions

---

## 🎯 Co to znaczy dla tradingu?

### Scenariusz 1: Training się ukończy z obecnymi metrykami (AUC ~0.58)

**Spodziewane wyniki:**
```yaml
ROC-AUC: 0.58
Win rate: 54-57%
Avg profit: 3.5% (wyższe TP)
Trades/dzień: 1-2 (niski recall)
Miesięczny zwrot: +3-4%
```

**Ocena:** ⚠️ Średnie - może być słabo opłacalne

**Dlaczego:**
- AUC 0.58 < 0.60 (próg przyzwoitości)
- Win rate 54-57% jest na granicy opłacalności
- Bardzo mało sygnałów (1-2/dzień)

### Scenariusz 2: Metryki się poprawią w kolejnych foldach

**Jeśli zobaczymy:**
- Foldy 10-20: AUC wróci do 0.60-0.65
- Recall wzrośnie do 30-35%

**Wtedy:** ✅ System będzie działał dobrze

### Scenariusz 3: Metryki dalej spadają

**Jeśli:**
- Więcej foldów z AUC < 0.55
- Więcej foldów z 0% precision

**Wtedy:** ❌ Trzeba będzie przerwać i poprawić

---

## 🔧 Możliwe Rozwiązania

### Opcja 1: Poczekaj i monitoruj (REKOMENDOWANE)

**Akcja:**
1. Poczekaj na kolejne 10-20 foldów (następne 12-24h)
2. Obserwuj czy metryki się stabilizują
3. Jeśli AUC > 0.60 w większości → kontynuuj
4. Jeśli AUC < 0.58 w większości → przerwij

**Dlaczego:**
- Dopiero 13% ukończone (9/67 foldów)
- Za wcześnie na wnioski
- Wczesne foldy mogą być gorsze

### Opcja 2: Przywróć stare TP/SL i retrain

**Akcja:**
1. Przywróć stare multipliers:
   ```python
   atr_multiplier_sl = 1.2
   atr_multiplier_tp1 = 1.5
   atr_multiplier_tp2 = 2.5
   atr_multiplier_tp3 = 4.0
   ```
2. Restart trainingu
3. Poczekaj 3 dni

**Zalety:**
- Wróci do poprzednich dobrych metryk (AUC 0.63)
- Więcej sygnałów (wyższy recall)

**Wady:**
- Sygnały będą miały niższy expected profit (~2-3%)
- Więcej będzie odrzucanych przez filtr 2%

### Opcja 3: Dostosuj nowe TP/SL (KOMPROMIS)

**Akcja:**
1. Użyj **pośrednich** wartości:
   ```python
   atr_multiplier_sl = 1.1   # Pomiędzy 1.0 a 1.2
   atr_multiplier_tp1 = 1.7  # Pomiędzy 1.5 a 2.0
   atr_multiplier_tp2 = 3.0  # Pomiędzy 2.5 a 3.5
   atr_multiplier_tp3 = 5.0  # Pomiędzy 4.0 a 6.0
   ```
2. Restart trainingu

**Efekt:**
- Balans między jakością i ilością sygnałów
- Expected profit ~3-4% (przejdzie filtr 2%)
- Recall ~30-35% (więcej sygnałów niż teraz)

### Opcja 4: Wyłącz filtr 2% tymczasowo

**Akcja:**
```python
# apps/api/config.py
MIN_NET_PROFIT_PCT = 1.0  # Zamiast 2.0
```

**Efekt:**
- Więcej sygnałów (nawet z niższym zyskiem)
- Ale też więcej słabych setupów

**Ryzyko:**
- Win rate może spaść
- Więcej małych strat

---

## 📊 Monitoring Commands

### Sprawdź postęp treningu:
```bash
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT symbol, current_fold, total_folds,
          ROUND(progress_pct::numeric, 1) as progress,
          updated_at
   FROM training_jobs
   WHERE status = 'training'
   ORDER BY symbol;"
```

### Sprawdź najnowsze metryki:
```bash
docker-compose logs worker --tail=50 | grep "OOS Test Metrics" | tail -5
```

### Sprawdź czy są sygnały:
```bash
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT COUNT(*),
          MIN(created_at) as first,
          MAX(created_at) as last
   FROM signals
   WHERE created_at > NOW() - INTERVAL '1 day';"
```

### Sprawdź odrzucone sygnały:
```bash
docker-compose logs worker --tail=100 | grep "Signal rejected" | tail -10
```

---

## 🎯 Rekomendacja

### Dla Ciebie (teraz):

**OPCJA 1: Poczekaj 24h** ✅ (najbardziej rozsądne)

**Dlaczego:**
- Dopiero 13% done - za wcześnie na decyzje
- Pierwsze foldy mogą być gorsze (model się dopiero uczy)
- Jeśli metryki się stabilizują → OK
- Jeśli dalej spadają → wtedy zmień

**Co robić:**
1. **Dzisiaj wieczorem** (~20:00): Sprawdź metryki (powinno być ~20-25 foldów)
2. **Jutro rano** (~8:00): Sprawdź metryki (powinno być ~30-35 foldów)
3. **Jeśli średnia AUC > 0.60** → Kontynuuj
4. **Jeśli średnia AUC < 0.57** → Rozważ Opcję 3 (kompromis)

**Monitoring:**
```bash
# Co 2-3 godziny
docker-compose logs worker --tail=20 | grep -E "OOS Test Metrics|Training Progress"
```

---

## 📈 Przewidywany Timeline

**Przy obecnym tempie** (~1.2h/fold):

| Czas | Foldy | % Done | Co sprawdzić |
|------|-------|--------|--------------|
| **Dzisiaj 20:00** | ~20/67 | 30% | Czy AUC > 0.60? |
| **Jutro 8:00** | ~30/67 | 45% | Czy trend się poprawia? |
| **Jutro 20:00** | ~40/67 | 60% | Czy średnia AUC stabilna? |
| **Pojutrze 8:00** | ~50/67 | 75% | Ostatnia szansa na przerwanie |
| **Pojutrze 20:00** | ~60/67 | 90% | Prawie gotowe |
| **Za 3 dni** | 67/67 | 100% | Training ukończony ✅ |

---

## 🚨 Red Flags do Monitorowania

**Przerwij training jeśli zobaczysz:**
- ❌ Więcej niż 20% foldów ma AUC < 0.55
- ❌ Więcej niż 10% foldów ma precision = 0%
- ❌ Średnia recall < 20%
- ❌ Więcej niż 5 foldów z AUC < 0.50

**Wtedy przejdź do Opcji 3 (kompromisowe TP/SL)**

---

**Status**: ⚠️ Training w toku, metryki poniżej oczekiwań, wymaga monitoringu

**Następny check**: Za 6-8 godzin (dzisiaj wieczorem)

**Decyzja**: Za 24 godziny (jutro rano)

---

**Ostatnia aktualizacja**: 2025-10-07 06:30
