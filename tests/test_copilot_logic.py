"""Tests for plugins.copilot - Co-pilot Explanations panel logic.

Covers the transparency manipulation (transparent vs opaque), the rolling
explanation history, timestamp formatting, widget refresh, and the
cross-plugin `explain()` entry-point used by sysmon and resman.

Instances are built with object.__new__() to bypass __init__ (which needs the
gettext/_ and Window singletons) following the pattern of test_sysmon_logic.py.
"""

from unittest.mock import MagicMock

from core import validation
from plugins.copilot import Copilot


def _make_copilot(transparency="transparent", with_widget=False):
    c = object.__new__(Copilot)
    c.alias = "copilot"
    c.scenario_time = 0
    c.alive = True
    c.paused = False
    c.visible = True
    c.history = []
    c.parameters = dict(transparency=transparency)
    c.widgets = {}
    if with_widget:
        text_widget = MagicMock()
        c.widgets["copilot_text"] = text_widget
    return c


# ──────────────────────────────────────────────
# Validation / configuration
# ──────────────────────────────────────────────


def test_transparency_validation_accepts_valid_levels():
    # is_in_list returns (value, error); error is None on success
    levels = ["transparent", "opaque"]
    assert validation.is_in_list("transparent", levels)[1] is None
    assert validation.is_in_list("opaque", levels)[1] is None


def test_transparency_validation_rejects_invalid_level():
    levels = ["transparent", "opaque"]
    assert validation.is_in_list("semitransparent", levels)[1] is not None


# ──────────────────────────────────────────────
# explain() history behaviour
# ──────────────────────────────────────────────


def test_explain_appends_entry_with_timestamp():
    c = _make_copilot()
    c.scenario_time = 75  # 75s -> 01:15
    c.explain("Pump 1 turned ON.")
    assert len(c.history) == 1
    assert "[01:15]" in c.history[0]
    assert "Pump 1 ON." in c.history[0]


def test_explain_timestamp_zero_padded():
    c = _make_copilot()
    c.scenario_time = 5  # 00:05
    c.explain("x")
    assert "[00:05]" in c.history[0]


def test_explain_history_capped_at_three():
    c = _make_copilot()
    for i in range(5):
        c.scenario_time = i
        c.explain(f"event {i}")
    assert len(c.history) == 3
    # Oldest two dropped, newest retained
    assert "event 2" in c.history[0]
    assert "event 4" in c.history[2]


def test_explain_refreshes_existing_text_widget():
    c = _make_copilot(with_widget=True)
    c.explain("hello")
    c.widgets["copilot_text"].set_text.assert_called_once()


def test_explain_no_widget_does_not_raise():
    c = _make_copilot(with_widget=False)
    c.explain("hello")  # should not raise even though no widget exists
    assert len(c.history) == 1


# ──────────────────────────────────────────────
# get_formatted_text() rendering
# ──────────────────────────────────────────────


def test_transparent_empty_history_shows_awaiting():
    c = _make_copilot("transparent")
    html = c.get_formatted_text()
    assert "Waiting" in html
    assert "ACTIVE" in html


def test_transparent_with_history_lists_entries():
    c = _make_copilot("transparent")
    c.scenario_time = 10
    c.explain("Pump 2 turned OFF.")
    html = c.get_formatted_text()
    assert "Pump 2 OFF." in html
    assert "Waiting" not in html


def test_opaque_hides_explanations_even_with_history():
    c = _make_copilot("opaque")
    c.scenario_time = 10
    c.explain("Pump 2 turned OFF.")  # history still recorded internally
    html = c.get_formatted_text()
    # Panel stays neutral and active...
    assert "ACTIVE" in html
    # ...the actual explanation text must NOT be displayed in opaque mode...
    assert "Pump 2 turned OFF." not in html
    # ...and it must NOT reveal that explanations are being withheld
    # (otherwise the manipulation would differ by meta-awareness).
    assert "opaque" not in html.lower()
    assert "disabled" not in html.lower()


# ──────────────────────────────────────────────
# Logging of co-pilot actions (manipulation check)
# ──────────────────────────────────────────────


def test_explain_logs_action_when_transparent():
    c = _make_copilot("transparent")
    c.logger = MagicMock()
    c.scenario_time = 30
    c.explain("Pump 1 turned <b>ON</b>.<br>&nbsp;&nbsp;<i>Reason: tank low</i>")

    calls = c.logger.log_performance.call_args_list
    metrics = {args[0][1]: args[0][2] for args in calls}
    assert metrics["explanation_displayed"] is True
    # HTML is stripped for the CSV log
    assert "<b>" not in metrics["explanation_text"]
    assert "Pump 1 turned ON." in metrics["explanation_text"]
    assert "Reason: tank low" in metrics["explanation_text"]


def test_explain_logs_action_but_marks_not_displayed_when_opaque():
    c = _make_copilot("opaque")
    c.logger = MagicMock()
    c.scenario_time = 30
    c.explain("Pump 1 turned ON.")

    calls = c.logger.log_performance.call_args_list
    metrics = {args[0][1]: args[0][2] for args in calls}
    # The co-pilot action is still recorded (identical AI behaviour)...
    assert "Pump 1 turned ON." in metrics["explanation_text"]
    # ...but flagged as not shown to the participant.
    assert metrics["explanation_displayed"] is False


def test_strip_html_removes_markup():
    assert (
        Copilot._strip_html("<b>[01:15]</b> Pump&nbsp;1 <i>ON</i>")
        == "[01:15] Pump 1 ON"
    )


# ──────────────────────────────────────────────
# refresh_widgets()
# ──────────────────────────────────────────────


def test_refresh_widgets_updates_text_when_visible(monkeypatch):
    c = _make_copilot("transparent", with_widget=True)
    # Patch AbstractPlugin.refresh_widgets (super) to return True
    monkeypatch.setattr("plugins.copilot.AbstractPlugin.refresh_widgets", lambda self: True)
    assert c.refresh_widgets() is True
    c.widgets["copilot_text"].set_text.assert_called()


def test_refresh_widgets_returns_false_when_super_false(monkeypatch):
    c = _make_copilot("transparent", with_widget=True)
    monkeypatch.setattr("plugins.copilot.AbstractPlugin.refresh_widgets", lambda self: False)
    assert c.refresh_widgets() is False
    c.widgets["copilot_text"].set_text.assert_not_called()


# ──────────────────────────────────────────────
# Experiment scenario files validate end-to-end
# ──────────────────────────────────────────────


def _parse_scenario_events(filename):
    """Parse a real scenario file into Event objects (no plugin instantiation,
    since some real plugins open audio devices that block in headless CI)."""
    from core.constants import PATHS as P
    from core.event import Event

    path = P["SCENARIOS"].joinpath(filename)
    with open(path, "r") as f:
        contents = f.readlines()
    return [
        Event.parse_from_string(n, line)
        for n, line in enumerate(contents)
        if len(line.strip()) > 0 and not line.startswith("#")
    ]


def test_transparent_scenario_parses_and_targets_known_plugins():
    import plugins as plugins_module

    events = _parse_scenario_events("transparency_transparent.txt")
    assert len(events) > 0
    for e in events:
        if e.plugin in ("__system__", "system"):
            continue
        assert hasattr(plugins_module, e.plugin.capitalize()), e.plugin


def test_opaque_scenario_parses_and_targets_known_plugins():
    import plugins as plugins_module

    events = _parse_scenario_events("transparency_opaque.txt")
    assert len(events) > 0
    for e in events:
        if e.plugin in ("__system__", "system"):
            continue
        assert hasattr(plugins_module, e.plugin.capitalize()), e.plugin


def test_scenario_copilot_transparency_values_validate():
    """The transparency value set in each scenario must pass the Copilot
    plugin's own validation rule."""
    levels = ["transparent", "opaque"]
    for fname, expected in [
        ("transparency_transparent.txt", "transparent"),
        ("transparency_opaque.txt", "opaque"),
    ]:
        events = _parse_scenario_events(fname)
        cmds = [e.command for e in events if e.plugin == "copilot" and e.command[0] == "transparency"]
        assert len(cmds) == 1
        assert cmds[0][1] == expected
        assert validation.is_in_list(cmds[0][1], levels)[1] is None


def test_both_scenarios_only_differ_in_transparency_level():
    """Control-variable check: the two condition scenarios must be identical
    except for the copilot transparency parameter, so AI behaviour and task
    difficulty are held constant between conditions."""
    from core.constants import PATHS as P

    def _significant_lines(name):
        with open(P["SCENARIOS"].joinpath(name)) as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    t = _significant_lines("transparency_transparent.txt")
    o = _significant_lines("transparency_opaque.txt")
    assert len(t) == len(o)

    diffs = [(a, b) for a, b in zip(t, o) if a != b]
    # The only difference must be the transparency level line
    assert all("copilot;transparency" in a for a, _b in diffs)
    assert any("transparent" in a and "opaque" in b for a, b in diffs)
