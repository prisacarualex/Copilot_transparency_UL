# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import re
from typing import Any, Callable

from core import validation
from core.constants import COLORS as C
from core.widgets import Frame, SimpleHTML
from plugins.abstractplugin import AbstractPlugin


class Copilot(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "topright", taskupdatetime: int = 1000) -> None:
        super().__init__(_("Co-pilot Explanations"), taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any] | tuple[Callable[..., Any], list[str]]] = {
            "transparency": (validation.is_in_list, ["transparent", "opaque"]),
            "maxvisiblemessages": validation.is_positive_integer,
        }

        new_par: dict[str, Any] = dict(
            transparency="transparent",
            maxvisiblemessages=10,
        )
        self.parameters.update(new_par)
        self.history: list[str] = []
        self.message_index: int = 0

    def create_widgets(self) -> None:
        super().create_widgets()

        # Keep content below the plugin title strip when titles are enabled.
        panel_container = self.task_container

        # Visual frame for copilot explanations
        self.add_widget(
            "border",
            Frame,
            container=panel_container,
            border_thickness=0.01,
            border_color=C["DARKGREY"],
            fill_color=C["BACKGROUND"],
            draw_order=self.m_draw + 1,
        )

        # HTML label to display history and status.
        # SimpleHTML expects normalized coordinates (0..1) relative to the container.
        # Positioned with generous padding and wrap for robustness across systems.
        # Font size uses pyglet HTML size 4 (~18pt) for cross-platform consistency.
        self.add_widget(
            "text",
            SimpleHTML,
            container=panel_container,
            text=self.get_formatted_text(),
            x=0.50,
            y=0.95,
            wrap_width=0.88,
            anchor_x="center",
            anchor_y="top",
            draw_order=self.m_draw + 2,
        )

    def explain(self, text: str) -> None:
        # Prepend the scenario time in MM:SS format
        m, s = divmod(int(self.scenario_time), 60)
        timestamp = f"{m:02d}:{s:02d}"
        plain = self._strip_html(text)
        simple = self._simplify_text(plain)
        entry = f"[{timestamp}] {simple}"

        self.history.append(entry)
        max_visible = int(self.parameters.get("maxvisiblemessages", 3))
        if len(self.history) > max_visible:
            self.history.pop(0)

        # Log every co-pilot action and whether it was shown to the participant.
        # The action is recorded identically in both conditions; the 'displayed'
        # flag (True only in transparent mode) enables a manipulation check and
        # time-window segmentation of the cognitive control strategy.
        displayed = self.parameters["transparency"] == "transparent"
        logger = getattr(self, "logger", None)
        if logger is not None:
            logger.log_performance("copilot", "explanation_displayed", displayed)
            logger.log_performance("copilot", "explanation_text", plain)

        # If widgets are already created, refresh text immediately
        text_widget = self.get_widget("text")
        if text_widget is not None:
            text_widget.set_text(self.get_formatted_text())

    @staticmethod
    def _strip_html(text: str) -> str:
        """Return a plain-text version of an explanation, safe for CSV logging."""
        plain = text.replace("<br>", " ")
        plain = re.sub(r"<[^>]+>", "", plain)
        plain = plain.replace("&nbsp;", " ")
        return re.sub(r"\s+", " ", plain).strip()

    @staticmethod
    def _simplify_text(text: str) -> str:
        """Shorten and simplify explanation text for on-screen readability."""
        simplified = text
        simplified = simplified.replace("manual intervention", "manual")
        simplified = simplified.replace("automatic solver", "auto")
        simplified = simplified.replace("transfer from Tank ", "")
        simplified = simplified.replace(" to Tank ", " -> ")
        simplified = simplified.replace("turned ", "")
        simplified = re.sub(r"\s*[—-]\s*", " - ", simplified)
        simplified = re.sub(r"\s+", " ", simplified).strip()

        if len(simplified) > 78:
            simplified = simplified[:75].rstrip() + "..."
        return simplified

    def get_formatted_text(self) -> str:
        # Font size 4 in pyglet HTML is approximately 18pt and reasonably consistent across systems.
        # Use explicit line-height spacing via line breaks for better readability.
        font_tag = '<font size="4" face="Courier New, monospace">'
        close_font = "</font>"

        if self.parameters["transparency"] == "opaque":
            # Neutral panel: identical visual weight to the transparent panel,
            # but content-free. It must NOT reveal that explanations exist and
            # are being withheld, otherwise the manipulation would differ by
            # meta-awareness rather than by explanation content alone.
            return f"<center><b>{font_tag}Co-pilot: ACTIVE</b><br>Monitoring...{close_font}</center>"

        if not self.history:
            return f"<center><b>{font_tag}Co-pilot: ACTIVE</b><br>Waiting for actions...{close_font}</center>"

        # Display history items with extra spacing for robustness and readability.
        # Monospace font ensures consistent column alignment across systems.
        items_html = "<br><br>".join(self.history)
        return f"<p align=\"center\">{font_tag}{items_html}{close_font}</p>"

    def refresh_widgets(self) -> bool:
        if not super().refresh_widgets():
            return False

        text_widget = self.get_widget("text")
        if text_widget is not None:
            text_widget.set_text(self.get_formatted_text())
        return True
