# -*- coding: utf-8 -*-
from qcodes import IPInstrument
from qcodes.validators import Arrays, ComplexNumbers, Enum, Ints, Numbers, Strings
from functools import partial
from time import sleep
import sys

class ICEoxfordVTI(IPInstrument):
    r"""
    ICEoxfordVTI Driver
    Uses TCP/IP sockets to communicate with the device.
    
    Version 0.1 (2022-12-03)
    Joost Ridderbos - Researcher at ICE/QTM
    University of Twente
    j.ridderbos@utwente.nl
    Todo:
    Gas Box
    Dual Cool
    Magnet
    Sensors

    """

    def __init__(
            self,
            name: str,
            address: str,
            port: int = 6340,
            terminator: str = '\r\n',
            timeout: float = 1,
            pid = None,
            **kwargs):
        super().__init__(name, address=address, port=port,
                         terminator=terminator, timeout=timeout, **kwargs)
        self.add_parameter(name='status',
                           label='Status',
                           get_cmd=self.LEMON_status)
        # Needle valve parameters
        for i in [1, 2]:
            self.add_parameter(f'nv{i}_mode',
                               label=f'NV{i} mode',
                               get_cmd=f'NV{i} MODE?',
                               get_parser=self.get_parser,
                               set_cmd=partial(self.set_mode,'NV',i),
                               val_mapping={'auto':  'AUTO', 'manual': 'MANUAL'})
            self.add_parameter(f'nv{i}_PID',
                               label=f'NV{i} PID',
                               get_cmd=f'NV{i} PID?',
                               get_parser=self.get_PID_parser,
                               set_cmd=partial(self.set_PID,'NV',i))
            self.add_parameter(f'nv{i}_set',
                               label=f'NV{i} set value command',
                               set_cmd=f'NV{i} SET VALUES')
            self.add_parameter(f'nv{i}_manual_val',
                               label=f'NV{i} manual output percentage',
                               get_cmd=f'NV{i} MAN OUT?',
                               get_parser=self.get_parser,
                               set_cmd=f'NV{i} MAN OUT={{}}',
                               unit='%',
                               vals=Numbers(min_value=0.0, max_value=100.0))
            self.add_parameter(f'nv{i}_error_band',
                               label=f'NV{i} error band',
                               get_cmd=f'NV{i} ERROR BAND?',
                               get_parser=self.get_parser,
                               set_cmd=f'NV{i} ERROR BAND={{}}',
                               unit='mBar',
                               vals=Numbers())
            self.add_parameter(f'nv{i}_setpoint',
                               label=f'NV{i} setpoint',
                               get_cmd=f'NV{i} SETPOINT?',
                               get_parser=self.get_parser,
                               set_cmd=f'NV{i} SETPOINT={{}}',
                               unit='mBar',
                               vals=Numbers())
            self.add_parameter(f'nv{i}_ramp',
                               label=f'NV{i} ramp',
                               get_cmd=f'NV{i} RAMP?',
                               get_parser=self.get_parser,
                               set_cmd=f'NV{i} RAMP={{}}',
                               unit='mBar/min',
                               vals=Numbers())
        # Heater parameters
        for i in [1, 2]:
            self.add_parameter(f'heater{i}_mode',
                               label=f'heater{i} mode',
                               get_cmd=f'HEATER{i} MODE?',
                               get_parser=self.get_parser,
                               set_cmd=partial(self.set_mode,'HEATER',i),
                               val_mapping={'auto':  'AUTO', 'manual': 'MANUAL'})
            self.add_parameter(f'heater{i}_PID',
                               label=f'heater{i} PID',
                               get_cmd=f'HEATER{i} PID?',
                               get_parser=self.get_PID_parser,
                               set_cmd=partial(self.set_PID,'HEATER',i))
            self.add_parameter(f'heater{i}_set',
                               label=f'heater{i} set value command',
                               set_cmd=f'HEATER{i} SET VALUES')
            self.add_parameter(f'heater{i}_manual_val',
                               label=f'heater{i} manual setpoint',
                               get_cmd=f'HEATER{i} MAN OUT?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEATER{i} MAN OUT={{}}',
                               unit='%',
                               vals=Numbers(min_value=0.0, max_value=100.0))
            self.add_parameter(f'heater{i}_setpoint',
                               label=f'heater{i} setpoint',
                               get_cmd=f'HEATER{i} SETPOINT?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEATER{i} SETPOINT={{}}',
                               unit='K',
                               vals=Numbers())
            self.add_parameter(f'heater{i}_ramp',
                               label=f'heater{i} ramp',
                               get_cmd=f'HEATER{i} RAMP?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEATER{i} RAMP={{}}',
                               unit='K/min',
                               vals=Numbers())
            self.add_parameter(f'heater{i}_range',
                               label=f'heater{i} range',
                               get_cmd=f'HEATER{i} RANGE?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEATER{i} RAMP={{}}',
                               val_mapping={'off':  'OFF', 
                                            'low': 'LOW',
                                            'medium': 'MED',
                                            'high': 'HIGH'
                                            })   
            self.add_parameter(f'heater{i}_channel',
                               label=f'heater{i} channel',
                               get_cmd=f'HEATER{i} CHAN?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEATER{i} CHAN={{}}',
                               val_mapping={'none':  'NONE', 
                                            'A': 'A',
                                            'B': 'B',
                                            'C': 'C',
                                            'D1': 'D1',
                                            'D2': 'D2',
                                            'D3': 'D3',
                                            'D4': 'D4',
                                            'D5': 'D5',
                                            })        
            self.add_parameter(f'heater{i}_setpoint_ramp',
                               label=f'heater{i} setpoint ramp',
                               get_cmd=f'HEATER{i} SETPOINT RAMP?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEATER{i} SETPOINT RAMP={{}}',
                               val_mapping={'on': 'ON',
                                            'off': 'OFF',
                                            })
        # Heat switch parameters
        for i in [1,2]:
            self.add_parameter(f'heat_switch{i}_mode',
                               label=f'heat switch {i} mode',
                               get_cmd=f'HEAT SW{i} MODE?',
                               get_parser=self.get_parser,
                               set_cmd=partial(self.set_mode,'HEAT SW',i),
                               val_mapping={'auto':  'AUTO', 'manual': 'MANUAL'})
            self.add_parameter(f'heat_switch{i}_channel',
                               label=f'heat switch {i} channel',
                               get_cmd=f'HEAT SW{i} CHAN?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEAT SW{i} CHAN={{}}',
                               val_mapping={'none':  'NONE', 
                                            'A': 'A',
                                            'B': 'B',
                                            'C': 'C',
                                            'D1': 'D1',
                                            'D2': 'D2',
                                            'D3': 'D3',
                                            'D4': 'D4',
                                            'D5': 'D5',
                                            }) 
            self.add_parameter(f'heat_switch{i}_setpoint',
                               label=f'heat switch {i} setpoint',
                               get_cmd=f'HEAT SW{i} SETPOINT?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEAT SW{i} SETPOINT={{}}',
                               unit='K',
                               vals=Numbers())
            self.add_parameter(f'heat_switch{i}_error_band',
                               label=f'heat switch {i} error band',
                               get_cmd=f'HEAT SW{i} ERROR BAND?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEAT SW{i} ERROR BAND={{}}',
                               unit='K',
                               vals=Numbers())
            self.add_parameter(f'heat_switch{i}_relay',
                               label=f'heat switch {i} relay',
                               get_cmd=f'HEAT SW{i} RELAY?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEAT SW{i} RELAY={{}}',
                               val_mapping={'on': 'ON',
                                            'off': 'OFF',
                                            })
            self.add_parameter(f'heat_switch{i}_set',
                               label=f'heat switch {i} set value command',
                               set_cmd=f'HEAT SW{i} SET VALUES')
        # Data channels
        for i in ['A', 'B', 'C', 'D1', 'D2', 'D3', 'D4', 'D5']:   
            self.add_parameter(f'T_{i}',
                               label=f'temperature channel {i}',
                               get_cmd=f'TEMPERATURE {i}?',
                               get_parser=self.get_parser,
                               unit='K')
            self.add_parameter(f'T_{i}_raw',
                               label=f'raw temperature channel {i}',
                               get_cmd=f'RAW {i}?',
                               get_parser=self.get_parser,
                               unit=r'$\Omega')
        for i in [1, 2]:
            self.add_parameter(f'heater{i}_output',
                                label=f'heater{i} output',
                                get_cmd=f'HEATER{i} OUPUT?',
                                get_parser=self.get_parser,
                                set_cmd=f'HEATER{i} OUTPUT={{}}',
                                unit='%',
                                vals=Numbers(min_value=0.0, max_value=100.0))
            self.add_parameter(f'nv{i}_output',
                                label=f'nv{i} output',
                                get_cmd=f'NV{i} OUPUT?',
                                get_parser=self.get_parser,
                                set_cmd=f'NV{i} OUTPUT={{}}',
                                unit='%',
                                vals=Numbers(min_value=0.0, max_value=100.0))

        self.add_parameter(f'P_dump',
                    label=f'dump pressure',
                    get_cmd=f'DUMP PRESSURE?',
                    get_parser=self.get_parser,
                    unit='mBar')
        self.add_parameter(f'P_sample',
                    label=f'sample space pressure',
                    get_cmd=f'SAMPLE SPACE PRESSURE?',
                    get_parser=self.get_parser,
                    unit='mBar')
        self.add_parameter(f'P_circ',
                    label=f'circulation pressure',
                    get_cmd=f'CIRCULATION PRESSURE?',
                    get_parser=self.get_parser,
                    unit='mBar')
        self.LEMON_connect()
        self.connect_message()

    def set_mode(self,dev,n,val):
        self.ask(f'{dev}{n} MODE={val}')
        sleep(0.1)
        self.ask(f'{dev}{n} SET VALUES')

    def set_values(self, dev, n):
        self.ask(f'{dev}{n} SET VALUES')

    def get_parser(self, val):
        ans = val.strip('\r\n').split('=')[1]
        return ans

    def get_PID_parser(self, val):
        lst = val.strip('\r\n').split('=')[1].split(',')
        return [float(i) for i in lst]

    def set_PID(self, dev, n, val):
        pidstr = str(val[0]) + ',' + str(val[1]) + ',' + str(val[2]) 
        self.ask(f'{dev}{n} PID={pidstr}')
        return pidstr

    def ask_custom(self, val):
        return self.ask(val).strip('\r\n')

    
    # LEMON commands ---------------------------------------------------------------------------   
    def LEMON_connect(self):
        self.ask_custom('CONNECT LEMON')
        
    def LEMON_disconnect(self):
        self.ask_custom('DISCONNECT LEMON')

    def LEMON_status(self):
        return self.ask_custom('LEMON CONNECTED?')