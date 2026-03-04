import pytest
from pathlib import Path
from backend.extraction import extract_to_markdown, MIN_CHAR_THRESHOLD

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_plain_text(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Hello world financial data Revenue: €10M")
    result = extract_to_markdown(str(f))
    assert "Revenue" in result
    assert len(result) > 10


def test_extract_returns_string(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Some content")
    result = extract_to_markdown(str(f))
    assert isinstance(result, str)


def test_min_char_threshold_is_defined():
    assert isinstance(MIN_CHAR_THRESHOLD, int)
    assert MIN_CHAR_THRESHOLD > 0


def test_extract_multiple_files_concatenated(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("Document A content")
    f2.write_text("Document B content")
    from backend.extraction import extract_files_to_markdown
    result = extract_files_to_markdown([str(f1), str(f2)])
    assert "Document A" in result
    assert "Document B" in result
