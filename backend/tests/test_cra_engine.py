"""Unit tests for the CRA compliance engine — the numbers that matter."""
import pytest

from rigbooks.cra import engine as cra

R25 = cra.get_rules(2025)
R24 = cra.get_rules(2024)


class TestRulePacks:
    def test_year_packs_load(self):
        assert R25["year"] == 2025
        assert R24["mileage"]["tier1_rate"] == 0.70
        assert R25["mileage"]["tier1_rate"] == 0.72

    def test_missing_year_falls_back_provisional(self):
        r = cra.get_rules(2099)
        assert r["provisional"] is True
        assert r["year"] == 2099
        assert r["mileage"]["tier1_rate"] > 0

    def test_overrides_deep_merge(self):
        r = cra.get_rules(2025, {"mileage": {"tier1_rate": 0.99}})
        assert r["mileage"]["tier1_rate"] == 0.99
        assert r["mileage"]["tier2_rate"] == 0.66  # untouched


class TestGstItc:
    def test_gst_rate_by_province(self):
        assert cra.gst_rate(R25, "AB") == 0.05
        assert cra.gst_rate(R25, "ON") == 0.13
        assert cra.gst_rate(R25, "NS") == 0.14  # dropped Apr 2025

    def test_extract_gst_tax_included(self):
        # $105 incl. 5% GST -> $5.00 embedded
        assert cra.extract_gst(105.0, 0.05) == 5.00

    def test_itc_full_recovery_category(self):
        # Fuel: 100% recoverable. $105 -> $5 ITC in AB.
        assert cra.calc_itc(105.0, "Fuel & Petroleum", R25) == 5.00

    def test_itc_meals_half(self):
        assert cra.calc_itc(105.0, "Meals (50%)", R25) == 2.50

    def test_itc_long_haul_meals_80(self):
        assert cra.calc_itc(105.0, "Meals - Long Haul (80%)", R25) == 4.00

    def test_itc_exempt_categories_zero(self):
        assert cra.calc_itc(500.0, "Insurance", R25) == 0.0
        assert cra.calc_itc(500.0, "Bank Fees", R25) == 0.0

    def test_itc_business_pct_prorates(self):
        full = cra.calc_itc(105.0, "Phone & Communications", R25)
        assert cra.calc_itc(105.0, "Phone & Communications", R25,
                            business_pct=60) == round(full * 0.6, 2)

    def test_itc_unknown_category_zero(self):
        assert cra.calc_itc(100.0, "Nonsense", R25) == 0.0


class TestMileage:
    def test_under_tier1_limit(self):
        assert cra.mileage_allowance(1000, R25) == 720.00

    def test_exactly_tier1_limit(self):
        assert cra.mileage_allowance(5000, R25) == 3600.00

    def test_over_tier1_limit_uses_tier2(self):
        # 5000*0.72 + 3000*0.66 = 3600 + 1980
        assert cra.mileage_allowance(8000, R25) == 5580.00

    def test_2024_rates_differ(self):
        assert cra.mileage_allowance(5000, R24) == 3500.00

    def test_territory_supplement(self):
        base = cra.mileage_allowance(1000, R25)
        assert cra.mileage_allowance(1000, R25, territories=True) == base + 40.0

    def test_business_use_pct(self):
        assert cra.business_use_pct(750, 1000) == 75.0
        assert cra.business_use_pct(0, 0) == 0.0
        assert cra.business_use_pct(1200, 1000) == 100.0  # capped


class TestMeals:
    def test_simplified_long_haul(self):
        d = cra.meal_deduction(R25, meals_count=3, long_haul=True)
        assert d["gross"] == 69.00           # 3 x $23
        assert d["deductible"] == 55.20      # 80%

    def test_simplified_standard_50(self):
        d = cra.meal_deduction(R25, meals_count=2, long_haul=False)
        assert d["deductible"] == 23.00      # 46 * 50%

    def test_detailed_method_uses_receipts(self):
        d = cra.meal_deduction(R25, actual_amount=100.0, method="detailed",
                               long_haul=True)
        assert d["gross"] == 100.0
        assert d["deductible"] == 80.0


class TestIfta:
    def test_apportionment(self):
        # 1000 km total, 400 L purchased -> 2.5 km/L.
        report = cra.ifta_quarter_report(
            {"AB": 600, "SK": 400}, {"AB": 400}, R25)
        assert report["fleet_kpl"] == 2.5
        ab = next(l for l in report["lines"] if l["jurisdiction"] == "AB")
        sk = next(l for l in report["lines"] if l["jurisdiction"] == "SK")
        assert ab["taxable_litres"] == 240.0     # 600/2.5
        assert sk["taxable_litres"] == 160.0     # 400/2.5
        # AB: bought 400, owed on 240 -> credit; SK: bought 0, owed on 160.
        assert ab["net_taxable_litres"] == -160.0
        assert sk["net_tax"] == round(160.0 * R25["ifta"]["fuel_tax_rates_per_litre"]["SK"], 2)

    def test_no_fuel_no_division_error(self):
        report = cra.ifta_quarter_report({"AB": 500}, {}, R25)
        assert report["fleet_kpl"] == 0.0
        assert report["net_tax_due"] == 0.0


class TestT4aAndGst34:
    def test_t4a_threshold(self):
        rows = cra.t4a_candidates(
            {"Big Law LLP": 1200.0, "Small Guy": 400.0, "": 999.0}, R25)
        assert [r["vendor"] for r in rows] == ["Big Law LLP"]
        assert rows[0]["box"] == "048"

    def test_gst_return_owing_and_refund(self):
        owing = cra.gst_return(105000, 5000, 3000)
        assert owing["line_109_net_tax"] == 2000.0 and owing["owing"]
        refund = cra.gst_return(10500, 500, 900)
        assert refund["line_109_net_tax"] == -400.0 and not refund["owing"]
