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
            maxvisiblemessages=6,
        )
        self.parameters.update(new_par)
        self.history: list[str] = []
        self.message_index: int = 0

    def create_widgets(self) -> None:
        super().create_widgets()

        # Visual frame for copilot explanations
        self.add_widget(
            "border",
            Frame,
            container=self.task_container,
            border_thickness=0.01,
            border_color=C["DARKGREY"],
            fill_color=C["WHITE"],
        )

        # HTML label to display history and status.
        # anchor_y="top" + y=0.97 means text flows downward from near the top
        # of the container, so it stays visible regardless of message count.
        self.add_widget(
            "text",
            SimpleHTML,
            container=self.task_container,
            text=self.get_formatted_text(),
            x=0.5,
            y=0.97,
            wrap_width=0.9,
            anchor_x="center",
            anchor_y="top",
        )

    def explain(self, text: str) -> None:
        # Prepend the scenario time in MM:SS format
        m, s = divmod(int(self.scenario_time), 60)
        timestamp = f"{m:02d}:{s:02d}"
        self.message_index = getattr(self, "message_index", 0) + 1
        entry = f"<b>#{self.message_index:03d} [{timestamp}]</b> {text}"

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
            plain = self._strip_html(text)
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

    def get_formatted_text(self) -> str:
        if self.parameters["transparency"] == "opaque":
            # Neutral panel: identical visual weight to the transparent panel,
            # but content-free. It must NOT reveal that explanations exist and
            # are being withheld, otherwise the manipulation would differ by
            # meta-awareness rather than by explanation content alone.
            return "<center><h2>Co-pilot Status: ACTIVE</h2><p>Monitoring systems...</p></center>"

        if not self.history:
            return "<center><h2>Co-pilot Status: ACTIVE</h2><p>Awaiting automated actions...</p></center>"

        # Display history items separated by spacing
        items_html = "<br>".join(self.history)
        return f"<p>{items_html}</p>"

    def refresh_widgets(self) -> bool:
        if not super().refresh_widgets():
            return False

        text_widget = self.get_widget("text")
        if text_widget is not None:
            text_widget.set_text(self.get_formatted_text())
        return True
