# Co-Pilot Transparency — Experiment Manual

A practical guide to running the **AI Co-Pilot Transparency** study in OpenMATB:
how to start it, what the participant sees and does in each condition, and how
the Resource Management (tank) task works.

---

## 1. Quick start (experimenter)

### 1.1 Install (once)

From the project folder:

```bash
python -m pip install -r requirements.txt
```

(Use `py` on Windows, `python3` on Linux/Mac if `python` is not found.)

### 1.2 Choose the condition

There are two scenario files, identical in every way **except** the co-pilot
transparency level:

| Condition    | Scenario file |
|--------------|---------------|
| Transparent  | [includes/scenarios/transparency_transparent.txt](includes/scenarios/transparency_transparent.txt) |
| Opaque       | [includes/scenarios/transparency_opaque.txt](includes/scenarios/transparency_opaque.txt) |

Select one in two ways:

- **Easiest:** leave `scenario_path=` empty in [config.ini](config.ini) and a
  file picker appears at launch — choose the scenario there.
- **Fixed assignment:** set the line in [config.ini](config.ini), e.g.
  `scenario_path=transparency_transparent.txt`.

### 1.3 Launch

```bash
python main.py
```

> **Language:** [config.ini](config.ini) ships with `language=en_EN`. The
> built-in questionnaires used by the scenario are the English versions
> (`nasatlx_en.txt`, `trust_en.txt`). For a fully English session set
> `language=en_EN`.

### 1.4 During / after a run

- **Pause:** press `P` or `Escape`.
- **Quit:** close the window (or pause, then quit).
- **Data:** every run writes a timestamped CSV under [sessions/](sessions/).

---

## 2. Equipment required

- **No joystick is needed.** The Tracking task is driven from the keyboard
  with the `W` `A` `S` `D` keys (see Section 4.1). A joystick may still be
  connected, but it is not required.
- A full keyboard with **function keys** `F1`–`F6` (system monitoring) and,
  optionally, a **numeric keypad** (`NUM_1`–`NUM_8`, only if you enable manual
  tank pumping).
- Speakers/headphones (the Communications task plays spoken radio calls).

---

## 3. The screen at a glance

```
+---------------------+----------------------+---------------------+
|  SYSTEM MONITORING  |       TRACKING       |     CO-PILOT        |
|   (sysmon, F1–F6)   |  (W/A/S/D cursor)    |   (explanations)    |
| [AI + operator can  |                      |   top-right panel   |
|   override]         |                      |                     |
+---------------------+----------------------+---------------------+
|   COMMUNICATIONS    |  RESOURCE MGMT (tanks)                     |
|  (UP/DOWN/L/R/ENTER)|        [AUTOMATED]                         |
+---------------------+--------------------------------------------+
```

Four MATB tasks run at once, plus the **Co-pilot** panel (top-right).

**Key point about this study:** in both conditions the **System Monitoring**,
**Communications**, and **Resource Management** tasks are handled by the
automatic solver. The manipulation is only the co-pilot transparency panel
(`transparent` vs `opaque`).

The participant can still intervene manually in shared-control channels:
- **System Monitoring override** (`F1`–`F6`) is enabled.
- **Resource Management pump override** is enabled (`NUM_1`–`NUM_8`, with key aliases).
- **Tracking** remains manual (`W A S D`).

---

## 4. What the participant actively does

Because the co-pilot automates System Monitoring, Communications, and Resource
Management, the participant's primary hands-on task is **Tracking**, with
optional shared-control interventions in SysMon and ResMan, while they
**observe** the co-pilot panel.

### 4.1 Tracking (keyboard: W A S D)
Keep the moving cursor centred on the target reticle using the keyboard. This
is the continuous task and the main source of the **RMSE** performance measure.

| Action        | Key |
|---------------|-----|
| Move up       | `W` |
| Move down     | `S` |
| Move left     | `A` |
| Move right    | `D` |

Hold a key to keep pushing the cursor in that direction; release it to stop.
The tracking keys (`W A S D`) are deliberately distinct from the Communications
keys (`UP/DOWN/LEFT/RIGHT/ENTER`) so the two tasks never conflict.

### 4.1b System Monitoring override (optional)
The AI normally corrects gauge failures (`F1`–`F6`) by itself. If enabled, the
operator may **beat the AI to a fix** by pressing the failing gauge's key
during the short window before the AI acts. This is *shared human-AI control*
and is identical across both conditions.

### 4.2 Communications (automated in current setup)
Communications radio prompts are active, but radio handling is automated by the
AI co-pilot in the current experiment scenarios.

Manual communication keys remain available for non-automated pilot scenarios:

| Action                       | Key     |
|------------------------------|---------|
| Select radio (move up)       | `UP`    |
| Select radio (move down)     | `DOWN`  |
| Tune frequency up            | `RIGHT` |
| Tune frequency down          | `LEFT`  |
| Validate the setting         | `ENTER` |

Ignore calls addressed to other call-signs.

### 4.3 Observe the co-pilot (top-right) — *this is the manipulation*
See Section 5.

---

## 5. What explanations the participant gets

The co-pilot acts (it auto-corrects gauges and switches pumps). Each action is
recorded to the log in **both** conditions, but only **shown** in the
Transparent condition.

### Transparent condition
The panel shows a running, time-stamped log of the **last 10** co-pilot
actions. Text is simplified to reduce visual load and may truncate long
messages. The panel uses a monospace font for cross-platform consistency and
includes extra spacing between entries for improved readability on all
displays. Example:

```
[00:47] Pump 2 ON.

[01:05] Indicator F1 reset to normal.

[01:22] Manual: Pump 1 ON.
```

### Opaque condition
The panel stays neutral and content-free — it shows that the co-pilot is active
but gives **no explanations and no hint that any are being withheld**:

```
        Co-pilot Status: ACTIVE
        Monitoring systems...
```

The participant must therefore infer *why* the automation acts, which is the
**interpretive workload** the study manipulates.

> **Design note:** the opaque panel is deliberately *not* labelled
> "explanations disabled," so the two conditions differ only by explanation
> **content**, not by the participant's awareness that something is hidden.

### What is logged (for analysis)
Every co-pilot action writes two performance rows to the session CSV:

- `copilot / explanation_text` — the plain-text action + reason
- `copilot / explanation_displayed` — `True` (transparent) or `False` (opaque)

Additional current-study logging used for classification and behavior checks:
- `track / center_deviation`, `track / cursor_in_target`, `track / response_time`
- `resman / a_deviation`, `resman / b_deviation`, `resman / a_in_tolerance`, `resman / b_in_tolerance`
- `resman / pump_<n>_user_action` (manual pump overrides)
- `sysmon / signal_detection`, `sysmon / response_time`, `sysmon / name`
- `communications / sdt_value`, `communications / response_time`, radio/frequency correctness fields

This lets you verify the manipulation and segment the session into time windows
for the Proactive/Reactive classification.

---

## 6. The Resource Management (tank) task — how it works and how to control it

In the **experiment scenarios the tanks are automated**, but manual pump
override is enabled for shared-control behavior. Participants may intervene
using pump keys while the AI solver continues to run.

For the current transparency-study scenarios, **Pump 7 (A -> B)** is
scenario-overridden to **1500 units/min** so that manual transfer from Tank A
to Tank B has a clear visible effect after the **Pump 4 failure** anomaly.

### 6.1 The goal
Keep the two **target tanks, A and B**, near their target level of **2500**
units (inside the green tolerance band **2250–2750**). Each target tank
continuously **drains 800 units/minute**, so they must be refilled.

### 6.2 The plumbing (defaults)

| Tank | Capacity | Start | Target | Supply type            |
|------|----------|-------|--------|------------------------|
| A    | 4000     | 2500  | 2500   | must be kept in band   |
| B    | 4000     | 2500  | 2500   | must be kept in band   |
| C    | 2000     | 1000  | —      | limited reservoir      |
| D    | 2000     | 1000  | —      | limited reservoir      |
| E    | 4000     | 3000  | —      | **infinite** (no drain)|
| F    | 4000     | 3000  | —      | **infinite** (no drain)|

| Pump | Key     | Moves     | Flow |
|------|---------|-----------|------|
| 1    | `NUM_1` | C → A     | 800  |
| 2    | `NUM_2` | E → A     | 600  |
| 3    | `NUM_3` | D → B     | 800  |
| 4    | `NUM_4` | F → B     | 600  |
| 5    | `NUM_5` | E → C     | 600  |
| 6    | `NUM_6` | F → D     | 600  |
| 7    | `NUM_7` | A → B     | 400  (1500 in the transparency-study scenarios) |
| 8    | `NUM_8` | B → A     | 400  |

### 6.3 How you react / calibrate (manual mode)
- **Toggle a pump on/off:** press its number key on the **numeric keypad**
  (`NUM_1` … `NUM_8`). Green = ON, white = OFF, red = failed.
- A **failed** pump (red) cannot be switched on until it recovers; route around
  it using another pump.

**A simple keep-it-green strategy:**
1. Feed the target tanks from the **infinite** reservoirs E and F:
   keep **Pump 2 (E→A)** and **Pump 4 (F→B)** running.
2. Because each target tank loses 800/min and those pumps supply only 600/min,
   top up with **Pump 1 (C→A)** and **Pump 3 (D→B)** (flow 800) as the level
   approaches the lower edge (~2300), then switch them off near the upper edge
   (~2700).
3. Keep the limited tanks C and D supplied by running **Pump 5 (E→C)** and
   **Pump 6 (F→D)** so Pumps 1 and 3 don't run dry.
4. Use **Pump 7 (A→B)** / **Pump 8 (B→A)** only to balance a temporary
   imbalance between A and B.

The aim is to keep both A and B inside the green band as much as possible;
time spent outside the band is what the task scores against you.

### 6.4 Shared-control behavior (current experiment)
The shipped transparency scenarios run ResMan in hybrid mode:
- AI pumps are active (`automaticsolver=True`)
- Manual pump input is enabled (`allowmanualoverride=True`)
- User toggles are immediate; AI may revise pump states on the next update cycle
- Failed pumps cannot be manually toggled

---

## 7. Running one participant — step by step

1. Assign the participant to a condition (Transparent or Opaque).
2. Set the matching scenario in [config.ini](config.ini) (or pick it in the
   launch selector).
3. Confirm the keyboard is connected and `W A S D` move the tracking cursor.
4. Brief the participant (Section 8 script).
5. Run `python main.py`.
6. The 5-minute task block runs; tasks then stop automatically.
7. The participant completes the on-screen **NASA-TLX** then **Trust**
   questionnaires (these are chained automatically at the end of the scenario).
8. Collect the CSV from [sessions/](sessions/).

---

## 8. Participant briefing script (read aloud)

Use the **same** script for both groups, except the bracketed co-pilot line.

> "You will operate a flight-deck simulator with several tasks running at once.
> Your two active tasks are:
> (1) **Tracking** — keep the moving cursor centred with the `W A S D` keys; and
> (2) **Communications** — when you hear a radio call for *your* call-sign,
> select the right radio with Up/Down, tune the frequency with Left/Right, and
> press Enter; ignore calls for other call-signs.
>
> An **AI co-pilot** automatically manages gauges, radios, and fuel pumps.
> You always control Tracking, and you may also intervene on gauges/pumps.
>
> *[Transparent group:]* The co-pilot will **explain each action it takes** in
> the top-right panel.
> *[Opaque group:]* The co-pilot is active in the top-right panel.
>
> Try to keep all tasks running as well as you can for about five minutes.
> Afterwards you'll answer two short questionnaires. Any questions before we
> begin?"

Keep wording, timing, and the keyboard setup identical across participants —
these are your control variables.

---

## 9. Where the data is

- **Per-session CSV:** [sessions/](sessions/) — one folder per date, one file
  per run. Contains time-stamped events, inputs, performance (Tracking RMSE,
  tank deviation/tolerance, signal detection, response times) and the new
  `copilot / explanation_text` + `copilot / explanation_displayed` rows.
- For the dependent variable, segment each session into ~30 s windows and
  classify each window as **Proactive** or **Reactive** from the performance
  indicators, then compute the **% of time Proactive** per participant.

### 9.1 Evaluation scripts (checked)
- [analyze_session.py](analyze_session.py): single-session report.
  Uses 30s bins and classifies mode from:
  - Tracking RMSE based on `track / center_deviation`
  - ResMan deviation based on `resman / a_deviation` and `resman / b_deviation`
  Also reports survey sliders and now prints copilot manipulation-check counts
  (`explanation_displayed`, `explanation_text`) plus shared-control action counts.
- [visualize_results.py](visualize_results.py): multi-session aggregation figure
  (`sessions/analysis.png`) with condition split, proactive %, tracking/resman trends,
  and SysMon signal detection metrics.

### 9.2 Research framing (current proposal)
- **IV:** AI transparency (`transparent` vs `opaque`)
- **DV (primary):** proportion of time in Proactive vs Reactive control mode
- **Control strategy proxy:** 30s-bin classification using tracking + resman metrics
- **Manipulation check:** `copilot / explanation_displayed` and explanation logs
- **Hypothesis:** transparent condition increases time in Proactive mode

---

## 10. Technical notes: Co-pilot panel rendering robustness

The co-pilot explanation panel was optimized for reliable cross-platform display:

- **Font:** Monospace (Courier New with fallback) for consistent rendering across
  Windows, macOS, and Linux systems and different monitors.
- **Layout:** Position adjusted (x=0.50, y=0.95, wrap_width=0.88) with generous
  padding to prevent text clipping on different display resolutions.
- **Spacing:** Double line breaks between entries (`<br><br>`) improve
  readability and robustness against DPI/font-size rendering variations.
- **Size:** Font size 4 (~18pt in pyglet HTML) is the reference size used
  throughout OpenMATB for consistent system-wide rendering.

If text appears misaligned or truncated on any particular system:
1. Ensure the display refresh rate and scaling settings are consistent across
   test computers.
2. Check the window is not minimized or partially occluded.
3. If needed, adjust `wrap_width=` in [plugins/copilot.py](plugins/copilot.py)
   line ~55 (reduce to ~0.85 if text is still clipping).

---

## 11. Experimenter checklist

- [ ] Keyboard connected; `W A S D` move the tracking cursor.
- [ ] Correct scenario selected for the assigned condition.
- [ ] Language set as intended (`en_EN` current default).
- [ ] Audio working (radio calls audible).
- [ ] Briefing read identically; only the co-pilot sentence differs.
- [ ] Session CSV saved and labelled with participant ID + condition.
