from qcodes.utils.validators import Enum, Strings
from qcodes import VisaInstrument


class N5183B(VisaInstrument):
    """
    This is the qcodes driver for the Agilent N5183B
    """

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, terminator='\n', **kwargs)

        idn = self.IDN.get()
        self.model = idn['model']

        self.add_parameter('frequency',
                           get_cmd=':FREQuency:CW?',
                           get_parser=float,
                           set_cmd=':FREQuency:CW {:f} Hz')

        self.add_parameter('power',
                           get_cmd=':POW?',
                           get_parser=float,
                           set_cmd=':POW {:f}')

        self.add_function('rf_off', call_cmd='OUTP OFF')
        self.add_function('rf_on', call_cmd='OUTP ON')
        
        self.connect_message()


    def reset(self):
        self.write('*RST')
