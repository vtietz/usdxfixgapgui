"""
Wrapper to integrate wizard splash with existing code.

This module provides a compatibility layer between the new wizard-based splash
and the existing application code that expects the old splash interface.
"""

import logging
from typing import Optional
from PySide6.QtWidgets import QDialog

from ui.splash_wizard import WizardSplash
from ui.splash_pages import HealthCheckPage, GpuPackOfferPage, DownloadProgressPage
from services.system_capabilities import SystemCapabilities

logger = logging.getLogger(__name__)


def create_startup_splash(parent=None, config=None) -> WizardSplash:
    """
    Create and configure wizard-based startup splash.

    Args:
        parent: Parent widget
        config: Config object

    Returns:
        Configured WizardSplash instance
    """
    # Create wizard
    wizard = WizardSplash(parent=parent, config=config)

    # Create pages
    health_page = HealthCheckPage()
    gpu_offer_page = GpuPackOfferPage()
    download_page = DownloadProgressPage()

    # Add pages to wizard
    wizard.add_page(health_page)   # Page 0
    wizard.add_page(gpu_offer_page) # Page 1
    wizard.add_page(download_page)  # Page 2

    # Determine which pages to show
    pages_to_show = []

    # Always try to show health check (page will skip itself if configured)
    pages_to_show.append(0)

    # GPU offer page will skip itself if not applicable
    pages_to_show.append(1)

    # Download page only shown if user requests download
    # (added dynamically via custom navigation in GPU offer page)

    wizard.set_page_flow(pages_to_show)

    # Override Next button behavior on GPU offer page
    def on_gpu_offer_page_showing():
        """Customize navigation for GPU offer page."""
        # Check if currently on GPU offer page
        current_page = wizard._get_current_page()
        if isinstance(current_page, GpuPackOfferPage):
            # Hide Skip button, show Download button
            wizard._skip_btn.setText("Skip (Use CPU)")
            wizard._next_btn.setText("Download GPU Pack →")

            # Custom Next button handler: trigger download
            def on_download_clicked_custom():
                # Add download page to flow
                if 2 not in wizard._page_indices_to_show:
                    wizard._page_indices_to_show.append(2)

                # Mark download as requested in page data
                wizard._page_data['download_requested'] = True

                # Proceed with normal advancement
                wizard._on_next_clicked()

            # Temporarily override next button
            wizard._next_btn.clicked.disconnect()
            wizard._next_btn.clicked.connect(on_download_clicked_custom)

    # Connect to page transitions to customize navigation
    wizard._stack.currentChanged.connect(on_gpu_offer_page_showing)

    return wizard


def run_startup_splash(parent=None, config=None) -> Optional[SystemCapabilities]:
    """
    Run startup splash and return capabilities.

    Compatible with existing StartupSplash.run() interface.

    Args:
        parent: Parent widget
        config: Config object

    Returns:
        SystemCapabilities if checks completed, None if cancelled
    """
    wizard = create_startup_splash(parent=parent, config=config)

    capabilities = None

    def on_wizard_complete(data):
        """Handle wizard completion."""
        nonlocal capabilities
        capabilities = data.get('capabilities')

    wizard.wizard_complete.connect(on_wizard_complete)

    # Start wizard
    wizard.start()

    return capabilities
