# based on the decadac driver

import visa
import logging
from time import sleep
from functools import partial
from qcodes import VisaInstrument, InstrumentChannel, ChannelList, MultiParameter
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
        volt = round((int(DACval,16) / float(838848)) - 10, 9)

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
        self.add_parameter('status',
                           label='Channel {} status'.format(channel),
                           set_cmd=partial(self._parent._set_status, channel),
                           get_cmd=partial(self._parent._get_status, channel),
                           val_mapping={'on':  'ON', 'off': 'OFF'} 
                           )

    def on(self):
        """
        Turn on channel.
        """
        self.write('{:0} ON'.format(self._channel))

    def off(self):
        """
        Turn off all channel.
        """
        self.write('{:0} OFF'.format(self._channel))

class AllChannels(MultiParameter,SP927Reader):

    def __init__(self, name: str, instrument: VisaInstrument) -> None:
        super().__init__(name='test', 
                         names = ('DAC_ch1','DAC_ch2','DAC_ch3','DAC_ch4','DAC_ch5','DAC_ch6','DAC_ch7','DAC_ch8'),
                         shapes=((), (), (), (), (), (), (), ()),
                         labels = ('DAC ch1','DAC ch2','DAC ch3','DAC ch4','DAC ch5','DAC ch6','DAC ch7','DAC ch8'),
                         units = ('V','V','V','V','V','V','V','V'),
                         setpoints = ((),(),(),(),(),(),(),())
                         )
        self._instrument=instrument


    def get_raw(self):
        codes = self._instrument.ask('ALL V?').split(';')
        #print(codes)
        volts = [None] * len(codes)
        for i in range(0,len(codes)):
            #print(codes[i])
            #print(SP927Reader._dac_code_to_v(codes[i]))
            #volts[i] = round((int(codes[i],16) / float(838848)) - 10, 9)
            volts[i] = self._dac_code_to_v(codes[i])
        return volts

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
    
    def __init__(self, name, address, baud_rate=9600, inter_delay=1e-3, step=1e-3, **kwargs):
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
                This value should correspond to the DAC code 16776960.

        """

        super().__init__(name, address, **kwargs)
        handle = self.visa_handle

        # serial port properties
        handle.baud_rate = baud_rate
        handle.parity = visa.constants.Parity.none
        handle.stop_bits = visa.constants.StopBits.one
        handle.data_bits = 8
        handle.flow_control = visa.constants.VI_ASRL_FLOW_XON_XOFF
        handle.write_termination = '\n'
        handle.read_termination = '\r\n'

        #self._write_response = ''
        
        # Hardcoded hardware properties
        self.min_val=-10
        self.max_val=10
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

        # set ramp speed for all channels (safety default is 1e-3/1e-3)
        
        for chan in self.channels:
            chan.volt.inter_delay=inter_delay
            chan.volt.step=step
        
        # For use in a measurement
        self.add_parameter(name='getall_multiparameter',
                   parameter_class = AllChannels,
                   )
        self.add_parameter(name='all',
                   label='Get all dac values',
                   unit='V',
                   set_cmd=self._set_all,
                   get_cmd=self._get_all,
                   )

        self.connect_message()

    def _set_voltage(self, chan, code):
        self.write('{:0} {:X}'.format(chan, code))
            
    def _read_voltage(self, chan):
        
        dac_code=self.write('{:0} V?'.format(chan))
            
        return self._dac_code_to_v(dac_code)


    def _set_all(self, volt):
        """
        Set all dac channels to a specific voltage. If channels are set to ramp then the ramps
        will occur in sequence, not simultaneously.

        Args:
            volt(float): The voltage to set all gates to.
        """
        code = self._dac_v_to_code(volt)
        self.write('ALL {:X}'.format(code))
    
    def _get_all(self):
        """
        Get all dac channels. If channels are set to ramp then the ramps
        will occur in sequence, not simultaneously.
        """
        codes = self.ask('ALL V?').split(';')
        volts = [None] * len(codes)
        for i in range(0,len(codes)):
            volts[i] = [self._dac_code_to_v(codes[i])]
        return volts
            
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
    
    def _get_status(self,chan):
        """
        Turn on single channels.
        """
        return self.ask_raw('{:0} S?'.format(chan))
        
    def _set_status(self,chan,val):
        """
        Change on/off status of single channel
        """
        self.write('{:0} {}'.format(chan,val))
        
    def multiline_ask(self,cmd):
        fullbuff = []
        fullbuff.append(self.ask(cmd))
        sleep(0.2)
        while self.visa_handle.bytes_in_buffer:
            fullbuff.append(self.visa_handle.read())
            sleep(0.075) # 75 ms waiting time for the buffer to be re-filled
        return fullbuff

    def empty_buffer(self):
        
        # make sure every reply was read from the DAC 
        if self.visa_handle.bytes_in_buffer:
            print("Unread bytes in the buffer of DAC SP927 have been found. Reading the buffer:")
            while self.visa_handle.bytes_in_buffer:
                print(self.visa_handle.read_raw())
                sleep(0.075) # 75 ms waiting time for buffer to be re-filled
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
        firmware = self.multiline_ask('SOFT?')[1].rstrip()
        sn = self.multiline_ask('HARD?')[1].rstrip()[3:]
        self.empty_buffer()
        return dict(zip(('vendor', 'model', 'serial', 'firmware'), 
                        ('UniBasel', 'HRLN DAC (SP927)', sn, firmware)))
