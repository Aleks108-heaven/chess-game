"""Design tokens: contrast is computed, not eyeballed (WCAG 2.x formulas)."""

import pytest

import theme


@pytest.mark.parametrize("name,foreground,background,minimum", theme.CONTRAST_PAIRS,
                         ids=[pair[0] for pair in theme.CONTRAST_PAIRS])
def test_pair_meets_its_contrast_minimum(name, foreground, background, minimum):
    ratio = theme.contrast_ratio(foreground, background)
    assert ratio >= minimum, f"{name}: {ratio:.2f}:1 is below the required {minimum}:1"


def test_contrast_formula_matches_known_values():
    assert theme.contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert theme.contrast_ratio((255, 255, 255), (255, 255, 255)) == pytest.approx(1.0)
    # Symmetric in its arguments.
    assert theme.contrast_ratio((10, 20, 30), (200, 210, 220)) == pytest.approx(
        theme.contrast_ratio((200, 210, 220), (10, 20, 30)))
    # Mid grey (119) on white is the classic ~4.5:1 boundary.
    assert theme.contrast_ratio((118, 118, 118), (255, 255, 255)) == pytest.approx(4.54, abs=0.02)


def test_shade_is_clamped():
    assert theme.shade((200, 100, 0), 2.0) == (255, 200, 0)
    assert theme.shade((200, 100, 10), 0.0) == (0, 0, 0)


def test_every_color_token_is_a_valid_rgb_triple():
    for name in dir(theme):
        value = getattr(theme, name)
        if name.isupper() and isinstance(value, tuple) and len(value) == 3 \
                and all(isinstance(v, int) for v in value):
            assert all(0 <= v <= 255 for v in value), name
