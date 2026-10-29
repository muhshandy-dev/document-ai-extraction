from docextract.layout import Word, group_lines


def test_groups_skewed_words_into_lines():
    words = [
        Word("TOTAL", 10, 100, 60, 120),
        Word("45.000", 200, 103, 260, 123),  # slightly lower, same row
        Word("Nasi", 10, 50, 50, 70),
        Word("Goreng", 60, 52, 120, 72),
        Word("20.000", 200, 49, 260, 69),
    ]
    page = group_lines(words, 300, 200)
    assert [ln.text for ln in page.lines] == ["Nasi Goreng 20.000", "TOTAL 45.000"]


def test_separate_rows_do_not_merge():
    words = [Word("A", 0, 0, 10, 10), Word("B", 0, 12, 10, 22)]
    assert len(group_lines(words, 100, 100).lines) == 2


def test_empty_words_are_dropped():
    page = group_lines([Word("  ", 0, 0, 10, 10)], 100, 100)
    assert page.lines == []
