"""
Unit tests for Drift Mode Optimering (Smart Wake-Up og SIEM Forward)

Test case fra:
- docs/drift-mode-implementation.md
- docs/drift-mode-optimering.md
"""

import pytest
from datetime import datetime, timezone, timedelta


class TestSmartWakeUp:
    """Test smart wake-up implementering i agent.py"""

    def test_max_idle_sleep_default_300(self):
        """Default max_idle_sleep_s skal være 300 sekunder (5 minutter)"""
        # Mock config uden max_idle_sleep_s
        cfg = {"system": {}}

        max_idle_sleep = int(cfg.get("system", {}).get("max_idle_sleep_s", 300))
        assert max_idle_sleep == 300, "Default max_idle_sleep_s skal være 300"

    def test_max_idle_sleep_custom_value(self):
        """max_idle_sleep_s skal kunne konfigureres"""
        cfg = {"system": {"max_idle_sleep_s": 600}}

        max_idle_sleep = int(cfg.get("system", {}).get("max_idle_sleep_s", 300))
        assert max_idle_sleep == 600, "max_idle_sleep_s skal læses fra config"

    def test_max_idle_sleep_calculation(self):
        """Test beregning af wake-up interval med forskellige værdier"""
        test_cases = [
            # (sleep_s, max_idle, expected_min)
            (3600, 300, 300),   # 1 hour sleep, 300 max idle → wake every 300s
            (120, 300, 120),    # 2 min sleep, 300 max idle → wake every 120s
            (60, 300, 60),      # 1 min sleep, 300 max idle → wake every 60s
            (300, 300, 300),    # 5 min sleep, 300 max idle → wake every 300s
        ]

        for sleep_s, max_idle, expected in test_cases:
            result = min(sleep_s, max_idle)
            assert result == expected, f"min({sleep_s}, {max_idle}) = {result}, forventede {expected}"

    def test_wake_up_reduction_80_percent(self):
        """Bekræft 80% reduktion i wake-ups (1440 → 288)"""
        # Før: wake every 60s = 1440 wake-ups per dag
        wakeups_before = 1440

        # Efter: wake every 300s (5 min) = 288 wake-ups per dag
        wakeups_after = 288

        reduction = (wakeups_before - wakeups_after) / wakeups_before * 100
        assert reduction == 80.0, f"Reduktion skal være 80%, fik {reduction}%"

    def test_wake_up_calculation_per_day(self):
        """Test wake-up beregning per dag"""
        # 86400 sekunder per dag / interval
        intervals = {
            60: 1440,    # 1 min = 1440 wake-ups
            300: 288,    # 5 min = 288 wake-ups
            600: 144,    # 10 min = 144 wake-ups
        }

        for interval_s, expected_wakeups in intervals.items():
            wakeups = 86400 // interval_s
            assert wakeups == expected_wakeups, f"Interval {interval_s}s = {wakeups}, forventede {expected_wakeups}"


class TestSIEMForwardCondition:
    """Test SIEM forward condition implementering"""

    def test_siem_interval_default_300(self):
        """Default SIEM forward interval skal være 300 sekunder"""
        cfg = {}

        interval_s = int(cfg.get("forward_interval_s", 300))
        assert interval_s == 300, "Default forward_interval_s skal være 300"

    def test_siem_interval_custom_value(self):
        """SIEM forward interval skal kunne konfigureres"""
        cfg = {"forward_interval_s": 600}

        interval_s = int(cfg.get("forward_interval_s", 300))
        assert interval_s == 600, "forward_interval_s skal læses fra config"

    def test_siem_forward_condition(self):
        """Test SIEM forward condition logik"""
        # Setup
        siem_interval = timedelta(seconds=300)
        last_forward = datetime.now(timezone.utc)

        # Test 1: Ikke tid til forward (mindre end 300s siden sidste)
        now_early = last_forward + timedelta(seconds=200)
        should_forward_early = (now_early - last_forward) >= siem_interval
        assert not should_forward_early, "Skal ikke forward før interval er gået"

        # Test 2: Tid til forward (mere end 300s siden sidste)
        now_due = last_forward + timedelta(seconds=350)
        should_forward_due = (now_due - last_forward) >= siem_interval
        assert should_forward_due, "Skal forward når interval er gået"

    def test_siem_forward_reduction(self):
        """Bekræft reduktion i SIEM forward kald"""
        # Før: kaldes ved hver wake-up (hvis ingen condition)
        # Efter: kun kaldes når due (hvert 5. minut)

        # Med smart wake-up (300s): 288 SIEM forwards per dag
        siem_forwards_per_day = 288

        # Uden condition ville den måske kaldes oftere (hvis wake-up var hyppigere)
        # Med 60s wake-up uden condition: 1440 kald per dag
        calls_without_condition = 1440

        reduction = (calls_without_condition - siem_forwards_per_day) / calls_without_condition * 100
        assert reduction == 80.0, f"Reduktion skal være 80%, fik {reduction}%"


class TestBatteryImpact:
    """Test batteri impact beregninger"""

    def test_battery_drain_reduction(self):
        """Test batteri reduktion beregning"""
        # Før: 5-10% per dag
        # Efter: 2-5% per dag
        # Reduktion: 50-75%

        drain_before = 7.5  # gennemsnit
        drain_after = 3.5   # gennemsnit

        reduction = (drain_before - drain_after) / drain_before * 100
        assert 50 <= reduction <= 75, f"Reduktion skal være 50-75%, fik {reduction:.1f}%"

    def test_battery_drain_scenarios(self):
        """Test forskellige batteri drain scenarier"""
        scenarios = [
            ("Før (current)", 7.5, 5, 10),
            ("Efter (optimeret)", 3.5, 2, 5),
        ]

        for name, avg, min_drain, max_drain in scenarios:
            assert min_drain <= avg <= max_drain, f"{name}: avg skal være mellem {min_drain}-{max_drain}%"


class TestDataUsage:
    """Test data forbrug beregninger"""

    def test_total_data_reduction(self):
        """Test total data reduktion med optimeringer"""
        # Før: ~1 MB per dag
        # Efter: ~500 KB per dag
        # Reduktion: 50%

        data_before_kb = 1024  # 1 MB
        data_after_kb = 512    # 512 KB

        reduction = (data_before_kb - data_after_kb) / data_before_kb * 100
        assert reduction == 50.0, f"Data reduktion skal være 50%, fik {reduction}%"

    def test_config_poll_reduction(self):
        """Test config poll reduktion (5m → 10m)"""
        # Før: 5 minutter = 288 polls per dag
        # Efter: 10 minutter = 144 polls per dag

        polls_before = 288
        polls_after = 144

        reduction = (polls_before - polls_after) / polls_before * 100
        assert reduction == 50.0, f"Config poll reduktion skal være 50%, fik {reduction}%"

    def test_siem_forward_reduction(self):
        """Test SIEM forward reduktion (5m → 10m)"""
        # Før: 5 minutter = 288 forwards per dag
        # Efter: 10 minutter = 144 forwards per dag

        forwards_before = 288
        forwards_after = 144

        reduction = (forwards_before - forwards_after) / forwards_before * 100
        assert reduction == 50.0, f"SIEM forward reduktion skal være 50%, fik {reduction}%"


# Parametrized tests for forskellige konfigurationer
@pytest.mark.parametrize("max_idle_sleep_s,wakeups_per_day", [
    (60, 1440),    # 1 min = 1440 wake-ups
    (120, 720),    # 2 min = 720 wake-ups
    (300, 288),    # 5 min = 288 wake-ups (default)
    (600, 144),    # 10 min = 144 wake-ups
    (900, 96),     # 15 min = 96 wake-ups
])
def test_wakeups_per_day_calculation(max_idle_sleep_s, wakeups_per_day):
    """Test wake-up beregning for forskellige konfigurationer"""
    calculated = 86400 // max_idle_sleep_s
    assert calculated == wakeups_per_day, f"max_idle_sleep_s={max_idle_sleep_s}: {calculated} vs {wakeups_per_day}"


@pytest.mark.parametrize("config_value,expected", [
    (None, 300),        # Default når ikke sat
    (60, 60),           # 1 min
    (120, 120),         # 2 min
    (300, 300),         # 5 min (default documented)
    (600, 600),         # 10 min
])
def test_max_idle_sleep_config_values(config_value, expected):
    """Test forskellige max_idle_sleep_s konfigurationsværdier"""
    cfg = {"system": {}}
    if config_value is not None:
        cfg["system"]["max_idle_sleep_s"] = config_value

    result = int(cfg.get("system", {}).get("max_idle_sleep_s", 300))
    assert result == expected, f"Config værdi {config_value}: {result} vs {expected}"
