import logging
from functools import partial
from typing import Any, Optional

import numpy as np

import qcodes.validators as vals
from qcodes import VisaInstrument
from qcodes import IPInstrument
from qcodes.instrument import (
    ChannelList, 
    Instrument, 
    InstrumentChannel, 
    VisaInstrument,
    IPInstrument
    )
from qcodes.parameters import (
    ArrayParameter,
    ManualParameter,
    MultiParameter,
    ParamRawDataType,
    create_on_off_val_mapping,
)

log = logging.getLogger(__name__)


#class MS2090A(VisaInstrument):
class MS2090A(IPInstrument):
    """
    Alpha qcodes driver for the Anritsu MS2090A series

    Args:
        name: instrument name
        address: Address of instrument probably in format
            'TCPIP0::192.168.15.100::inst0::INSTR'
        init_s_params: Automatically setup channels matching S parameters
        **kwargs: passed to base class

    TODO:
    - check initialisation settings and test functions
    """

    def __init__(self, 
                 name: str, 
                 address: str, 
                 port: int,
                 terminator='\r\n',
                 timeout: float = 5,
                 **kwargs):

        super().__init__(name=name, 
                         address=address, 
                         port = port, 
                         terminator=terminator, 
                         **kwargs)

        self.write_termination=terminator
        self.read_termination='\n'
        self._buffer_size = 999999

        model = self.get_idn()['model'].split('-')[0]
        
        self.add_parameter(name='start',
                           get_cmd='SENS:FREQ:START?',
                           set_cmd=self._set_start,
                           get_parser=float)
        self.add_parameter(name='stop',
                           get_cmd='SENS:FREQ:STOP?',
                           set_cmd=self._set_stop,
                           get_parser=float)
        self.add_parameter(name='center',
                   get_cmd='SENS:FREQ:CENT?',
                   set_cmd=self._set_center,
                   get_parser=float)
        self.add_parameter(name='video_bandwidth',
                   get_cmd='SENS:BWID:VID?',
                   set_cmd=self._set_video_bandwidth,
                   get_parser=float)

        self.add_parameter(name='resolution_bandwidth',
                   get_cmd='SENS:BWID:RES?',
                   set_cmd=self._set_resolution_bandwidth,
                   get_parser=float)
        
        # # self.add_parameter(name='power',
        # #            get_cmd='CALC:MARK:FUNC:POW:RES?',
        # #            get_parser=float)
        
        # # self.add_parameter(name='obwpower',
        # #            get_cmd='CALC:MARK:FUNC:POW:SEL? ACP',
        # #            get_parser=float)

        self.add_parameter(name='span',
                   get_cmd='SENS:FREQ:SPAN?',
                   set_cmd=self._set_span,
                   get_parser=float)
        
        self.add_parameter(
            name="npts",
            get_cmd="DISP:POIN?",
            set_cmd=self._set_npts,
            get_parser=int,
        )

        self.add_parameter(
            name="trace",
            start=self.start(),
            stop=self.stop(),
            npts=self.npts(),
            channel=1,
            parameter_class=FrequencySweep,
        )
        
   
        self.add_function('reset', call_cmd='*RST')
        self.add_function('tooltip_on', call_cmd='SYST:ERR:DISP ON')
        self.add_function('tooltip_off', call_cmd='SYST:ERR:DISP OFF')
        self.add_function('cont_meas_on', call_cmd='INIT:CONT:ALL ON')
        self.add_function('cont_meas_off', call_cmd='INIT:CONT:ALL OFF')
        self.add_function('update_display_once', call_cmd='SYST:DISP:UPD ONCE')
        self.add_function('update_display_on', call_cmd='SYST:DISP:UPD ON')
        self.add_function('update_display_off', call_cmd='SYST:DISP:UPD OFF')

        self.add_function('display_single_window',
                          call_cmd='DISP:LAY GRID;:DISP:LAY:GRID 1,1')
        self.add_function('display_dual_window',
                          call_cmd='DISP:LAY GRID;:DISP:LAY:GRID 2,1')


        #self.update_display_on()
        self.connect_message()


    def display_grid(self, rows: int, cols: int):
        """
        Display a grid of channels rows by cols
        """
        self._send('DISP:LAY GRID;:DISP:LAY:GRID {},{}'.format(rows, cols))

    # def _get_trace(self, ntrace)
    #     ylist = list(map(str.strip, self.ask_raw(f'TRAC:DATA? TRACE{i}').split(',')))
    #     datay =[float(i) for i in ylist]
    #     xlist = list(map(str.strip, self.ask_raw(f'TRAC:DATA:X? TRACE{i}').split(',')))
    #     datax =[float(i) for i in xlist]
    #     return

    def _strip(self, var):
        "Strip newline and quotes from instrument reply"
        return var.rstrip()[1:-1]

    def _set_start(self, val):
        self._send('SENS:FREQ:START {:.7f}'.format(val))
        stop = self.stop()
        if val >= stop:
            raise ValueError(
                "Stop frequency must be larger than start frequency.")
        # we get start as the vna may not be able to set it to the exact value provided
        start = self.start()
        if val != start:
            log.warning(
                "Could not set start to {} setting it to {}".format(val, start))
        #self._update_traces()

    def _set_stop(self, val):
        start = self.start()
        if val <= start:
            raise ValueError(
                "Stop frequency must be larger than start frequency.")
        self._send('SENS:FREQ:STOP {:.7f}'.format(val))
        # we get stop as the vna may not be able to set it to the exact value provided
        stop = self.stop()
        if val != stop:
            log.warning(
                "Could not set stop to {} setting it to {}".format(val, stop))
        #self._update_traces()

    def _set_npts(self, val):
        self._send('DISP:POIN {:.7f}'.format(val))
        #self._update_traces()

    def _set_span(self, val):
        self._send('SENS:FREQ:SPAN {:.7f}'.format(val))
        #self._update_traces()

    def _set_center(self, val):
        self._send('SENS:FREQ:CENT {:.7f}'.format(val))
        #time.sleep(0.01)
        #self._update_traces()

    def _set_video_bandwidth(self, val):
        self._send('SENS:BWID:VID {:.7f}'.format(val))
    
    def _set_resolution_bandwidth(self, val):
        self._send('SENS:BWID:RES {:.7f}'.format(val))

    def _set_span(self,val):
        self._send('SENS:FREQ:SPAN {:.7f}'.format(val))

    def query(self, val):
        cmd = val
        self.visa_handle.write(cmd)
        resp = self.visa_handle.read()
        return resp

class FrequencySweep(ArrayParameter):
    """
    Hardware controlled parameter class for Rohde Schwarz ZNB trace.

    Instrument returns an array of transmission or reflection data depending
    on the active measurement.

    Args:
        name: parameter name
        instrument: instrument the parameter belongs to
        start: starting frequency of sweep
        stop: ending frequency of sweep
        npts: number of points in frequency sweep

    Methods:
          get(): executes a sweep and returns magnitude and phase arrays

    """

    def __init__(
        self,
        name: str,
        instrument: Instrument,
        start: float,
        stop: float,
        npts: int,
        channel: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name,
            shape=(npts,),
            instrument=instrument,
            unit="dBm",
            label=f"{instrument.short_name} magnitude",
            setpoint_units=("Hz",),
            setpoint_labels=(f"{instrument.short_name} frequency",),
            setpoint_names=(f"{instrument.short_name}_frequency",),
            **kwargs,
        )
        self.set_sweep(start, stop, npts)
        self._instrument_channel = channel
        self._instrument = instrument

    def set_sweep(self, start: float, stop: float, npts: int) -> None:
        """
        sets the shapes and setpoint arrays of the parameter to
        correspond with the sweep

        Args:
            start: Starting frequency of the sweep
            stop: Stopping frequency of the sweep
            npts: Number of points in the sweep

        """
        # Needed to update config of the software parameter on sweep change
        # freq setpoints tuple as needs to be hashable for look up.
        f = tuple(np.linspace(int(start), int(stop), num=npts))
        self.setpoints = (f,)
        self.shape = (npts,)

    def get_raw(self) -> ParamRawDataType:
        #assert isinstance(self.instrument, RohdeSchwarzZNBChannel)
        return self._get_sweep_data()

    def _get_sweep_data(self, force_polar: bool = False) -> np.ndarray:
        # The device gives more data than nbytes indicates, so lets check against npoints
        npoints = self._instrument.npts.get()
        # The command send two responses: firstly the header indicating the block length (which we ignore), then the data itself
        self._instrument._send("INIT:CONT OFF")
        self._instrument._send("INIT; *WAI")
        trace = self._instrument.ask_raw('TRAC:DATA? 1')
        headerlength = int(trace[1])+ 2
        nbytes = int(trace[2:headerlength])
        if len(trace) > headerlength:
            trace = trace[headerlength:]
            print(len(trace.encode('utf8')))
            print(nbytes)
            while len(trace.encode('utf8')) < nbytes:
                trace = trace + self._instrument._recv()

        else:
            trace = self._instrument._recv()
            print(len(trace.encode('utf8')))
            print(nbytes)
            while len(trace.encode('utf8')) < nbytes:
                trace = trace + self._instrument._recv()
            
        # The data is now a string of '-169.22', '-140.22', ... , so convert to float array  
        self._instrument._send("INIT:CONT ON")
        return np.array(trace.split(','), dtype=np.float32)
        

        # #self._instrument.write("SENS:SWE:COUN 1")
        # #self._instrument.write("SENS:AVER:STAT1 ON")
        # #self._instrument.write("SENS:AVER:COUN 1")
        # self._instrument.write("INIT:CONT OFF")
        # #self._instrument.write("INIT; *WAI")
        # ylist = list(map(str.strip, self._instrument.ask_raw('TRAC:DATA? TRACE1').split(',')))
        # datay =[float(i) for i in ylist]
        # self._instrument.write("INIT:CONT ON")
        # return datay
        # #xlist = list(map(str.strip, self._instrument.ask_raw('TRAC:DATA:X? TRACE1').split(',')))
        # #datax =[float(i) for i in xlist]        

        # It is possible that the instrument and QCoDeS disagree about
        # which parameter is measured on this channel.
        # instrument_parameter = self.vna_parameter()
        # if instrument_parameter != self._vna_parameter:
        #     raise RuntimeError(
        #         "Invalid parameter. Tried to measure "
        #         f"{self._vna_parameter} "
        #         f"got {instrument_parameter}"
        #     )
        #self.averaging_enabled(True)
        #self.write(f"SENS{self._instrument_channel}:AVER:CLE")

        # preserve original state of the znb
        # self._instrument.write(f"INIT:IMM; *WAI")
        # self._instrument.write(
        #                 f"CALC:PAR:SEL "
        #                 f"'{self._instrument_channel}'"
        #             )
        # data_str = self._instrument.ask(
        #                 f"CALC:DATA? FDAT"
        #             )
        # data = np.array(data_str.rstrip().split(",")).astype("float64")
        # self.root_instrument.cont_meas_on()
        # return data