from functools import partial
from qcodes import VisaInstrument
from qcodes.instrument.parameter import MultiParameter

class TimeStatistics(MultiParameter):
    def __init__(self, name, instrument):

        super().__init__(name=name, names=("mean", "stddev", "minval", "maxval"), 
                          shapes=((), (),(),()),
                          labels=('Mean time', 'Standart deviation','Min value', 'Max value'),
                          units=('s', 's', 's', 's'),)
        self._instrument = instrument
        
    def get_raw(self):
        reply = self._instrument.ask("CALCulate:AVERage:ALL?")
        mean, stddev, minval, maxval, _ = reply.split(",")

        return (mean, stddev, minval, maxval)


class FCA3100(VisaInstrument):
    """
    This is the qcodes driver for the FCA3100 counter

    Args:
      name (str): What this instrument is called locally.
      address (str): The GPIB address of this instrument
      kwargs (dict): kwargs to be passed to VisaInstrument class
      terminator (str): read terminator for reads/writes to the instrument.
    """

    def __init__(self, name: str, address: str, 
                 **kwargs) -> None:
        super().__init__(name, address, device_clear = False, **kwargs)

       
#        self.add_parameter('output',
#                           label='Output State',
#                           get_cmd=self.state,
#                           set_cmd=lambda x: self.on() if x else self.off(),
#                           val_mapping={
#                               'off': 0,
#                               'on': 1,
#                           })
#
        self.add_parameter('timeinterval',
                           label='timeinterval',
                           unit='s',
                           get_cmd="MEASure:TINTerval",
                           get_parser=float
                           )

        self.add_parameter(name='timestats',
                           parameter_class=TimeStatistics)
        
        self.connect_message()

    
    def reset(self):
        return
    
    def startread(self):
        self.ask("Read?")
        return

