"""
Keyboard Shortcuts Handler - Global shortcuts for gap editing workflow.

Shortcuts:
- Space: Play/Pause
- G: Jump to current gap
- D: Jump to detected gap
- A: Apply detected gap
- R: Revert to saved gap
- S: Save current gap
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtCore import Signal


class KeyboardShortcuts(QWidget):
    """
    Manages keyboard shortcuts for gap editing workflow.

    Signals:
        play_pause_requested: Emitted when Space is pressed
        jump_to_current_requested: Emitted when G is pressed
        jump_to_detected_requested: Emitted when D is pressed
        apply_detected_requested: Emitted when A is pressed
        revert_requested: Emitted when R is pressed
        save_requested: Emitted when S is pressed
    """

    # Signals for each shortcut action
    play_pause_requested = Signal()
    jump_to_current_requested = Signal()
    jump_to_detected_requested = Signal()
    apply_detected_requested = Signal()
    revert_requested = Signal()
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._shortcuts_enabled = True
        self._shortcuts = []

        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Create all keyboard shortcuts."""
        # Space: Play/Pause
        space_shortcut = QShortcut(QKeySequence("Space"), self)
        space_shortcut.activated.connect(self._on_play_pause)
        self._shortcuts.append(space_shortcut)

        # G: Jump to current gap
        g_shortcut = QShortcut(QKeySequence("G"), self)
        g_shortcut.activated.connect(self._on_jump_to_current)
        self._shortcuts.append(g_shortcut)

        # D: Jump to detected gap
        d_shortcut = QShortcut(QKeySequence("D"), self)
        d_shortcut.activated.connect(self._on_jump_to_detected)
        self._shortcuts.append(d_shortcut)

        # A: Apply detected gap
        a_shortcut = QShortcut(QKeySequence("A"), self)
        a_shortcut.activated.connect(self._on_apply_detected)
        self._shortcuts.append(a_shortcut)

        # R: Revert to saved
        r_shortcut = QShortcut(QKeySequence("R"), self)
        r_shortcut.activated.connect(self._on_revert)
        self._shortcuts.append(r_shortcut)

        # S: Save current gap
        s_shortcut = QShortcut(QKeySequence("S"), self)
        s_shortcut.activated.connect(self._on_save)
        self._shortcuts.append(s_shortcut)

    def _on_play_pause(self):
        """Handle Space key."""
        if self._shortcuts_enabled:
            self.play_pause_requested.emit()

    def _on_jump_to_current(self):
        """Handle G key."""
        if self._shortcuts_enabled:
            self.jump_to_current_requested.emit()

    def _on_jump_to_detected(self):
        """Handle D key."""
        if self._shortcuts_enabled:
            self.jump_to_detected_requested.emit()

    def _on_apply_detected(self):
        """Handle A key."""
        if self._shortcuts_enabled:
            self.apply_detected_requested.emit()

    def _on_revert(self):
        """Handle R key."""
        if self._shortcuts_enabled:
            self.revert_requested.emit()

    def _on_save(self):
        """Handle S key."""
        if self._shortcuts_enabled:
            self.save_requested.emit()

    def set_enabled(self, enabled: bool):
        """
        Enable or disable all shortcuts.

        Useful when text input fields have focus and should receive
        letter keypresses instead of triggering shortcuts.

        Args:
            enabled: True to enable shortcuts, False to disable
        """
        self._shortcuts_enabled = enabled
        for shortcut in self._shortcuts:
            shortcut.setEnabled(enabled)

    def is_enabled(self) -> bool:
        """Check if shortcuts are currently enabled."""
        return self._shortcuts_enabled
