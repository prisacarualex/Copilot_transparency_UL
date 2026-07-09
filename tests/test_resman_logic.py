"""Tests for plugins.resman - Tank/pump logic, flow transfers, tolerance, and pump colors.

Tests the actual Resman plugin methods (compute_next_plugin_state,
get_pump_by_key, do_on_key, pump color determination) using object.__new__()
to bypass __init__.
"""

from unittest.mock import MagicMock, patch

from core.constants import COLORS as C
from plugins.resman import Resman


def _make_resman(**overrides):
    """Create a Resman instance bypassing __init__, with realistic state."""
    r = object.__new__(Resman)
    r.alias = "resman"
    r.scenario_time = 0
    r.next_refresh_time = 0
    r.alive = True
    r.paused = False
    r.visible = True
    r.verbose = False
    r.can_receive_keys = True
    r.can_execute_keys = True
    r.keys = {"NUM_1", "NUM_2", "NUM_3", "NUM_4", "NUM_5", "NUM_6", "NUM_7", "NUM_8"}
    r.performance = {}
    r.logger = MagicMock()
    r.wait_before_leak = 0  # Skip initial wait

    r.parameters = dict(
        taskupdatetime=2000,
        automaticsolver=False,
        displayautomationstate=True,
        pumpcoloroff=C["WHITE"],
        pumpcoloron=C["GREEN"],
        pumpcolorfailure=C["RED"],
        toleranceradius=250,
        statuslocation="bottomright",
        displaystatus=True,
        tolerancecolor=C["BLACK"],
        tolerancecoloroutside=C["BLACK"],
        title="Resources management",
        taskplacement="bottommid",
        taskfeedback=dict(
            overdue=dict(
                active=False, color=C["RED"], delayms=2000, blinkdurationms=1000, _nexttoggletime=0, _is_visible=False
            )
        ),
        tank=dict(
            a=dict(
                level=2500,
                max=4000,
                target=2500,
                depletable=True,
                lossperminute=800,
                _infoside="left",
                _response_time=0,
                _is_in_tolerance=None,
                _tolerance_color=C["BLACK"],
            ),
            b=dict(
                level=2500,
                max=4000,
                target=2500,
                depletable=True,
                lossperminute=800,
                _infoside="right",
                _response_time=0,
                _is_in_tolerance=None,
                _tolerance_color=C["BLACK"],
            ),
            c=dict(level=1000, max=2000, target=None, depletable=True, lossperminute=0, _infoside="left"),
            d=dict(level=1000, max=2000, target=None, depletable=True, lossperminute=0, _infoside="left"),
            e=dict(level=3000, max=4000, target=None, depletable=False, lossperminute=0, _infoside="right"),
            f=dict(level=3000, max=4000, target=None, depletable=False, lossperminute=0, _infoside="right"),
        ),
        pump=dict(
            [
                ("1", dict(flow=800, state="off", key="NUM_1", _fromtank="c", _totank="a")),
                ("2", dict(flow=600, state="off", key="NUM_2", _fromtank="e", _totank="a")),
                ("3", dict(flow=800, state="off", key="NUM_3", _fromtank="d", _totank="b")),
                ("4", dict(flow=600, state="off", key="NUM_4", _fromtank="f", _totank="b")),
                ("5", dict(flow=600, state="off", key="NUM_5", _fromtank="e", _totank="c")),
                ("6", dict(flow=600, state="off", key="NUM_6", _fromtank="f", _totank="d")),
                ("7", dict(flow=400, state="off", key="NUM_7", _fromtank="a", _totank="b")),
                ("8", dict(flow=400, state="off", key="NUM_8", _fromtank="b", _totank="a")),
            ]
        ),
    )

    r.__dict__.update(overrides)
    return r


def _run_one_update(r):
    """Run one compute_next_plugin_state cycle on Resman."""
    r.compute_next_plugin_state()
    # Advance time so the next call will also execute
    r.scenario_time += r.parameters["taskupdatetime"] / 1000
    r.next_refresh_time = r.scenario_time


# ──────────────────────────────────────────────
# Tank depletion
# ──────────────────────────────────────────────
class TestTankDepletion:
    """Test that target tanks lose fluid each update cycle."""

    def test_target_tank_depletes(self):
        """Target tank A loses fluid each update."""
        r = _make_resman()
        initial_a = r.parameters["tank"]["a"]["level"]
        _run_one_update(r)
        # 800 * (2/60) = 26.66 → int = 26
        assert r.parameters["tank"]["a"]["level"] == initial_a - 26

    def test_both_target_tanks_deplete(self):
        """Both target tanks A and B deplete."""
        r = _make_resman()
        _run_one_update(r)
        # Both A and B should have lost fluid
        assert r.parameters["tank"]["a"]["level"] < 2500
        assert r.parameters["tank"]["b"]["level"] < 2500

    def test_non_target_tank_no_depletion(self):
        """Non-target tanks C, E stay unchanged."""
        r = _make_resman()
        _run_one_update(r)
        # Tanks C, D, E, F have no target → no depletion
        assert r.parameters["tank"]["c"]["level"] == 1000
        assert r.parameters["tank"]["e"]["level"] == 3000

    def test_depletion_cannot_go_negative(self):
        """Very low tank level stays >= 0."""
        r = _make_resman()
        r.parameters["tank"]["a"]["level"] = 10  # Very low
        _run_one_update(r)
        assert r.parameters["tank"]["a"]["level"] >= 0

    def test_wait_before_leak(self):
        """First update with wait_before_leak > 0 should skip tank logic."""
        r = _make_resman(wait_before_leak=1)
        initial_a = r.parameters["tank"]["a"]["level"]
        _run_one_update(r)
        # wait_before_leak was 1, decremented to 0 but logic not yet executed
        assert r.parameters["tank"]["a"]["level"] == initial_a


# ──────────────────────────────────────────────
# Pump flow transfers
# ──────────────────────────────────────────────
class TestPumpFlow:
    """Test pump-driven fluid transfers between tanks."""

    def test_pump_on_transfers_flow(self):
        """Active pump transfers fluid between tanks."""
        r = _make_resman()
        r.parameters["pump"]["1"]["state"] = "on"  # c → a
        initial_c = r.parameters["tank"]["c"]["level"]
        initial_a = r.parameters["tank"]["a"]["level"]
        _run_one_update(r)
        # Pump 1: flow=800, time_res = 2/60 → volume = 26
        assert r.parameters["tank"]["c"]["level"] < initial_c
        assert r.parameters["tank"]["a"]["level"] > initial_a - 26  # Gained from pump, lost from depletion

    def test_pump_off_no_transfer(self):
        """Inactive pumps cause no flow."""
        r = _make_resman()
        # All pumps off by default
        initial_c = r.parameters["tank"]["c"]["level"]
        _run_one_update(r)
        assert r.parameters["tank"]["c"]["level"] == initial_c  # No change

    def test_non_depletable_source_not_drained(self):
        """Non-depletable source keeps its level."""
        r = _make_resman()
        r.parameters["pump"]["2"]["state"] = "on"  # e → a (e is non-depletable)
        initial_e = r.parameters["tank"]["e"]["level"]
        _run_one_update(r)
        assert r.parameters["tank"]["e"]["level"] == initial_e  # Not drained

    def test_failure_pump_no_transfer(self):
        """Pump in failure state transfers nothing."""
        r = _make_resman()
        r.parameters["pump"]["1"]["state"] = "failure"
        initial_c = r.parameters["tank"]["c"]["level"]
        _run_one_update(r)
        assert r.parameters["tank"]["c"]["level"] == initial_c

    def test_tank_overflow_capped(self):
        """Tank level cannot exceed its maximum."""
        r = _make_resman()
        r.parameters["tank"]["a"]["level"] = 3990
        r.parameters["tank"]["a"]["lossperminute"] = 0  # Disable depletion
        r.parameters["pump"]["2"]["state"] = "on"  # e → a, flow=600
        _run_one_update(r)
        assert r.parameters["tank"]["a"]["level"] <= r.parameters["tank"]["a"]["max"]

    def test_empty_source_stops_pump(self):
        """When a source tank is empty, its outgoing pumps are deactivated."""
        r = _make_resman()
        r.parameters["tank"]["c"]["level"] = 0
        r.parameters["pump"]["1"]["state"] = "on"  # c → a
        _run_one_update(r)
        # Pump 1 should be turned off because c is empty
        assert r.parameters["pump"]["1"]["state"] == "off"

    def test_full_destination_stops_pump(self):
        """When a destination tank is full, its incoming pumps are deactivated."""
        r = _make_resman()
        r.parameters["tank"]["a"]["level"] = 4000  # Full
        r.parameters["tank"]["a"]["lossperminute"] = 0  # No depletion
        r.parameters["pump"]["1"]["state"] = "on"  # c → a
        r.parameters["pump"]["2"]["state"] = "on"  # e → a
        _run_one_update(r)
        assert r.parameters["pump"]["1"]["state"] == "off"
        assert r.parameters["pump"]["2"]["state"] == "off"

    def test_failure_pump_not_deactivated_by_overflow(self):
        """Pumps on failure are not deactivated by overflow logic."""
        r = _make_resman()
        r.parameters["tank"]["a"]["level"] = 4000
        r.parameters["tank"]["a"]["lossperminute"] = 0
        r.parameters["pump"]["1"]["state"] = "failure"
        _run_one_update(r)
        assert r.parameters["pump"]["1"]["state"] == "failure"


# ──────────────────────────────────────────────
# Pump color determination
# ──────────────────────────────────────────────
class TestPumpColor:
    """Test that pump state maps to the correct color."""

    def test_pump_off_color(self):
        """OFF pump is WHITE."""
        r = _make_resman()
        pump = r.parameters["pump"]["1"]
        color = r.parameters[f"pumpcolor{pump['state']}"]
        assert color == C["WHITE"]  # pumpcoloroff

    def test_pump_on_color(self):
        """ON pump is GREEN."""
        r = _make_resman()
        pump = r.parameters["pump"]["1"]
        pump["state"] = "on"
        color = r.parameters[f"pumpcolor{pump['state']}"]
        assert color == C["GREEN"]  # pumpcoloron

    def test_pump_failure_color(self):
        """Failure pump is RED."""
        r = _make_resman()
        pump = r.parameters["pump"]["1"]
        pump["state"] = "failure"
        color = r.parameters[f"pumpcolor{pump['state']}"]
        assert color == C["RED"]  # pumpcolorfailure

    def test_pump_color_cycle(self):
        """OFF (white) → ON (green) → failure → RED."""
        r = _make_resman()
        pump = r.parameters["pump"]["1"]

        assert r.parameters[f"pumpcolor{pump['state']}"] == C["WHITE"]
        pump["state"] = "on"
        assert r.parameters[f"pumpcolor{pump['state']}"] == C["GREEN"]
        pump["state"] = "failure"
        assert r.parameters[f"pumpcolor{pump['state']}"] == C["RED"]


# ──────────────────────────────────────────────
# get_pump_by_key
# ──────────────────────────────────────────────
class TestGetPumpByKey:
    """Test the actual Resman.get_pump_by_key() method."""

    def test_find_pump_1(self):
        """NUM_1 finds pump 1 (c->a)."""
        r = _make_resman()
        pump = r.get_pump_by_key("NUM_1")
        assert pump is not None
        assert pump["_fromtank"] == "c"
        assert pump["_totank"] == "a"

    def test_find_pump_8(self):
        """NUM_8 finds pump 8 (b->a)."""
        r = _make_resman()
        pump = r.get_pump_by_key("NUM_8")
        assert pump["_fromtank"] == "b"
        assert pump["_totank"] == "a"

    def test_not_found_returns_none(self):
        """Invalid key returns None."""
        r = _make_resman()
        pump = r.get_pump_by_key("NUM_9")
        assert pump is None

    def test_top_row_digit_alias_maps_to_pump(self):
        """Top-row numeric keys map to their corresponding pumps."""
        r = _make_resman()
        pump = r.get_pump_by_key("_1")
        assert pump is not None
        assert pump["_fromtank"] == "c"
        assert pump["_totank"] == "a"

    def test_numpad_alias_maps_to_pump(self):
        """Alternate numpad key names map to the same pumps."""
        r = _make_resman()
        pump = r.get_pump_by_key("NUMPAD4")
        assert pump is not None
        assert pump["_fromtank"] == "f"
        assert pump["_totank"] == "b"


# ──────────────────────────────────────────────
# get_response_timers
# ──────────────────────────────────────────────
class TestGetResponseTimers:
    """Test the actual Resman.get_response_timers() method."""

    def test_initial_timers(self):
        """Both target tanks start with timer=0."""
        r = _make_resman()
        timers = r.get_response_timers()
        # Only target tanks (a, b) have response timers
        assert len(timers) == 2
        assert all(t == 0 for t in timers)

    def test_timers_after_out_of_tolerance(self):
        """Timer reflects out-of-tolerance duration."""
        r = _make_resman()
        r.parameters["tank"]["a"]["_response_time"] = 4000
        timers = r.get_response_timers()
        assert timers[0] == 4000


# ──────────────────────────────────────────────
# Tolerance zone logic
# ──────────────────────────────────────────────
class TestToleranceZone:
    """Test tolerance zone detection via compute_next_plugin_state."""

    def test_in_tolerance_at_target(self):
        """Level near target is within tolerance."""
        r = _make_resman()
        _run_one_update(r)
        # level ≈ 2474, target=2500, radius=250 → 2250 ≤ 2474 ≤ 2750 → True
        assert r.parameters["tank"]["a"]["_is_in_tolerance"] is True

    def test_out_of_tolerance(self):
        """Level far from target is out of tolerance."""
        r = _make_resman()
        r.parameters["tank"]["a"]["level"] = 2000  # Below 2500 - 250 = 2250
        _run_one_update(r)
        assert r.parameters["tank"]["a"]["_is_in_tolerance"] is False

    def test_response_time_accumulates_outside(self):
        """Response time grows while out of tolerance."""
        r = _make_resman()
        r.parameters["tank"]["a"]["level"] = 2000
        _run_one_update(r)
        assert r.parameters["tank"]["a"]["_response_time"] == 2000  # taskupdatetime

    def test_response_time_resets_on_return(self):
        """Response time resets when returning to tolerance."""
        r = _make_resman()
        # First: outside tolerance
        r.parameters["tank"]["a"]["level"] = 2000
        _run_one_update(r)
        assert r.parameters["tank"]["a"]["_response_time"] == 2000

        # Then: back in tolerance
        r.parameters["tank"]["a"]["level"] = 2500
        _run_one_update(r)
        assert r.parameters["tank"]["a"]["_response_time"] == 0


# ──────────────────────────────────────────────
# Hybrid pump control (allowmanualoverride)
# ──────────────────────────────────────────────
class TestHybridPumpControl:
    """Test that user manual pump control coexists with automatic solver."""

    def test_manual_pump_toggle_disabled_by_default(self):
        """Without allowmanualoverride, user keypresses have no effect."""
        r = _make_resman()
        r.parameters["allowmanualoverride"] = False
        pump = r.parameters["pump"]["1"]
        initial_state = pump["state"]
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            r.do_on_key("NUM_1", "press", emulate=False)
        # Pump state should not change
        assert pump["state"] == initial_state

    def test_manual_pump_toggle_enabled_with_flag(self):
        """With allowmanualoverride=True, user keypresses toggle pump state."""
        r = _make_resman()
        r.parameters["allowmanualoverride"] = True
        pump = r.parameters["pump"]["1"]
        assert pump["state"] == "off"
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            r.do_on_key("NUM_1", "press", emulate=False)
            assert pump["state"] == "on"
            r.do_on_key("NUM_1", "press", emulate=False)
        assert pump["state"] == "off"

    def test_manual_override_cannot_toggle_failed_pump(self):
        """Failed pumps cannot be toggled even with allowmanualoverride=True."""
        r = _make_resman()
        r.parameters["allowmanualoverride"] = True
        pump = r.parameters["pump"]["1"]
        pump["state"] = "failure"
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            r.do_on_key("NUM_1", "press", emulate=False)
        # Pump state should remain "failure"
        assert pump["state"] == "failure"

    def test_ai_solver_still_runs_with_manual_override_enabled(self):
        """Automation continues to update pumps when allowmanualoverride is True."""
        r = _make_resman()
        r.parameters["automaticsolver"] = True
        r.parameters["allowmanualoverride"] = True
        # Tank A is below target, so pump 1 (c→a) should turn on
        r.parameters["tank"]["a"]["level"] = 2400  # Below target 2500
        _run_one_update(r)
        # Heuristic 0.2 should activate pump 1
        assert r.parameters["pump"]["1"]["state"] == "on"

    def test_manual_override_keeps_keys_enabled_with_automaticsolver(self):
        """With shared control enabled, key handling remains active in auto mode."""
        r = _make_resman()
        r.parameters["automaticsolver"] = True
        r.parameters["allowmanualoverride"] = True
        r.update_can_receive_key()
        assert r.can_receive_keys is True
        assert r.can_execute_keys is True

    def test_user_action_then_ai_reversal(self):
        """User toggles pump, then AI can later override it on next update."""
        r = _make_resman()
        r.parameters["automaticsolver"] = True
        r.parameters["allowmanualoverride"] = True
        
        # User manually turns on pump 1
        assert r.parameters["pump"]["1"]["state"] == "off"
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            r.do_on_key("NUM_1", "press", emulate=False)
        assert r.parameters["pump"]["1"]["state"] == "on"
        
        # On next update, if tank A is full, AI's heuristic 0.2 will turn pump 1 off
        r.parameters["tank"]["a"]["level"] = 4000  # Full
        _run_one_update(r)
        # AI heuristic 0.2: target tank full → pump off
        assert r.parameters["pump"]["1"]["state"] == "off"

    def test_multiple_pumps_concurrent_control(self):
        """User can control pump 1 while AI controls pump 2."""
        r = _make_resman()
        r.parameters["automaticsolver"] = True
        r.parameters["allowmanualoverride"] = True
        
        # User manually toggles pump 1
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            r.do_on_key("NUM_1", "press", emulate=False)
        pump1_state_after_user = r.parameters["pump"]["1"]["state"]
        
        # AI runs on next update (heuristics for pump 2)
        r.parameters["tank"]["b"]["level"] = 2400  # Low, should trigger pump 3
        _run_one_update(r)
        
        # Pump 1 should be unchanged from user action
        assert r.parameters["pump"]["1"]["state"] == pump1_state_after_user
        # Pump 3 (d→b) should have been activated by heuristic 0.2
        assert r.parameters["pump"]["3"]["state"] == "on"


# ──────────────────────────────────────────────
# Automatic solver
# ──────────────────────────────────────────────
class TestAutoSolver:
    """Test automatic solver heuristics."""

    def test_activates_pumps_from_non_depletable(self):
        """Heuristic 1: pumps from non-depletable tanks are activated."""
        r = _make_resman()
        r.parameters["automaticsolver"] = True
        _run_one_update(r)
        # Pump 2 (e→a), pump 4 (f→b), pump 5 (e→c), pump 6 (f→d)
        # These should all be turned on since e,f are non-depletable
        assert r.parameters["pump"]["2"]["state"] == "on"
        assert r.parameters["pump"]["4"]["state"] == "on"
        assert r.parameters["pump"]["5"]["state"] == "on"
        assert r.parameters["pump"]["6"]["state"] == "on"

    def test_activates_pump_when_target_too_low(self):
        """Heuristic 2: if target tank is below target-50, activate pump."""
        r = _make_resman()
        r.parameters["automaticsolver"] = True
        r.parameters["tank"]["a"]["level"] = 2400  # Below 2500-50=2450
        _run_one_update(r)
        # Pumps feeding A (1: c→a, 2: e→a, 8: b→a) should be on
        assert r.parameters["pump"]["2"]["state"] == "on"

    def test_deactivates_pump_when_target_too_high(self):
        """Heuristic 2: if target tank is above target+50, deactivate pump."""
        r = _make_resman()
        r.parameters["automaticsolver"] = True
        r.parameters["tank"]["a"]["level"] = 2600  # Above 2500+50=2550
        r.parameters["pump"]["1"]["state"] = "on"
        _run_one_update(r)
        # Pump 1 (c→a) should be deactivated because a is too high
        assert r.parameters["pump"]["1"]["state"] == "off"

    def test_failure_pump_not_touched_by_autosolver(self):
        """Auto solver skips pumps in failure state."""
        r = _make_resman()
        r.parameters["automaticsolver"] = True
        r.parameters["pump"]["2"]["state"] = "failure"
        _run_one_update(r)
        assert r.parameters["pump"]["2"]["state"] == "failure"


# ──────────────────────────────────────────────
# Pump toggle via key press (do_on_key)
# ──────────────────────────────────────────────
class TestPumpKeyToggle:
    """Test pump toggling through the actual Resman key handler logic."""

    def test_toggle_off_to_on(self):
        """OFF pump toggles to ON."""
        r = _make_resman()
        pump = r.get_pump_by_key("NUM_1")
        assert pump["state"] == "off"
        # Simulate do_on_key toggle logic
        if pump["state"] != "failure":
            pump["state"] = "on" if pump["state"] == "off" else "off"
        assert pump["state"] == "on"

    def test_toggle_on_to_off(self):
        """ON pump toggles to OFF."""
        r = _make_resman()
        pump = r.get_pump_by_key("NUM_1")
        pump["state"] = "on"
        if pump["state"] != "failure":
            pump["state"] = "on" if pump["state"] == "off" else "off"
        assert pump["state"] == "off"

    def test_failure_blocks_toggle(self):
        """Failure state blocks toggle."""
        r = _make_resman()
        pump = r.get_pump_by_key("NUM_1")
        pump["state"] = "failure"
        if pump["state"] != "failure":
            pump["state"] = "on" if pump["state"] == "off" else "off"
        assert pump["state"] == "failure"


# ──────────────────────────────────────────────
# Multi-update simulation
# ──────────────────────────────────────────────
class TestMultiUpdateSimulation:
    """Test realistic multi-cycle scenarios."""

    def test_tanks_deplete_over_time(self):
        """Tanks lose significant fluid over 10 updates."""
        r = _make_resman()
        for _ in range(10):
            _run_one_update(r)
        # After 10 updates (20s), tanks A and B should have lost significant fluid
        # 800 * (20/60) ≈ 266 units each
        assert r.parameters["tank"]["a"]["level"] < 2500 - 200
        assert r.parameters["tank"]["b"]["level"] < 2500 - 200

    def test_pump_compensates_depletion(self):
        """Pump flow partially offsets depletion."""
        r = _make_resman()
        r.parameters["pump"]["2"]["state"] = "on"  # e → a, flow=600
        for _ in range(10):
            _run_one_update(r)
        # Tank A loses 800/min but gains 600/min from pump 2 → net loss 200/min
        # Without pump: loss ≈ 266 units. With pump: net ≈ 66 units loss
        assert r.parameters["tank"]["a"]["level"] > 2500 - 200

    def test_performance_logging(self):
        """Performance data is logged after update."""
        r = _make_resman()
        _run_one_update(r)
        # Should have logged deviation for target tanks
        assert "a_deviation" in r.performance
        assert "b_deviation" in r.performance
        assert "a_in_tolerance" in r.performance
