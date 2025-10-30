"""
Startup splash screen with system requirements checking.

Shows application initialization progress including:
- PyTorch availability check
- CUDA/GPU detection
- FFmpeg availability
- GPU Pack download prompt (if needed)

Integrates with SystemCapabilitiesService to provide real-time feedback
during application startup.
"""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QProgressBar, QWidget
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap

from services.system_capabilities import SystemCapabilities, check_system_capabilities

logger = logging.getLogger(__name__)


class StartupSplash(QDialog):
    """
    Startup splash screen with system capability checks.

    Workflow:
    1. Show splash immediately on app start
    2. Run system checks (log progress to UI)
    3. If PyTorch missing → show build error (GPU Pack won't fix this)
    4. If PyTorch CPU available but CUDA missing + user wants GPU → offer GPU Pack download
    5. Emit checks_complete signal and close

    Signals:
        checks_complete: Emitted when all checks finish (passes SystemCapabilities)
        gpu_pack_requested: Emitted when user requests GPU Pack download
    """

    # Signals
    checks_complete = Signal(object)  # SystemCapabilities
    gpu_pack_requested = Signal()

    def __init__(self, parent=None, config=None):
        """
        Initialize startup splash screen.

        Args:
            parent: Parent widget (usually None for splash)
            config: Config object to check gpu_opt_in setting
        """
        super().__init__(parent)
        self.config = config
        self.capabilities: Optional[SystemCapabilities] = None

        self._setup_ui()

        # Don't auto-start checks - caller will use run() method

    def _setup_ui(self):
        """Setup splash screen UI with dark theme."""
        self.setWindowTitle("USDXFixGap - Starting...")
        self.setModal(True)
        self.setFixedSize(650, 450)
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)

        # Apply dark theme styling to dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #353535;
                color: white;
            }
            QLabel {
                color: white;
            }
        """)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # App title
        title_label = QLabel("USDXFixGap")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Version label
        try:
            from usdxfixgap import get_version
            version = get_version()
        except:
            version = "v1.2.0"

        version_label = QLabel(f"Version {version}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #999;")
        layout.addWidget(version_label)

        # Spacer
        layout.addSpacing(10)

        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(11)
        self.status_label.setFont(status_font)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        # Log output area
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)

        log_label = QLabel("System Check:")
        log_label.setStyleSheet("color: #999;")
        log_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(180)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
        """)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_container)

        # Button container (hidden initially)
        self.button_container = QWidget()
        button_layout = QHBoxLayout(self.button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        # GPU Pack download button
        self.gpu_pack_btn = QPushButton("Download GPU Pack")
        self.gpu_pack_btn.clicked.connect(self._on_gpu_pack_requested)
        self.gpu_pack_btn.setMinimumHeight(35)
        button_layout.addWidget(self.gpu_pack_btn)

        # Use CPU button
        self.use_cpu_btn = QPushButton("Use CPU Mode")
        self.use_cpu_btn.clicked.connect(self._on_use_cpu)
        self.use_cpu_btn.setMinimumHeight(35)
        button_layout.addWidget(self.use_cpu_btn)

        # Continue button
        self.continue_btn = QPushButton("Continue")
        self.continue_btn.clicked.connect(self.accept)
        self.continue_btn.setMinimumHeight(35)
        button_layout.addWidget(self.continue_btn)

        self.button_container.setVisible(False)
        layout.addWidget(self.button_container)

    def log(self, message: str):
        """
        Add message to log output.

        Args:
            message: Message to display
        """
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        logger.info(f"[Splash] {message}")

    def _run_checks(self):
        """Run system capability checks."""
        self.log("Starting system checks...")
        self.log("")

        # Run checks with progress logging
        self.capabilities = check_system_capabilities(log_callback=self.log)

        self.log("")
        self.log("=" * 50)

        # Update UI based on results
        self._update_ui_for_results()

    def _update_ui_for_results(self):
        """Update UI based on capability check results."""
        if not self.capabilities:
            logger.error("No capabilities detected")
            return

        # Stop progress bar
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

        # PATH 1 & 2: Detection possible (has torch + ffmpeg)
        if self.capabilities.can_detect:
            # Detection available
            detection_mode = self.capabilities.get_detection_mode()

            if detection_mode == 'gpu':
                # PATH 1a: Happy path - GPU mode
                self.log("")
                self.log("✅ GPU acceleration available")
                self.log("   Starting application...")
                self.status_label.setText("✅ System Ready (GPU Mode)")
                self._auto_close()

            elif detection_mode == 'cpu':
                # Check if user explicitly wants GPU
                if self.config and self.config.gpu_opt_in:
                    # PATH 2: GPU upgrade path - User wants GPU but only has CPU
                    self.log("")
                    self.log("⚡ GPU acceleration not available")
                    self.log("   → Download GPU Pack for 5-10x faster detection")
                    self.status_label.setText("⚡ GPU Pack Available")
                    self._show_gpu_pack_prompt()
                else:
                    # PATH 1b: Happy path - CPU mode is fine
                    self.log("")
                    self.log("✅ CPU detection available")
                    self.log("   Starting application...")
                    self.status_label.setText("✅ System Ready (CPU Mode)")
                    self._auto_close()

        # PATH 3: Failure - Critical components missing
        else:
            self.log("")

            if not self.capabilities.has_torch:
                # PATH 3a: PyTorch missing → BUILD ERROR
                # GPU Pack won't fix this - it supplements bundled PyTorch, doesn't install it
                self.log("❌ PyTorch not available")
                self.log(f"   Error: {self.capabilities.torch_error}")
                self.log("")

                # Detect specific error: CUDA DLLs bundled in CPU-only exe
                if self.capabilities.torch_error and ('c10_cuda' in self.capabilities.torch_error or
                                                      'cuda.dll' in self.capabilities.torch_error.lower()):
                    self.log("⚠️  This is a build error - CUDA DLLs were incorrectly bundled")
                    self.log("   → Executable should be CPU-only (~450MB)")
                    self.log("   → Current build has CUDA DLLs that can't load without NVIDIA drivers")
                    self.log("   → Gap detection disabled")
                    self.log("")
                    self.log("💡 Fix: Rebuild with CPU-only PyTorch (see requirements-build.txt)")
                    self.status_label.setText("❌ Build Error - CUDA in CPU Build")
                else:
                    self.log("⚠️  This is a build error - PyTorch should be bundled in the executable")
                    self.log("   → Gap detection disabled")
                    self.log("   → Application will start in view-only mode")
                    self.log("")
                    self.log("💡 Tip: Rebuild the executable or report this issue")
                    self.status_label.setText("❌ Build Error - PyTorch Missing")

                self._show_continue_button()

            elif not self.capabilities.has_ffmpeg:
                # PATH 3b: FFmpeg missing → permanent failure (download won't help)
                self.log("❌ FFmpeg not available")
                self.log("")
                self.log("⚠️  Gap detection disabled")
                self.log("   → Install FFmpeg and add to system PATH")
                self.log("   → Application will start in view-only mode")
                self.status_label.setText("❌ Gap Detection Disabled")
                self._show_continue_button()

            else:
                # PATH 3c: Unknown failure
                self.log("❌ System requirements not met")
                self.log("")
                self.log("⚠️  Gap detection disabled")
                self.log("   → Application will start in view-only mode")
                self.status_label.setText("❌ Gap Detection Disabled")
                self._show_continue_button()

    def _show_gpu_pack_prompt(self):
        """Show GPU Pack download prompt."""
        self.button_container.setVisible(True)
        self.gpu_pack_btn.setVisible(True)
        self.use_cpu_btn.setVisible(True)
        self.continue_btn.setVisible(False)

    def _show_continue_button(self):
        """Show continue button only."""
        self.button_container.setVisible(True)
        self.gpu_pack_btn.setVisible(False)
        self.use_cpu_btn.setVisible(False)
        self.continue_btn.setVisible(True)

    def _auto_close(self):
        """Auto-close splash after short delay."""
        self.log("Starting application...")
        QTimer.singleShot(1000, self._complete)

    def _complete(self):
        """Complete startup and emit signal."""
        if self.capabilities:
            self.checks_complete.emit(self.capabilities)
        self.accept()

    def _on_gpu_pack_requested(self):
        """Handle GPU Pack download request."""
        self.log("GPU Pack download requested...")
        self.gpu_pack_requested.emit()
        # Don't close - let parent handle GPU Pack dialog

    def _on_use_cpu(self):
        """Handle use CPU mode button - offer GPU Pack download first."""
        self.log("")
        self.log("📦 GPU Pack available for 10x faster detection!")
        self.log("   Download now or continue in CPU mode?")
        self.log("   (You can also download later from Settings)")
        
        # Update UI to show GPU Pack offer
        self.status_label.setText("GPU Pack Available")
        
        # Update buttons: Show "Download GPU Pack" and "No, Use CPU"
        self.gpu_pack_btn.setVisible(True)
        self.gpu_pack_btn.setText("Download GPU Pack")
        self.use_cpu_btn.setText("No, Use CPU Mode")
        self.use_cpu_btn.clicked.disconnect()  # Disconnect old handler
        self.use_cpu_btn.clicked.connect(self._on_confirm_cpu_mode)  # Connect to confirmation
        self.continue_btn.setVisible(False)

    def _on_confirm_cpu_mode(self):
        """Confirm CPU mode without GPU Pack."""
        self.log("Continuing in CPU mode...")

        # Update config to disable GPU opt-in
        if self.config:
            self.config.gpu_opt_in = False
            self.config.save()
            self.log("✓ GPU opt-in disabled in config")

        self._auto_close()

    def run(self) -> Optional[SystemCapabilities]:
        """
        Show splash and run capability checks.

        Returns:
            SystemCapabilities if checks completed successfully, None if cancelled
        """
        # Start checks immediately
        QTimer.singleShot(100, self._run_checks)

        # Show dialog and wait for completion
        result = self.exec()

        # Return capabilities if accepted
        if result == QDialog.DialogCode.Accepted:
            return self.capabilities
        else:
            return None

    def get_capabilities(self) -> Optional[SystemCapabilities]:
        """
        Get detected capabilities.

        Returns:
            SystemCapabilities if checks completed, None otherwise
        """
        return self.capabilities
