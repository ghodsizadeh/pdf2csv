"""Regression tests against real, reproducible English example PDFs."""

from pathlib import Path

import pandas as pd
import pytest

from pdf2csv import convert
from pdf2csv.extract import _cluster

EXAMPLES = Path(__file__).parents[1] / "examples"


@pytest.mark.parametrize(
    "name",
    [
        "english_stacked",
        "english_close_stacked",
        "english_side_by_side",
        "english_mixed_stacked",
        "english_mixed_side_by_side",
        "english_borderless_stacked",
    ],
)
def test_disconnected_tables_stay_separate(name):
    frames = convert(EXAMPLES / f"{name}.pdf")
    assert len(frames) == 2
    for number, frame in enumerate(frames, 1):
        expected = pd.DataFrame({f"Name {number}": ["Ada", "Grace"], "Score": [10, 12]})
        pd.testing.assert_frame_equal(frame, expected)


def test_rectangle_borders_form_a_table():
    frames = convert(EXAMPLES / "english_rectangles.pdf")
    assert len(frames) == 1
    assert list(frames[0].columns) == ["Name 1", "Score"]
    assert frames[0].values.tolist() == [["Ada", 10], ["Grace", 12]]


def test_collinear_segments_join_only_when_their_endpoints_touch():
    rules = _cluster([(40, 10, 30), (41, 30, 60), (40, 100, 120)])
    assert [(rule.start, rule.end) for rule in rules] == [(10, 60), (100, 120)]
