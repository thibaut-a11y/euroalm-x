"""Chaîne ALM minimale : courbe -> flux -> scénarios -> risque -> allocation.

Toutes les valeurs monétaires sont exprimées dans la même unité abstraite.
Les taux sont des nombres décimaux (0.03 signifie 3 %), en capitalisation continue.
Les scénarios sont fictifs et ne représentent aucune calibration de marché.
"""

from dataclasses import dataclass
from itertools import combinations
from math import exp, isfinite
from random import Random


@dataclass(frozen=True)
class Curve:
    """Taux zéro par maturité ; interpolation linéaire des taux zéro."""

    nodes: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if not self.nodes or any(t <= 0 or not isfinite(t) or not isfinite(r) for t, r in self.nodes):
            raise ValueError("La courbe doit contenir des maturités positives et des taux finis.")
        if any(b[0] <= a[0] for a, b in zip(self.nodes, self.nodes[1:])):
            raise ValueError("Les maturités de la courbe doivent être strictement croissantes.")

    def rate(self, maturity: float) -> float:
        if maturity <= 0:
            raise ValueError("La maturité doit être positive.")
        if maturity < self.nodes[0][0] or maturity > self.nodes[-1][0]:
            raise ValueError("Maturité hors courbe : extrapolation interdite.")
        for (t0, r0), (t1, r1) in zip(self.nodes, self.nodes[1:]):
            if t0 <= maturity <= t1:
                return r0 + (r1 - r0) * (maturity - t0) / (t1 - t0)
        return self.nodes[-1][1]

    def discount(self, maturity: float, parallel_shock: float = 0.0) -> float:
        if maturity == 0:
            return 1.0
        return exp(-(self.rate(maturity) + parallel_shock) * maturity)


@dataclass(frozen=True)
class Liability:
    year: int
    amount: float

    def __post_init__(self) -> None:
        if self.year < 1 or self.amount <= 0 or not isfinite(self.amount):
            raise ValueError("Chaque passif doit avoir une échéance et un montant positifs.")


@dataclass(frozen=True)
class PortfolioResult:
    weights: tuple[float, ...]
    expected_asset_return: float
    duration_gap: float
    es99: float
    cash_coverage: float


def expected_shortfall(losses: list[float], confidence: float = 0.99) -> float:
    """Moyenne de la pire masse 1-confidence, avec fraction d'observation en bordure.

    Cela correspond à l'intégrale des quantiles et reste défini pour une
    distribution empirique discrète, même si 1 % de n n'est pas entier.
    """
    if not losses or not 0 < confidence < 1 or any(not isfinite(x) for x in losses):
        raise ValueError("Pertes finies et confiance dans ]0, 1[ requises.")
    ordered = sorted(losses, reverse=True)
    mass = len(ordered) * (1 - confidence)
    whole = int(mass)
    numerator = sum(ordered[:whole])
    if whole < len(ordered):
        numerator += (mass - whole) * ordered[whole]
    return numerator / mass


def value_liabilities(liabilities: tuple[Liability, ...], curve: Curve, elapsed: int = 0, shock: float = 0.0) -> float:
    return sum(item.amount * curve.discount(item.year - elapsed, shock)
               for item in liabilities if item.year > elapsed)


def build_demo() -> tuple[Curve, tuple[Liability, ...], tuple[int, ...], float]:
    """Exemple intégralement fictif, sans téléchargement de données."""
    curve = Curve(((1, .020), (2, .023), (5, .026), (10, .029), (20, .032)))
    liabilities = (Liability(1, 6), Liability(5, 20), Liability(10, 35), Liability(20, 55))
    bond_maturities = (2, 5, 10, 20)
    initial_assets = 100.0
    return curve, liabilities, bond_maturities, initial_assets


def make_shocks(count: int = 2000, seed: int = 42, volatility: float = .0075) -> tuple[float, ...]:
    if count < 100 or volatility <= 0:
        raise ValueError("Prévoir au moins 100 scénarios et une volatilité positive.")
    generator = Random(seed)
    return tuple(generator.gauss(0, volatility) for _ in range(count))


def grid_weights(asset_count: int, step: float = .1):
    """Toutes les allocations long-only sur une grille ; somme des poids = 1."""
    units = round(1 / step)
    if asset_count < 2 or not 0 < step <= 1 or abs(units * step - 1) > 1e-10:
        raise ValueError("Le pas de grille doit diviser 1 exactement.")
    for cuts in combinations(range(units + asset_count - 1), asset_count - 1):
        marks = (-1,) + cuts + (units + asset_count - 1,)
        counts = tuple(marks[i + 1] - marks[i] - 1 for i in range(asset_count))
        yield tuple(k / units for k in counts)


def optimize(curve: Curve, liabilities: tuple[Liability, ...], bond_maturities: tuple[int, ...],
             initial_assets: float, shocks: tuple[float, ...], min_return: float = .02,
             max_abs_duration_gap: float = 2.0, min_cash_weight: float = .08,
             step: float = .1) -> PortfolioResult | None:
    """Minimise ES99 du surplus sur une grille de portefeuilles admissibles.

    Le rendement est la moyenne des valeurs d'actif à un an sur les scénarios,
    rapportée au montant investi. Les passifs sont exclus de cette contrainte.
    """
    if initial_assets <= 0 or not shocks or any(t <= 1 for t in bond_maturities):
        raise ValueError("Actif positif, scénarios et obligations d'échéance > 1 an requis.")
    if not 0 <= min_cash_weight <= 1 or max_abs_duration_gap < 0:
        raise ValueError("Contraintes invalides.")
    if not any(item.year == 1 for item in liabilities):
        raise ValueError("L'exemple requiert un flux de passif à un an.")

    liability_pv = value_liabilities(liabilities, curve)
    liability_dollar_duration = sum(item.year * item.amount * curve.discount(item.year)
                                    for item in liabilities)
    payment_one_year = sum(item.amount for item in liabilities if item.year == 1)
    liability_ref = value_liabilities(liabilities, curve, elapsed=1)
    liability_scenarios = tuple(value_liabilities(liabilities, curve, elapsed=1, shock=s)
                                for s in shocks)

    # Une obligation zéro coupon est achetée à sa valeur de marché initiale.
    # Sa valeur nominale est donc investissement / facteur d'actualisation.
    asset_reference = (initial_assets * exp(curve.rate(1)),) + tuple(
        initial_assets * curve.discount(t - 1) / curve.discount(t) for t in bond_maturities)
    asset_scenarios = tuple(
        (initial_assets * exp(curve.rate(1)),) + tuple(
            initial_assets * curve.discount(t - 1, s) / curve.discount(t) for t in bond_maturities)
        for s in shocks)
    mean_asset_values = tuple(sum(row[j] for row in asset_scenarios) / len(shocks)
                              for j in range(1 + len(bond_maturities)))

    best: PortfolioResult | None = None
    for weights in grid_weights(1 + len(bond_maturities), step):
        cash_coverage = weights[0] * asset_reference[0] / payment_one_year
        if weights[0] + 1e-10 < min_cash_weight or cash_coverage + 1e-10 < 1:
            continue
        asset_dollar_duration = initial_assets * sum(w * t for w, t in zip(weights[1:], bond_maturities))
        duration_gap = (asset_dollar_duration - liability_dollar_duration) / initial_assets
        if abs(duration_gap) > max_abs_duration_gap + 1e-10:
            continue
        expected_return = sum(w * v for w, v in zip(weights, mean_asset_values)) / initial_assets - 1
        if expected_return + 1e-10 < min_return:
            continue

        # Les paiements à un an sont retranchés aux deux surplus : ils s'annulent
        # dans la différence, mais leur couverture en cash reste contrainte.
        surplus_ref = sum(w * v for w, v in zip(weights, asset_reference)) - payment_one_year - liability_ref
        losses = [surplus_ref - (sum(w * v for w, v in zip(weights, row))
                                 - payment_one_year - liability_value)
                  for row, liability_value in zip(asset_scenarios, liability_scenarios)]
        risk = expected_shortfall(losses)
        result = PortfolioResult(weights, expected_return, duration_gap, risk, cash_coverage)
        if best is None or result.es99 < best.es99:
            best = result
    return best


def run_analysis(seed: int = 42, count: int = 2000, step: float = .1) -> dict[float, PortfolioResult | None]:
    curve, liabilities, maturities, assets = build_demo()
    shocks = make_shocks(count=count, seed=seed)
    return {target: optimize(curve, liabilities, maturities, assets, shocks,
                             min_return=target, step=step) for target in (.02, .03, .04)}
