"""Defensive static security analysis utilities.

This package reports evidence and risk indicators. It does not execute
inspected content and does not provide a deterministic malware verdict.
"""
from ._analysis import analyze_file
from ._models import FileHashes, Finding, SecurityReport

__all__ = ["analyze_file", "FileHashes", "Finding", "SecurityReport"]
