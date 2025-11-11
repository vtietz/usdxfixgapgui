"""Output parsing utilities for code analysis.

Parses output from various analysis tools (lizard, flake8, etc.)
to extract metrics and issue counts.
"""

from collections import defaultdict


def parse_style_output(output: str) -> dict:
    """Parse flake8 output to count issues per file.

    Args:
        output: flake8 output string

    Returns:
        Dict mapping file path to issue count
    """
    file_issues = defaultdict(int)

    for line in output.split("\n"):
        if line.strip() and ":" in line:
            # flake8 format: filepath:line:col: error_code error_message
            parts = line.split(":")
            if len(parts) >= 4:
                filepath = parts[0].strip()
                if filepath:
                    file_issues[filepath] += 1

    return dict(file_issues)


def _parse_lizard_file_and_line(file_part: str) -> tuple:
    """Extract filepath and line number from lizard warning file part.

    Args:
        file_part: File part of lizard warning (e.g., "path/to/file.py:123")

    Returns:
        Tuple of (filepath, line_num) or (None, None) if parse fails
    """
    file_parts = file_part.rsplit(":", 1)
    if len(file_parts) == 2:
        return file_parts[0].strip(), file_parts[1].strip()
    return None, None


def _parse_lizard_metrics(metrics_part: str) -> tuple:
    """Extract function name, CCN, and NLOC from lizard warning metrics part.

    Args:
        metrics_part: Metrics part of lizard warning (e.g., "func_name has 10 NLOC, 5 CCN, ...")

    Returns:
        Tuple of (func_name, ccn, nloc) or (None, None, None) if parse fails
    """
    if " has " not in metrics_part:
        return None, None, None

    func_and_metrics = metrics_part.split(" has ")
    func_name = func_and_metrics[0].strip()

    # Extract NLOC and CCN values
    nloc = None
    ccn = None
    metrics_str = func_and_metrics[1] if len(func_and_metrics) > 1 else ""

    # Parse "X NLOC, Y CCN, ..."
    metric_parts = metrics_str.split(",")
    for part in metric_parts:
        part = part.strip()
        if " NLOC" in part:
            nloc = int(part.split()[0])
        elif " CCN" in part:
            ccn = int(part.split()[0])

    if nloc is not None and ccn is not None:
        return func_name, ccn, nloc

    return None, None, None


def parse_complexity_output(output: str) -> tuple:
    """Parse Lizard output to extract complexity metrics per file.

    Args:
        output: Lizard output string

    Returns:
        Tuple of (file_issue_count_dict, file_metrics_list)
        where file_metrics_list contains (filepath, function_name, ccn, nloc, line_number)
    """
    file_issues = defaultdict(int)
    file_metrics = []

    lines = output.split("\n")
    for line in lines:
        # Lizard warning format: "filepath:line: warning: function_name has X NLOC, Y CCN, ..."
        if ": warning: " not in line or " has " not in line or " NLOC" not in line or " CCN" not in line:
            continue

        try:
            # Split by ": warning: "
            parts = line.split(": warning: ")
            if len(parts) < 2:
                continue

            # Extract filepath and line number
            filepath, line_num = _parse_lizard_file_and_line(parts[0])
            if not filepath:
                continue

            # Extract function name and metrics
            func_name, ccn, nloc = _parse_lizard_metrics(parts[1])
            if func_name and ccn is not None and nloc is not None:
                file_issues[filepath] += 1
                file_metrics.append((filepath, func_name, ccn, nloc, line_num))

        except (ValueError, IndexError):
            # Skip malformed lines
            pass

    return dict(file_issues), file_metrics


def parse_file_length_output(output: str) -> dict:
    """Parse file length output to count issues per file.

    Args:
        output: File length analysis output

    Returns:
        Dict mapping file path to issue count (1 per file)
    """
    file_issues = {}

    for line in output.split("\n"):
        if ".py:" in line and "lines" in line:
            # Extract file path
            parts = line.strip().split(":")
            if len(parts) >= 2:
                filepath = parts[0].strip()
                if filepath:
                    file_issues[filepath] = 1

    return file_issues
