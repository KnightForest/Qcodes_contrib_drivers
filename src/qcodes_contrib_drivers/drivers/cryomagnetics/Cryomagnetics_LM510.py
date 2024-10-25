# Cryomagnetics_LM510.py class, to communicate with the Liquid Cryogen Level Monitor

import logging
from qcodes import VisaInstrument
from qcodes import validators as vals
from time import sleep
import visa
import qcodes.utils.validators as vals

log = logging.getLogger(__name__)


class Cryomagnetics_LM510(VisaInstrument):

    """This is the python driver for the Cryomagnetics_LM-510 Liquid Cryogen Level Monitor

    Usage:
    Initialize with:
    from qcodes.instrument_drivers.cryomagnetics.Cryomagnetics_LM510 import Cryomagnetics_LM510
    level_meter = Cryomagnetics_LM510(name='level', address='GPIB0::26::INSTR')
    """
    
    #Define the channels 
    _helium_channel = 1
    _nitrogen_channel = 2

    def __init__(
        self,
        name,
        address,
        **kwargs
        ):
        super().__init__(name, address, **kwargs)
        
        self.visa_handle.read_termination="\n"
        self.visa_handle.write_termination  ="\n"

        # Add parameters

        self.add_parameter(
            'interval',
            label='Interval',
            get_cmd='INTVL?',
            set_cmd='INTVL {}', # HH:MM:SS
            unit='time',
            )
        self.add_parameter(
            'channel',
            label='Channel',
            get_cmd='CHAN?',
            get_parser=int,
            set_cmd='CHAN {:d}',
            vals=vals.Numbers(1, 2),
            )

    def _status_byte(self):
        """
        Get the status byte
        
        Bits correspond to: 
        (order - least significant to most significant)
            Ch1 Data Ready
            Ch1 Fill Active
            Ch2 Data Ready
            Ch2 Fill Active
            MAV (Message Available
            ESB (Extended Status Byte
            MSS (Master Summary Status
            Menu Selected
        """
        status_byte = self.visa_handle.query('*STB?')
        return int(status_byte)
        
    def _level(self, channel):

    # Query last completed measurement

        self.channel(channel)  # select the default channel
        ans = self.visa_handle.query('MEAS?')
        return ans

    def _measure_now(self, channel):

    # Measure the level now....on the specified channel

        self.channel(channel)  # select the default channel
        self.visa_handle.write('MEAS')
        while self._status_byte() % 2 == 0:
            sleep(0.5)
        print('Level: ')
        print(self._level(channel))

    def helium_level(self):

    # Query last completed measurement for Helium

        ans = self._level(self._helium_channel)
        return ans

    def helium_measure_now(self):

    # Measure Helium level now....

        self._measure_now(self._helium_channel)