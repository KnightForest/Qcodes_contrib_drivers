# -*- coding: utf-8 -*-
"""
Created on Tue Jan 22 14:41:09 2019

@author: meso
"""

import numpy as np
import time
import qcodes as qc
from qcodes.instrument_drivers.agilent.N5183B import N5183B
from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI
import matplotlib.pyplot as plt

LOsignalgen=N5183B(name="LOgenerator",address="GPIB0::5::INSTR")
RFsignalgen=N5183B(name="RFgenerator",address="GPIB0::19::INSTR")

zilockin=ZIUHFLI(name="Lockin",device_ID= 'dev333')
zilockin.demod1_R.get()
#%%
class heterodyne_readout(qc.MultiParameter):
    #For defining an instance that will return magnitude and phase of the ZI lockin at a fixed LO and RF frequency
    def __init__(self, lockin_instance):
        super().__init__('V_ac',
                         names=('R', 'Theta'),
                         shapes=((), ()),
                         labels=('Magnitude ','Phase'),
                         units=('V', 'rad'),
                         setpoints=((), ()),
                        docstring='Magnitude and Phase as gained from heterodyne detection')
        self._lockin_instance = lockin_instance
    
    def get_raw(self):
        magnitude=self._lockin_instance.demod1_R.get()[0]
        phase=self._lockin_instance.demod1_phi.get()[0]
    
        return magnitude,phase

hr=heterodyne_readout(zilockin)

class heterodyne_frequency(qc.Parameter):
    #take the RF frequency as an input and set LO and RF frequency of the instruments
    def __init__(self, LO_parameter, RF_parameter,fIF=50e6):#intermediate frequency fRF=fLO+fIF
        # only name is required
        super().__init__(name="heterodyne_frequency", label='RF_frequency')
        self._fIF=fIF
        self._fLO=LO_parameter
        self._fRF=RF_parameter

    # you must provide a get method, a set method, or both.
    def get_raw(self):
        return self._fRF.get()

    def set_raw(self, val):
        self._fRF.set(val)
        self._fLO.set(val-self._fIF)


hf=heterodyne_frequency(LO_parameter=LOsignalgen.frequency,RF_parameter=RFsignalgen.frequency,fIF=45e6)   
#%%
class FrequencySweepMagPhase(qc.MultiParameter):
    """
    Sweep that return magnitude and phase.
    """

    def __init__(self, name, start, stop, npts, heterodyne_readout_parameter,heterodyne_frequency_parameter,waittime):
        super().__init__(name, names=("", ""), shapes=((), ()))
        self.set_sweep(start, stop, npts)
        self.names = ('magnitude',
                      'phase')
        self.labels = ('magnitude',
                       'phase')
        self.units = ('V', 'rad')
        self.setpoint_units = (('Hz',), ('Hz',))
        self.setpoint_labels = ('frequency', 'frequency')
        self.setpoint_names = ('frequency', 'frequency')
        self._hr=heterodyne_readout_parameter
        self._hf=heterodyne_frequency_parameter
        self._waittime=waittime
        
    def set_sweep(self, start, stop, npts):
        #  needed to update config of the software parameter on sweep change
        # freq setpoints tuple as needs to be hashable for look up
        f = tuple(np.linspace(int(start), int(stop), num=npts))
        self.setpoints = ((f,), (f,))
        self.shapes = ((npts,), (npts,))

    def get_raw(self):
        frange=self.setpoints[0][0]
        amplitudes=[]
        phases=[]
        for f in frange:
            #print(f)
            self._hf.set(f)
            time.sleep(self._waittime)
            a,phase=self._hr.get()
            amplitudes.append(a)
            phases.append(phase)
                
        return tuple(amplitudes), tuple(phases)
#%%
FreqSweep=FrequencySweepMagPhase(name="Heterodyne_freq_Sweep",
                                 start=3.07e9,stop=3.085e9,npts=201,
                                 heterodyne_readout_parameter=hr,
                                 heterodyne_frequency_parameter=hf,
                                 waittime=100e-3)
sweepdata=FreqSweep.get()
#%%
frange=FreqSweep.setpoints[0][0]
plt.plot(frange,sweepdata[0])
#plt.plot(frange,20*np.log(sweepdata[0]/max(sweepdata[0])))