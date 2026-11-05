import unittest
from math import exp

from euroalm_mvp.core import (
    Curve, Liability, build_demo, expected_shortfall, grid_weights,
    make_shocks, optimize, value_liabilities,
)


class CoreTests(unittest.TestCase):
    def test_discount_and_no_silent_extrapolation(self):
        curve = Curve(((1, .02), (3, .04)))
        self.assertAlmostEqual(curve.rate(2), .03)
        self.assertAlmostEqual(curve.discount(2), exp(-.06))
        with self.assertRaises(ValueError):
            curve.discount(4)

    def test_liability_payment_and_roll_forward(self):
        curve = Curve(((1, .02), (2, .02)))
        flows = (Liability(1, 6), Liability(2, 10))
        self.assertAlmostEqual(value_liabilities(flows, curve), 6 * exp(-.02) + 10 * exp(-.04))
        self.assertAlmostEqual(value_liabilities(flows, curve, elapsed=1), 10 * exp(-.02))

    def test_es_uses_fraction_of_boundary_observation(self):
        # 4 observations, queue de 25 % : seule la pire perte entre.
        self.assertAlmostEqual(expected_shortfall([0, 1, 2, 4], .75), 4)
        # Queue de 37,5 % : la pire perte et la moitié de la suivante.
        self.assertAlmostEqual(expected_shortfall([0, 1, 2, 4], .625), (4 + .5 * 2) / 1.5)

    def test_grid_is_long_only_and_fully_invested(self):
        weights = list(grid_weights(3, .5))
        self.assertEqual(len(weights), 6)
        self.assertTrue(all(min(row) >= 0 and abs(sum(row) - 1) < 1e-12 for row in weights))

    def test_scenarios_repeat_and_optimizer_reports_infeasibility(self):
        self.assertEqual(make_shocks(100, seed=7), make_shocks(100, seed=7))
        curve, liabilities, maturities, assets = build_demo()
        shocks = make_shocks(100, seed=7)
        self.assertIsNone(optimize(curve, liabilities, maturities, assets, shocks,
                                   min_return=1.0, step=.2))
        result = optimize(curve, liabilities, maturities, assets, shocks,
                          min_return=-1.0, step=.2)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreaterEqual(result.weights[0], .08)
        self.assertGreaterEqual(result.cash_coverage, 1)
        self.assertLessEqual(abs(result.duration_gap), 2.0 + 1e-10)


if __name__ == "__main__":
    unittest.main()
