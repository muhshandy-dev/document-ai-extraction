from docextract.layout import Page, Word, group_lines


def make_page(rows: list[list[str]], width: float = 600.0, line_h: float = 20.0) -> Page:
    """Build a page from rows of tokens laid out left to right."""
    words = []
    for r, row in enumerate(rows):
        x = 10.0
        for tok in row:
            w = 9.0 * len(tok)
            words.append(Word(tok, x, r * line_h * 1.5, x + w, r * line_h * 1.5 + line_h))
            x += w + 8.0
    return group_lines(words, width, len(rows) * line_h * 1.5)
