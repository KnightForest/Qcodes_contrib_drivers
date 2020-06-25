# based on the decadac driver

import visa
import logging
from time import sleep
from functools import partial
from qcodes import VisaInstrument, InstrumentChannel, ChannelList
from qcodes.utils import validators as vals
log = logging.getLogger(__name__)


class SP927Exception(Exception):
    pass


class SP927Reader(object):
    @staticmethod
    def _dac_parse(resp):
        """
        Parses responses from the DAC. 
        """
        return resp.strip()

    def _dac_v_to_code(self, volt):
        """
        Convert a voltage to the internal DAC code 
        DACval = (Vout + 10) · 838’848
        """
        if volt < self.min_val or volt > self.max_val:
            raise ValueError('Value out of range: {} V '.format(volt) +
                             '({} V - {} V).'.format(self.min_val,
                                                     self.max_val))
        
        DACval = (float(volt) + 10) * 838848
        DACval = int(round(DACval))

        return DACval

    def _dac_code_to_v(self, DACval):
        """
        Convert from DAC code to voltage
        Vout = (DACval / 838’848) – 10
        """
        DACval = DACval.strip()
        volt = round((int(DACval,16) / float(838848)) - 10, 6)

        return volt


class SP927Channel(InstrumentChannel, SP927Reader):
    """
    A single DAC channel of the SP927
    """
    _CHANNEL_VAL = vals.Ints(1, 8)

    def __init__(self, parent, name, channel, min_val=-10, max_val=10):
        super().__init__(parent, name)

        # Validate slot and channel values
        self._CHANNEL_VAL.validate(channel)
        self._channel = channel

        # Store min/max voltages
        assert(min_val < max_val)
        self.min_val = min_val
        self.max_val = max_val

        # Add channel parameters
        # Note we will use the older addresses to read the value from the dac rather than the newer
        # 'd' command for backwards compatibility
        self._volt_val = vals.Numbers(self.min_val, self.max_val)
        
        self.add_parameter('volt',
                           label='Channel {} voltage'.format(channel),
                           unit='V',
                           set_cmd=partial(self._parent._set_voltage, channel),
                           set_parser=self._dac_v_to_code,
                           get_cmd=partial(self._parent._read_voltage, channel),
                           vals=self._volt_val 
                           )

class SP927(VisaInstrument, SP927Reader):
    """
    Driver for the SP927 LNHR DAC from
    University of Basel, Department of Physics

    https://www.physik.unibas.ch/department/infrastructure-services/electronics-lab/low-noise-high-resolution-dac-sp-927.html

    User manual:

    https://www.physik.unibas.ch/fileadmin/user_upload/physik-unibas-ch/02_Department/04_Infrastructure_Services/Electronics_Lab/LNHR_DAC_Users_Manual_1_6.pdf

    Attributes:

        _ramp_state (bool): If True, ramp state is ON. Default False.

        _ramp_time (int): The ramp time in ms. Default 100 ms.
    """
    
    def __init__(self, name, address, min_val=-10, max_val=10, baud_rate=9600, **kwargs):
        """

        Creates an instance of the SP927 LNHR DAC instrument.

        Args:
            name (str): What this instrument is called locally.

            port (str): The address of the DAC. For a serial port this is ASRLn::INSTR
                where n is replaced with the address set in the VISA control panel.
                Baud rate and other serial parameters must also be set in the VISA control
                panel.

            min_val (number): The minimum value in volts that can be output by the DAC.
                This value should correspond to the DAC code 0.

            max_val (number): The maximum value in volts that can be output by the DAC.
                This value should correspond to the DAC code 65536.

        """

        super().__init__(name, address, **kwargs)
        handle = self.visa_handle

        # serial port properties
        handle.baud_rate = baud_rate
        handle.parity = visa.constants.Parity.none
        handle.stop_bits = visa.constants.StopBits.one
        handle.data_bits = 8
        handle.flow_control = visa.constants.VI_ASRL_FLOW_XON_XOFF
        #handle.set_terminator('\n')
        handle.write_termination = '\n'

        #self._write_response = ''

        self.num_chans = 8

        # Create channels
        channels = ChannelList(self, "Channels", SP927Channel, snapshotable=False)
        
        self.chan_range = range(1, 1 + self.num_chans)

        for i in self.chan_range:
            channel = SP927Channel(self, 'chan{:1}'.format(i), i)
            channels.append(channel)
            # Should raise valueerror if name is invalid (silently fails now)
            self.add_submodule('ch{:1}'.format(i), channel)
        channels.lock()
        self.add_submodule('channels', channels)

        # set small ramp speed for all channels (safety)
        
        for chan in self.channels:
            chan.volt.inter_delay=0.001
            chan.volt.step=0.001
            
        self.connect_message()

    def _set_voltage(self, chan, code):
        self.write('{:0} {:X}'.format(chan, code))
            
    def _read_voltage(self, chan):
        
        dac_code=self.write('{:0} V?'.format(chan))
            
        return self._dac_code_to_v(dac_code)


    def set_all(self, volt):
        """
        Set all dac channels to a specific voltage. If channels are set to ramp then the ramps
        will occur in sequence, not simultaneously.

        Args:
            volt(float): The voltage to set all gates to.
        """
        for chan in self.channels:
            chan.volt.set(volt)
            
    def all_on(self):
        """
        Turn on all channels.
        """
        self.write('ALL ON')
    
    def all_off(self):
        """
        Turn off all channels.
        """
        self.write('ALL OFF')
    
    def empty_buffer(self):
        
        # make sure every reply was read from the DAC 
        
        while self.visa_handle.bytes_in_buffer:
            print("Unread bytes in the buffer of DAC SP927 has been found. Reading the buffer...")
            self.visa_handle.read_raw()
            print("... done")
            
    def write(self, cmd):
        """
        Since there is always a return code from the instrument, we use ask instead of write
        TODO: interpret the return code (0: no error)
        """
        
        # before we begin the ask, we make sure there is nothing in the buffer
        
        self.empty_buffer()
            
        return self.ask(cmd)
    
    def get_idn(self):
       
        return dict(zip(('vendor', 'model', 'serial', 'firmware'), 
                        ('UniBasel', 'SP927', 'n.a.', 'n.a.')))