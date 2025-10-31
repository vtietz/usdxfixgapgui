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
        # No monkeypatching - pages manage their own buttons
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
