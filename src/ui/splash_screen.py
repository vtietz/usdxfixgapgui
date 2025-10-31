"""
Startup splash screen with wizard-based system checks.

Modern wizard-style interface for system health checks, GPU Pack offers,
and GPU Pack download progress with smart page skipping.
"""

import logging
from typing import Optional

from ui.splash_wizard import WizardSplash
from ui.splash_pages import HealthCheckPage, GpuPackOfferPage, DownloadProgressPage
from services.system_capabilities import SystemCapabilities

logger = logging.getLogger(__name__)


class StartupSplash:
    """Factory for creating wizard-based startup splash."""

    @staticmethod
    def create(parent=None, config=None):
        """Create and configure wizard-based startup splash."""
        wizard = WizardSplash(parent=parent, config=config)
        wizard.add_page(HealthCheckPage())
        wizard.add_page(GpuPackOfferPage())
        wizard.add_page(DownloadProgressPage())
        wizard.set_page_flow([0, 1])
        _setup_gpu_navigation(wizard)
        return wizard

    @staticmethod
    def run(parent=None, config=None):
        """Run startup splash and return capabilities."""
        wizard = StartupSplash.create(parent=parent, config=config)
        capabilities = None

        def on_complete(data):
            nonlocal capabilities
            capabilities = data.get("capabilities")

        wizard.wizard_complete.connect(on_complete)
        wizard._page_data = {"config": config}
        wizard.start()
        return capabilities


def _setup_gpu_navigation(wizard):
    """Setup custom navigation for GPU offer page."""
    original_show = wizard._show_current_page

    def custom_show():
        original_show()
        current_page = wizard._get_current_page()
        if isinstance(current_page, GpuPackOfferPage):
            wizard._skip_btn.setText("Skip (Use CPU)")
            wizard._next_btn.setText("Download GPU Pack")
            try:
                wizard._next_btn.clicked.disconnect()
            except:
                pass

            def on_download():
                if 2 not in wizard._page_indices_to_show:
                    wizard._page_indices_to_show.append(2)
                wizard._page_data["download_requested"] = True
                wizard._page_data.update(current_page.get_page_data())
                wizard._current_page_index += 1
                wizard._show_current_page()

            wizard._next_btn.clicked.connect(on_download)
        else:
            wizard._skip_btn.setText("Skip")
            wizard._next_btn.setText("Next")

    wizard._show_current_page = custom_show
