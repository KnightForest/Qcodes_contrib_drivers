from functools import partial
from typing import Optional

from qcodes import VisaInstrument

def float_round(val):
    """
    Rounds a floating number

    Args:
        val: number to be rounded

    Returns:
        Rounded integer
    """
    return round(float(val))


class YKGW7651Exception(Exception):
    pass


class YKGW7651(VisaInstrument):
    """
    This is the qcodes driver for the Yokogawa YKGW7651 voltage and current source

    Args:
      name (str): What this instrument is called locally.
      address (str): The GPIB address of this instrument
      kwargs (dict): kwargs to be passed to VisaInstrument class
      terminator (str): read terminator for reads/writes to the instrument.
    """

    def __init__(self, name: str, address: str, terminator: str="\r\n",
                 **kwargs) -> None:
        super().__init__(name, address, terminator=terminator, device_clear = False, **kwargs)

       
        self.add_parameter('output',
                           label='Output State',
                           get_cmd=self.state,
                           set_cmd=lambda x: self.on() if x else self.off(),
                           val_mapping={
                               'off': 0,
                               'on': 1,
                           })

        self.add_parameter('current',
                           label='Current',
                           unit='I',
                           set_cmd=partial(self._set_current),
                           get_cmd=partial(self._get_current)
                           )


        self.visa_handle.read_termination="\r\n"
        self.visa_handle.write_termination  ="\r\n"
        #self.write("DL1") 
        
        self.connect_message()

    def on(self):
        """Turn output on"""
        self.write('O1E')

    def off(self):
        """Turn output off"""
        self.write('O0E')

    def state(self):
        """Check state"""
        oc = int(self.ask("OC")[5:])
        state = oc & 0b10000
        return int(state>0)

    def _get_current(self):
        result = self.ask("OD")
        return float(result.replace('NDCA', ''))

    def _set_current(self,value):
        self.write('S{:e}E'.format(value))
        return
        
    def connect_message(self):
        print("Yoko 7651 as current generator. Switch the instrument to current mode!s")
        return