---
id: SPEC-006
title: Visualize and tabulate a tool result without its tool
status: Retro (iteration 2 implemented)
requirements: [REQ-RES-001, REQ-RES-002, REQ-RES-003, REQ-RES-004, REQ-RES-006, REQ-TOOL-002]
depends_on: [SPEC-001]
commits: [84fd388c, 7aa06e0c, 35941db6, 61af514f, c138b36f, ffac784a]
owner: Sebastien Bocquet
---

# Visualize and tabulate a tool result without its tool

## Requirements

- Let anyone explore a tool result — figures and numerical tables — from the result
  alone, e.g. loaded from a file or an archive, without the tool nor the model which
  produced it.
- Show everything by default; let the settings narrow the selection.
- Export the figures as static images for reports.
- Out of scope: finding a result from a URI and the command line (SPEC-007); the key
  values logged as metrics (SPEC-005).

Acceptance criteria:

- Given any result class, when `result.visualize()` is called with no setting, then it
  returns all its figures as a flat `dict[str, Figure]` (Plotly or matplotlib), with
  no side effect on disk unless `save=True`.
- Given `result.tabulate()`, then it returns `dict[str, DataFrame]`, with a `settings`
  table when the tool had settings.
- Given a setting which is not a field of the visualization settings of the result,
  then a validation error is raised.
- Given `save=True, file_format="png"`, then the Plotly figures are written as PNG,
  on Linux and on Windows.
- Given a result of a Bayesian analysis whose chains are sampled, then
  `visualize()` shows the MCMC chains.
- Given a DOE varying a single input, then `visualize()` shows the scalar outputs
  versus this input and the curves of the model `PLOTS` superposed for all samples.
- Given `BaseTool.plot_results(...)`, then a `DeprecationWarning` is emitted and the
  figures of `visualize()` are returned.

Acceptance criteria of iteration 2 (review of 2026-10-20/21, decisions 14, 23 and 35 of
the review document):

- Given any result, when `result.plot()` is called with no setting, then it returns the
  same flat `dict[str, Figure]` as `visualize()` did; `result.to_dataframes()` returns
  what `tabulate()` returned.
- Given `result.visualize(...)` or `result.tabulate()`, then a `DeprecationWarning`
  names `plot` or `to_dataframes`, and the same value is returned.
- Given a result class, then its settings class is declared by `_PLOT_SETTINGS` and
  extends `BasePlotSettings`; `get_plot_settings()` and `get_plot_choices()` replace
  `get_visualization_settings()` and `get_visualization_choices()`, which stay as
  deprecated aliases. `BaseVisualizationSettings` stays importable as an alias of
  `BasePlotSettings`.
- Given a DOE varying a single input, then its parametric study figures are drawn by
  the shared function `plot_family`, the one used by the families of a collection
  (SPEC-010): scalar outputs versus the varying input, and the curves of the model
  `PLOTS` superposed, labelled by the value of the varying input.

## Entities

```mermaid
classDiagram
direction TB

class BaseResult {
    +ToolResultMetadata metadata
    +_PLOT_SETTINGS: type
    +plot(settings, directory_path, save, show, file_format, **options) dict
    +to_dataframes() dict~str,DataFrame~
    +get_plot_settings(settings, **options)
    +get_plot_choices() dict~str,list~
    +visualize() deprecated
    +tabulate() deprecated
    +get_key_values() dict~str,float~
    -_create_figures(settings) Mapping
    -_create_tables() dict~str,DataFrame~
}
class BasePlotSettings {
    flat fields, defaults = everything
    alias BaseVisualizationSettings
}
class result_visualization {
    +plot_family(curve_sets, along_values, scalars, along, title) dict
}
class DOEResult {
    +list~Plot~ plots
}
class DOEVisualizationSettings {
    +str abscissa_name
    +tuple output_names
    +tuple scatter_matrix_variable_names
}
class BayesAnalysisResult {
    +plot_mcmc_chains()
}
class BaseTool {
    +plot_results() deprecated
    +load_results(path) BaseResult
}

BaseResult <|-- DOEResult
BaseResult <|-- BayesAnalysisResult
BasePlotSettings <|-- DOEVisualizationSettings
DOEResult --> DOEVisualizationSettings : _PLOT_SETTINGS
DOEResult --> result_visualization : plot_family
BaseTool --> BaseResult : produces, delegates plot_results
```

Other result classes with their own figures and settings: verification,
solution verification, validation point, validation case, calibration step,
sensitivity, statistics, surrogate, space tool.

## Approach

1. Template method on `BaseResult`:
   - `visualize()` validates the settings, calls `_create_figures(settings)`, flattens
     nested mappings into keys joined by `_`, then optionally saves and shows.
   - `tabulate()` calls `_create_tables()` (by default, tabular fields give one table
     each and scalars are gathered in `scalars`) and adds the `settings` table.
   - Each result class declares `_VISUALIZATION_SETTINGS` and overrides
     `_create_figures`, and `_create_tables` if needed.
2. Settings:
   - Flat fields only (numbers, strings, booleans, enums, tuples of strings), each with
     a default meaning *all*, so that a user interface or a command line can build
     them generically.
   - `get_visualization_choices()` lists the names available for the selection
     settings (e.g. the variables of the DOE scatter matrix), for user interfaces.
3. Plotters without side effects:
   - The existing `Plotter` tools are run by `create_figure` in a temporary directory,
     with `archive_manager="none"`, without saving nor showing.
4. Migration from the tools:
   - The `plot_results` overrides of the tools move to `_create_figures` of their
     results. `BaseTool.plot_results` is deprecated and delegates to `visualize()`,
     mapping the old singular options (`output_name`) to the plural settings.
   - The Bayesian post-processing is stored in the result (`metadata.misc["post"]`,
     observed data, free parameter names) and the result is published again in the
     archive (`_republish_result`).
   - The DOE result stores the figures of the model (`DOEResult.plots`, from
     `IntegratedModel.plots`): the model description no longer holds them since
     upstream `3fa371bb` removed `ModelDescription.plots`.
5. Loading without knowing the class: `load_result_file()` and
   `load_result_buffer()` read the class from the HDF5 attributes.
6. Static export: `kaleido` (0.2.1; 0.1.0.post1 on Windows, where 0.2.1 hangs), as
   kaleido ≥ 1 needs plotly ≥ 6.1.
7. Rejected alternatives:
   - Keeping the plots in the tools: a result could not be visualized after loading.
   - Nested visualization settings: they cannot be built generically by a CLI or a
     dashboard.
8. Names of iteration 2 (review of 2026-10-20/21):
   - `plot()` replaces `visualize()`: the verb says what is returned (figures), and it is
     the verb of the collections of SPEC-010 (`ModelResults.plot()`, `Families.plot()`).
     `to_dataframes()` replaces `tabulate()`: it returns `DataFrame` objects of numerical
     values, aligned on `to_dataframe()` / `to_dataset()` of the collections.
   - The settings follow: `_PLOT_SETTINGS`, `BasePlotSettings`, `get_plot_settings`,
     `get_plot_choices`. The figure keys and file names do not change.
   - The old names are public since this branch: `visualize`, `tabulate`,
     `get_visualization_settings`, `get_visualization_choices` stay one version as
     deprecated aliases (`DeprecationWarning`); `BaseVisualizationSettings` is a plain
     alias (no warning, a class alias cannot warn at import). `_VISUALIZATION_SETTINGS`
     is renamed without alias: it is private.
   - No collision with `BaseTool.plot_results`, deprecated since iteration 1.
   - The command line `visualize_tool_result` keeps its name (CLIs deprioritized); it
     calls `plot()` and `to_dataframes()`.
9. One drawing of a parametric family (iteration 2, decision 14):
   - The DOE parametric study (`doe_plots.py`) and the families of a collection
     (SPEC-010) draw the same thing: results differing by one input. A single function
     `plot_family(curve_sets, along_values, scalars, along, title)` in
     `tools/result_visualization.py` returns the figures: one per plot name, superposing
     one trace per result labelled `{along} = {value}` and sorted by value, plus one figure
     "scalar output versus `along`" per scalar output.
   - `DOEResult` calls it from its stored data (`plots` and the dataset), without
     reloading its simulations from the archive.

## Structure

### Inheritance Relationships

1. Every result class extends `BaseResult` and may define a settings class extending
   `BaseVisualizationSettings`.

### Dependencies

1. `BaseResult` → `result_visualization` (`flatten_figures`, `save_figures`,
   `show_figures`, `fields_to_dataframes`, `settings_to_dataframe`).
2. Result classes → `create_figure` → `Plotter` tools.
3. `BaseTool.plot_results`, `BaseTool.load_results` → `BaseResult.visualize`,
   `load_result_file`.

### Layered Architecture

1. `tools/base_result.py`: the contract.
2. `tools/result_visualization.py`: generic helpers for figures and tables.
3. `tools/*/*_result.py`, `tools/doe/doe_plots.py`: the figures of each tool.

## Operations

### Update - `BaseResult`

1. Add `_VISUALIZATION_SETTINGS`, `visualize`, `get_visualization_settings`,
   `get_visualization_choices`, `_create_figures`, `tabulate`, `_create_tables`.

### Create - `vimseo/tools/result_visualization.py`

1. `BaseVisualizationSettings`, `KEY_SEPARATOR`, `flatten_figures`, `get_file_stem`,
   `save_figures` (matplotlib in PNG when the format is HTML), `show_figures`,
   `create_figure`, and the table helpers (`to_cell`, `mapping_to_dataframe`,
   `value_to_dataframe`, `fields_to_dataframes`, `settings_to_dataframe`).

### Move figures to results

1. For each tool overriding `plot_results`: create or extend its result class with a
   settings class and `_create_figures`; delete the override from the tool; update its
   examples.
2. `BayesAnalysisResult`: `plot_mcmc_chains`, posterior and predictive plots; remove
   `BayesTool.plot_burnin`, `plot_posterior_distribution`,
   `plot_predictive_distribution`.
3. `DOEResult`: store the model description and the figures of the model
   (`plots`, set by `DOETool` and `CustomDOETool`); scatter matrix with
   `scatter_matrix_variable_names`; parametric study when a single input varies
   (`doe_plots.py`).

### Update - `BaseTool`

1. Deprecate `plot_results`; drop the pickle format; `load_results` uses
   `load_result_file`.

### Create - `tool_results_factory.load_result_file`, `load_result_buffer`

### Update dependencies

1. `pyproject.toml`: `kaleido` with platform markers.

### Tests

1. `tests/tools/test_result_visualization.py`, and per tool (`test_doe.py`,
   `test_bayes.py`, ...): default visualization of each result, settings validation,
   tables, image export.

### Iteration 2 (review of 2026-10-20/21) - `plot`, `to_dataframes`, `plot_family`

1. `tools/base_result.py`: rename `visualize` → `plot`, `tabulate` → `to_dataframes`,
   `get_visualization_settings` → `get_plot_settings`, `get_visualization_choices` →
   `get_plot_choices`, `_VISUALIZATION_SETTINGS` → `_PLOT_SETTINGS`; add the four old
   method names as deprecated aliases, each emitting a `DeprecationWarning` naming the
   new one and returning its value.
2. `tools/result_visualization.py`: rename `BaseVisualizationSettings` →
   `BasePlotSettings`, keep `BaseVisualizationSettings = BasePlotSettings`; add
   `plot_family(curve_sets, along_values, scalars, along, title="") -> dict[str, Figure]`
   (curve sets: one sequence of `CurveSet` per result; along values: one per result;
   scalars: one mapping name → number per result), built on `superpose_curves`.
3. Every result class: `_VISUALIZATION_SETTINGS` → `_PLOT_SETTINGS`, settings classes
   extend `BasePlotSettings`; their names stay (`DOEVisualizationSettings`, ...) to
   limit the churn.
4. `tools/doe/doe_plots.py`: the parametric study calls `plot_family`.
5. Callers in `src/` (CLI `visualize_tool_result`, `BaseTool.plot_results`, dashboards
   of `vimseo`), tests and examples: the new names.
6. Tests: `plot()` and `to_dataframes()` return what the old methods returned; each old
   name warns; `plot_family` with two results and one scalar output gives one figure per
   plot name plus one per scalar, traces sorted by the varying input.
7. `CHANGELOG.md`: the renamed methods and their deprecated aliases.

## Norms

1. The shared norms of `docs/specs/index.md`.
2. A result never needs its tool to be visualized: no reference to a tool instance in
   `_create_figures`.
3. Visualization settings are flat, and default to "everything".
4. Figure keys are stable: they are the file names of the saved figures.

## Safeguards

1. Functional: `visualize()` without `save`/`show` has no side effect on disk.
2. Functional: creating a figure never archives a tool run.
3. Breaking changes `84fd388c` (`feat(results)!`): the keys and file names of the
   figures change; the pickle format is removed; `ModelResult` of `model_tool` is
   renamed `ModelCreationResult`.
4. Breaking change `7aa06e0c` (`feat(bayes)!`): `BayesTool.plot_burnin`,
   `plot_posterior_distribution`, `plot_predictive_distribution` are removed; use the
   methods of the result.
5. Platform: the image export works on Windows with kaleido 0.1.0.post1.
6. Tests: every result class is visualized with default settings.
7. Compatibility (iteration 2): `visualize`, `tabulate`, `get_visualization_settings`,
   `get_visualization_choices` and `BaseVisualizationSettings` keep working, with a
   `DeprecationWarning` for the methods; a subclass overriding `_VISUALIZATION_SETTINGS`
   outside VIMSEO must rename it (private name, noted in `CHANGELOG.md`).

## Open questions

1. `kaleido` is a **mandatory** dependency, while REQ-DEP-001 asks for an install
   without a graphical stack. Should it move to an extra (e.g. `export`)?
2. When will `BaseTool.plot_results` be removed?
3. Should the figure keys be documented as a stable interface, since they are file
   names?
