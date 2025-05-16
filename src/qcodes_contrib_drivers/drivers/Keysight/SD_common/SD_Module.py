import warnings
import os
<<<<<<< HEAD:src/qcodes_contrib_drivers/drivers/Keysight/SD_common/SD_Module.py
from typing import Any, Callable, Dict, List, Optional, Union
=======
import logging
from typing import List, Union, Callable, Any
>>>>>>> master:qcodes_contrib_drivers/drivers/Keysight/SD_common/SD_Module.py
from qcodes.instrument.base import Instrument
from time import perf_counter
import numpy as np
from . import Keysight_fpga_utils as fpga_utils

try:
    import keysightSD1
except ImportError:
    raise ImportError('to use the Keysight SD drivers install the keysightSD1 module '
                      '(http://www.keysight.com/main/software.jspx?ckey=2784055)')

# check whether SD1 version 2.x or 3.x
is_sd1_3x = 'SD_SandBoxRegister' in dir(keysightSD1)


def result_parser(value: Any, name: str = 'result',
                  verbose: bool = False) -> Any:
    """
    This method is used for parsing the result in the get-methods.
    For values that are non-negative, the value is simply returned.
    Negative values indicate an error, so an error is raised
    with a reference to the error code.

    The parser also can print to the result to the shell if verbose is 1.

    Args:
        value: the value to be parsed
        name: name of the value to be parsed
        verbose: boolean indicating verbose mode

    Returns:
        parsed value, which is the same as value if non-negative or not a number
    """
    if isinstance(value, int) and (int(value) < 0):
        error_message = keysightSD1.SD_Error.getErrorMessage(value)
        call_message = f' ({name})' if name != 'result' else ''
        raise Exception(f'Error in call to module ({value}): '
                        f'{error_message}{call_message}')
    else:
        if verbose:
            print(f'{name}: {value}')
        return value


class SD_Module(Instrument):
    """
    This is the general SD_Module driver class that implements shared
    parameters and functionality among all PXIe-based digitizer/awg/combo
    cards by Keysight.

    This driver was written to be inherited from by either the SD_AWG,
    SD_DIG or SD_Combo class, depending on the functionality of the card.

    Specifically, this driver was written with the M3201A and M3300A cards in
    mind.

    This driver makes use of the Python library provided by Keysight as part
    of the SD1 Software package (v.2.01.00).

    Args:
        name: an identifier for this instrument, particularly for
            attaching it to a Station.
        chassis: identification of the chassis.
        slot: slot of the module in the chassis.
    """

    def __init__(self, name: str, chassis: int, slot: int,
                 module_class: Callable = keysightSD1.SD_Module,
                 **kwargs) -> None:
        super().__init__(name, **kwargs)

        # Create instance of keysight module class
        self.SD_module = module_class()
        self.fpga_utils = fpga_utils

        #Intialise some parameters and imports
        self.bit_depth=15
        self.digi_clock = 5e8#self.sys_frequency.get() 
        
        # Open the device, using the specified chassis and slot number
        self.module_name = self.SD_module.getProductNameBySlot(chassis, slot)
        result_parser(self.module_name,
                      f'getProductNameBySlot({chassis}, {slot})')

        result_code = self.SD_module.openWithSlot(self.module_name, chassis, slot)
        result_parser(result_code,
                      f'openWithSlot({self.module_name}, {chassis}, {slot})')

        self.add_parameter('module_count',
                           label='module count',
                           get_cmd=self.get_module_count,
                           docstring='The number of Keysight modules '
                                     'installed in the system')
        self.add_parameter('product_name',
                           label='product name',
                           get_cmd=self.get_product_name,
                           docstring='The product name of the device')
        self.add_parameter('serial_number',
                           label='serial number',
                           get_cmd=self.get_serial_number,
                           docstring='The serial number of the device')
        self.add_parameter('chassis_number',
                           label='chassis number',
                           get_cmd=self.get_chassis,
                           docstring='The chassis number where the device is '
                                     'located')
        self.add_parameter('slot_number',
                           label='slot number',
                           get_cmd=self.get_slot,
                           docstring='The slot number where the device is '
                                     'located')
        self.add_parameter('status',
                           label='status',
                           get_cmd=self.get_status,
                           docstring='The status of the device')
        self.add_parameter('firmware_version',
                           label='firmware version',
                           get_cmd=self.get_firmware_version,
                           docstring='The firmware version of the device')
        self.add_parameter('hardware_version',
                           label='hardware version',
                           get_cmd=self.get_hardware_version,
                           docstring='The hardware version of the device')
        self.add_parameter('instrument_type',
                           label='type',
                           get_cmd=self.get_type,
                           docstring='The type of the device')
        self.add_parameter('open',
                           label='open',
                           get_cmd=self.get_open,
                           docstring='Indicating if device is open, '
                                     'True (open) or False (closed)')
        self.add_parameter('temperature',
                           label='temperature',
                           get_cmd=self.get_temperature,
                           docstring='Module temperature')

    #
    # Get-commands
    #

    def get_idn(self) -> Dict[str, Optional[str]]:
        """Returns IDN of module"""
        return dict(vendor='Keysight',
                    model=self.get_product_name(),
                    serial=self.get_serial_number(),
                    firmware=self.get_firmware_version(),
                    )

    def get_module_count(self, verbose: bool = False) -> int:
        """Returns the number of SD modules installed in the system"""
        value = self.SD_module.moduleCount()
        value_name = 'module_count'
        return result_parser(value, value_name, verbose)

    def get_product_name(self, verbose: bool = False) -> str:
        """Returns the product name of the device"""
        value = self.SD_module.getProductName()
        value_name = 'product_name'
        return result_parser(value, value_name, verbose)

    def get_serial_number(self, verbose: bool = False) -> str:
        """Returns the serial number of the device"""
        value = self.SD_module.getSerialNumber()
        value_name = 'serial_number'
        return result_parser(value, value_name, verbose)

    def get_chassis(self, verbose: bool = False) -> int:
        """Returns the chassis number where the device is located"""
        value = self.SD_module.getChassis()
        value_name = 'chassis_number'
        return result_parser(value, value_name, verbose)

    def get_slot(self, verbose: bool = False) -> int:
        """Returns the slot number where the device is located"""
        value = self.SD_module.getSlot()
        value_name = 'slot_number'
        return result_parser(value, value_name, verbose)

    def get_status(self, verbose: bool = False) -> int:
        """Returns the status of the device"""
        value = self.SD_module.getStatus()
        value_name = 'status'
        return result_parser(value, value_name, verbose)

    def get_firmware_version(self, verbose: bool = False) -> str:
        """Returns the firmware version of the device"""
        value = self.SD_module.getFirmwareVersion()
        value_name = 'firmware_version'
        return result_parser(value, value_name, verbose)

    def get_hardware_version(self, verbose: bool = False) -> str:
        """Returns the hardware version of the device"""
        value = self.SD_module.getHardwareVersion()
        value_name = 'hardware_version'
        return result_parser(value, value_name, verbose)

    def get_type(self, verbose: bool = False) -> int:
        """Returns the type of the device"""
        value = self.SD_module.getType()
        value_name = 'type'
        return result_parser(value, value_name, verbose)

    def get_open(self, verbose: bool = False) -> bool:
        """Returns whether the device is open (True) or not (False)"""
        value = self.SD_module.isOpen()
        value_name = 'open'
        return result_parser(value, value_name, verbose)

    def get_pxi_trigger(self, pxi_trigger: int, verbose: bool = False) -> int:
        """
        Returns the digital value of the specified PXI trigger

        Args:
            pxi_trigger: PXI trigger number (4000 + Trigger No.)
            verbose: boolean indicating verbose mode

        Returns:
            Digital value with negated logic, 0 (ON) or 1 (OFF), or negative
                numbers for errors
        """
        value = self.SD_module.PXItriggerRead(pxi_trigger)
        value_name = f'pxi_trigger number {pxi_trigger}'
        return result_parser(value, value_name, verbose)

    #
    # Set-commands
    #

    def set_pxi_trigger(self, value: int, pxi_trigger: int,
                        verbose: bool = False) -> None:
        """
        Sets the digital value of the specified PXI trigger

        Args:
            pxi_trigger: PXI trigger number (4000 + Trigger No.)
            value: Digital value with negated logic, 0 (ON) or 1 (OFF)
            verbose: boolean indicating verbose mode
        """
        result = self.SD_module.PXItriggerWrite(pxi_trigger, value)
        value_name = f'set pxi_trigger {pxi_trigger} to {value}'
        result_parser(result, value_name, verbose)

    #
    # FPGA related functions
    #

    def get_fpga_pc_port(self, port: int, data_size: int, address: int,
                         address_mode: int, access_mode: int,
                         verbose: bool = False) -> Any:
        """
        Reads data at the PCport FPGA Block

        Args:
            port: PCport number
            data_size: number of 32-bit words to read (maximum is 128 words)
            address: address that wil appear at the PCport interface
            address_mode: auto-increment (0), or fixed (1)
            access_mode: non-dma (0), or dma (1)
            verbose: boolean indicating verbose mode
        Returns:
            register data.
        """
        data = self.SD_module.FPGAreadPCport(port, data_size, address,
                                          address_mode, access_mode)
        value_name = f'data at PCport {port}'
        return result_parser(data, value_name, verbose)

    def set_fpga_pc_port(self, port: int, data: List[int], address: int,
                         address_mode: int, access_mode: int,
                         verbose: bool = False) -> None:
        """
        Writes data at the PCport FPGA Block

        Args:
            port: PCport number
            data: array of integers containing the data
            address: address that will appear at the PCport interface
            address_mode: auto-increment (0), or fixed (1)
            access_mode: non-dma (0), or dma (1)
            verbose: boolean indicating verbose mode
        """
        result = self.SD_module.FPGAwritePCport(port, data, address,
                                               address_mode,
                                             access_mode)
        value_name = f'set fpga PCport {port} to data:{data}, ' \
                     f'address:{address}, address_mode:{address_mode}, ' \
                     f'access_mode:{access_mode}'
        result_parser(result, value_name, verbose)

    def load_fpga_image(self, filename: str) -> None:
        """
        Loads FPGA binary image in module.

        Args:
            filename: name of the FPGA image.
        """
        if not os.path.exists(filename):
            raise Exception(f'FPGA bitstream {filename} not found')
        result_parser(self.SD_module.FPGAload(filename),
                      f'loading FPGA bitstream: {filename}')

    #
    # FPGA utils legacy
    #
    # from SD1_utils, Delft 
    def check_error(self, result, s=''):
        if (type(result) is int and result < 0):
            error = result
            msg = f'Keysight error: {keysightSD1.SD_Error.getErrorMessage(error)} ({error}) {s}'
            logging.error(msg)
        return result
    #### 

    def trim(self, s):
        end = s.index('\x00')
        return s[:end]


    def write_fpga(self, reg_name, value):
        reg = self.check_error(self.SD_module.FPGAgetSandBoxRegister(reg_name), reg_name)
        reg.writeRegisterInt32(value)

    def read_fpga(self, reg_name):
        reg = self.check_error(self.SD_module.FPGAgetSandBoxRegister(reg_name), reg_name)
        if reg.Address > 2**24 or reg.Address < 0:
            raise Exception(f'Register out of range: Reg {reg.Address:6} ({reg.Length:6}) {reg_name}')
        return reg.readRegisterInt32()

    def write_fpga_array(self, reg_name, offset, data):
        reg = self.check_error(self.SD_module.FPGAgetSandBoxRegister(reg_name), reg_name)
        self.check_error(reg.writeRegisterBuffer(offset, data, keysightSD1.SD_AddressingMode.AUTOINCREMENT, keysightSD1.SD_AccessMode.NONDMA),
                    f'write_fpga_array({reg_name})')

    def read_fpga_array(self, reg_name, offset, data_size):
        reg = self.check_error(self.SD_module.FPGAgetSandBoxRegister(reg_name), reg_name)
        data = self.check_error(reg.readRegisterBuffer(offset, data_size,
                                                keysightSD1.SD_AddressingMode.AUTOINCREMENT, keysightSD1.SD_AccessMode.NONDMA))
        return data

    def has_fpga_info(self):
        register = self.SD_module.FPGAgetSandBoxRegister('Host_SysInfo_ImageId')
        if isinstance(register, int) and register < 0:
            return False
        return True

    def get_fpga_info(self):
        image_id = self.read_fpga(self, 'Host_SysInfo_ImageId')
        version_date = self.read_fpga(self, 'Host_SysInfo_Version')
        clock_frequency = self.read_fpga(self, 'Host_SysInfo_ClockFrequency')
        return image_id, version_date, clock_frequency

    def print_fpga_info(self):
        if not self.has_fpga_info(self):
            print(f'No FPGA image info available')
            return
        image_id, version_date, clock_frequency = self.get_fpga_info(self)
        print(f'FPGA image: {image_id}, {version_date}, {clock_frequency} MHz')

    def get_fpga_image_path(self):
        fw = self.trim(self.SD_module.getFirmwareVersion())
        major,minor,revision = fw.split('.')
        module_name = self.check_error(self.SD_module.getProductName(), 'getProductNameBySlot')
        base_dir = os.path.join(os.getcwd(), '..')
        return os.path.join(base_dir, 'bitstreams', f'{module_name}_{major[1]}_{minor}_{revision}')

    def fpga_list_registers(self, n=None):
        if n is not None:
            registers = self.check_error(self.SD_module.FPGAgetSandBoxRegisters(n))
        else:
            done = False
            n = 0
            registers = []
            while not done:
                n += 1
                result = self.SD_module.FPGAgetSandBoxRegisters(n)
                if isinstance(result, int) and result < 0:
                    done = True
                else:
                    registers = result

        for reg in registers:
            if reg.Address > 2**24:
                raise Exception(f'Reg {reg.Address:6} ({reg.Length:6}) {self.trim(reg.Name)}')
            access_type = self.trim(reg.AccessType)
            if access_type == 'RW' and reg.Length == 4:
                print(f'Reg {reg.Address:6} ({reg.Length:6}) {access_type} {self.trim(reg.Name)}: {reg.readRegisterInt32()}')
            elif access_type == 'RW' and reg.Length == 1:
                print(f'HVI {reg.Address:6} ({reg.Length:6}) {access_type} {self.trim(reg.Name)}')
            elif access_type == 'MemoryMap':
                print(f'Mem {reg.Address:6} ({reg.Length:6}) {access_type} {self.trim(reg.Name)}')
                data = reg.readRegisterBuffer(0, min(16, reg.Length//4),
                                            keysightSD1.SD_AddressingMode.AUTOINCREMENT, keysightSD1.SD_AccessMode.NONDMA)
                print(data)


    def config_fpga_debug_log(self, change_mask=0, enable_mask=0, capture_start_mask=0, capture_duration=0):
        regs = [change_mask, enable_mask, capture_start_mask, capture_duration]
        self.write_fpga_array(self, 'Host_LogMemory', 2**11+2, regs)


    def print_fpga_log(self, clear=False, clock200=False, column=None, formatter=None):
        d = 2 if clock200 else 1
        log_reg = self.check_error(self.SD_module.FPGAgetSandBoxRegister('Host_LogMemory'), 'Host_LogMemory')
        log_info = log_reg.readRegisterBuffer(2**11, 2, keysightSD1.SD_AddressingMode.AUTOINCREMENT, keysightSD1.SD_AccessMode.NONDMA)
        print(f'FPGA logging: {log_info} entries')
        print('  systick relative    delta --      value      hex    .' + (column if column is not None else ''))
        n_entries = log_info[1]
        if n_entries > 0:
            log_data = log_reg.readRegisterBuffer(0, 2*n_entries,
                                                keysightSD1.SD_AddressingMode.AUTOINCREMENT, keysightSD1.SD_AccessMode.NONDMA)
            t0 = (log_data[1] & 0xFFFFFFFF) // d
            t_last = t0
            for i in range(n_entries):
                t = (log_data[2*i+1] & 0xFFFFFFFF) // d
                v = log_data[2*i] & 0xFFFFFFFF
                formatted = formatter(v) if formatter is not None else ''
                print(f'{t:9} {t-t0:8} {t-t_last:+8} -- {v:10} ({v>>16:04X} {v&0xFFFF:04X}) {formatted}')
                t_last = t
        if clear:
            self.check_error(log_reg.writeRegisterBuffer(2**11, [1], keysightSD1.SD_AddressingMode.AUTOINCREMENT, keysightSD1.SD_AccessMode.NONDMA))


    class FpgaSysExtension:
        def __init__(self, name, builder):
            self.name = name
            self.builder = builder
            engine = builder.engine
            self.ticks_register = engine.fpga_register('HVI_SysInfo_SysTicks')
            self.ticks_clear_register = engine.fpga_register('HVI_SysInfo_Clear')

        @property
        def ticks(self):
            return self.ticks_register

        def clear_ticks(self):
            self.builder.write_fpga(self.ticks_clear_register, 0, text=f'{self.name}.clear_ticks()')


    class FpgaNoLogExtension:
        def __init__(self, name, builder):
            self.name = name
            self.builder = builder

        def write(self, value):
            self.builder.wait(10)

        def capture(self, n_ticks):
            self.builder.wait(10)


    class FpgaLogExtension:
        def __init__(self, name, builder):
            self.name = name
            self.builder = builder
            engine = builder.engine
            self.log_register = engine.fpga_register('HVI_Log_Data')
            self.capture_register = engine.fpga_register('HVI_Log_Capture')

        def write(self, value):
            self.builder.write_fpga(self.log_register, value, text=f'{self.name}.write({value})')

        def capture(self, n_ticks):
            self.builder.write_fpga(self.capture_register, n_ticks, text=f'{self.name}.capture({n_ticks})')

    def dummy(*args, **kwargs):
        pass

    class FpgaMissingExtension:
        def __init__(self, name, builder):
            self._name = name
            self._warned = False

        def __getattr__(self, name):
            if not self._warned:
                self.logging.warn(f'hvi2 extension {self._name} not loaded')
                self._warned = True
            return self.dummy

        def __setattr__(self, name, value):
            if name not in ['_warned', '_name']:
                if not self._warned:
                    self.logging.warn(f'hvi2 extension {self._name} not loaded')
                    self._warned = True
            else:
                object.__setattr__(self, name, value)


    #
    # HVI related functions
    #

    def set_hvi_register(self, register: Union[int, str], value: int,
                         verbose: bool = False) -> None:
        """
        Sets value of specified HVI register.

        Args:
            register: register to set.
            value: new value.
            verbose: boolean indicating verbose mode
        """
        if type(register) == int:
            result = self.SD_module.writeRegisterByNumber(register, value)
        else:
            result = self.SD_module.writeRegisterByName(register, value)
        value_name = f'set HVI register {register}:{value}'
        result_parser(result, value_name, verbose)

    def get_hvi_register(self, register: Union[int, str],
                         verbose: bool = False) -> int:
        """
        Returns value of specified HVI register.

        Args:
            register: register to read.
            verbose: boolean indicating verbose mode
        Returns:
            register value.
        """
        if type(register) == int:
            error, result = self.SD_module.readRegisterByNumber(register)
        else:
            error, result = self.SD_module.readRegisterByName(register)

        value_name = f'get HVI register {register}'
        result_parser(error, value_name, verbose)
        return result

    #
    # The methods below are not used for setting or getting parameters,
    # but can be used in the test functions of the test suite e.g. The main
    # reason they are defined is to make this driver more complete
    #

    def get_product_name_by_slot(self, chassis: int, slot: int,
                                 verbose: bool = False) -> str:
        value = self.SD_module.getProductNameBySlot(chassis, slot)
        value_name = 'product_name'
        return result_parser(value, value_name, verbose)

    def get_product_name_by_index(self, index: Any,
                                  verbose: bool = False) -> str:
        value = self.SD_module.getProductNameByIndex(index)
        value_name = 'product_name'
        return result_parser(value, value_name, verbose)

    def get_serial_number_by_slot(self, chassis: int, slot: int,
                                  verbose: bool = False) -> str:
        warnings.warn('Returns faulty serial number due to error in Keysight '
                      'lib v.2.01.00', UserWarning)
        value = self.SD_module.getSerialNumberBySlot(chassis, slot)
        value_name = 'serial_number'
        return result_parser(value, value_name, verbose)

    def get_serial_number_by_index(self, index: Any,
                                   verbose: bool = False) -> str:
        warnings.warn('Returns faulty serial number due to error in Keysight '
                      'lib v.2.01.00', UserWarning)
        value = self.SD_module.getSerialNumberByIndex(index)
        value_name = 'serial_number'
        return result_parser(value, value_name, verbose)

    def get_type_by_slot(self, chassis: int, slot: int,
                         verbose: bool = False) -> int:
        value = self.SD_module.getTypeBySlot(chassis, slot)
        value_name = 'type'
        return result_parser(value, value_name, verbose)

    def get_type_by_index(self, index: Any, verbose: bool = False) -> int:
        value = self.SD_module.getTypeByIndex(index)
        value_name = 'type'
        return result_parser(value, value_name, verbose)

    def get_temperature(self) -> float:
        return self.SD_module.getTemperature()

    #
    # The methods below are useful for controlling the device, but are not
    # used for setting or getting parameters
    #

    def close(self) -> None:
        """
        Closes the hardware device and frees resources.

        If you want to open the instrument again, you have to initialize a
        new instrument object
        """
        # Note: module keeps track of open/close state. So, keep the reference.
        self.SD_module.close()
        super().close()

    # only closes the hardware device, does not delete the current instrument
    # object
    def close_soft(self) -> None:
        self.SD_module.close()

    def open_with_serial_number(self, name: str, serial_number: int) -> Any:
        result = self.SD_module.openWithSerialNumber(name, serial_number)
        return result_parser(result,
                             f'openWithSerialNumber({name}, {serial_number})')

    def open_with_slot(self, name: str, chassis: int, slot: int) -> Any:
        result = self.SD_module.openWithSlot(name, chassis, slot)
        return result_parser(result, f'openWithSlot({name}, {chassis}, {slot})')

    def run_self_test(self) -> int:
        value = self.SD_module.runSelfTest()
        print(f'Did self test and got result: {value}')
        return value

#-------------------------------------
# Test functions from Antonio's code
#-------------------------------------
    def _waitPointsRead(self,channel,npts):
        timeout=3
        t0=perf_counter()
        totalPointsRead = 0
        while totalPointsRead< npts and perf_counter()-t0 < timeout:
            totalPointsRead= self.SD_module.DAQcounterRead(channel)

    def read_buffer_avg(self,channel,npts):
        timeout=3 # timeout for reading buffer, timeout for filling buffer in _waitPointsRead
        # print(npts)
        self._waitPointsRead(channel,npts)
        daq_data=self.SD_module.DAQread(channel,npts,timeout)
        value=np.mean(daq_data)*self.SD_module.channelFullScale(channel)/2**(self.bit_depth)
        
        return value
    

    def read_buffer_array(self, channel, npts):
        timeout=3
        print(npts)
        # npts = window_length*self.digi_clock
        self._waitPointsRead(channel,npts)
        daq_data=self.SD_module.DAQread(channel,npts,timeout)
        daq_data=daq_data*self.SD_module.channelFullScale(channel)/2**(self.bit_depth)
        
        return daq_data 
    
### FPGA functions

    def load_and_config_fpga(self,directory,bitstream_file, verbose=False): # load_fpga_image in SD_Module.py
        dig_bitstream = os.path.join(directory, bitstream_file)

        start = perf_counter()
        result_parser(self.SD_module.FPGAload(dig_bitstream))
        #fpga_utils.check_error(self.core.FPGAload(dig_bitstream), 'loading dig bitstream')
        duration = (perf_counter() - start) * 1000
        print(f'dig {self.SD_module.getSlot()}: {duration:5.1f} ms')

        self.SD_module.FPGAconfigureFromK7z(dig_bitstream)

        self.fpga_loaded = 1


    def get_fpga_registers(self):
        if self.fpga_loaded:
            fpga_utils.fpga_list_registers(self.SD_module)
        else:
            print('No bitstream loaded to FPGA')

    def fpga_write_to_registerbank(self,registerbank_name,dict_to_write):
        '''
        dict_to_write of the form: {register_name: value, ...}
        '''
        if self.fpga_loaded:
            for entry in dict_to_write:
                print('to fpga_utils.writefpga',self.SD_module, registerbank_name+'_' + entry, dict_to_write[entry])
                fpga_utils.write_fpga(self.SD_module, registerbank_name+'_' + entry, dict_to_write[entry])
                

        else:
            print('No bitstream loaded to FPGA')


    def fpga_read_registerbank(self,registerbank_name,register_name):
        if self.fpga_loaded:
            value = fpga_utils.read_fpga(self.SD_module, registerbank_name+'_' + register_name)
            # value = value*self.core.channelFullScale(channel)/2**(self.bit_depth) # this is handled at NEInstruments
        else:
            print('No bitstream loaded to FPGA')

        return value

def trim(s):
    end = s.index('\x00')
    return s[:end]

def fpga_return_RW_registers(module):

    done = False
    n = 0
    registers = []
    while not done:
        n += 1
        result = module.FPGAgetSandBoxRegisters(n)
        if isinstance(result, int) and result < 0:
            done = True
        else:
            registers = result
    rwregcounter = 0
    for reg in registers:
        access_type = trim(reg.AccessType)
        if access_type == 'RW' and reg.Length == 4:
            rwregcounter = rwregcounter+1
    
    regnames = [None]*rwregcounter
    regvals = [None]*rwregcounter
    for nreg,reg in enumerate(registers):
        if reg.Address > 2**24:
            raise Exception(f'Reg {reg.Address:6} ({reg.Length:6}) {trim(reg.Name)}')
        access_type = trim(reg.AccessType)
        if access_type == 'RW' and reg.Length == 4:
            rwregcounter = rwregcounter+1
            regnames[nreg]=trim(reg.Name)
            regvals[nreg]=reg.readRegisterInt32()
    return regnames,regvals