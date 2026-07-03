"""Unit tests for the corporate CRA engine: GST/ITC, dividends/T5, CCA,
shareholder loan and T2 estimates."""
from oilforge.cra import engine as cra

R25 = cra.get_rules(2025)
R24 = cra.get_rules(2024)


class TestRulePacks:
    def test_packs_load(self):
        assert R24["year"] == 2024 and R25["year"] == 2025
        assert R25["gst_hst"]["rates"]["NS"] == 0.14

    def test_missing_year_provisional(self):
        r = cra.get_rules(2099)
        assert r["provisional"] and r["year"] == 2099

    def test_override_merge(self):
        r = cra.get_rules(2025, {"shareholder_loan": {"prescribed_rate": 0.05}})
        assert r["shareholder_loan"]["prescribed_rate"] == 0.05
        assert r["dividends"]["eligible"]["gross_up"] == 0.38  # untouched


class TestGst:
    def test_itc_full_and_partial(self):
        assert cra.calc_itc(1050.0, "Fuel & Petroleum", R25) == 50.0
        assert cra.calc_itc(105.0, "Meals (50%)", R25) == 2.5
        assert cra.calc_itc(500.0, "WCB Premiums", R25) == 0.0
        assert cra.calc_itc(500.0, "Insurance - Commercial", R25) == 0.0

    def test_gst_return(self):
        r = cra.gst_return(100000, 5000, 1200)
        assert r["line_109_net_tax"] == 3800.0 and r["owing"]


class TestDividends:
    def test_non_eligible_t5_boxes(self):
        t5 = cra.dividend_t5({"non_eligible": 80000.0}, R25)
        k = t5["kinds"]["non_eligible"]
        assert k["actual"] == 80000.0
        assert k["taxable"] == 92000.0            # 15% gross-up
        assert k["dtc"] == round(92000 * 0.090301, 2)
        assert t5["boxes"]["10"] == 80000.0
        assert t5["boxes"]["11"] == 92000.0
        assert t5["boxes"]["12"] == k["dtc"]

    def test_eligible_t5_boxes(self):
        t5 = cra.dividend_t5({"eligible": 10000.0}, R25)
        k = t5["kinds"]["eligible"]
        assert k["taxable"] == 13800.0            # 38% gross-up
        assert k["dtc"] == round(13800 * 0.150198, 2)
        assert t5["boxes"]["24"] == 10000.0
        assert t5["boxes"]["25"] == 13800.0

    def test_zero_dividends(self):
        t5 = cra.dividend_t5({}, R25)
        assert t5["kinds"]["eligible"]["taxable"] == 0.0


class TestShareholderLoan:
    def test_directions(self):
        assert cra.loan_direction("withdrawal") == +1
        assert cra.loan_direction("personal_expense") == +1
        assert cra.loan_direction("contribution") == -1
        assert cra.loan_direction("dividend_applied") == -1
        assert cra.loan_direction("bogus") == 0

    def test_assessment_owing(self):
        a = cra.shareholder_loan_assessment(50000.0, "2025-12-31", R25)
        assert a["owing_to_corp"]
        assert a["annual_imputed_interest_80_4"] == round(50000 * 0.04, 2)
        assert "12 months" in a["repayment_deadline_note"]

    def test_assessment_clear(self):
        a = cra.shareholder_loan_assessment(-1200.0, "2025-12-31", R25)
        assert not a["owing_to_corp"]
        assert a["annual_imputed_interest_80_4"] == 0.0


class TestCorporateTax:
    def test_small_business_only(self):
        est = cra.corporate_tax_estimate(200000, R25, "AB")
        # 9% federal + 2% AB = 11%
        assert est["estimated_tax"] == 22000.0
        assert est["after_tax"] == 178000.0

    def test_above_sbd_limit(self):
        est = cra.corporate_tax_estimate(600000, R25, "AB")
        expected = 500000 * 0.11 + 100000 * 0.23
        assert est["estimated_tax"] == round(expected, 2)

    def test_loss_year(self):
        assert cra.corporate_tax_estimate(-50000, R25)["estimated_tax"] == 0.0


class TestCCA:
    rules = staticmethod(lambda y: cra.get_rules(y))

    def test_first_year_aiip(self):
        # Class 38 skid steer, $120k bought 2024: CCA = 30% x 1.5 x 120k = 54k
        sched = cra.cca_schedule(
            [{"cca_class": "38", "cost": 120000, "acquired_year": 2024}],
            2024, self.rules)
        row = sched["classes"][0]
        assert row["cca"] == 54000.0
        assert row["ucc_closing"] == 66000.0

    def test_second_year_declining_balance(self):
        sched = cra.cca_schedule(
            [{"cca_class": "38", "cost": 120000, "acquired_year": 2024}],
            2025, self.rules)
        row = sched["classes"][0]
        assert row["ucc_opening"] == 66000.0
        assert row["cca"] == 19800.0              # 30% of 66k
        assert row["ucc_closing"] == 46200.0

    def test_disposal_triggers_recapture(self):
        sched = cra.cca_schedule(
            [{"cca_class": "10", "cost": 50000, "acquired_year": 2024,
              "disposed_year": 2025, "proceeds": 30000}],
            2025, self.rules)
        row = sched["classes"][0]
        # 2024: base 1.5*50k=75k -> CCA 22.5k, UCC 27.5k
        # 2025: 27.5k - 30k disposal -> UCC -2.5k -> recapture income
        assert row["recapture"] == 2500.0
        assert row["cca"] == 0.0
        assert row["ucc_closing"] == 0.0
        assert sched["total_recapture"] == 2500.0

    def test_disposal_triggers_terminal_loss(self):
        # Sold cheap: class emptied with UCC left -> terminal loss deduction.
        sched = cra.cca_schedule(
            [{"cca_class": "10", "cost": 50000, "acquired_year": 2024,
              "disposed_year": 2025, "proceeds": 10000}],
            2025, self.rules)
        row = sched["classes"][0]
        # 2025: UCC 27.5k - 10k = 17.5k, no assets left -> terminal loss.
        assert row["terminal_loss"] == 17500.0
        assert row["cca"] == 0.0
        assert row["ucc_closing"] == 0.0

    def test_no_terminal_loss_while_assets_remain(self):
        sched = cra.cca_schedule(
            [{"cca_class": "10", "cost": 50000, "acquired_year": 2024,
              "disposed_year": 2025, "proceeds": 10000},
             {"cca_class": "10", "cost": 20000, "acquired_year": 2024}],
            2025, self.rules)
        row = sched["classes"][0]
        assert row["terminal_loss"] == 0.0
        assert row["cca"] > 0.0

    def test_multiple_classes(self):
        sched = cra.cca_schedule(
            [{"cca_class": "8", "cost": 10000, "acquired_year": 2025},
             {"cca_class": "50", "cost": 4000, "acquired_year": 2025}],
            2025, self.rules)
        classes = {r["class"]: r for r in sched["classes"]}
        assert classes["8"]["cca"] == 3000.0      # 20% x 1.5 x 10k
        assert classes["50"]["cca"] == 3300.0     # 55% x 1.5 x 4k
        assert sched["total_cca"] == 6300.0

    def test_claim_pct_optional_cca(self):
        sched = cra.cca_schedule(
            [{"cca_class": "8", "cost": 10000, "acquired_year": 2025}],
            2025, self.rules, claim_pct=0)
        assert sched["total_cca"] == 0.0
        assert sched["classes"][0]["ucc_closing"] == 10000.0


class TestSchedule1:
    def test_meals_addback_and_cca(self):
        s1 = cra.schedule1(100000.0, {"Meals (50%)": 4000.0}, 20000.0, 0, 0, R25)
        # 100k + 2k meals add-back - 20k CCA
        assert s1["net_income_for_tax"] == 82000.0
        assert any("Meals" in l["line"] for l in s1["lines"])

    def test_recapture_and_terminal_loss_lines(self):
        s1 = cra.schedule1(50000.0, {}, 0.0, 3000.0, 1000.0, R25)
        assert s1["net_income_for_tax"] == 52000.0
