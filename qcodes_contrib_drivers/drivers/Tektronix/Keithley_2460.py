import numpy as np
from typing import cast, Dict, Union

from qcodes import VisaInstrument, InstrumentChannel, ParameterWithSetpoints
from qcodes.utils.validators import Enum, Numbers, Arrays, Ints
from qcodes.utils.helpers import create_on_off_val_mapping


class Sense2460(InstrumentChannel):
    """
    The sense module of the Keithley 2460 SMU.

    Args:
        parent
        name
        proper_function: This can be one of either "current", "voltage"
            or "resistance". All parameters and methods in this submodule
            should only be accessible to the user if
            self.parent.sense_function.get() == self._proper_function. We
            ensure this through the 'sense' property on the main driver class
            which returns the proper submodule for any given function mode
    """

    function_modes = {
        "current": {
            "name": '"CURR:DC"',
            "unit": "A",
            #"range_vals": Numbers(10E-9, 1)
            "range_vals": Numbers(1E-6, 7)
        },
        "resistance": {
            "name": '"RES"',
            "unit": "Ohm",
            "range_vals": Numbers(20, 20E6)
        },
        "voltage": {
            "name": '"VOLT:DC"',
            "unit": "V",
            "range_vals": Numbers(0.2, 100)
        }
    }

    def __init__(self, parent: 'Keithley2460', name: str, proper_function: str) -> None:
        super().__init__(parent, name)
        self._proper_function = proper_function
        range_vals = self.function_modes[self._proper_function]["range_vals"]
        unit = self.function_modes[self._proper_function]["unit"]

        self.function = self.parent.sense_function

        self.add_parameter(
            "four_wire_measurement",
            set_cmd=f":SENSe:{self._proper_function}:RSENse {{}}",
            get_cmd=f":SENSe:{self._proper_function}:RSENse?",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0")
        )

        self.add_parameter(
            "range",
            set_cmd=f":SENSe:{self._proper_function}:RANGe {{}}",
            get_cmd=f":SENSe:{self._proper_function}:RANGe?",
            vals=range_vals,
            get_parser=float,
            unit=unit
        )

        self.add_parameter(
            "auto_range",
            set_cmd=f":SENSe:{self._proper_function}:RANGe:AUTO {{}}",
            get_cmd=f":SENSe:{self._proper_function}:RANGe:AUTO?",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0")
        )

        self.add_parameter(
            self._proper_function,
            get_cmd=self._measure,
            get_parser=float,
            unit=unit,
            snapshot_value=False
        )

        self.add_parameter(
            "sweep",
            label=self._proper_function,
            get_cmd=self._measure_sweep,
            unit=unit,
            vals=Arrays(shape=(self.parent.npts,)),
            parameter_class=ParameterWithSetpoints
        )

        self.add_parameter(
            "nplc",
            get_cmd=f":SENSe:{self._proper_function}:NPLCycles?",
            set_cmd=f":SENSe:{self._proper_function}:NPLCycles {{}}",
            vals=Numbers(0.001, 10)
        )

        self.add_parameter(
            'user_number',
            get_cmd=None,
            set_cmd=None,
            vals=Ints(1, 5)
        )

        self.add_parameter(
            "user_delay",
            get_cmd=self._get_user_delay,
            set_cmd=self._set_user_delay,
            vals=Numbers(0, 1e4)
        )

    def _measure(self) -> str:
        if not self.parent.output_enabled():
            raise RuntimeError("Output needs to be on for a measurement")
        return self.ask(":MEASure?")

    def _measure_sweep(self) -> np.ndarray:

        source = cast(Source2460, self.parent.source)
        source.sweep_start()
        raw_data = self.ask(f":TRACe:DATA? 1, {self.parent.npts()}")
        # Clear the trace so we can be assured that a subsequent measurement
        # will not be contaminated with data from this run.
        self.clear_trace()

        return np.array([float(i) for i in raw_data.split(",")])

    def clear_trace(self) -> None:
        """
        Clear the data buffer
        """
        self.write(":TRACe:CLEar")

    def _get_user_delay(self) -> str:
        get_cmd = f":SENSe:{self._proper_function}:DELay:USER" \
                  f"{self.user_number()}?"
        return self.ask(get_cmd)

    def _set_user_delay(self, value) -> None:
        set_cmd = f":SENSe:{self._proper_function}:DELay:USER" \
                  f"{self.user_number()} {value}"
        self.write(set_cmd)


class Source2460(InstrumentChannel):
    """
    The source module of the Keithley 2460 SMU.

    Args:
        parent
        name
        proper_function: This can be one of either "current" or "voltage"
            All parameters and methods in this submodule should only be
            accessible to the user if
            self.parent.source_function.get() == self._proper_function. We
            ensure this through the 'source' property on the main driver class
            which returns the proper submodule for any given function mode
    """
    function_modes = {
        "current": {
            "name": "CURR",
            "unit": "A",
            "range_vals": Numbers(-7, 7)
        },
        "voltage": {
            "name": "VOLT",
            "unit": "V",
            "range_vals": Numbers(-100, 100)
        }
    }

    def __init__(self, parent: 'Keithley2460', name: str, proper_function: str) -> None:
        super().__init__(parent, name)
        self._proper_function = proper_function
        range_vals = self.function_modes[self._proper_function]["range_vals"]
        unit = self.function_modes[self._proper_function]["unit"]

        self.function = self.parent.source_function
        self._sweep_arguments: Dict[str, Union[float, int, str]] = {}

        self.add_parameter(
            "range",
            set_cmd=f":SOUR:{self._proper_function}:RANGe {{}}",
            get_cmd=f":SOUR:{self._proper_function}:RANGe?",
            vals=range_vals,
            get_parser=float,
            unit=unit
        )

        self.add_parameter(
            "auto_range",
            set_cmd=f":SOURce:{self._proper_function}:RANGe:AUTO {{}}",
            get_cmd=f":SOURce:{self._proper_function}:RANGe:AUTO?",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0")
        )

        limit_cmd = {"current": "VLIM", "voltage": "ILIM"}[self._proper_function]
        self.add_parameter(
            "limit",
            set_cmd=f"SOUR:{self._proper_function}:{limit_cmd} {{}}",
            get_cmd=f"SOUR:{self._proper_function}:{limit_cmd}?",
            get_parser=float,
            unit=unit
        )

        self.add_parameter(
            "limit_tripped",
            get_cmd=f":SOUR:{self._proper_function}:{limit_cmd}:TRIPped?",
            val_mapping={True: 1, False: 0}
        )

        self.add_parameter(
            self._proper_function,
            set_cmd=f"SOUR:{self._proper_function} {{}}",
            get_cmd=f"SOUR:{self._proper_function}?",
            get_parser=float,
            unit=unit,
            snapshot_value=False
        )

        self.add_parameter(
            "sweep_axis",
            label=self._proper_function,
            get_cmd=self.get_sweep_axis,
            vals=Arrays(shape=(self.parent.npts,)),
            unit=unit
        )

        self.add_parameter(
            "delay",
            get_cmd=f":SOURce:{self._proper_function}:DELay?",
            set_cmd=f":SOURce:{self._proper_function}:DELay {{}}",
            vals=Numbers(0, 1e4)
        )

        self.add_parameter(
            'user_number',
            get_cmd=None,
            set_cmd=None,
            vals=Ints(1, 5)
        )

        self.add_parameter(
            "user_delay",
            get_cmd=self._get_user_delay,
            set_cmd=self._set_user_delay,
            vals=Numbers(0, 1e4)
        )

        self.add_parameter(
            "auto_delay",
            get_cmd=f":SOURce:{self._proper_function}:DELay:AUTO?",
            set_cmd=f":SOURce:{self._proper_function}:DELay:AUTO {{}}",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0")
        )

    def get_sweep_axis(self) -> np.ndarray:
        if self._sweep_arguments == {}:
            raise ValueError(
                "Please setup the sweep before getting values of this parameter"
            )

        return np.linspace(
            start=self._sweep_arguments["start"],
            stop=self._sweep_arguments["stop"],
            num=self._sweep_arguments["step_count"]
        )

    def sweep_setup(
            self,
            start: float,
            stop: float,
            step_count: int,
            delay: float = 0,
            sweep_count: int = 1,
            range_mode: str = "AUTO"
    ) -> None:

        self._sweep_arguments = dict(
            start=start,
            stop=stop,
            step_count=step_count,
            delay=delay,
            sweep_count=sweep_count,
            range_mode=range_mode
        )

    def sweep_start(self) -> None:
        """
        Start a sweep and return when the sweep has finished.
        Note: This call is blocking
        """
        cmd_args = dict(self._sweep_arguments)
        cmd_args["function"] = self._proper_function

        cmd = ":SOURce:SWEep:{function}:LINear {start},{stop}," \
              "{step_count},{delay},{sweep_count},{range_mode}".format(**cmd_args)

        self.write(cmd)
        self.write(":INITiate")
        self.write("*WAI")

    def sweep_reset(self) -> None:
        self._sweep_arguments = {}

    def _get_user_delay(self) -> str:
        get_cmd = f":SOURce:{self._proper_function}:DELay:USER" \
                  f"{self.user_number()}?"
        return self.ask(get_cmd)

    def _set_user_delay(self, value) -> None:
        set_cmd = f":SOURce:{self._proper_function}:DELay:USER" \
                  f"{self.user_number()} {value}"
        self.write(set_cmd)


class Keithley2460(VisaInstrument):
    """
    The QCoDeS driver for the Keithley 2460 SMU
    """

    def __init__(self, name: str, address: str, **kwargs) -> None:

        super().__init__(name, address, terminator='\n', **kwargs)

        if not self._has_correct_language_mode():
            self.log.warning(
                f"The instrument is in an unsupported language mode. "
                f"Please run `instrument.set_correct_language()` and try to "
                f"initialize the driver again after an instrument power cycle. "
                f"No parameters/sub modules will be available on this driver "
                f"instance"
            )
            return

        self.add_parameter(
            "source_function",
            set_cmd=self._set_source_function,
            get_cmd=":SOUR:FUNC?",
            val_mapping={
                key: value["name"]
                for key, value in Source2460.function_modes.items()
            }
        )

        self.add_parameter(
            "sense_function",
            set_cmd=self._set_sense_function,
            get_cmd=":SENS:FUNC?",
            val_mapping={
                key: value["name"]
                for key, value in Sense2460.function_modes.items()
            }
        )

        self.add_parameter(
            "terminals",
            set_cmd="ROUTe:TERMinals {}",
            get_cmd="ROUTe:TERMinals?",
            vals=Enum("rear", "front")
        )

        self.add_parameter(
            "output_enabled",
            set_cmd=":OUTP {}",
            get_cmd=":OUTP?",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0")
        )

        # Make a source module for every source function ('current' and 'voltage')
        for proper_source_function in Source2460.function_modes:
            self.add_submodule(
                f"_source_{proper_source_function}",
                Source2460(self, "source", proper_source_function)
            )

        # Make a sense module for every sense function ('current', voltage' and 'resistance')
        for proper_sense_function in Sense2460.function_modes:
            self.add_submodule(
                f"_sense_{proper_sense_function}",
                Sense2460(self, "sense", proper_sense_function)
            )

        self.connect_message()

    def _set_sense_function(self, value: str) -> None:
        """
        Change the sense function. The property 'sense' will return the
        sense module appropriate for this function setting.

        We need to ensure that the setpoints of the sweep parameter in the
        active sense module is correctly set. Normally we would do that
        with 'self.sense.sweep.setpoints = (self.source.sweep_axis,)'

        However, we cannot call the property 'self.sense', because that property
        will call `get_latest` on the parameter for which this function
        (that is '_set_sense_function') is the setter
        """
        self.write(f":SENS:FUNC {value}",)
        sense_function = self.sense_function.inverse_val_mapping[value]
        sense = self.submodules[f"_sense_{sense_function}"]
        if not isinstance(sense, Sense2460):
            raise RuntimeError(f"Expect Sense Module to be of type "
                               f"Sense2460 got {type(sense)}")
        sense.sweep.setpoints = (self.source.sweep_axis,)

    def _set_source_function(self, value: str) -> None:
        """
        Change the source function. The property 'source' will return the
        source module appropriate for this function setting.

        We need to ensure that the setpoints of the sweep parameter in the
        active sense module reflects the change in the source module.
        Normally we would do that with
        'self.sense.sweep.setpoints = (self.source.sweep_axis,)'

        However, we cannot call the property 'self.source', because that property
        will call `get_latest` on the parameter for which this function
        (that is '_set_source_function') is the setter
        """

        if self.sense_function() == "resistance":
            raise RuntimeError(
                "Cannot change the source function while sense function is in 'resistance' mode"
            )

        self.write(f":SOUR:FUNC {value}")
        source_function = self.source_function.inverse_val_mapping[value]
        source = self.submodules[f"_source_{source_function}"]
        self.sense.sweep.setpoints = (source.sweep_axis,)
        if not isinstance(source, Source2460):
            raise RuntimeError(f"Expect Sense Module to be of type "
                               f"Source2460 got {type(source)}")
        # Once the source function has changed,
        # we cannot trust the sweep setup anymore
        source.sweep_reset()

    @property
    def source(self) -> Source2460:
        """
        We have different source modules depending on the source function, which can be
        'current' or 'voltage'

        Return the correct source module based on the source function
        """
        source_function = self.source_function.get_latest() or self.source_function()
        submodule = self.submodules[f"_source_{source_function}"]
        return cast(Source2460, submodule)

    @property
    def sense(self) -> Sense2460:
        """
        We have different sense modules depending on the sense function, which can be
        'current', 'voltage' or 'resistance'

        Return the correct source module based on the sense function
        """
        sense_function = self.sense_function.get_latest() or self.sense_function()
        submodule = self.submodules[f"_sense_{sense_function}"]
        return cast(Sense2460, submodule)

    def npts(self) -> int:
        """
        Get the number of points in the sweep axis
        """
        return len(self.source.get_sweep_axis())

    def set_correct_language(self) -> None:
        """
        The correct communication protocol is SCPI, make sure this is set
        """
        self.write("*LANG SCPI")
        self.log.warning("Please power cycle the instrument to make the change take effect")
        # We want the user to be able to instantiate a driver with the same name
        self.close()

    def _has_correct_language_mode(self) -> bool:
        """
        Query if we have the correct language mode
        """
        return self.ask("*LANG?") == "SCPI"

    def abort(self) -> None:
        """
        This command stops all trigger model commands on the instrument.
        """
        self.write(":ABORt")

    def initiate(self) -> None:
        """
        This command starts the trigger model.
        """
        self.write(":INITiate")

    def wait(self) -> None:
        """
        This command postpones the execution of subsequent commands until all
        previous overlapped commands are finished.
        """
        self.write("*WAI")

    def clear_event_register(self) -> None:
        """
        This function clears event registers.
        """
        self.write(":STATus:CLEar")

    def clear_event_log(self) -> None:
        """
        This command clears the event log.
        """
        self.write(":SYSTem:CLEar")

    def reset(self) -> None:
        """
        Returns instrument to default settings, cancels all pending commands.
        """
        self.write("*RST")
