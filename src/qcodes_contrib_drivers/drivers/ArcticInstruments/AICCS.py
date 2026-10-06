# -*- coding: utf-8 -*-
"""
QCoDeS driver for the AI-CCS.

The AI-CCS is controlled over TCP/IP using SCPI-like commands.

Physical configuration
----------------------
The instrument has four current channels:

    1A, 1B, 2A, 2B

Channels 1A/1B form one hardware output pair, as do 2A/2B.

The raw channels remain available for diagnostics and special use cases.
For normal differential device biasing, use the high-level BiasPair
modules:

    aiccs.pair1.current
    aiccs.pair2.current

A BiasPair deliberately imposes the higher-level invariant:

    channel_A = +current
    channel_B = -current

The hardware itself permits unequal currents, provided the signs within
a pair are opposite. The pair abstraction intentionally does not expose
that more general operating mode.

Important instrument behavior
-----------------------------
The AI-CCS interprets bare numeric current setpoints in amperes, and
current queries return amperes.

Changing the sign of one channel's current causes the other channel in
the hardware pair to be set to zero.

Output control operates on the whole hardware pair. In particular,
turning a pair ON sets both current setpoints to zero. Therefore
BiasPair.output_on() enables the pair and then restores the pair's
previously requested current.

SHUNT is intentionally not used by the high-level safety methods.
"""

from __future__ import annotations

from typing import Any

from qcodes.instrument import IPInstrument
from qcodes.instrument import InstrumentChannel, InstrumentModule
from qcodes.validators import Enum, Numbers


class AICCSBiasPair(InstrumentModule):
    """
    High-level representation of one AI-CCS differential bias pair.

    Parameters
    ----------
    parent:
        Parent AICCS instrument.
    name:
        Name of this pair.
    channel_a:
        Positive-side raw channel.
    channel_b:
        Negative-side raw channel.

    Notes
    -----
    The pair abstraction maintains equal and opposite commanded currents.
    The underlying hardware permits more general unequal currents, but
    those should be accessed through the raw channel objects if required.
    """

    def __init__(
        self,
        parent: AICCS,
        name: str,
        channel_a: AICCSChannel,
        channel_b: AICCSChannel,
    ):
        super().__init__(parent, name)

        self.channel_a = channel_a
        self.channel_b = channel_b

        # Last current requested through this high-level pair interface.
        # This is deliberately separate from the hardware readback because
        # OUTP ON/OFF resets the hardware setpoints to zero.
        self._current_setpoint = 0.0

        self.add_parameter(
            "current",
            label=f"{name} bias current",
            unit="A",
            get_cmd=self._get_current,
            set_cmd=self._set_current,
            vals=Numbers(-4e-3, 4e-3),
            docstring=(
                "Differential bias current. "
                "The two physical channels are driven with equal "
                "and opposite currents."
            ),
        )

        self.add_parameter(
            "voltage_a",
            label=f"{name} channel A voltage",
            unit="V",
            get_cmd=self._get_voltage_a,
        )

        self.add_parameter(
            "voltage_b",
            label=f"{name} channel B voltage",
            unit="V",
            get_cmd=self._get_voltage_b,
        )

        self.add_parameter(
            "voltage",
            label=f"{name} differential voltage",
            unit="V",
            get_cmd=self._get_differential_voltage,
        )

    # ------------------------------------------------------------------
    # Current
    # ------------------------------------------------------------------

    def _get_current(self) -> float:
        """
        Read the pair current from the hardware.

        The pair current is defined as channel A current. Both channels
        are queried so that an accidentally unbalanced raw hardware state
        is detected.
        """
        current_a = self.channel_a.current.get()
        current_b = self.channel_b.current.get()

        # The instrument reports currents in amperes. This tolerance is
        # deliberately small but avoids rejecting insignificant numerical
        # differences in readback.
        tolerance = 1e-12

        if abs(current_a + current_b) > tolerance:
            raise RuntimeError(
                f"Bias pair {self.name} is not balanced: "
                f"{self.channel_a.name} = {current_a:.6g} A, "
                f"{self.channel_b.name} = {current_b:.6g} A"
            )

        return current_a

    def _set_current(self, current: float) -> None:
        """
        Set equal and opposite currents on the two channels.

        When reversing polarity, both channels are explicitly brought to
        zero before applying the new polarity. This avoids relying on the
        instrument's implicit pair-polarity behavior.

        The requested value is cached so that output_on() can restore it
        after the instrument has zeroed the setpoints.
        """
        current_a = self.channel_a.current.get()
        current_b = self.channel_b.current.get()

        if current == 0:
            self.channel_a.current(0.0)
            self.channel_b.current(0.0)
            self._current_setpoint = 0.0
            return

        current_sign = 1 if current > 0 else -1

        old_sign_a = (
            1 if current_a > 0
            else -1 if current_a < 0
            else 0
        )
        old_sign_b = (
            1 if current_b > 0
            else -1 if current_b < 0
            else 0
        )

        polarity_change = (
            (old_sign_a != 0 and old_sign_a != current_sign)
            or
            (old_sign_b != 0 and old_sign_b != -current_sign)
        )

        if polarity_change:
            self.channel_a.current(0.0)
            self.channel_b.current(0.0)

        self.channel_a.current(current)
        self.channel_b.current(-current)

        self._current_setpoint = current

    # ------------------------------------------------------------------
    # Voltage
    # ------------------------------------------------------------------

    def _get_voltage_a(self) -> float:
        return self.channel_a.voltage()

    def _get_voltage_b(self) -> float:
        return self.channel_b.voltage()

    def _get_differential_voltage(self) -> float:
        return self.voltage_a() - self.voltage_b()

    # ------------------------------------------------------------------
    # Output control
    # ------------------------------------------------------------------

    def output_on(self) -> None:
        """
        Enable the hardware pair and restore the requested pair current.

        The AI-CCS sets both current setpoints to zero whenever OUTP is
        switched ON, so simply enabling the output is not sufficient.
        """
        self.channel_a.output(1)
        self._set_current(self._current_setpoint)

    def output_off(self) -> None:
        """
        Disable the hardware pair.

        The instrument also zeros the hardware current setpoints. The
        requested high-level current is retained in _current_setpoint so
        that output_on() can restore it.
        """
        self.channel_a.output(0)

    def zero(self) -> None:
        """Set both channels to zero current."""
        self.current(0.0)

    def enable(self) -> None:
        """Enable the pair and restore its requested current."""
        self.output_on()

    def disable(self) -> None:
        """Disable the pair without changing its requested current."""
        self.output_off()

    def shutdown(self) -> None:
        """
        Safely zero the pair and switch its output off.

        After shutdown, the requested high-level current is also zero,
        so a later output_on() will not unexpectedly restore a bias.
        """
        self.zero()
        self.output_off()


class AICCSChannel(InstrumentChannel):
    """
    Low-level representation of one physical AI-CCS channel.

    The public current parameter uses SI amperes, matching QCoDeS and the
    AI-CCS SCPI query/setpoint semantics.

    Normal differential device biasing should preferably use AICCSBiasPair.
    """

    def __init__(
        self,
        parent: AICCS,
        name: str,
        channel_name: str,
    ):
        super().__init__(parent, name)

        self.channel_name = channel_name

        self.add_parameter(
            "current",
            label=f"Channel {channel_name} current",
            unit="A",
            get_cmd=self._get_current,
            set_cmd=self._set_current,
            vals=Numbers(-4e-3, 4e-3),
            docstring=(
                f"Raw current of AI-CCS channel {channel_name}. "
                "Range: +/-4 mA. Values are specified in amperes."
            ),
        )

        self.add_parameter(
            "voltage",
            label=f"Channel {channel_name} voltage",
            unit="V",
            get_cmd=self._get_voltage,
        )

        self.add_parameter(
            "output",
            label=f"Channel {channel_name} output",
            get_cmd=self._get_output,
            set_cmd=self._set_output,
            vals=Enum(0, 1, 2),
            docstring=(
                "Output state: "
                "0 = OFF, 1 = ON, 2 = SHUNT. "
                "Output control applies to the complete hardware pair."
            ),
        )

    # ------------------------------------------------------------------
    # Current
    # ------------------------------------------------------------------

    def _set_current(self, current_A: float) -> None:
        """
        Set current in amperes.

        The AI-CCS accepts bare numeric current values in amperes, so no
        mA conversion is performed here.
        """
        self.root_instrument.write(
            f"SOUR{self.channel_name}:CURR {current_A:.12g}"
        )

    def _get_current(self) -> float:
        """
        Read current in amperes.

        The AI-CCS returns current queries directly in amperes.
        """
        response = self.root_instrument.ask(
            f"SOUR{self.channel_name}:CURR?"
        )
        return float(response.strip())

    # ------------------------------------------------------------------
    # Voltage
    # ------------------------------------------------------------------

    def _get_voltage(self) -> float:
        response = self.root_instrument.ask(
            f"MEAS{self.channel_name}?"
        )
        return float(response.strip())

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _set_output(self, state: int) -> None:
        """
        Set output state.

        Note that the hardware applies this state to both channels in
        the pair and zeros their current setpoints.
        """
        self.root_instrument.write(
            f"OUTP{self.channel_name} {state}"
        )

    def _get_output(self) -> int:
        response = self.root_instrument.ask(
            f"OUTP{self.channel_name}?"
        )
        return int(response.strip())


class AICCS(IPInstrument):
    """
    QCoDeS driver for the AI-CCS.

    Raw physical channels:

        ch1A
        ch1B
        ch2A
        ch2B

    High-level differential bias pairs:

        pair1 = ch1A + ch1B
        pair2 = ch2A + ch2B

    The recommended interface for device biasing is pair1 and pair2.
    """

    def __init__(
        self,
        name: str,
        address: str,
        port: int = 5025,
        timeout: float = 5,
        terminator: str = "\n",
        **kwargs: Any,
    ):
        super().__init__(
            name=name,
            address=address,
            port=port,
            timeout=timeout,
            terminator=terminator,
            persistent=True,
            write_confirmation=False,
            **kwargs,
        )

        # --------------------------------------------------------------
        # Raw channels
        # --------------------------------------------------------------

        self.ch1A = AICCSChannel(self, "ch1A", "1A")
        self.ch1B = AICCSChannel(self, "ch1B", "1B")
        self.ch2A = AICCSChannel(self, "ch2A", "2A")
        self.ch2B = AICCSChannel(self, "ch2B", "2B")

        # --------------------------------------------------------------
        # High-level bias pairs
        # --------------------------------------------------------------

        self.pair1 = AICCSBiasPair(
            self, "pair1", self.ch1A, self.ch1B
        )
        self.pair2 = AICCSBiasPair(
            self, "pair2", self.ch2A, self.ch2B
        )

    # ==================================================================
    # Identification
    # ==================================================================

    def get_idn(self) -> dict[str, str | None]:
        """
        Query *IDN? and return a QCoDeS-style dictionary.
        """
        response = self.ask("*IDN?").strip()

        parts = [
            part.strip().strip('"')
            for part in response.split(",")
        ]

        return {
            "vendor": parts[0] if len(parts) > 0 else None,
            "model": parts[1] if len(parts) > 1 else None,
            "serial": parts[2] if len(parts) > 2 else None,
            "firmware": parts[3] if len(parts) > 3 else None,
        }

    # ==================================================================
    # Reset
    # ==================================================================

    def reset(self) -> None:
        """
        Reset the instrument using *RST.

        The instrument's hardware state is reset, so cached pair current
        requests are also cleared.
        """
        self.write("*RST")
        self.pair1._current_setpoint = 0.0
        self.pair2._current_setpoint = 0.0

    # ==================================================================
    # Safety
    # ==================================================================

    def zero_all(self) -> None:
        """Set both bias pairs to zero."""
        self.pair1.zero()
        self.pair2.zero()

    def outputs_off(self) -> None:
        """
        Switch all hardware output pairs off.

        One command per hardware pair is sufficient because output
        control is inherently paired.
        """
        self.ch1A.output(0)
        self.ch2A.output(0)

    def shutdown(self) -> None:
        """
        Safely shut down the AI-CCS.

        Currents are zeroed before the outputs are disabled.
        """
        self.zero_all()
        self.outputs_off()
