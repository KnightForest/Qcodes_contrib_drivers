# -*- coding: utf-8 -*-
from qcodes import IPInstrument
from qcodes.parameters import Function
from qcodes.validators import Arrays, ComplexNumbers, Enum, Ints, Numbers, Strings
from functools import partial
import time
import sys
import pandas as pd
import numpy as np

class ICEoxfordVTI(IPInstrument):
    r"""
    ICEoxfordVTI Driver
    Uses TCP/IP sockets to communicate with the device.
    
    Version 0.2 (2023-09-06)
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
            timeout: float = 3,
            probe: str = '1.5K', # Can be '1.5K' or '300mK' to select different heater and needle valve temperature dependent lookup tables.
            temp_errormargin: float = 0.02, # Factor
            stabilisationtime: float = 120, # Seconds
            **kwargs):
        super().__init__(name, 
                         address=address, 
                         port=port,
                         terminator=terminator, 
                         timeout=timeout, **kwargs)
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
                               set_cmd=partial(self.set_values,'NV',i))
            self.add_parameter(f'nv{i}_manual_val',
                               label=f'NV{i} manual output percentage',
                               get_cmd=f'NV{i} MAN OUT?',
                               get_parser=self.get_parser_float,
                               set_cmd=f'NV{i} MAN OUT={{}}',
                               unit='%',
                               vals=Numbers(min_value=0.0, max_value=100.0))
            self.add_parameter(f'nv{i}_error_band',
                               label=f'NV{i} error band',
                               get_cmd=f'NV{i} ERROR BAND?',
                               get_parser=self.get_parser_float,
                               set_cmd=f'NV{i} ERROR BAND={{}}',
                               unit='mBar',
                               vals=Numbers())
            self.add_parameter(f'nv{i}_setpoint',
                               label=f'NV{i} setpoint',
                               get_cmd=f'NV{i} SETPOINT?',
                               get_parser=self.get_parser_float,
                               set_cmd=f'NV{i} SETPOINT={{}}',
                               unit='mBar',
                               vals=Numbers())
            self.add_parameter(f'nv{i}_ramp',
                               label=f'NV{i} ramp',
                               get_cmd=f'NV{i} RAMP?',
                               get_parser=self.get_parser_float,
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
                               set_cmd=partial(self.set_values,'HEATER',i))
            self.add_parameter(f'heater{i}_manual_val',
                               label=f'heater{i} manual setpoint',
                               get_cmd=f'HEATER{i} MAN OUT?',
                               get_parser=self.get_parser_float,
                               set_cmd=f'HEATER{i} MAN OUT={{}}',
                               unit='%',
                               vals=Numbers(min_value=0.0, max_value=100.0))
            self.add_parameter(f'heater{i}_setpoint',
                               label=f'heater{i} setpoint',
                               get_cmd=f'HEATER{i} SETPOINT?',
                               get_parser=self.get_parser_float,
                               set_cmd=f'HEATER{i} SETPOINT={{}}',
                               unit='K',
                               vals=Numbers())
            self.add_parameter(f'heater{i}_ramp',
                               label=f'heater{i} ramp',
                               get_cmd=f'HEATER{i} RAMP?',
                               get_parser=self.get_parser_float,
                               set_cmd=f'HEATER{i} RAMP={{}}',
                               unit='K/min',
                               vals=Numbers())
            self.add_parameter(f'heater{i}_range',
                               label=f'heater{i} range',
                               get_cmd=f'HEATER{i} RANGE?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEATER{i} RANGE={{}}',
                               val_mapping={'off':  'OFF', 
                                            'low': 'LOW',
                                            'medium': 'MEDIUM',
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
                               get_parser=self.get_parser_float,
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
                               get_cmd=f'HEAT SW{i} INPUT?',
                               get_parser=self.get_parser,
                               set_cmd=f'HEAT SW{i} INPUT={{}}',
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
                               get_parser=self.get_parser_float,
                               set_cmd=f'HEAT SW{i} SETPOINT={{}}',
                               unit='K',
                               vals=Numbers())
            self.add_parameter(f'heat_switch{i}_error_band',
                               label=f'heat switch {i} error band',
                               get_cmd=f'HEAT SW{i} ERROR BAND?',
                               get_parser=self.get_parser_float,
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
                               set_cmd=partial(self.set_values,'HEAT SW',i))
        # Data channels
        for i in ['A', 'B', 'C', 'D1', 'D2', 'D3', 'D4', 'D5']:   
            self.add_parameter(f'T_{i}',
                               label=f'temperature channel {i}',
                               get_cmd=f'TEMPERATURE {i}?',
                               get_parser=self.get_parser_float,
                               unit='K')
            self.add_parameter(f'T_{i}_raw',
                               label=f'raw temperature channel {i}',
                               get_cmd=f'RAW {i}?',
                               get_parser=self.get_parser_float,
                               unit=r'$\Omega')
        for i in [1, 2]:
            self.add_parameter(f'heater{i}_output',
                                label=f'heater{i} output',
                                get_cmd=f'HEATER OUTPUT {i}?',
                                get_parser=self.get_parser_float,
                                set_cmd=f'HEATER OUTPUT {i}={{}}',
                                unit='%',
                                vals=Numbers(min_value=0.0, max_value=100.0))
            self.add_parameter(f'nv{i}_output',
                                label=f'nv{i} output',
                                get_cmd=f'NV OUTPUT {i}?',
                                get_parser=self.get_parser_float,
                                set_cmd=f'NV OUTPUT {i}={{}}',
                                unit='%',
                                vals=Numbers(min_value=0.0, max_value=100.0))

        self.add_parameter(f'P_dump',
                            label=f'dump pressure',
                            get_cmd=f'DUMP PRESSURE?',
                            get_parser=self.get_parser_float,
                            unit='mBar')
        self.add_parameter(f'P_sample',
                            label=f'sample space pressure',
                            get_cmd=f'SAMPLE SPACE PRESSURE?',
                            get_parser=self.get_parser_float,
                            unit='mBar')
        self.add_parameter(f'P_circ',
                            label=f'circulation pressure',
                            get_cmd=f'CIRCULATION PRESSURE?',
                            get_parser=self.get_parser_float,
                            unit='mBar')

        self.add_parameter(f'dualcool_channel',
                            label=f'dualcool temperature channel',
                            get_cmd=f'DC TEMP CHAN?',
                            get_parser=self.get_parser,
                            set_cmd=f'DC TEMP CHAN={{}}',
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
        self.add_parameter(f'dualcool_dynamic_nv_setpoint',
                           label=f'dualcool dynamic needle valve setpoint',
                           get_cmd=f'DC DYNAMIC NV SETPOINT?',
                           get_parser=self.get_parser_float,
                           set_cmd=f'DC DYNAMIC NV SETPOINT={{}}',
                           unit='K',
                           vals=Numbers())
        for i in [1, 2]:
            self.add_parameter(f'dualcool_temp_setpoint{i}',
                               label=f'dualcool temperature setpoint stage {i}',
                               get_cmd=f'DC TEMP SETPOINT{i}?',
                               get_parser=self.get_parser_float,
                               set_cmd=f'DC TEMP SETPOINT{i}={{}}',
                               unit='K',
                               vals=Numbers())
            self.add_parameter(f'dualcool_static_nv_setpoint{i}',
                               label=f'dualcool static needle valve setpoint stage {i}',
                               get_cmd=f'DC STATIC NV SETPOINT{i}?',
                               get_parser=self.get_parser_float,
                               set_cmd=f'DC STATIC NV SETPOINT{i}={{}}',
                               unit='K',
                               vals=Numbers())
        self.add_parameter(f'autotemp',
                           label=f'Temperature',
                           get_cmd=self.T_D4,
                           set_cmd=self.autotempcontrol,
                           unit='K',
                           vals=Numbers())
        self.LEMON_connect()
        self.connect_message()
        self.stabilisationtime = stabilisationtime
        self.temp_errormargin = temp_errormargin
        self.probe = probe
    # Gas box commands
    def gasbox_purge(self):
        self.ask_custom('GB PURGE GB')
    def gasbox_purgelines(self):
        self.ask_custom('GB PURGE GB&SSL')

    # Dual cool procedures and parameters
    def dualcool_full(self):
        self.ask_custom('DC FULL')
    def dualcool_change_probe(self):
        self.ask_custom('DC CHANGE PROBE')
    def dualcool_dynamic(self):
        self.ask_custom('DC DYNAMIC')
    def dualcool_static(self):
        self.ask_custom('DC STATIC')
    def dualcool_stop(self):
        self.ask_custom('DC STOP')
    def dualcool_stop(self):
            self.ask_custom('DC STOP')

    # General fuctions
    def set_mode(self, dev, n, val):
        self.ask(f'{dev}{n} MODE={val}')
        #time.sleep(0.1)
        self.ask(f'{dev}{n} SET VALUES')

    def set_values(self, dev, n, val):
        tmag = self.T_C.get()
        if tmag > 4.5:
            print('Magnet top (sensor C) temperature too high: ' + str(tmag) + ' K. Remote setting of values disabled. Wait for the magnet to cool down below 4.5 K and try again.')     
        else:
            time.sleep(0.1)
            self.ask(f'{dev}{n} SET VALUES')
            time.sleep(0.1)
            self.ask(f'{dev}{n} SET VALUES')

    def get_parser(self, val):
        ans = val.strip('\r\n').split('=')[1]
        return ans

    def get_parser_float(self, val):
        ans = val.strip('\r\n').split('=')[1]
        return float(ans)

    def get_PID_parser(self, val):
        lst = val.strip('\r\n').split('=')[1].split(',')
        return [float(i) for i in lst]

    def set_PID(self, dev, n, val):
        pidstr = str(val[0]) + ',' + str(val[1]) + ',' + str(val[2]) 
        self.ask(f'{dev}{n} PID={pidstr}')
        return pidstr

    def ask_custom(self, val):
        return self.ask(val).strip('\r\n')

    # Temperature control & stabilisation

    def autotempcontrol(self,val):
        tset = val
        tmag = self.T_C.get()
        if tmag > 4.5:
            print('Magnet top (sensor C) temperature too high: ' + str(tmag) + ' K. Remote setting of values disabled. Wait for the magnet to cool down below 4.5 K and try again.')     
        else:
            if self.probe == '1.5K':
                # List of PIDs and flows corresponding to the 1.5 K insert
                templist = [[1.5, [200,50,0], 'low', 7, [18,25,0.05], 0.001],
                            [1.6, [200,50,0], 'low', 7, [18,25,0.05], 0.002],
                            [1.7, [200,50,0], 'low', 7, [18,25,0.05], 0.003],
                            [1.8, [200,50,0], 'low', 7, [18,25,0.05], 0.005],
                            [1.9, [100,50,0], 'low', 7, [80,30,10],   0.003],
                            [2.0, [100,50,0], 'low', 7, [80,30,10],   0.005],
                            [2.5, [25,50,0],  'low', 7, [40,5,0],     0.005],
                            [3,   [25,50,0],  'low', 7, [8,0.5,0],    0.010],
                            [3.5, [25,50,0],  'low', 7, [8,0.5,0],    0.010],
                            [4.5, [25,50,0],  'low', 7, [8,0.5,0],    0.050],
                            [6,   [25,50,0],  'low', 7, [8,0.5,0],    0.020],
                            [10,  [25,50,0],  'low', 7, [8,0.5,0],    0.050],
                            [20,  [25,50,0],  'low', 7, [8,0.5,0],    0.035],

                            [50,   [50,0.8,0],  'medium', 8, [400,5,0], 0.06],
                            [100,  [100,0.8,0], 'medium', 8, [400,5,0], 0.025],
                            [200,  [100,0.8,0], 'medium', 8, [400,5,0], 0.025],
                        
                            [250,  [100,100,0], 'high', 8, [400,5,0], 0.025],
                            [300,  [100,100,0], 'high', 8, [400,5,0], 0.025],
                        ]
            elif self.probe == '300mK':
                # List of PIDs and flows corresponding to the 300 mK insert. (Dummyentry for now)
                templist = [[1.5, [200,50,0], 'low', 7, [18,25,0.05], 0.001],
                        ]
            else:
                print('Probe must be set to either \'1.5K\' or \'300mK\'')
            df = pd.DataFrame(templist, columns = ['heater2_setpoint', 'heater2_PID', 'heater2_range', 'nv1_setpoint', 'nv1_PID', 'error'])
            df.set_index('heater2_setpoint', inplace=True)
            tstab = self.stabilisationtime
            templist = np.array(df.index.values.tolist())
            tval = templist[np.argmin(np.abs(templist-tset))]
            setlist = list(df.loc[templist[np.argmin(np.abs(templist-tset))]])
            self.heater2_mode.set('auto')
            self.heater2_channel.set('D4')
            self.heater2_setpoint.set(tset)
            self.heater2_PID.set(setlist[0])
            self.heater2_range.set(setlist[1])
            self.heater2_set.set(0)
            self.nv1_mode('auto')
            self.nv1_setpoint.set(setlist[2])
            self.nv1_PID.set(setlist[3])
            self.nv1_error_band.set(0)
            self.nv1_set.set(True)
            error = tset*0.01
            #print(tval)
            #print(error)
            #print(str(tset-error))
            #print(str(tset+error))
            tsetreached = False
            while not tsetreached:
                tactual = float(self.T_D4.get())
                while abs(tactual-tset) > error:       
                    tactual = float(self.T_D4.get())
                    print('Waiting to reach temperature. Current: ' + str(tactual) + ' K, target: ' + str(tset) + ' K.')
                    time.sleep(3)
                print('Target temperature reached, waiting to stabilise for ' + str(tstab) + ' s.')
                time_start = time.time()
                while not tsetreached:
                    tactual = self.T_D4.get()
                    if abs(tactual-tset) < error:
                        time.sleep(3)
                        time_elapsed = int(time.time() - time_start)
                        print(str(time_elapsed) + ' of ' + str(tstab) + ' s of stabilization..')
                        if  time_elapsed > tstab:
                            print('Set temperature reached and stabilized')
                            tsetreached = True
                    else:
                        print('Temperature outside stable range: ' + str(tactual) +' K, restarting counter..')
                        time_start = time.time()
                        time.sleep(3)
        return tset


    # LEMON commands ---------------------------------------------------------------------------   
    def LEMON_connect(self):
        self.ask_custom('CONNECT LEMON')
        
    def LEMON_disconnect(self):
        self.ask_custom('DISCONNECT LEMON')

    def LEMON_status(self):
        return self.ask_custom('LEMON CONNECTED?')