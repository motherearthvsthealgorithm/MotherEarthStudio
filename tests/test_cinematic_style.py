from __future__ import annotations

import unittest

from mother_earth_studio.cinematic_style import split_into_reflective_phrases


class CinematicStyleTests(unittest.TestCase):
    def test_short_text_stays_together(self):
        self.assertEqual(
            split_into_reflective_phrases("Mother Earth remembers."),
            ["Mother Earth remembers."],
        )

    def test_long_text_is_grouped_into_short_phrases(self):
        phrases = split_into_reflective_phrases(
            "We keep asking technology to move faster because slowing down feels impossible."
        )
        self.assertTrue(phrases)
        self.assertTrue(all(len(phrase.split()) <= 5 for phrase in phrases))
        self.assertEqual(" ".join(phrases), "We keep asking technology to move faster because slowing down feels impossible.")

    def test_empty_text_returns_no_phrases(self):
        self.assertEqual(split_into_reflective_phrases("   "), [])


if __name__ == "__main__":
    unittest.main()
