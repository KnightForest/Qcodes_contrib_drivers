import sys
import numpy as np
from functools import partial
from time import perf_counter
from os import path
from qcodes import Instrument
from qcodes.utils.validators import Numbers
from qcodes_contrib_drivers.drivers.Keysight.SD_common.SD_DIG import SD_DIG
from qcodes_contrib_drivers.drivers.Keysight.SD_common.SD_Module import result_parser
import keysightSD1 as SD1



from . import Keysight_fpga_utils as fpga_utils



class Keysight_M3102A(SD_DIG):

    def __init__(self, name, chassis, slot, channels, triggers, **kwargs):
    
        super().__init__(name, chassis, slot, channels, triggers, **kwargs)
        
        DIGI_PRODUCT = self.product_name.get()#"M3102A"                # Product's model number
        CHASSIS = chassis                      # Chassis number holding product
        SLOT = slot                        # Slot number of product in chassis
 
        self.bit_depth=15
        self.digi_clock = self.sys_frequency.get() 

        self.core=SD1.SD_AIN()
        self.result_parser = result_parser
        self.fpga_utils = fpga_utils

        #self.open(DIGI_PRODUCT, CHASSIS, SLOT)
        #print('digi loaded')

        self.fpga_loaded = 0




    def _waitPointsRead(self,channel,npts):
        timeout=70
        t0=perf_counter()
        totalPointsRead = 0
        while totalPointsRead< npts and perf_counter()-t0 < timeout:
            totalPointsRead= self.core.DAQcounterRead(channel)
            
        # print('Elapsed '+str(perf_counter()-t0)+' s.')

        
    # Redundant
    # def start(self,channel):
    #     self.core.DAQstart(channel)
        
    # Redundant
    # def flush_buffer(self,channel):
    #     self.core.DAQflush(channel)
        
    # Added to SD_DIG.py
    # def pause(self,channel):
    #     self.core.DAQpause(channel)
    
    # Added to SD_DIG.py
    # def resume(self,channel):
    #     self.core.DAQresume(channel)
        
    # Redundant
    # def stop(self,channel):
    #     self.core.DAQstop(channel)
        
    # Redundant
    # def trigger(self,channel):
    #     self.core.DAQtrigger(channel)

    # Redundant
    # def open(self, DIGI_PRODUCT, CHASSIS, SLOT): 
    #     core_id = self.core.openWithSlot(DIGI_PRODUCT, CHASSIS, SLOT)
        
    #     if core_id < 0:
    #         print("Module open error:", core_id)
    #     else:
    #         print("Module opened:", core_id)
    #         print("Module name:", self.core.getProductName())
    #         print("Slot:", self.core.getSlot())
    #         print("Chassis:", self.core.getChassis())

    # Added to SD_DIG.py
    # def close(self):
    #     self.core.close()

#### Configuration functions


#### Digitizer functions

    def read_buffer_avg(self,channel,npts):
        timeout=3 # timeout for reading buffer, timeout for filling buffer in _waitPointsRead
        # print(npts)
        self._waitPointsRead(channel,npts)
        daq_data=self.core.DAQread(channel,npts,timeout)
        value=np.mean(daq_data)*self.core.channelFullScale(channel)/2**(self.bit_depth)
        
        return value
    

    def read_buffer_array(self, channel, npts):
        timeout=70
        print(npts)
        # npts = window_length*self.digi_clock
        self._waitPointsRead(channel,npts)
        daq_data=self.core.DAQread(channel,npts,timeout)
        daq_data=daq_data*self.core.channelFullScale(channel)/2**(self.bit_depth)
        
        return daq_data 
    
### FPGA functions

    def load_and_config_fpga(self,directory,bitstream_file, verbose=False): # load_fpga_image in SD_Module.py
        dig_bitstream = path.join(directory, bitstream_file)

        start = perf_counter()
        self.result_parser(self.core.FPGAload(dig_bitstream))
        #fpga_utils.check_error(self.core.FPGAload(dig_bitstream), 'loading dig bitstream')
        duration = (perf_counter() - start) * 1000
        print(f'dig {self.core.getSlot()}: {duration:5.1f} ms')

        self.core.FPGAconfigureFromK7z(dig_bitstream)

        self.fpga_loaded = 1


    def get_fpga_registers(self):
        if self.fpga_loaded:
            fpga_utils.fpga_list_registers(self.core)
        else:
            print('No bitstream loaded to FPGA')

    def fpga_write_to_registerbank(self,registerbank_name,dict_to_write):
        '''
        dict_to_write of the form: {register_name: value, ...}
        '''
        if self.fpga_loaded:
            for entry in dict_to_write:
                print('to fpga_utils.writefpgamk',self.core, registerbank_name+'_' + entry, dict_to_write[entry])
                fpga_utils.write_fpga(self.core, registerbank_name+'_' + entry, dict_to_write[entry])
                

        else:
            print('No bitstream loaded to FPGA')


    def fpga_read_registerbank(self,registerbank_name,register_name):
        if self.fpga_loaded:
            value = fpga_utils.read_fpga(self.core, registerbank_name+'_' + register_name)
            # value = value*self.core.channelFullScale(channel)/2**(self.bit_depth) # this is handled at NEInstruments
        else:
            print('No bitstream loaded to FPGA')

        return value