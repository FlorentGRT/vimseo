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

"""Tests of the dashboard exploring the model results of an archive."""

from __future__ import annotations

from pathlib import Path

import pytest
from numpy import array

from vimseo.api import create_model
from vimseo.api import open_model_results
from vimseo.utilities.test_utils import run_dashboard

# The dashboards require the ``dashboard`` extra.
pytest.importorskip("streamlit")

import vimseo.dashboards.model_results.model_results_viewer as viewer  # ruff: ignore[module-import-not-at-top-of-file]
from vimseo.dashboards.model_results.model_results_viewer_model import build_query  # ruff: ignore[module-import-not-at-top-of-file]
from vimseo.dashboards.model_results.model_results_viewer_model import (  # ruff: ignore[module-import-not-at-top-of-file]
    get_variable_columns,
)
from vimseo.dashboards.model_results.model_results_viewer_model import plot_scalars  # ruff: ignore[module-import-not-at-top-of-file]

ARCHIVE = "archive"


@pytest.fixture
def archive(tmp_wd) -> str:
    """A directory archive holding two simulations of a model in a study and one
    simulation of another model in another study."""
    model = create_model(
        "BendingTestAnalytical", "Cantilever", directory_archive_root=ARCHIVE
    )
    for young_modulus in (200000.0, 210000.0):
        model.execute({"young_modulus": array([young_modulus])})
    create_model(
        "MockMultiCurves",
        "Dummy",
        directory_archive_root=ARCHIVE,
        study_name="other_study",
    ).execute()
    return ARCHIVE


def _open(archive: str):
    """Open the dashboard on an archive."""
    app = run_dashboard(Path(viewer.__file__))
    app.sidebar.text_input(key="directory_archive_root").set_value(archive).run()
    return app


def test_everything_is_listed_by_default(archive):
    """Without any filter, every result of the archive is listed."""
    app = _open(archive)
    assert not app.exception
    assert not app.error
    table = app.dataframe[0].value
    assert len(table) == 3
    assert set(table["model_name"]) == {"BendingTestAnalytical", "MockMultiCurves"}
    assert set(table["study_name"]) == {"default_study", "other_study"}


def test_refine_by_metadata_and_query(archive):
    """The results are refined from the values present in the archive."""
    app = _open(archive)
    models = app.sidebar.multiselect(key="model_name")
    assert models.options == ["BendingTestAnalytical", "MockMultiCurves"]
    models.set_value(["BendingTestAnalytical"]).run()
    assert len(app.dataframe[0].value) == 2

    app.sidebar.text_input(key="query").set_value(
        "`inputs.young_modulus` > 205000"
    ).run()
    assert not app.error
    assert len(app.dataframe[0].value) == 1

    app.multiselect(key="variable_columns").set_value(["inputs.young_modulus"]).run()
    assert "inputs.young_modulus" in app.dataframe[0].value.columns


def test_malformed_query(archive):
    """A malformed query is reported."""
    app = _open(archive)
    app.sidebar.text_input(key="query").set_value("height >").run()
    assert not app.exception
    assert "cannot be evaluated" in app.error[0].value


def test_empty_archive(tmp_wd):
    """An empty archive is reported."""
    app = _open("empty")
    assert not app.exception
    assert "no model result" in app.info[0].value


def test_build_query():
    """The empty selections keep everything."""
    assert build_query({"model_name": [], "status": []}) == ""
    assert (
        build_query({"model_name": ["A", "B"], "status": []}, "`inputs.x` > 1")
        == "`model_name` in ['A', 'B'] and (`inputs.x` > 1)"
    )


def test_plot_the_selected_results(archive):
    """The scalars of the selected results are plotted against each other."""
    model_results = open_model_results(directory_archive_root=archive)
    columns = get_variable_columns(model_results.summaries)
    assert "inputs.young_modulus" in columns
    figure = plot_scalars(
        model_results.filter(model_name="BendingTestAnalytical").summaries,
        ["inputs.young_modulus", "outputs.reaction_forces"],
    )
    assert len(figure.data[0].dimensions) == 2
