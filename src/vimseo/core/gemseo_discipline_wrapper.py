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

from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from gemseo import READ_ONLY_EMPTY_DICT
from gemseo.core.discipline import Discipline
from gemseo.core.discipline.io import IO
from gemseo.utils.string_tools import pretty_str

try:
    from gemseo.core.grammar.error import InvalidDataError
except ImportError:  # gemseo < 7
    from gemseo.core.grammars.errors import InvalidDataError

if TYPE_CHECKING:
    from gemseo.core.discipline.discipline_data import DisciplineData
    from gemseo.typing import StrKeyMapping

_GEMSEO_HAS_FORBID_EXTRA_OUTPUT_NAMES = hasattr(IO, "get_extra_output_names")
"""Whether the installed GEMSEO natively provides ``forbid_extra_output_names``."""


class GemseoDisciplineWrapper(Discipline):
    """A wrapper around a Gemseo Discipline.

    It adds some practical public methods, and allows to check if extra names
    are present in the input data. It is useful to prevent users from making typos
    in the input data.
    """

    EXTRA_INPUT_GRAMMAR_CHECK: ClassVar[bool] = False

    forbid_extra_output_names: bool
    """Whether to raise an error when ``_run()`` returns names not in the output grammar.

    Otherwise, these names are silently ignored by GEMSEO.
    Backport of ``BaseDiscipline.forbid_extra_output_names`` (GEMSEO MR !2821).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Same name, default and semantics as GEMSEO, so that this backport
        # can be removed without changing the callers.
        if not _GEMSEO_HAS_FORBID_EXTRA_OUTPUT_NAMES:
            self.forbid_extra_output_names = False

    # TODO remove _execute and _get_extra_output_names once the minimal gemseo
    # version ships forbid_extra_output_names (GEMSEO MR !2821).
    def _get_extra_output_names(self, output_data: StrKeyMapping) -> set[str]:
        """Return the names of ``output_data`` that ``update_output_data`` would drop.

        Backport of ``IO.get_extra_output_names``.
        """
        output_grammar = self.io.output_grammar
        return (
            output_data.keys()
            - output_grammar.keys()
            - output_grammar.to_namespaced.keys()
        )

    def _execute(self) -> None:
        if _GEMSEO_HAS_FORBID_EXTRA_OUTPUT_NAMES:
            super()._execute()
            return

        # Mirror of the default ``BaseDiscipline._execute`` plus the strict check.
        io = self.io
        if io.input_grammar.to_namespaced:
            input_data = io.get_input_data(with_namespaces=False)
        else:
            input_data = io._data

        data_processor = io.data_processor
        if data_processor is not None:
            input_data = data_processor.pre_process_data(input_data)

        output_data = self._run(input_data=input_data)

        if output_data is not None:
            if data_processor is not None:
                output_data = data_processor.post_process_data(output_data)

            if self.forbid_extra_output_names and (
                extra_names := self._get_extra_output_names(output_data)
            ):
                msg = (
                    f"The discipline {self.name} returned outputs "
                    "that are not in its output grammar: "
                    f"{pretty_str(extra_names)}. "
                    "This strict check was enabled by setting "
                    "forbid_extra_output_names attribute to True."
                )
                raise InvalidDataError(msg)

            io.update_output_data(output_data)

    def _get_input_data(self) -> dict[str, Any]:
        return self.get_input_data(with_namespaces=False)

    def get_input_data_names(self):
        return list(self.input_grammar.names)

    def get_output_data_names(self):
        return list(self.output_grammar.names)

    def execute(
        self,
        input_data: StrKeyMapping = READ_ONLY_EMPTY_DICT,
    ) -> DisciplineData:

        if self.EXTRA_INPUT_GRAMMAR_CHECK:
            from vimseo.core.base_integrated_model import IntegratedModel

            all_input_names = list(input_data.keys()) + list(
                self.default_input_data.keys()
            )

            if (isinstance(self, (IntegratedModel))) and not set(
                all_input_names
            ).issubset(set(self.input_grammar.names)):
                extra_inputs = list(
                    set(all_input_names) - set(self.input_grammar.names)
                )
                msg = (
                    f"Input {extra_inputs} are not defined in the input grammar."
                    f"Input grammar names are {list(self.input_grammar.names)}."
                )
                raise KeyError(msg)

        return super().execute(input_data)
