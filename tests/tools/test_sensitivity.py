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
from pandas.testing import assert_frame_equal

from vimseo.api import create_model
from vimseo.problems.mock.mock_pre_run_post.mock_main import MockModel
from vimseo.tools.base_result import assert_results_equal
from vimseo.tools.base_tool import BaseTool
from vimseo.tools.doe.doe import DOETool
from vimseo.tools.sensitivity.sensitivity import SensitivityTool
from vimseo.tools.sensitivity.sensitivity import SensitivityToolInputs
from vimseo.tools.sensitivity.sensitivity import SensitivityToolSettings
from vimseo.tools.sensitivity.sensitivity_result import SensitivityResult


@pytest.fixture
def parameter_space():
    parameter_space = ParameterSpace()
    parameter_space.add_random_variable(
        "x1", "OTUniformDistribution", size=1, minimum=-1.0, maximum=1.0
    )
    parameter_space.add_random_variable(
        "x1_maximum_only", "OTUniformDistribution", size=1, minimum=-1.0, maximum=1.0
    )
    return parameter_space


@pytest.fixture
def sensitivity_tool(parameter_space):
    model = MockModel("LC1")
    sensitivity_tool = SensitivityTool()
    sensitivity_tool.execute(
        model=model,
        parameter_space=parameter_space,
        sensitivity_algo="MorrisAnalysis",
        n_replicates=5,
    )
    return sensitivity_tool


def test_mockmodel_morris(tmp_wd, sensitivity_tool):
    assert pytest.approx(
        sensitivity_tool.result.indices.mu["y1"][0]["x1"], 0.01
    ) == array([0.2])


def test_hsic(tmp_wd, parameter_space):
    """Check that a HSIC sensitivity analysis can be performed."""
    model = MockModel("LC1")
    sensitivity_tool = SensitivityTool()
    sensitivity_tool.execute(
        inputs=SensitivityToolInputs(parameter_space=parameter_space, model=model),
        settings=SensitivityToolSettings(sensitivity_algo="HSIC", n_samples=10),
    )
    assert sensitivity_tool.result.indices.hsic["y1"][0]["x1"] == pytest.approx(
        0.1138726
    )


@pytest.mark.parametrize(
    ("sensitivity_algo", "settings", "expected_indices"),
    [
        (
            "Morris",
            {"n_replicates": 5},
            {
                "attr": "mu",
                "x1": array([0.0]),
                "x3": array([0.040035, 0.043367, 0.122493]),
            },
        ),
        (
            "HSIC",
            {"n_samples": 10},
            {
                "attr": "hsic",
                "x1": array([0.00417611]),
                "x3": array([-0.00311482, -0.01120872, -0.00406003]),
            },
        ),
    ],
)
def test_sensitivity_vector_input(tmp_wd, sensitivity_algo, settings, expected_indices):
    """Check that a sensitivity analysis can be performed on a vector input."""
    model = create_model("MockModelPersistent", "LC1")
    parameter_space = ParameterSpace()
    parameter_space.add_random_vector(
        "x3",
        "OTNormalDistribution",
        size=3,
        mu=[1.0, 1.5, 1.9],
        sigma=[0.2],
    )
    parameter_space.add_random_variable(
        "x1", "OTUniformDistribution", minimum=0.0, maximum=2.0
    )
    sensitivity_tool = SensitivityTool()
    sensitivity_tool.execute(
        inputs=SensitivityToolInputs(parameter_space=parameter_space, model=model),
        settings=SensitivityToolSettings(
            sensitivity_algo=sensitivity_algo, output_names=["y4", "y5"], **settings
        ),
    )
    for name in ["x1", "x3"]:
        assert_allclose(
            getattr(sensitivity_tool.result.indices, expected_indices["attr"])["y4"][0][
                name
            ],
            expected_indices[name],
            rtol=1e-5,
        )
    sensitivity_tool.save_results()
    sensitivity_tool.plot_results(
        sensitivity_tool.result, output_names=["y4"], save=True, show=False
    )


def test_save_and_load_result(tmp_wd, sensitivity_tool):
    """Check that a sensitivity analysis can be saved and that a new instance can be
    created and loaded from saved data.

    A plot can be generated from the new instance.
    """
    sensitivity_tool.save_results()
    results = BaseTool.load_results(
        sensitivity_tool.working_directory / "SensitivityTool_result.hdf5"
    )
    assert pytest.approx(results.indices.mu["y1"][0]["x1"], 0.01) == array([0.2])


def test_plots(tmp_wd, sensitivity_tool):
    sensitivity_tool.plot_results(
        sensitivity_tool.result,
        save=True,
        show=False,
        output_names=["y1"],
        standardize=True,
    )
    expected_filenames = ["bar_plot.html", "radar_chart.png", "standard_plot_y1.png"]
    for name in expected_filenames:
        assert (sensitivity_tool.working_directory / name).is_file()


def test_serialization(tmp_wd, sensitivity_tool):
    """Check that a SensitivityResult can be serialized to hdf5."""
    result = sensitivity_tool.result
    result.to_hdf5("result.hdf5")
    serialized_result = SensitivityResult.from_hdf5("result.hdf5")
    assert_results_equal(result, serialized_result)


def _prepare_doe(parameter_space, algo, n_samples, output_names=()):
    """Return the samples of a DOE of MockModel prepared in advance."""
    doe_tool = DOETool()
    doe_tool.execute(
        model=MockModel("LC1"),
        parameter_space=parameter_space,
        algo=algo,
        n_samples=n_samples,
        output_names=list(output_names),
    )
    return doe_tool.result.dataset


def test_morris_prepared_doe(tmp_wd, parameter_space, sensitivity_tool):
    """Check a Morris analysis from the samples of a MorrisDOE prepared in advance.

    The DOE computes all the outputs of the model, including its metadata, which are
    filtered out.
    """
    dataset = _prepare_doe(parameter_space, "MorrisDOE", 15)
    tool = SensitivityTool()
    tool.execute(
        inputs=SensitivityToolInputs(doe_dataset=dataset),
        settings=SensitivityToolSettings(sensitivity_algo="Morris"),
    )
    assert tool.result.metadata.report["output_names"] == ["y1"]
    assert tool.result.metadata.report["doe_dataset_name"] == dataset.name
    assert tool.result.variable_dimensions == {
        "x1": 1,
        "x1_maximum_only": 1,
        "y1": 1,
    }
    for name in ["x1", "x1_maximum_only"]:
        assert tool.result.indices.mu["y1"][0][name] == pytest.approx(
            sensitivity_tool.result.indices.mu["y1"][0][name]
        )
    tool.result.analysis.compute_indices(normalize=True)


def test_hsic_prepared_doe(tmp_wd, parameter_space):
    """Check a HSIC analysis from the i.i.d. samples of a Monte Carlo sampling
    prepared in advance."""
    tool = SensitivityTool()
    tool.execute(
        doe_dataset=_prepare_doe(parameter_space, "OT_MONTE_CARLO", 10, ["y1"]),
        sensitivity_algo="HSIC",
    )
    assert set(tool.result.indices.hsic["y1"][0]) == {"x1", "x1_maximum_only"}


def test_morris_prepared_doe_not_morris(tmp_wd, parameter_space):
    """Check that a Morris analysis rejects the samples of a DOE other than
    MorrisDOE."""
    with pytest.raises(ValueError, match="use the DOE algorithm 'MorrisDOE'"):
        SensitivityTool().execute(
            doe_dataset=_prepare_doe(parameter_space, "OT_OPT_LHS", 6, ["y1"]),
            sensitivity_algo="Morris",
        )


def test_no_model_nor_doe(tmp_wd):
    """Check that a model or a prepared DOE is required."""
    with pytest.raises(ValueError, match="Either a model or the samples"):
        SensitivityTool().execute(sensitivity_algo="HSIC")


def test_morris_prepared_doe_variables_not_sorted(tmp_wd):
    """Check a Morris analysis from a prepared DOE whose variables are not sorted
    alphabetically.

    The samples of the DOE are ordered like the variables of the parameter space.
    """
    parameter_space = ParameterSpace()
    for name in ["x1_maximum_only", "x1"]:
        parameter_space.add_random_variable(
            name, "OTUniformDistribution", minimum=-1.0, maximum=1.0
        )
    tool = SensitivityTool()
    tool.execute(
        doe_dataset=_prepare_doe(parameter_space, "MorrisDOE", 15, ["y1"]),
        sensitivity_algo="Morris",
    )
    assert tool.result.indices.mu["y1"][0]["x1"] == pytest.approx(0.2)
    assert tool.result.indices.mu["y1"][0]["x1_maximum_only"] == pytest.approx(0.0)


def test_indices_dataframe(tmp_wd, sensitivity_tool):
    """Check the table of the indices, by default the main ones."""
    result = sensitivity_tool.result
    table = result.get_indices_dataframe()
    assert list(table.columns) == ["y1"]
    assert list(table.index) == ["x1", "x1_maximum_only"]
    assert table.loc["x1", "y1"] == pytest.approx(
        float(result.indices.mu_star["y1"][0]["x1"][0])
    )
    sigma = result.get_indices_dataframe("sigma")
    assert sigma.loc["x1", "y1"] == pytest.approx(
        float(result.indices.sigma["y1"][0]["x1"][0])
    )


def test_indices_dataframe_loaded_result(tmp_wd, sensitivity_tool):
    """Check the table of the indices of a result loaded from the disk.

    The HDF5 serialization does not preserve the order of the inputs.
    """
    sensitivity_tool.save_results()
    result = BaseTool.load_results(
        sensitivity_tool.working_directory / "SensitivityTool_result.hdf5"
    )
    assert_frame_equal(
        result.get_indices_dataframe(),
        sensitivity_tool.result.get_indices_dataframe(),
        check_like=True,
    )


def test_indices_dataframe_hsic_vector(tmp_wd):
    """Check the table of the main HSIC indices for vector inputs and outputs."""
    parameter_space = ParameterSpace()
    parameter_space.add_random_vector(
        "x3", "OTNormalDistribution", size=3, mu=[1.0, 1.5, 1.9], sigma=[0.2]
    )
    tool = SensitivityTool()
    tool.execute(
        model=create_model("MockModelPersistent", "LC1"),
        parameter_space=parameter_space,
        sensitivity_algo="HSIC",
        n_samples=10,
        output_names=["y5"],
    )
    table = tool.result.get_indices_dataframe()
    assert list(table.columns) == ["y5[0]", "y5[1]", "y5[2]"]
    assert list(table.index) == ["x3[0]", "x3[1]", "x3[2]"]
    assert table.loc["x3[1]", "y5[2]"] == pytest.approx(
        float(tool.result.indices.r2_hsic["y5"][2]["x3"][1])
    )
