from mother_earth_studio.adaptive_typography import layout_overlay_text


def test_short_overlay_keeps_large_type():
    layout = layout_overlay_text("Nature remembers.")
    assert layout.fit_status == "good"
    assert layout.font_divisor == 27
    assert "\n" not in layout.text


def test_long_overlay_balances_and_scales():
    layout = layout_overlay_text(
        "Maybe that's a lesson worth carrying with us. We should ask ourselves one simple question."
    )
    assert layout.fits
    assert "\n" in layout.text
    assert layout.font_divisor >= 27
    assert max(len(line) for line in layout.text.splitlines()) < len(layout.text.replace("\n", " "))


def test_extreme_overlay_is_blocked():
    layout = layout_overlay_text("word " * 80)
    assert layout.fit_status == "overflow"
    assert not layout.fits
