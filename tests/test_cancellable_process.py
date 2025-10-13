import pytest

from utils.cancellable_process import run_cancellable_process


def test_missing_executable():
    # Use a clearly non-existing command name to assert custom error
    with pytest.raises(FileNotFoundError) as exc:
        run_cancellable_process(["__definitely_not_existing_binary__", "--help"])  # noqa
    assert "Executable not found" in str(exc.value)
