from time import sleep, time

import numpy as np
import qcodes as qcodes
from qcodes.instrument import Instrument
from qcodes.validators import Arrays, Numbers
from qcodes.parameters import Parameter, ParameterWithSetpoints

from moku.instruments import MultiInstrument
from moku.instruments import Oscilloscope
from moku.instruments import WaveformGenerator

class Moku_Pro_fastIV(Instrument):

    def __init__(self,
                 name: str,
                 address: str,
                 **kwargs):
        super().__init__(name, **kwargs)
        
        # Connect to Moku:Pro, enforce MultiInstrument mode (reprograms FPGA!)
        print('Connecting to Moku:Pro and configuring multi-instrument mode...')
        mim = MultiInstrument(address, force_connect=True, platform_id=4)
        
        # Setup instruments
        print('Creating waveform generator...')
        wg = mim.set_instrument(1, WaveformGenerator)
        print('Creating oscilloscope...')
        osc = mim.set_instrument(2, Oscilloscope)

        # Configure connections
        print('Setting up connections...')
        connections = [dict(source='Input1', destination='Slot2InB'), # Physical input 1 to Slot 2 (scope) software input B
                       dict(source='Slot1OutA', destination='Slot2InA'), # Waveform software output A to scope software input A
                       dict(source='Slot1OutA', destination='Output1')]  # Waveform software output A to physical output 1
        mim.set_connections(connections=connections)

        # Configure inputs
        print('Configuring inputs...')
        mim.set_frontend(1, '1MOhm', 'DC', '0dB') # Standard input attenuation = -20 dB (4Vpp). May need to set this to 40 dB rather than 0 dB to get better resolution...

        # Configure outputs
        print('Configuring outputs...')
        mim.set_output(1, '0dB')


        # self.add_parameter('IV',
        #                    get_cmd=self.get_wav_avg,
        #                    parameter_class=)
         
    def get_idn(self):
        """ Return the Instrument Identifier Message """
        idstr = self.ask('*IDN?')
        idparts = [p.strip() for p in idstr.split(',', 4)][:]
        return dict(zip(('vendor', 'model', 'serial', 'firmware'), idparts))

    def get_wav_avg(navg=32):
        V1_list = np.array([], dtype=np.float64)
        V2_list = np.array([], dtype=np.float64)
        for i in range(navg):
            data = osc.get_data()
            if len(V1_list) == 0:
                V1_list = data['ch1']
                V2_list = data['ch2']
            else:
                V1_list = np.vstack((V1_list, data['ch1']))
                V2_list = np.vstack((V2_list, data['ch2']))
        V1 = np.mean(V1_list, 0)
        V2 = np.mean(V2_list, 0)
        return V1, V2