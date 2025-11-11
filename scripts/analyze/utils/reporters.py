"""Reporting utilities for code analysis.

Handles all display and formatting of analysis results including
priority scoring, complexity hotspots, and summary tables.
"""

from typing import List
import sys

# Import symbols from main script (will be passed as module constant)
if sys.platform == "win32":
    SYMBOL_INFO = "[i]"
else:
    SYMBOL_INFO = "💡"

# Configuration constants (will be imported from main)
MAX_COMPLEXITY = 15
MAX_NLOC = 100


def _calculate_file_priority_scores(complexity_metrics, complexity_issues, style_issues, length_issues):
    """Calculate priority scores for each file based on all metrics.

    Priority score formula:
    - Each complexity issue: base 10 points + (CCN - 15) * 2 + (NLOC - 100) * 0.5
    - Each style issue: 1 point
    - File length warning: 5 points

    Args:
        complexity_metrics: List of (filepath, func_name, ccn, nloc, line_num)
        complexity_issues: Dict of filepath -> issue count
        style_issues: Dict of filepath -> issue count
        length_issues: Dict of filepath -> 1 (if has length issue)

    Returns:
        List of (filepath, priority_score, details_dict) sorted by priority descending
    """
    file_scores = {}

    # Add complexity scores (weighted by actual CCN and NLOC values)
    for filepath, func_name, ccn, nloc, line_num in complexity_metrics:
        if filepath not in file_scores:
            file_scores[filepath] = {
                "priority": 0,
                "complexity_count": 0,
                "max_ccn": 0,
                "max_nloc": 0,
                "style_count": 0,
                "has_length_issue": False,
            }

        # Weight by severity: higher CCN = much higher priority
        ccn_penalty = max(0, ccn - MAX_COMPLEXITY) * 2
        nloc_penalty = max(0, nloc - MAX_NLOC) * 0.5
        base_score = 10
        complexity_score = base_score + ccn_penalty + nloc_penalty

        file_scores[filepath]["priority"] += complexity_score
        file_scores[filepath]["complexity_count"] += 1
        file_scores[filepath]["max_ccn"] = max(file_scores[filepath]["max_ccn"], ccn)
        file_scores[filepath]["max_nloc"] = max(file_scores[filepath]["max_nloc"], nloc)

    # Add style issues (1 point each)
    for filepath, count in style_issues.items():
        if filepath not in file_scores:
            file_scores[filepath] = {
                "priority": 0,
                "complexity_count": 0,
                "max_ccn": 0,
                "max_nloc": 0,
                "style_count": 0,
                "has_length_issue": False,
            }
        file_scores[filepath]["priority"] += count
        file_scores[filepath]["style_count"] = count

    # Add length issues (5 points)
    for filepath in length_issues.keys():
        if filepath not in file_scores:
            file_scores[filepath] = {
                "priority": 0,
                "complexity_count": 0,
                "max_ccn": 0,
                "max_nloc": 0,
                "style_count": 0,
                "has_length_issue": False,
            }
        file_scores[filepath]["priority"] += 5
        file_scores[filepath]["has_length_issue"] = True

    # Convert to sorted list
    result = [(filepath, details["priority"], details) for filepath, details in file_scores.items()]
    result.sort(key=lambda x: x[1], reverse=True)

    return result


def print_top_priority_files(file_priority_scores, complexity_metrics):
    """Print top priority files combining all metrics.

    Args:
        file_priority_scores: List of (filepath, priority_score, details_dict)
        complexity_metrics: List of (filepath, func_name, ccn, nloc, line_num) for detail lookup
    """
    print(f"\n{'=' * 80}")
    print("⚡ TOP REFACTORING PRIORITIES (Combined: Complexity + Style + Length)")
    print(f"{'=' * 80}")
    header = f"{'Rank':>4} {'Priority':>8} {'File':<40} {'MaxCCN':>7} {'Complex':>7} {'Style':>6} {'Length':>6}"
    print(header)
    print(f"{'-' * 4} {'-' * 8} {'-' * 40} {'-' * 7} {'-' * 7} {'-' * 6} {'-' * 6}")

    # Show top 15 files
    for rank, (filepath, priority, details) in enumerate(file_priority_scores[:15], start=1):
        # Shorten path for display
        if len(filepath) > 40:
            display_path = "..." + filepath[-37:]
        else:
            display_path = filepath

        max_ccn_str = str(details["max_ccn"]) if details["max_ccn"] > 0 else "-"
        complexity_str = str(details["complexity_count"]) if details["complexity_count"] > 0 else "-"
        style_str = str(details["style_count"]) if details["style_count"] > 0 else "-"
        length_str = "YES" if details["has_length_issue"] else "-"

        row = (
            f"{rank:>4} {priority:>8.1f} {display_path:<40} {max_ccn_str:>7} "
            f"{complexity_str:>7} {style_str:>6} {length_str:>6}"
        )
        print(row)

    total_files = len(file_priority_scores)
    if total_files > 15:
        print(f"\n... and {total_files - 15} more file(s) with issues")

    print(f"\n{SYMBOL_INFO} Priority Score: Higher = More Urgent (complexity heavily weighted by CCN)")
    print(f"{SYMBOL_INFO} MaxCCN: Highest cyclomatic complexity in file")
    print(f"{SYMBOL_INFO} Complex: Number of functions exceeding thresholds")
    print(f"{SYMBOL_INFO} Start from Rank 1 downward for maximum impact")


def get_severity(ccn: int, nloc: int) -> str:
    """Determine severity level based on CCN and NLOC thresholds.

    Args:
        ccn: Cyclomatic complexity number
        nloc: Number of lines of code

    Returns:
        Severity string: CRITICAL, HIGH, or MEDIUM
    """
    if ccn > 30 or nloc > 150:
        return "CRITICAL"
    elif ccn > 20 or nloc > 120:
        return "HIGH"
    else:
        return "MEDIUM"


def print_complexity_hotspots(complexity_metrics: List[tuple]) -> None:
    """Print complexity hotspots section with function-level details.

    Args:
        complexity_metrics: List of (filepath, func_name, ccn, nloc, line_num) tuples
    """
    print(f"\n{'=' * 80}")
    print("🔥 COMPLEXITY HOTSPOTS (Highest Priority)")
    print(f"{'=' * 80}")

    # Sort by CCN (descending), then by NLOC
    sorted_metrics = sorted(complexity_metrics, key=lambda x: (x[2], x[3]), reverse=True)

    # Show top 20 functions
    print(f"{'File':>45} {'Function':<30} {'CCN':>5} {'NLOC':>5} {'Severity':>10}")
    print(f"{'-' * 45} {'-' * 30} {'-' * 5} {'-' * 5} {'-' * 10}")

    for filepath, func_name, ccn, nloc, line_num in sorted_metrics[:20]:
        severity = get_severity(ccn, nloc)

        # Shorten paths for display
        display_path = ("..." + filepath[-42:]) if len(filepath) > 45 else filepath

        # Shorten function name
        display_func = (func_name[:27] + "...") if len(func_name) > 30 else func_name

        print(f"{display_path:>45} {display_func:<30} {ccn:>5} {nloc:>5} {severity:>10}")

    total_hotspots = len(complexity_metrics)
    if total_hotspots > 20:
        print(f"\n... and {total_hotspots - 20} more function(s) with complexity issues")

    severity_msg = "Severity: CRITICAL (CCN>30/NLOC>150), HIGH (CCN>20/NLOC>120), MEDIUM (exceeds thresholds)"
    print(f"\n{SYMBOL_INFO} {severity_msg}")
    print(f"{SYMBOL_INFO} Refactor hotspots from top to bottom for maximum impact")


def print_file_level_summary(complexity_issues: dict, style_issues: dict, length_issues: dict) -> None:
    """Print file-level issue summary table.

    Args:
        complexity_issues: Dict mapping filepath to complexity issue count
        style_issues: Dict mapping filepath to style issue count
        length_issues: Dict mapping filepath to length issue count
    """
    # Combine all files for overall summary
    all_files = set(complexity_issues.keys()) | set(style_issues.keys()) | set(length_issues.keys())

    if not all_files:
        return

    # Calculate totals per file
    file_totals = []
    for filepath in all_files:
        complexity = complexity_issues.get(filepath, 0)
        style = style_issues.get(filepath, 0)
        length = length_issues.get(filepath, 0)
        total = complexity + style + length
        file_totals.append((filepath, complexity, style, length, total))

    # Sort by total issues (descending)
    file_totals.sort(key=lambda x: x[4], reverse=True)

    # Print file-level summary
    print(f"\n{'=' * 80}")
    print("📋 FILE-LEVEL ISSUE SUMMARY")
    print(f"{'=' * 80}")
    print(f"{'File':<55} {'Complex':>7} {'Style':>7} {'Length':>7} {'Total':>7}")
    print(f"{'-' * 55} {'-' * 7} {'-' * 7} {'-' * 7} {'-' * 7}")

    # Show top 20 files
    for filepath, complexity, style, length, total in file_totals[:20]:
        # Shorten path for display
        display_path = filepath if len(filepath) <= 55 else "..." + filepath[-52:]
        print(f"{display_path:<55} {complexity:>7} {style:>7} {length:>7} {total:>7}")

    total_files = len(file_totals)
    if total_files > 20:
        print(f"\n... and {total_files - 20} more file(s) with issues")
