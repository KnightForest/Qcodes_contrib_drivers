from functools import partial
from typing import Optional

from qcodes import VisaInstrument, validators as vals

class DS345(VisaInstrument):
    """
    This is the qcodes driver for the Yokogawa YKGW7651 voltage and current source

    Args:
      name (str): What this instrument is called locally.
      address (str): The GPIB address of this instrument
      kwargs (dict): kwargs to be passed to VisaInstrument class
      terminator (str): read terminator for reads/writes to the instrument.
    """

    def __init__(self, name: str, address: str, terminator: str="\n",
                 **kwargs) -> None:
        super().__init__(name, address, terminator=terminator, device_clear = False, **kwargs)

       
        self.add_parameter(name='frequency',
                           label='Frequency',
                           unit='Hz',
                           get_cmd='FREQ?',
                           set_cmd='FREQ {:.3f}',
                           get_parser=float,
                           vals=vals.Numbers(min_value=1e-5,
                                             max_value=30e6))
        
        self.add_parameter(name='amplitude',
                   label='Amplitude',
                   unit='Vpp',
                   get_cmd='AMPL?',
                   set_cmd='AMPL {:.2f}VP',
                   get_parser=float)
        
        self.connect_message()