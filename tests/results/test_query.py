# Copyright 2021 IRT Saint Exupery, https://www.irt-saintexupery.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Tests of the queries on the summaries of the results."""

from __future__ import annotations

import pytest
from pandas import DataFrame

from vimseo.results.query import apply_query
from vimseo.results.query import to_mlflow_filter

pytestmark = pytest.mark.fast


@pytest.fixture
def summaries() -> DataFrame:
    return DataFrame({
        "run_id": ["a", "b", "c"],
        "load_case": ["Cantilever", "Cantilever", "ThreePoints"],
        "inputs.height": [40.0, 50.0, 60.0],
        "outputs.reaction_forces": [-2333.3, -4557.3, -7875.0],
    })


def test_query_with_or(summaries):
    """A query combines comparisons with and, or and parentheses."""
    selected = apply_query(
        summaries,
        "`inputs.height` > 45 and (`outputs.reaction_forces` > -5000 "
        "or load_case == 'ThreePoints')",
    )
    assert list(selected["run_id"]) == ["b", "c"]


def test_empty_query(summaries):
    assert apply_query(summaries, "").equals(summaries)


@pytest.mark.parametrize("query", ["`inputs.height` >", "height > @limit"])
def test_invalid_query(summaries, query):
    """A malformed query, or one reading a Python variable, raises a ValueError."""
    with pytest.raises(ValueError, match="query"):
        apply_query(summaries, query)


def test_mlflow_filter_keeps_the_conjunctive_part():
    """Only the comparisons joined by and at the top of the query are translated."""
    names = {
        "inputs.height": "metrics.`inputs.height`",
        "load_case": "tags.`vimseo.load_case`",
    }
    query = (
        "`inputs.height` > 45 and load_case == 'Cantilever' "
        "and (`outputs.y` < 0 or load_case == 'ThreePoints')"
    )
    assert to_mlflow_filter(query, names) == (
        "metrics.`inputs.height` > 45 and tags.`vimseo.load_case` = 'Cantilever'"
    )
    assert to_mlflow_filter("`inputs.height` > 45 or load_case == 'x'", names) == ""
