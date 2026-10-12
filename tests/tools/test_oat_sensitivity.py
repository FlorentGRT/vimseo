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

from __future__ import annotations

import pytest
from gemseo.algos.parameter_space import ParameterSpace
from numpy import array
from numpy.testing import assert_allclose

from vimseo.api import create_model
from vimseo.problems.mock.mock_pre_run_post.mock_main import MockModel
from vimseo.tools.base_result import assert_results_equal
from vimseo.tools.base_tool import BaseTool
from vimseo.tools.doe.doe import DOETool
from vimseo.tools.sensitivity.oat_sensitivity import OATSensitivityInputs
from vimseo.tools.sensitivity.oat_sensitivity import OATSensitivitySettings
from vimseo.tools.sensitivity.oat_sensitivity import OATSensitivityTool
from vimseo.tools.sensitivity.oat_sensitivity_result import OATSensitivityResult

CENTER = {"x1": 0.5, "x1_maximum_only": 0.5}


@pytest.fixture
def parameter_space():
    parameter_space = ParameterSpace()
    parameter_space.add_random_variable(
        "x1", "OTUniformDistribution", minimum=-1.0, maximum=1.0
    )
    parameter_space.add_random_variable(
        "x1_maximum_only", "OTUniformDistribution", minimum=-1.0, maximum=1.0
    )
    return parameter_space


@pytest.fixture
def oat_tool(tmp_wd, parameter_space):
    """An OAT sensitivity analysis of y1 = 2 * x1 + 5 around x1 = 0.5."""
    tool = OATSensitivityTool()
    tool.execute(
        inputs=OATSensitivityInputs(
            model=MockModel("LC1"), parameter_space=parameter_space
        ),
        settings=OATSensitivitySettings(output_names=["y1"], center=CENTER),
    )
    return tool


def test_indices(oat_tool):
    """Check the indices of a linear output around a center."""
    result = oat_tool.result
    assert result.two_sided
    assert_allclose(result.center["x1"], [0.5])
    assert_allclose(result.input_steps["x1"], [0.025])
    indices = result.indices
    assert_allclose(indices["delta_f_plus"]["y1"][0]["x1"], [0.05])
    assert_allclose(indices["delta_f_minus"]["y1"][0]["x1"], [-0.05])
    assert_allclose(indices["delta_f"]["y1"][0]["x1"], [0.05])
    assert_allclose(indices["relative_delta_f"]["y1"][0]["x1"], [0.05 / 6])
    assert_allclose(indices["gradient"]["y1"][0]["x1"], [2.0])
    assert_allclose(indices["delta_f"]["y1"][0]["x1_maximum_only"], [0.0])
    assert result.sort_input_variables("y1") == ["x1", "x1_maximum_only"]
    assert len(result.dataset) == 5
    assert "x1" in str(result)


def test_prepared_doe(tmp_wd, oat_tool, parameter_space):
    """Check that the samples of a star DOE prepared in advance give the same
    indices.

    The DOE computes all the outputs of the model, including its metadata, which are
    filtered out.
    """
    doe_tool = DOETool()
    doe_tool.execute(
        model=MockModel("LC1"),
        parameter_space=parameter_space,
        algo="StarDOE",
        algo_settings={"center": CENTER},
    )
    tool = OATSensitivityTool()
    tool.execute(doe_dataset=doe_tool.result.dataset, output_names=["y1"])
    assert_results_equal(tool.result.indices, oat_tool.result.indices)
    assert tool.result.metadata.report["doe_dataset_name"] == (
        doe_tool.result.dataset.name
    )


def test_prepared_doe_with_star_settings(tmp_wd, oat_tool, caplog):
    """Check that the settings of the star DOE are ignored with a prepared DOE."""
    OATSensitivityTool().execute(doe_dataset=oat_tool.result.dataset, relative_step=0.1)
    assert "The settings ['relative_step'] are ignored" in caplog.text


@pytest.mark.parametrize(
    ("algo", "algo_settings", "message"),
    [
        ("OT_MONTE_CARLO", {}, "The DOE has 4 samples, whereas a star DOE"),
        (
            "OATDOE",
            {"initial_point": array([0.5, 0.5])},
            "The sample 2 of the DOE must differ from the center",
        ),
    ],
)
def test_not_a_star(tmp_wd, parameter_space, algo, algo_settings, message):
    """Check that the samples of a DOE that is not a star are rejected."""
    doe_tool = DOETool()
    doe_tool.execute(
        model=MockModel("LC1"),
        parameter_space=parameter_space,
        output_names=["y1"],
        algo=algo,
        n_samples=4,
        algo_settings=algo_settings,
    )
    with pytest.raises(ValueError, match=message):
        OATSensitivityTool().execute(doe_dataset=doe_tool.result.dataset)


def test_no_model_nor_doe(tmp_wd):
    """Check that a model or a prepared DOE is required."""
    with pytest.raises(ValueError, match="Either a model or the samples"):
        OATSensitivityTool().execute()


@pytest.mark.parametrize(
    ("two_sided", "gradient", "steps"),
    [
        # The centered difference is exact for a quadratic function.
        (True, [12.0, 12.0, 12.0], [0.05, 0.1, 0.15]),
        (False, [12.05, 12.1, 12.15], [0.05, 0.1, 0.15]),
    ],
)
def test_vector_input_and_output(tmp_wd, two_sided, gradient, steps):
    """Check the indices of y5 = [s, s**2, s**3] with s = sum(x3) and x3 = [1, 2, 3].

    The gradient of s**2 is 2s = 12; its one-sided estimation is 2s+h.
    """
    parameter_space = ParameterSpace()
    parameter_space.add_variable(
        "x3", size=3, lower_bound=0.0, upper_bound=10.0, value=[1.0, 2.0, 3.0]
    )
    tool = OATSensitivityTool()
    tool.execute(
        model=create_model("MockModelPersistent", "LC1"),
        parameter_space=parameter_space,
        output_names=["y5"],
        two_sided=two_sided,
    )
    result = tool.result
    assert result.two_sided is two_sided
    assert_allclose(result.input_steps["x3"], steps)
    assert_allclose(result.indices["gradient"]["y5"][0]["x3"], [1.0, 1.0, 1.0])
    assert_allclose(result.indices["gradient"]["y5"][1]["x3"], gradient)
    table = result.get_indices_dataframe("gradient")
    assert list(table.columns) == ["y5[0]", "y5[1]", "y5[2]"]
    assert list(table.index) == ["x3[0]", "x3[1]", "x3[2]"]


def test_zero_output_at_center(tmp_wd, caplog):
    """Check that the relative indices are NaN when the output is zero at the
    center."""
    parameter_space = ParameterSpace()
    # y4 = sum(x3) is zero at the center.
    parameter_space.add_variable(
        "x3", size=3, lower_bound=-10.0, upper_bound=10.0, value=[1.0, -1.0, 0.0]
    )
    tool = OATSensitivityTool()
    tool.execute(
        model=create_model("MockModelPersistent", "LC1"),
        parameter_space=parameter_space,
        output_names=["y4"],
    )
    assert_allclose(tool.result.input_steps["x3"], [0.05, 0.05, 1.0])
    assert_allclose(tool.result.indices["gradient"]["y4"][0]["x3"], [1.0, 1.0, 1.0])
    assert_allclose(
        tool.result.indices["relative_delta_f"]["y4"][0]["x3"], [float("nan")] * 3
    )
    assert "The output y4 is zero at the center of the star" in caplog.text


def test_serialization(oat_tool):
    """Check that an OAT sensitivity result can be serialized to HDF5."""
    oat_tool.save_results()
    result = BaseTool.load_results(
        oat_tool.working_directory / "OATSensitivityTool_result.hdf5"
    )
    assert isinstance(result, OATSensitivityResult)
    assert_results_equal(result.indices, oat_tool.result.indices)
    assert result.two_sided


def test_plot(oat_tool):
    """Check the tornado diagram."""
    figures = oat_tool.plot_results(oat_tool.result, save=True, show=False)
    assert list(figures) == ["tornado_y1"]
    assert [trace.name for trace in figures["tornado_y1"].data] == [
        "+ step",
        "- step",
    ]
    assert (oat_tool.working_directory / "tornado_y1.html").is_file()


def test_variables_not_sorted(tmp_wd):
    """Check the indices when the variables are not sorted alphabetically.

    The samples of the DOE are ordered like the variables of the parameter space.
    """
    parameter_space = ParameterSpace()
    for name in ["x1_maximum_only", "x1"]:
        parameter_space.add_random_variable(
            name, "OTUniformDistribution", minimum=-1.0, maximum=1.0
        )
    tool = OATSensitivityTool()
    tool.execute(
        model=MockModel("LC1"),
        parameter_space=parameter_space,
        output_names=["y1"],
        center=CENTER,
    )
    assert list(tool.result.center) == ["x1_maximum_only", "x1"]
    assert_allclose(tool.result.indices["gradient"]["y1"][0]["x1"], [2.0])
    assert_allclose(tool.result.indices["gradient"]["y1"][0]["x1_maximum_only"], [0.0])
