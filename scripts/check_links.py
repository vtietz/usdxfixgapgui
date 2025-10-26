"""
Link checker for markdown documentation.

Validates all links in markdown files, checking:
- Internal file references exist
- Internal anchors are valid
- No broken relative paths
- Proper formatting

Exit codes:
- 0: All links valid
- 1: Broken links found (blocking)
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set


@dataclass
class Link:
    """Represents a link found in documentation."""
    file: Path
    line_num: int
    url: str
    text: str
    is_external: bool


@dataclass
class LinkIssue:
    """Represents a broken or invalid link."""
    link: Link
    reason: str
    severity: str  # 'error' or 'warning'


class MarkdownLinkChecker:
    """Checks all links in markdown files."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.issues: List[LinkIssue] = []
        self.link_pattern = re.compile(
            r'\[([^\]]+)\]\(([^\)]+)\)'  # [text](url)
        )
        # Common heading patterns for anchor validation
        self.heading_pattern = re.compile(r'^#+\s+(.+)$', re.MULTILINE)

    def check_all_links(self) -> int:
        """Check all markdown files for broken links."""
        md_files = self._find_markdown_files()

        print(f"🔍 Checking links in {len(md_files)} markdown files...")
        print()

        for md_file in md_files:
            self._check_file(md_file)

        self._print_summary()
        return 1 if self._has_errors() else 0

    def _find_markdown_files(self) -> List[Path]:
        """Find all markdown files in the repository."""
        md_files = []
        for ext in ['*.md', '*.MD']:
            md_files.extend(self.root_dir.rglob(ext))

        # Exclude build artifacts, virtual environments, and third-party libs
        excluded = {
            '.venv', 'venv', 'build', 'dist', '__pycache__', 'node_modules',
            '.conda', 'site-packages', 'pretrained_models'
        }
        return [
            f for f in md_files
            if not any(part in excluded for part in f.parts)
        ]

    def _check_file(self, md_file: Path):
        """Check all links in a single markdown file."""
        try:
            content = md_file.read_text(encoding='utf-8')
        except Exception as e:
            self.issues.append(LinkIssue(
                link=Link(md_file, 0, '', '', False),
                reason=f"Failed to read file: {e}",
                severity='error'
            ))
            return

        # Extract all headings for anchor validation
        headings = self._extract_headings(content)

        # Find all links
        for line_num, line in enumerate(content.splitlines(), start=1):
            for match in self.link_pattern.finditer(line):
                text, url = match.groups()

                # Skip external URLs (we don't validate those)
                is_external = url.startswith(('http://', 'https://', 'mailto:', 'ftp://'))

                link = Link(
                    file=md_file,
                    line_num=line_num,
                    url=url,
                    text=text,
                    is_external=is_external
                )

                if not is_external:
                    self._validate_internal_link(link, md_file, headings)

    def _extract_headings(self, content: str) -> Set[str]:
        """Extract all heading anchors from markdown content."""
        headings = set()
        for match in self.heading_pattern.finditer(content):
            heading_text = match.group(1).strip()
            # Convert to GitHub-style anchor
            anchor = self._text_to_anchor(heading_text)
            headings.add(anchor)
        return headings

    def _text_to_anchor(self, text: str) -> str:
        """Convert heading text to GitHub-style anchor."""
        # Remove emoji and special chars, convert to lowercase
        anchor = text.lower()
        # Remove code backticks
        anchor = re.sub(r'`([^`]+)`', r'\1', anchor)
        # Remove special characters except spaces and hyphens
        anchor = re.sub(r'[^\w\s-]', '', anchor)
        # Replace spaces with hyphens
        anchor = re.sub(r'\s+', '-', anchor.strip())
        return anchor

    def _validate_internal_link(self, link: Link, current_file: Path, headings: Set[str]):
        """Validate an internal link."""
        url = link.url

        # Skip template placeholders (meant to be filled during release)
        if url in ('link', 'TBD', 'TODO', '#'):
            return

        # Split path and anchor
        if '#' in url:
            path_part, anchor = url.split('#', 1)
        else:
            path_part, anchor = url, None

        # Handle anchor-only links (same file)
        if not path_part:
            if anchor and anchor not in headings:
                self.issues.append(LinkIssue(
                    link=link,
                    reason=f"Anchor '#{anchor}' not found in current file",
                    severity='error'
                ))
            return

        # Resolve relative path
        if path_part.startswith('/'):
            # Absolute from repo root
            target_path = self.root_dir / path_part.lstrip('/')
        else:
            # Relative to current file
            target_path = (current_file.parent / path_part).resolve()

        # Check if target exists
        if not target_path.exists():
            self.issues.append(LinkIssue(
                link=link,
                reason=f"File not found: {path_part}",
                severity='error'
            ))
            return

        # Validate anchor if present
        if anchor:
            try:
                target_content = target_path.read_text(encoding='utf-8')
                target_headings = self._extract_headings(target_content)
                if anchor not in target_headings:
                    self.issues.append(LinkIssue(
                        link=link,
                        reason=f"Anchor '#{anchor}' not found in {target_path.name}",
                        severity='error'
                    ))
            except Exception as e:
                self.issues.append(LinkIssue(
                    link=link,
                    reason=f"Failed to validate anchor in {target_path.name}: {e}",
                    severity='warning'
                ))

    def _has_errors(self) -> bool:
        """Check if any errors (not warnings) were found."""
        return any(issue.severity == 'error' for issue in self.issues)

    def _print_summary(self):
        """Print summary of link check results."""
        if not self.issues:
            print("✅ All links are valid!")
            return

        # Group by file
        issues_by_file = {}
        for issue in self.issues:
            file_path = issue.link.file
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)

        # Print grouped issues
        for file_path, file_issues in sorted(issues_by_file.items()):
            rel_path = file_path.relative_to(self.root_dir)
            print(f"\n📄 {rel_path}")
            print("─" * 80)

            for issue in file_issues:
                icon = "❌" if issue.severity == 'error' else "⚠️"
                print(f"  {icon} Line {issue.link.line_num}: {issue.reason}")
                print(f"     Link: [{issue.link.text}]({issue.link.url})")

        # Summary stats
        errors = sum(1 for i in self.issues if i.severity == 'error')
        warnings = sum(1 for i in self.issues if i.severity == 'warning')

        print("\n" + "=" * 80)
        if errors > 0:
            print(f"❌ Found {errors} error(s) and {warnings} warning(s)")
            print("   Fix errors before committing.")
        else:
            print(f"⚠️  Found {warnings} warning(s) (non-blocking)")
        print("=" * 80)


def main():
    """Entry point for link checker."""
    # Find repository root (contains .git)
    current = Path.cwd()
    while current != current.parent:
        if (current / '.git').exists():
            break
        current = current.parent
    else:
        print("❌ Not in a git repository", file=sys.stderr)
        return 1

    checker = MarkdownLinkChecker(current)
    return checker.check_all_links()


if __name__ == '__main__':
    sys.exit(main())
