import re
import logging

logger = logging.getLogger(__name__)

class SongFileValidator:
    def __init__(self, filepath, encoding='utf-8'):
        self.filepath = filepath
        self.encoding = encoding
        self.errors = []
        self.warnings = []

    def validate(self):
        """Validates the song file."""
        try:
            with open(self.filepath, 'r', encoding=self.encoding) as file:
                content = file.read()
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False

        # Check for TITLE and ARTIST as mandatory attributes
        for attr, pattern in {"TITLE": r"#TITLE:.+", "ARTIST": r"#ARTIST:.+"}.items():
            if not re.search(pattern, content, re.MULTILINE):
                self.errors.append(f"Mandatory attribute missing or incorrect: {attr}")

        # Check for AUDIO or MP3
        if not re.search(r"#AUDIO:.+", content, re.MULTILINE) and not re.search(r"#MP3:.+", content, re.MULTILINE):
            self.errors.append("Either #AUDIO or #MP3 attribute must be present.")

        # BPM is also mandatory
        if not re.search(r"#BPM:\d+", content, re.MULTILINE):
            self.errors.append("Mandatory attribute missing or incorrect: BPM")

        # VERSION is optional but warn if missing
        if not re.search(r"#VERSION:\d+\.\d+\.\d+", content, re.MULTILINE):
            self.warnings.append("#VERSION attribute is missing. Consider adding it for better compatibility.")

        if self.errors or self.warnings:
            return False
        else:
            return content

    def print_issues(self):
        """Prints the errors and warnings encountered during validation."""
        if self.errors:
            print("Validation errors:")
            for error in self.errors:
                logger.error(f"- {error}")
        if self.warnings:
            print("Warnings:")
            for warning in self.warnings:
                logger.warn(f"- {warning}")
        if not self.errors and not self.warnings:
            logger.debug("No issues found.")

