"""Tests for centralized status mapping via GapInfo."""
import pytest
from model.song import Song, SongStatus
from model.gap_info import GapInfo, GapInfoStatus


class TestGapInfoStatusMapping:
    """Test that GapInfo is the single source of truth for status mapping."""
    
    def test_gap_info_match_maps_to_song_match(self):
        """Setting gap_info.status = MATCH should set Song.status = MATCH."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        gap_info.status = GapInfoStatus.MATCH
        
        assert song.status == SongStatus.MATCH
    
    def test_gap_info_mismatch_maps_to_song_mismatch(self):
        """Setting gap_info.status = MISMATCH should set Song.status = MISMATCH."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        gap_info.status = GapInfoStatus.MISMATCH
        
        assert song.status == SongStatus.MISMATCH
    
    def test_gap_info_updated_maps_to_song_updated(self):
        """Setting gap_info.status = UPDATED should set Song.status = UPDATED."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        gap_info.status = GapInfoStatus.UPDATED
        
        assert song.status == SongStatus.UPDATED
    
    def test_gap_info_solved_maps_to_song_solved(self):
        """Setting gap_info.status = SOLVED should set Song.status = SOLVED."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        gap_info.status = GapInfoStatus.SOLVED
        
        assert song.status == SongStatus.SOLVED
    
    def test_gap_info_error_maps_to_song_error(self):
        """Setting gap_info.status = ERROR should set Song.status = ERROR."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        gap_info.status = GapInfoStatus.ERROR
        
        assert song.status == SongStatus.ERROR
    
    def test_gap_info_status_change_triggers_song_update(self):
        """Changing gap_info.status should trigger Song status update."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        # Start with MATCH
        gap_info.status = GapInfoStatus.MATCH
        assert song.status == SongStatus.MATCH
        
        # Change to MISMATCH
        gap_info.status = GapInfoStatus.MISMATCH
        assert song.status == SongStatus.MISMATCH
        
        # Change to SOLVED
        gap_info.status = GapInfoStatus.SOLVED
        assert song.status == SongStatus.SOLVED
    
    def test_gap_info_assignment_triggers_mapping(self):
        """Assigning gap_info with status should immediately map to Song status."""
        song = Song()
        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.MATCH
        
        # Assigning gap_info should trigger mapping
        song.gap_info = gap_info
        
        assert song.status == SongStatus.MATCH
    
    def test_gap_info_none_resets_to_not_processed(self):
        """Setting gap_info to None should reset Song status to NOT_PROCESSED."""
        song = Song()
        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.MATCH
        song.gap_info = gap_info
        assert song.status == SongStatus.MATCH
        
        song.gap_info = None
        
        assert song.status == SongStatus.NOT_PROCESSED


class TestTransientWorkflowStates:
    """Test that QUEUED and PROCESSING states are allowed for workflow."""
    
    def test_song_can_be_set_to_queued(self):
        """Actions can set Song.status = QUEUED for workflow."""
        song = Song()
        
        song.status = SongStatus.QUEUED
        
        assert song.status == SongStatus.QUEUED
    
    def test_song_can_be_set_to_processing(self):
        """Actions can set Song.status = PROCESSING for workflow."""
        song = Song()
        
        song.status = SongStatus.PROCESSING
        
        assert song.status == SongStatus.PROCESSING
    
    def test_transient_states_not_affected_by_gap_info_none(self):
        """QUEUED/PROCESSING states should persist when gap_info is None."""
        song = Song()
        song.gap_info = None
        
        song.status = SongStatus.QUEUED
        assert song.status == SongStatus.QUEUED
        
        song.status = SongStatus.PROCESSING
        assert song.status == SongStatus.PROCESSING
    
    def test_gap_info_mapping_overrides_transient_state(self):
        """Setting gap_info.status should override transient workflow states."""
        song = Song()
        song.status = SongStatus.PROCESSING
        
        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.MATCH
        song.gap_info = gap_info
        
        assert song.status == SongStatus.MATCH


class TestErrorHandlingPatterns:
    """Test error handling via set_error() and gap_info.status."""
    
    def test_set_error_for_non_gap_errors(self):
        """Non-gap errors should use set_error()."""
        song = Song()
        
        song.set_error("File not found")
        
        assert song.status == SongStatus.ERROR
        assert song.error_message == "File not found"
    
    def test_gap_info_error_status_maps_to_song_error(self):
        """Gap-related errors should set gap_info.status = ERROR."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        gap_info.status = GapInfoStatus.ERROR
        
        assert song.status == SongStatus.ERROR
    
    def test_set_error_and_gap_info_error_both_result_in_error_status(self):
        """Both error patterns should result in ERROR status."""
        song1 = Song()
        song1.set_error("Non-gap error")
        
        song2 = Song()
        gap_info = GapInfo()
        song2.gap_info = gap_info
        gap_info.status = GapInfoStatus.ERROR
        
        assert song1.status == SongStatus.ERROR
        assert song2.status == SongStatus.ERROR


class TestStatusMappingIntegrity:
    """Test that status mapping is the single source of truth."""
    
    def test_all_gap_info_statuses_have_song_mappings(self):
        """Every GapInfoStatus should map to a SongStatus."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        mapping = {
            GapInfoStatus.NOT_PROCESSED: SongStatus.NOT_PROCESSED,
            GapInfoStatus.MATCH: SongStatus.MATCH,
            GapInfoStatus.MISMATCH: SongStatus.MISMATCH,
            GapInfoStatus.UPDATED: SongStatus.UPDATED,
            GapInfoStatus.SOLVED: SongStatus.SOLVED,
            GapInfoStatus.ERROR: SongStatus.ERROR,
        }
        
        for gap_status, expected_song_status in mapping.items():
            gap_info.status = gap_status
            assert song.status == expected_song_status, \
                f"GapInfoStatus.{gap_status.name} should map to SongStatus.{expected_song_status.name}"
    
    def test_gap_info_owner_hook_is_set(self):
        """GapInfo should have owner reference after assignment."""
        song = Song()
        gap_info = GapInfo()
        
        song.gap_info = gap_info
        
        assert gap_info.owner is song
    
    def test_status_change_before_owner_set_does_not_crash(self):
        """Changing gap_info.status before owner is set should not crash."""
        gap_info = GapInfo()
        
        # This should not crash even without owner
        gap_info.status = GapInfoStatus.MATCH
        
        assert gap_info.status == GapInfoStatus.MATCH
    
    def test_multiple_status_changes_all_propagate(self):
        """Multiple status changes should all propagate correctly."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        statuses = [
            (GapInfoStatus.MATCH, SongStatus.MATCH),
            (GapInfoStatus.MISMATCH, SongStatus.MISMATCH),
            (GapInfoStatus.UPDATED, SongStatus.UPDATED),
            (GapInfoStatus.SOLVED, SongStatus.SOLVED),
            (GapInfoStatus.ERROR, SongStatus.ERROR),
            (GapInfoStatus.NOT_PROCESSED, SongStatus.NOT_PROCESSED),
        ]
        
        for gap_status, expected_song_status in statuses:
            gap_info.status = gap_status
            assert song.status == expected_song_status


class TestDetectionWorkflow:
    """Test typical detection workflow status transitions."""
    
    def test_detection_workflow_status_progression(self):
        """Test typical workflow: NOT_PROCESSED -> QUEUED -> PROCESSING -> MATCH."""
        song = Song()
        assert song.status == SongStatus.NOT_PROCESSED
        
        # Actions queue the task
        song.status = SongStatus.QUEUED
        assert song.status == SongStatus.QUEUED
        
        # Worker starts
        song.status = SongStatus.PROCESSING
        assert song.status == SongStatus.PROCESSING
        
        # Worker completes with result
        gap_info = GapInfo()
        song.gap_info = gap_info
        gap_info.status = GapInfoStatus.MATCH
        assert song.status == SongStatus.MATCH
    
    def test_manual_update_workflow(self):
        """Test manual update workflow: MISMATCH -> UPDATED."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        # Initial detection shows mismatch
        gap_info.status = GapInfoStatus.MISMATCH
        assert song.status == SongStatus.MISMATCH
        
        # User manually updates gap
        gap_info.status = GapInfoStatus.UPDATED
        assert song.status == SongStatus.UPDATED
    
    def test_keep_gap_workflow(self):
        """Test keep gap workflow: MISMATCH -> SOLVED."""
        song = Song()
        gap_info = GapInfo()
        song.gap_info = gap_info
        
        # Initial detection shows mismatch
        gap_info.status = GapInfoStatus.MISMATCH
        assert song.status == SongStatus.MISMATCH
        
        # User keeps the gap value
        gap_info.status = GapInfoStatus.SOLVED
        assert song.status == SongStatus.SOLVED
