"""
Download Module for Resilient HTTP Downloads

Provides modular components for robust file downloads with resume support,
checksum verification, and retry logic with exponential backoff.
"""

from .downloader import download_file

__all__ = ['download_file']
