"""Lancement : python -m euroalm_mvp depuis prototype_mvp."""

from argparse import ArgumentParser

from .core import build_demo, run_analysis, value_liabilities


def main() -> None:
    parser = ArgumentParser(description="Démo pédagogique d'optimisation ALM")
    parser.add_argument("--seed", type=int, default=42, help="Graine des scénarios synthétiques")
    parser.add_argument("--scenarios", type=int, default=2000, help="Nombre de scénarios")
    parser.add_argument("--step", type=float, default=.1, help="Pas de grille des poids")
    args = parser.parse_args()

    curve, liabilities, maturities, assets = build_demo()
    print("EuroALM-X — prototype pédagogique, données et scénarios fictifs")
    print(f"Actifs initiaux : {assets:.2f} ; passifs actualisés : {value_liabilities(liabilities, curve):.2f}")
    print("Actifs : cash, " + ", ".join(f"zéro coupon {t} ans" for t in maturities))
    print("Poids : long-only, somme = 100 % ; cash >= 8 % ; couverture du flux à 1 an >= 100 %")
    print("Écart de duration monétaire normalisé <= 2 ans ; risque = ES99 du surplus à 1 an")
    for target, result in run_analysis(args.seed, args.scenarios, args.step).items():
        if result is None:
            print(f"Objectif de rendement {target:.0%} : aucun portefeuille admissible sur cette grille.")
            continue
        weights = ", ".join(f"{w:.0%}" for w in result.weights)
        print(f"Objectif {target:.0%} | poids [{weights}] | rendement moyen {result.expected_asset_return:.2%} "
              f"| écart duration {result.duration_gap:+.2f} an(s) "
              f"| ES99 {result.es99:.4f} (unité monétaire) "
              f"| couverture cash {result.cash_coverage:.2f}x")


if __name__ == "__main__":
    main()
