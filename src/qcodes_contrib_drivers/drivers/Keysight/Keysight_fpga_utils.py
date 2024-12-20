import keysightSD1 as SD1
#from qcodes_contrib_drivers.drivers.Keysight.SD_common.SD_Module import result_parser
from typing import Any, Callable, Dict, List, Optional, Union
import os
import logging

# from sd1_utils import self.result_parser

# from SD1_utils, Delft, obsolete due to result_parser function in SD_Module
# def check_error(result, s=''):
#     if (type(result) is int and result < 0):
#         error = result
#         msg = f'Keysight error: {SD1.SD_Error.getErrorMessage(error)} ({error}) {s}'
#         logging.error(msg)
#     return result
#### 
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
        error_message = SD1.SD_Error.getErrorMessage(value)
        call_message = f' ({name})' if name != 'result' else ''
        raise Exception(f'Error in call to module ({value}): '
                        f'{error_message}{call_message}')
    else:
        if verbose:
            print(f'{name}: {value}')
        return value

def trim(s):
    end = s.index('\x00')
    return s[:end]


def write_fpga(module, reg_name, value):
    print('to module.FPGAgetSandBoxRegister','regname', reg_name, 'value',value)
    reg = result_parser(module.FPGAgetSandBoxRegister(reg_name), reg_name)
    print('reg.writeRegister32',reg, value)
    reg.writeRegisterInt32(value)

def read_fpga(module, reg_name):
    reg = result_parser(module.FPGAgetSandBoxRegister(reg_name), reg_name)
    if reg.Address > 2**24 or reg.Address < 0:
        raise Exception(f'Register out of range: Reg {reg.Address:6} ({reg.Length:6}) {reg_name}')
    return reg.readRegisterInt32()

def write_fpga_array(module, reg_name, offset, data):
    reg = result_parser(module.FPGAgetSandBoxRegister(reg_name), reg_name)
    result_parser(reg.writeRegisterBuffer(offset, data, SD1.SD_AddressingMode.AUTOINCREMENT, SD1.SD_AccessMode.NONDMA),
                f'write_fpga_array({reg_name})')

def read_fpga_array(module, reg_name, offset, data_size):
    reg = result_parser(module.FPGAgetSandBoxRegister(reg_name), reg_name)
    data = result_parser(reg.readRegisterBuffer(offset, data_size,
                                              SD1.SD_AddressingMode.AUTOINCREMENT, SD1.SD_AccessMode.NONDMA))
    return data

def has_fpga_info(module):
    register = module.FPGAgetSandBoxRegister('Host_SysInfo_ImageId')
    if isinstance(register, int) and register < 0:
        return False
    return True

def get_fpga_info(module):
    image_id = read_fpga(module, 'Host_SysInfo_ImageId')
    version_date = read_fpga(module, 'Host_SysInfo_Version')
    clock_frequency = read_fpga(module, 'Host_SysInfo_ClockFrequency')
    return image_id, version_date, clock_frequency

def print_fpga_info(module):
    if not has_fpga_info(module):
        print(f'No FPGA image info available')
        return
    image_id, version_date, clock_frequency = get_fpga_info(module)
    print(f'FPGA image: {image_id}, {version_date}, {clock_frequency} MHz')

def get_fpga_image_path(module):
    fw = trim(module.getFirmwareVersion())
    major,minor,revision = fw.split('.')
    module_name = result_parser(module.getProductName(), 'getProductNameBySlot')
    base_dir = os.path.join(os.getcwd(), '..')
    return os.path.join(base_dir, 'bitstreams', f'{module_name}_{major[1]}_{minor}_{revision}')

def fpga_list_registers(module, n=None):
    if n is not None:
        registers = result_parser(module.FPGAgetSandBoxRegisters(n))
    else:
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

    for reg in registers:
        if reg.Address > 2**24:
            raise Exception(f'Reg {reg.Address:6} ({reg.Length:6}) {trim(reg.Name)}')
        access_type = trim(reg.AccessType)
        if access_type == 'RW' and reg.Length == 4:
            print(f'Reg {reg.Address:6} ({reg.Length:6}) {access_type} {trim(reg.Name)}: {reg.readRegisterInt32()}')
        elif access_type == 'RW' and reg.Length == 1:
            print(f'HVI {reg.Address:6} ({reg.Length:6}) {access_type} {trim(reg.Name)}')
        elif access_type == 'MemoryMap':
            print(f'Mem {reg.Address:6} ({reg.Length:6}) {access_type} {trim(reg.Name)}')
            data = reg.readRegisterBuffer(0, min(16, reg.Length//4),
                                          SD1.SD_AddressingMode.AUTOINCREMENT, SD1.SD_AccessMode.NONDMA)
            print(data)


def config_fpga_debug_log(module, change_mask=0, enable_mask=0, capture_start_mask=0, capture_duration=0):
    regs = [change_mask, enable_mask, capture_start_mask, capture_duration]
    write_fpga_array(module, 'Host_LogMemory', 2**11+2, regs)


def print_fpga_log(module, clear=False, clock200=False, column=None, formatter=None):
    d = 2 if clock200 else 1
    log_reg = result_parser(module.FPGAgetSandBoxRegister('Host_LogMemory'), 'Host_LogMemory')
    log_info = log_reg.readRegisterBuffer(2**11, 2, SD1.SD_AddressingMode.AUTOINCREMENT, SD1.SD_AccessMode.NONDMA)
    print(f'FPGA logging: {log_info} entries')
    print('  systick relative    delta --      value      hex    .' + (column if column is not None else ''))
    n_entries = log_info[1]
    if n_entries > 0:
        log_data = log_reg.readRegisterBuffer(0, 2*n_entries,
                                              SD1.SD_AddressingMode.AUTOINCREMENT, SD1.SD_AccessMode.NONDMA)
        t0 = (log_data[1] & 0xFFFFFFFF) // d
        t_last = t0
        for i in range(n_entries):
            t = (log_data[2*i+1] & 0xFFFFFFFF) // d
            v = log_data[2*i] & 0xFFFFFFFF
            formatted = formatter(v) if formatter is not None else ''
            print(f'{t:9} {t-t0:8} {t-t_last:+8} -- {v:10} ({v>>16:04X} {v&0xFFFF:04X}) {formatted}')
            t_last = t
    if clear:
        result_parser(log_reg.writeRegisterBuffer(2**11, [1], SD1.SD_AddressingMode.AUTOINCREMENT, SD1.SD_AccessMode.NONDMA))


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
            logging.warning(f'hvi2 extension {self._name} not loaded')
            self._warned = True
        return dummy

    def __setattr__(self, name, value):
        if name not in ['_warned', '_name']:
            if not self._warned:
                logging.warning(f'hvi2 extension {self._name} not loaded')
                self._warned = True
        else:
            object.__setattr__(self, name, value)

