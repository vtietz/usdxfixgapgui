from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QHeaderView, QTableView


@dataclass(frozen=True)
class ColumnDefaults:
    numeric_widths: dict[int, int]
    primary_ratios: Sequence[float]
    primary_min_width: int = 120
    primary_columns: Sequence[int] = (0, 1, 2)


class ColumnLayoutController(QObject):
    """Keeps table columns performant, resizable, and spanning viewport width."""

    def __init__(self, table: QTableView, defaults: ColumnDefaults) -> None:
        super().__init__(table)
        self._table = table
        self._defaults = defaults
        self._rebalance_guard = False
        self._initialized = False

    def apply_policy(self) -> None:
        header = self._table.horizontalHeader()
        if not self._initialized:
            header.sectionResized.connect(self._on_section_resized)
            self._initialized = True

        for idx in range(header.count()):
            header.setSectionResizeMode(idx, QHeaderView.ResizeMode.Interactive)
            if idx not in self._defaults.primary_columns:
                width = self._defaults.numeric_widths.get(idx)
                if width:
                    self._table.setColumnWidth(idx, width)

        QTimer.singleShot(0, self._rebalance_full_layout)

    def rebalance_viewport(self) -> None:
        self._rebalance()

    def _on_section_resized(self, *_args) -> None:
        self._rebalance()

    def _rebalance_full_layout(self) -> None:
        header = self._table.horizontalHeader()
        primaries = [idx for idx in self._defaults.primary_columns if idx < header.count()]
        if not primaries:
            return

        viewport_width = max(self._table.viewport().width(), self._table.width(), 600)
        fixed_total = sum(
            self._table.columnWidth(idx)
            for idx in range(header.count())
            if idx not in primaries
        )

        available = max(viewport_width - fixed_total, len(primaries) * self._defaults.primary_min_width)
        ratios = self._defaults.primary_ratios[: len(primaries)]
        ratio_sum = sum(ratios) or 1.0

        for pos, col in enumerate(primaries):
            share = ratios[pos] if pos < len(ratios) else ratios[-1]
            width = max(int(available * share / ratio_sum), self._defaults.primary_min_width)
            self._table.setColumnWidth(col, width)

        self._rebalance()

    def _rebalance(self) -> None:
        if self._rebalance_guard:
            return

        header = self._table.horizontalHeader()
        primaries = [idx for idx in self._defaults.primary_columns if idx < header.count()]
        if not primaries:
            return

        viewport_width = max(self._table.viewport().width(), self._table.width(), 0)
        if viewport_width == 0:
            return

        total_width = sum(self._table.columnWidth(idx) for idx in range(header.count()))
        diff = viewport_width - total_width
        if abs(diff) <= len(primaries):
            return

        self._rebalance_guard = True
        try:
            self._adjust_primaries(primaries, diff)
        finally:
            self._rebalance_guard = False

    def _adjust_primaries(self, primaries: Iterable[int], diff: int) -> None:
        ratios = self._defaults.primary_ratios[: len(primaries)]
        ratio_sum = sum(ratios) or 1.0
        primary_list = list(primaries)

        if diff > 0:
            remaining = diff
            for idx, col in enumerate(primary_list):
                share = int(diff * (ratios[idx] / ratio_sum)) if idx < len(ratios) else int(diff / len(primary_list))
                if idx == len(primary_list) - 1:
                    share = remaining
                remaining -= share
                if share > 0:
                    self._table.setColumnWidth(col, self._table.columnWidth(col) + share)
        else:
            deficit = -diff
            capacities = []
            total_capacity = 0
            for col in primary_list:
                capacity = max(self._table.columnWidth(col) - self._defaults.primary_min_width, 0)
                capacities.append((col, capacity))
                total_capacity += capacity
            if total_capacity == 0:
                return
            remaining = deficit
            for idx, (col, capacity) in enumerate(capacities):
                share = int(deficit * (capacity / total_capacity)) if total_capacity else 0
                share = min(share, capacity)
                if idx == len(capacities) - 1:
                    share = min(remaining, capacity)
                remaining -= share
                if share > 0:
                    self._table.setColumnWidth(col, self._table.columnWidth(col) - share)
