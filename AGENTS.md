# AGENTS.md

Repository guidance for AI coding agents working in this OpenMATB variant.

## Start Here

- Read [README.md](README.md) for runtime usage, scenarios, and session logs.
- Read [BUILDING.md](BUILDING.md) before touching standalone build scripts or release packaging.
- Treat this file as the short path: only project-specific constraints that are easy to miss belong here.

## Repo Map

- `core/`: framework code shared by all tasks and widgets.
- `plugins/`: task modules and integrations. Most behavior changes belong here, not in `main.py`.
- `core/widgets/`: reusable UI primitives used by plugins.
- `tests/`: unit tests with heavy mocking for Pyglet/OpenGL and global singletons.
- `includes/scenarios/`: scenario inputs, including transparency study scenarios.

## Common Commands

- Install runtime dependencies: `python -m pip install -r requirements.txt`
- Install dev dependencies: `python -m pip install -r requirements-dev.txt`
- Run the app: `python main.py`
- Run tests: `pytest`
- Run lint: `ruff check .`

## Working Rules

- Preserve the gettext bootstrap order in `main.py`: language installation must happen before importing translated `core` or `plugins` modules.
- Prefer fixing behavior in the owning plugin, widget, or scheduler path rather than patching around it in startup wiring.
- Keep changes compatible with Python 3.9. Ruff ignores some newer rewrites intentionally.
- Respect existing style choices in [ruff.toml](ruff.toml), especially the allowed short geometry names (`l`, `b`, `w`, `h`) and established wildcard imports in widgets.
- Avoid broad refactors in rendering, window, or widget code unless the task clearly requires it; many tests depend on the current interfaces.

## Tests And Mocks

- `tests/conftest.py` installs `builtins._` and mocks Pyglet/OpenGL before application imports. Reuse that pattern when adding tests for UI-heavy code.
- Many tests instantiate objects with `object.__new__(...)` to bypass side effects in `__init__`. Follow nearby tests before introducing heavier fixtures.
- If a change touches plugin logic, look for a focused `tests/test_*_logic.py` file before running broader checks.

## Plugin Conventions

- New or changed scenario-facing plugin parameters should be validated through `validation_dict` on the plugin class.
- `AbstractPlugin` owns lifecycle state (`start`, `stop`, `pause`, `resume`, visibility, key handling). Keep plugin subclasses aligned with that lifecycle instead of duplicating state logic.
- Scenario and UI text may be translated through `_()`. Do not move translated imports ahead of language installation.

## Build And Runtime Pitfalls

- Standalone builds write session logs next to the executable, so they must run from a writable directory.
- Packaged builds embed `config.ini`, `includes/`, and locale data at build time. If behavior depends on those assets, check [BUILDING.md](BUILDING.md) before changing paths.
- Headless environments usually cannot run the real app because of Pyglet/OpenGL requirements; prefer tests for validation unless the task explicitly needs manual runtime verification.

## Good Anchors

- Plugin lifecycle: [plugins/abstractplugin.py](plugins/abstractplugin.py)
- Transparency study logic: [plugins/copilot.py](plugins/copilot.py)
- Startup and language bootstrap: [main.py](main.py)
- Test harness and import stubs: [tests/conftest.py](tests/conftest.py)