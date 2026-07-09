"""Tests for resilient joystick discovery."""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock


def _load_joystick_module(get_joysticks):
    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = []

    constants_mod = types.ModuleType("core.constants")
    constants_mod.REPLAY_MODE = False

    errors_mod = types.ModuleType("core.error")
    errors_mod.get_errors = lambda: MagicMock(add_error=MagicMock())

    logger_mod = types.ModuleType("core.logger")
    logger_mod.get_logger = lambda: MagicMock(record_input=MagicMock())

    pyglet_mod = types.ModuleType("pyglet")
    pyglet_input_mod = types.ModuleType("pyglet.input")
    pyglet_input_mod.get_joysticks = get_joysticks
    pyglet_mod.input = pyglet_input_mod

    old_modules = dict(sys.modules)
    sys.modules.update(
        {
            "core": core_pkg,
            "core.constants": constants_mod,
            "core.error": errors_mod,
            "core.logger": logger_mod,
            "pyglet": pyglet_mod,
            "pyglet.input": pyglet_input_mod,
        }
    )

    try:
        module_path = Path(__file__).resolve().parents[1] / "core" / "joystick.py"
        spec = importlib.util.spec_from_file_location("_test_core_joystick", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.clear()
        sys.modules.update(old_modules)


class TestGetAvailableJoysticks:
    def test_returns_empty_list_when_linux_input_dir_is_missing(self):
        """Missing /dev/input should not prevent application startup."""
        module = _load_joystick_module(lambda: (_ for _ in ()).throw(FileNotFoundError()))
        assert module.get_available_joysticks() == []

    def test_returns_pyglet_results_when_discovery_succeeds(self):
        """Successful discovery passes the joystick list through unchanged."""
        joysticks = [
            types.SimpleNamespace(open=lambda: None, buttons=[], hat_x=0, hat_y=0, x=0, y=0),
            types.SimpleNamespace(open=lambda: None, buttons=[], hat_x=0, hat_y=0, x=0, y=0),
        ]
        module = _load_joystick_module(lambda: joysticks)
        assert module.get_available_joysticks() == joysticks