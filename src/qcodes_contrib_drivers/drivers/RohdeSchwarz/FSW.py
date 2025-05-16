import logging

from qcodes import VisaInstrument
from qcodes import ChannelList, InstrumentChannel
from qcodes.utils import validators as vals
import numpy as np
from qcodes import MultiParameter, ArrayParameter
import time
log = logging.getLogger(__name__)


class FSW(VisaInstrument):
    """
    qcodes driver for the Rohde & Schwarz ZNB8 and ZNB20
    virtual network analyser. It can probably be extended to ZNB4 and 40
    without too much work.

    Requires FrequencySweep parameter for taking a trace

    Args:
        name: instrument name
        address: Address of instrument probably in format
            'TCPIP0::192.168.15.100::inst0::INSTR'
        init_s_params: Automatically setup channels matching S parameters
        **kwargs: passed to base class

    TODO:
    - check initialisation settings and test functions
    """

    def __init__(self, name: str, address: str, terminator='\n',**kwargs):

        super().__init__(name=name, address=address, terminator=terminator, **kwargs)

        self.read_termination='\n'

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
        
        self.add_parameter(name='power',
                   get_cmd='CALC:MARK:FUNC:POW:RES?',
                   get_parser=float)
        
        self.add_parameter(name='obwpower',
                   get_cmd='CALC:MARK:FUNC:POW:RES? ACP',
                   get_parser=float)

        self.add_parameter(name='span',
                   get_cmd='SENS:FREQ:SPAN?',
                   set_cmd=self._set_span,
                   get_parser=float)
        
   
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


        self.update_display_on()
        self.connect_message()


    def display_grid(self, rows: int, cols: int):
        """
        Display a grid of channels rows by cols
        """
        self.write('DISP:LAY GRID;:DISP:LAY:GRID {},{}'.format(rows, cols))

    def _strip(self, var):
        "Strip newline and quotes from instrument reply"
        return var.rstrip()[1:-1]

    def _set_start(self, val):
        self.write('SENS:FREQ:START {:.7f}'.format(val))
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
        self.write('SENS:FREQ:STOP {:.7f}'.format(val))
        # we get stop as the vna may not be able to set it to the exact value provided
        stop = self.stop()
        if val != stop:
            log.warning(
                "Could not set stop to {} setting it to {}".format(val, stop))
        #self._update_traces()

    def _set_npts(self, val):
        self.write('SENS:SWE:POIN {:.7f}'.format(val))
        #self._update_traces()

    def _set_span(self, val):
        self.write('SENS:FREQ:SPAN {:.7f}'.format(val))
        #self._update_traces()

    def _set_center(self, val):
        self.write('SENS:FREQ:CENT {:.7f}'.format(val))
        #time.sleep(0.01)
        #self._update_traces()

    def _set_video_bandwidth(self, val):
        self.write('SENS:BWID:VID {:.7f}'.format(val))
    
    def _set_resolution_bandwidth(self, val):
        self.write('SENS:BWID:RES {:.7f}'.format(val))

    def _set_span(self,val):
        self.write('SENS:FREQ:SPAN {:.7f}'.format(val))