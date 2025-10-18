"""Feature flags for gradual rollout of refactored code.

This module provides feature flags that control which implementation
is used for major refactored components. Flags default to False (use legacy)
and can be enabled via config file for testing before full rollout.

Usage:
    from common.feature_flags import FeatureFlags
    
    flags = FeatureFlags.from_config(config)
    if flags.USE_REFACTORED_GAP_DETECTION:
        return perform_refactored(options)
    else:
        return perform_legacy(options)
"""


class FeatureFlags:
    """Feature flags for complexity reduction refactoring.
    
    All flags default to False to preserve legacy behavior.
    Enable individually via config file for testing.
    """
    
    # Phase 1: Gap detection pipeline (P0)
    USE_REFACTORED_GAP_DETECTION = False
    
    # Phase 2: MDX scanning (P0)
    USE_MODULAR_MDX_SCANNING = False
    
    # Phase 3: Downloader (P0)
    USE_RESILIENT_DOWNLOADER = False
    
    # Phase 4: GPU bootstrap (P1)
    USE_STAGED_GPU_BOOTSTRAP = False
    
    # Phase 5: UI logic (P1)
    USE_STRATEGY_BASED_SORTING = False
    USE_MAP_BASED_FORMATTING = False
    
    @classmethod
    def from_config(cls, config):
        """Load feature flags from config file.
        
        Args:
            config: Application config object
            
        Returns:
            FeatureFlags instance with flags set from config
            
        Example config.ini section:
            [experimental]
            refactored_gap_detection = true
            modular_mdx_scanning = false
        """
        flags = cls()
        
        # Check for experimental section
        if hasattr(config, 'experimental'):
            experimental = config.experimental
            
            # Phase 1
            if hasattr(experimental, 'refactored_gap_detection'):
                flags.USE_REFACTORED_GAP_DETECTION = experimental.refactored_gap_detection
            
            # Phase 2
            if hasattr(experimental, 'modular_mdx_scanning'):
                flags.USE_MODULAR_MDX_SCANNING = experimental.modular_mdx_scanning
            
            # Phase 3
            if hasattr(experimental, 'resilient_downloader'):
                flags.USE_RESILIENT_DOWNLOADER = experimental.resilient_downloader
            
            # Phase 4
            if hasattr(experimental, 'staged_gpu_bootstrap'):
                flags.USE_STAGED_GPU_BOOTSTRAP = experimental.staged_gpu_bootstrap
            
            # Phase 5
            if hasattr(experimental, 'strategy_based_sorting'):
                flags.USE_STRATEGY_BASED_SORTING = experimental.strategy_based_sorting
            
            if hasattr(experimental, 'map_based_formatting'):
                flags.USE_MAP_BASED_FORMATTING = experimental.map_based_formatting
        
        return flags
    
    def __repr__(self):
        """String representation showing all flag states."""
        return (
            f"FeatureFlags(\n"
            f"  USE_REFACTORED_GAP_DETECTION={self.USE_REFACTORED_GAP_DETECTION},\n"
            f"  USE_MODULAR_MDX_SCANNING={self.USE_MODULAR_MDX_SCANNING},\n"
            f"  USE_RESILIENT_DOWNLOADER={self.USE_RESILIENT_DOWNLOADER},\n"
            f"  USE_STAGED_GPU_BOOTSTRAP={self.USE_STAGED_GPU_BOOTSTRAP},\n"
            f"  USE_STRATEGY_BASED_SORTING={self.USE_STRATEGY_BASED_SORTING},\n"
            f"  USE_MAP_BASED_FORMATTING={self.USE_MAP_BASED_FORMATTING}\n"
            f")"
        )
