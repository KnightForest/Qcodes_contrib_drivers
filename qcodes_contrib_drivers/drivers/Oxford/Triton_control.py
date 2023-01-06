import configparser
import re
from functools import partial
import logging
from traceback import format_exc
from typing import Optional, Any, Union, List, Dict

from qcodes import IPInstrument
from qcodes.utils.validators import Enum, Ints

from time import sleep
import sys


class Triton(IPInstrument):
    r"""
    Triton Driver
    Args:
        tmpfile: Optional: an exported windows registry file from the registry
            path:
            `[HKEY_CURRENT_USER\Software\Oxford Instruments\Triton System Control\Thermometry]`
            and is used to extract the available temperature channels.
    Status: beta-version.
        TODO:
        fetch registry directly from fridge-computer
    """

    def __init__(
            self,
            name: str,
            address: Optional[str] = None,
            port: Optional[int] = None,
            terminator: str = '\r\n',
            tmpfile: Optional[str] = None,
            timeout: float = 20,
            pid = None,
            condense_tlim = 1.2,
            tlim_safety = True,
            **kwargs: Any):
        super().__init__(name, address=address, port=port,
                         terminator=terminator, timeout=timeout, **kwargs)

        self._heater_range_auto = False
        self._heater_range_temp = [0.0, 0.015, 0.025, 0.07,  0.2,  1.5,  40.,  300]
        self._heater_range_curr = [0.0, 0.316, 1,     3.16,  10.,  31.6, 100., 100.]
        self._heaterdict = dict(zip(self._heater_range_temp,self._heater_range_curr))
        #self._control_channel = 5

        self.add_parameter(name='turbo_status',
                           label='turbo_status',
                           get_cmd=partial(self._get_turbo_status),
                           set_cmd=partial(self._set_turbo_status),
                           val_mapping={'on':  'ON', 'off': 'OFF'})
        
        self.add_parameter(name='turbo_speed',
                           label='turbo_speed',
                           unit = 'Hz',
                           get_cmd=partial(self._get_turbo_speed))

        self.add_parameter(name='autotemperature',
                           label='autotemperature',
                           unit='K',
                           get_cmd=partial(self._get_autotempcontrol),
                           set_cmd=partial(self._set_autotempcontrol))

        self.add_parameter(name='time',
                           label='System Time',
                           get_cmd='READ:SYS:TIME',
                           get_parser=self._parse_time)

        self.add_parameter(name='action',
                           label='Current action',
                           get_cmd='READ:SYS:DR:ACTN',
                           get_parser=self._parse_action)

        self.add_parameter(name='status',
                           label='Status',
                           get_cmd='READ:SYS:DR:STATUS',
                           get_parser=self._parse_status)

        self.add_parameter(name='pid_control_channel',
                           label='PID control channel',
                           get_cmd=self._get_control_channel,
                           set_cmd=self._set_control_channel,
                           vals=Ints(1, 16))

        self.add_parameter(name='pid_mode',
                           label='PID Mode',
                           get_cmd=partial(self._get_control_param, 'MODE'),
                           set_cmd=partial(self._set_control_param, 'MODE'),
                           val_mapping={'on':  'ON', 'off': 'OFF'})

        self.add_parameter(name='pid_ramp',
                           label='PID ramp enabled',
                           get_cmd=partial(self._get_control_param,
                                           'RAMP:ENAB'),
                           set_cmd=partial(self._set_control_param,
                                           'RAMP:ENAB'),
                           val_mapping={'on':  'ON', 'off': 'OFF'})

        self.add_parameter(name='pid_setpoint',
                           label='PID temperature setpoint',
                           unit='K',
                           get_cmd=partial(self._get_control_param, 'TSET'),
                           set_cmd=partial(self._set_control_param, 'TSET'),
                           snapshot_exclude=True)

        self.add_parameter(name='pid_rate',
                           label='PID ramp rate',
                           unit='K/min',
                           get_cmd=partial(self._get_control_param,
                                           'RAMP:RATE'),
                           set_cmd=partial(self._set_control_param,
                                           'RAMP:RATE'),
                           snapshot_exclude=True)

        self.add_parameter(name='pid_range',
                           label='PID heater range',
                           # TODO: The units in the software are mA, how to
                           # do this correctly?
                           unit='mA',
                           get_cmd=partial(self._get_control_param, 'RANGE'),
                           set_cmd=partial(self._set_control_param, 'RANGE'),
                           vals=Enum(*self._heater_range_curr),
                           snapshot_exclude=True)

        self.add_parameter(name='magnet_status',
                           label='Magnet status',
                           unit='',
                           get_cmd=partial(self._get_control_B_param, 'ACTN'))

        self.add_parameter(name='magnet_sweeprate',
                           label='Magnet sweep rate',
                           unit='T/min',
                           get_cmd=partial(
                               self._get_control_B_param, 'RVST:RATE'),
                           set_cmd=partial(self._set_control_magnet_sweeprate_param))

        self.add_parameter(name='magnet_sweeprate_insta',
                           label='Instantaneous magnet sweep rate',
                           unit='T/min',
                           get_cmd=partial(self._get_control_B_param, 'RFST'))

        self.add_parameter(name='B',
                           label='Magnetic field',
                           unit='T',
                           get_cmd=partial(self._get_control_B_param, 'VECT'))

        self.add_parameter(name='Bx',
                           label='Magnetic field x-component',
                           unit='T',
                           get_cmd=partial(
                               self._get_control_Bcomp_param, 'VECTBx'),
                           set_cmd=partial(self._set_control_Bx_param))

        self.add_parameter(name='By',
                           label='Magnetic field y-component',
                           unit='T',
                           get_cmd=partial(
                               self._get_control_Bcomp_param, 'VECTBy'),
                           set_cmd=partial(self._set_control_By_param))

        self.add_parameter(name='Bz',
                           label='Magnetic field z-component',
                           unit='T',
                           get_cmd=partial(
                               self._get_control_Bcomp_param, 'VECTBz'),
                           set_cmd=partial(self._set_control_Bz_param))

        self.add_parameter(name='magnet_sweep_time',
                           label='Magnet sweep time',
                           unit='T/min',
                           get_cmd=partial(self._get_control_B_param, 'RVST:TIME'))

        self.chan_alias: Dict[str, str] = {}
        self.chan_temp_names: Dict[str, Dict[str, Optional[str]]] = {}
        if tmpfile is not None:
            self._get_temp_channel_names(tmpfile)
        self._get_temp_channels()
        self._get_pressure_channels()
        self._get_valve_channels()
        self._control_channel = None 
        self._control_channel = self._get_control_channel()
        self._get_pid_channels()
        if pid is not None:
            self.pid_P.set(pid[0])
            self.pid_I.set(pid[1])
            self.pid_D.set(pid[2])
        try:
            self._get_named_channels()
        except:
            logging.warning('Ignored an error in _get_named_channels\n' +
                            format_exc())

        self.condense_tlim = condense_tlim
        self.tlim_safety = tlim_safety
        self.connect_message()

    def _get_autotempcontrol(self):
        return eval("self.%s.get()" % (self ._get_named_control_channel()))

    def _checkcirculating(self,tlim):
        if self.turbo_status.get() == 'on' and (self.MC.get()) < tlim and (self.P2.get()) < 2.5 and (self.P1.get()) < 5e-2:
            return True
        else:
            return False

    def _set_autotempcontrol(self,val,wait=True,tolerance = 0.02):
        print('Temperature setpoint: '+ str(val) + ' K')
        #self.pid_mode.set('off')
        sleep(1)
        
        # heater routine below tlim (while circulating)
        if val <= self.condense_tlim and self._checkcirculating(self.condense_tlim)==True:
            if self._get_named_control_channel != 'MC':
                self._set_named_control_channel('MC')
            if self.MC_status.get() == 'off':
                self.MC_status.set('on')
            if self.COOL_status.get() == 'on':
                self.COOL_status.set('off')
            #self.pid_mode.set('off')
        else:
            print('Temperature control below ' + str(self.condense_tlim) + ' K not possible, recondense first.')
            #break
        
        #heater routine above tlim (turbo off and mixture collected)
        if val > self.condense_tlim :
            if self.tlim_safety == False:
                print('Warning: you\'ll need to recondense for temperature control below ' + str(self.condense_tlim) + ' K.')
                if self.turbo_status.get() == 'on':
                    self.turbo_status.set('off')
                while self.turbo_speed.get() > 100:
                    print('Waiting for turbo to spin down below 100 Hz, currently ' + str(self.turbo_speed.get()) + ' Hz.')
                    sleep(10)
                    self.V9.set('closed')
                    self.V4.set('open')
            else:
                print('Temperature control above condense limit of ' + str(self.condense_tlim) + ' K not allowed.')
            #break
            
        if self.pid_mode.get() == 'off' and val > 0.015:
            self.pid_mode.set('on')
            sleep(1)

        for i,hval in enumerate(self._heater_range_temp): #Select correct heater range
            if val >= self._heater_range_temp[i] and val < self._heater_range_temp[i+1]:
                heaterval = self._heaterdict[hval]
                self.pid_range.set(heaterval)
                print('Heater set to ' + str(heaterval) + ' mA')

        self.pid_setpoint.set(str(val))
        sleep(1)
        if wait==True:
            actualtemp = self._istempreached(val,tolerance)
            return actualtemp

    def _istempreached(self,val,tolerance):
        thighperc = val*(1+tolerance)
        tlowperc = val/(1+tolerance)
        thighabs = val+0.002
        tlowabs = val-0.002
        if thighperc<thighabs:
            thigh = thighabs
            tlow = tlowabs
        else:
            thigh = thighperc
            tlow = tlowperc

        print('Temp. lower limit: ' + "{:.4f}".format(tlow) + ' K\nTemp. upper limit: ' + "{:.4f}".format(thigh) + ' K')
        stability_samples_limit = 2 # consecutive samples within tolerance to be considered stable
        stability_samples = 0       # init
        tlow_samples_limit = 5      # increases heater power after n-samples
        tlow_samples = 0            # init
        tick = 60                   # polling interval, choose not lower than lakeshore update freq (60 s)
        for i in range(0,int(tick)): # allows keyboard interrupts every second
            sleep(1)
        while stability_samples != stability_samples_limit:
            actualtemp = eval("self.%s.get()" % (self ._get_named_control_channel()))
            for i in range(0,int(tick)): # allows keyboard interrupts every second
                if self.turbo_status.get()=='on':
                    if self.P3.get() > 3e-3 or self.P2.get() > 2.5:
                        self.pid_setpoint.set(str(0))
                        self.pid_range.set(0.0)
                        self.pid_mode.set('off')
                        sys.exit('Temperature control aborted, P2 at ' + "{:.4f}".format(self.P2.get()) + ' Bar, P3 at ' + "{:.4f}".format(self.P3.get()*1e3) + ' mBar.')
                        # throw error and abort
                sleep(1)
            if actualtemp > tlow and actualtemp < thigh:
                stability_samples = stability_samples + 1
                print('T = '+ str(actualtemp) + ', waiting for temp to stabilise. Samples:' + str(stability_samples))
            elif actualtemp < tlow:
                stability_samples = 0
                tlow_samples = tlow_samples + 1
                print('Waiting to reach temp, temp = ' + str(actualtemp) + ' Tlow_samples:' + str(tlow_samples))
            elif actualtemp > thigh:
                if val > 1.5:
                    self.pid_range.set(10.)
                stability_samples = 0
                tlow_samples = 0
                print('Temp higher than setpoint: '+ str(actualtemp) +', waiting...')
            if tlow_samples == tlow_samples_limit:
                tlow_samples = 0
                heatind = self._heater_range_curr.index(self.pid_range.get())
                if heatind+1 < len(self._heater_range_curr):
                    self.pid_range.set(self._heater_range_curr[heatind+1])
                    print('heater power increased to: ' + str(self._heater_range_curr[heatind+1]))
                #timeout = 0
        print('Temp reached & stable')
        return(actualtemp)

    def _get_turbo_status(self):
        result = self.ask('READ:DEV:TURB1:PUMP:SIG:STATE')
        result = (result.replace('STAT:DEV:TURB1:PUMP:SIG:STATE:',''))
        return result

    def _set_turbo_status(self, val):
        self.write('SET:DEV:TURB1:PUMP:SIG:STATE:{}'.format(val))

    def _get_turbo_speed(self):
        return float(self.ask('READ:DEV:TURB1:PUMP:SIG:SPD').split(':')[-1].split('Hz')[0])

    def set_B(self, x: float, y: float, z: float, s: float) -> None:
        if 0 < s <= 0.2:
            self.write('SET:SYS:VRM:COO:CART:RVST:MODE:RATE:RATE:' + str(s) +
                       ':VSET:[' + str(x) + ' ' + str(y) + ' ' + str(z) + ']\r\n')
            self.write('SET:SYS:VRM:ACTN:RTOS\r\n')
            t_wait = self.magnet_sweep_time() * 60 + 10
            print('Please wait ' + str(t_wait) +
                  ' seconds for the field sweep...')
            sleep(t_wait)
        else:
            print('Warning: set magnet sweep rate in range (0 , 0.2] T/min')

    def _get_control_B_param(
            self,
            param: str
    ) -> Optional[Union[float, str, List[float]]]:
        cmd = f'READ:SYS:VRM:{param}'
        return self._get_response_value(self.ask(cmd))

    def _get_control_Bcomp_param(
            self,
            param: str
    ) -> Optional[Union[float, str, List[float]]]:
        cmd = f'READ:SYS:VRM:{param}'
        return self._get_response_value(self.ask(cmd[:-2]) + cmd[-2:])

    def _get_response(self, msg: str) -> str:
        return msg.split(':')[-1]

    def _get_response_value(
            self,
            msg: str
    ) -> Optional[Union[float, str, List[float]]]:
        msg = self._get_response(msg)
        if msg.endswith('NOT_FOUND'):
            return None
        elif msg.endswith('IDLE'):
            return 'IDLE'
        elif msg.endswith('RTOS'):
            return 'RTOS'
        elif msg.endswith('Bx'):
            return float(re.findall(r"[-+]?\d*\.\d+|\d+", msg)[0])
        elif msg.endswith('By'):
            return float(re.findall(r"[-+]?\d*\.\d+|\d+", msg)[1])
        elif msg.endswith('Bz'):
            return float(re.findall(r"[-+]?\d*\.\d+|\d+", msg)[2])
        elif len(re.findall(r"[-+]?\d*\.\d+|\d+", msg)) > 1:
            return [float(re.findall(r"[-+]?\d*\.\d+|\d+", msg)[0]), float(re.findall(r"[-+]?\d*\.\d+|\d+", msg)[1]), float(re.findall(r"[-+]?\d*\.\d+|\d+", msg)[2])]
        try:
            return float(re.findall(r"[-+]?\d*\.\d+|\d+", msg)[0])
        except Exception:
            return msg

    def get_idn(self) -> Dict[str, Optional[str]]:
        """ Return the Instrument Identifier Message """
        idstr = self.ask('*IDN?')
        idparts = [p.strip() for p in idstr.split(':', 4)][1:]
        return dict(zip(('vendor', 'model', 'serial', 'firmware'), idparts))

    def _get_control_channel(self, force_get: bool = False) -> int:

        # verify current channel
        if self._control_channel and not force_get:
            tempval = self.ask(
                f'READ:DEV:T{self._control_channel}:TEMP:LOOP:MODE')
            if not tempval.endswith('NOT_FOUND'):
                return self._control_channel
        # either _control_channel is not set or wrong
        for i in range(1, 17):
            tempval = self.ask(f'READ:DEV:T{i}:TEMP:LOOP:MODE')
            if not tempval.endswith('NOT_FOUND'):
                self._control_channel = i
                break
        return self._control_channel

    def _set_control_channel(self, channel: int) -> None:
        self._control_channel = channel
        self.write('SET:DEV:T{}:TEMP:LOOP:HTR:H1'.format(
            channel))

    def _get_control_param(
            self,
            param: str
    ) -> Optional[Union[float, str, List[float]]]:
        chan = self._get_control_channel()
        cmd = f'READ:DEV:T{chan}:TEMP:LOOP:{param}'
        return self._get_response_value(self.ask(cmd))

    def _set_control_param(self, param: str, value: float) -> None:
        chan = self._get_control_channel()
        cmd = f'SET:DEV:T{chan}:TEMP:LOOP:{param}:{value}'
        self.write(cmd)

    def _set_control_magnet_sweeprate_param(self, s: float) -> None:
        if 0 < s <= 0.2:
            x = round(self.Bx(), 4)
            y = round(self.By(), 4)
            z = round(self.Bz(), 4)
            self.write('SET:SYS:VRM:COO:CART:RVST:MODE:RATE:RATE:' + str(s) +
                       ':VSET:[' + str(x) + ' ' + str(y) + ' ' + str(z) + ']\r\n')
        else:
            print(
                'Warning: set sweeprate in range (0 , 0.2] T/min, not setting sweeprate')

    def _set_control_Bx_param(self, x: float) -> None:
        s = self.magnet_sweeprate()
        y = round(self.By(), 4)
        z = round(self.Bz(), 4)
        self.write('SET:SYS:VRM:COO:CART:RVST:MODE:RATE:RATE:' + str(s) +
                   ':VSET:[' + str(x) + ' ' + str(y) + ' ' + str(z) + ']\r\n')
        self.write('SET:SYS:VRM:ACTN:RTOS\r\n')
        # just to give an time estimate, +10s for overhead
        t_wait = self.magnet_sweep_time() * 60 + 10
        print('Please wait ' + str(t_wait) + ' seconds for the field sweep...')
        while self.magnet_status() != 'IDLE':
            pass

    def _set_control_By_param(self, y: float) -> None:
        s = self.magnet_sweeprate()
        x = round(self.Bx(), 4)
        z = round(self.Bz(), 4)
        self.write('SET:SYS:VRM:COO:CART:RVST:MODE:RATE:RATE:' + str(s) +
                   ':VSET:[' + str(x) + ' ' + str(y) + ' ' + str(z) + ']\r\n')
        self.write('SET:SYS:VRM:ACTN:RTOS\r\n')
        # just to give an time estimate, +10s for overhead
        t_wait = self.magnet_sweep_time() * 60 + 10
        print('Please wait ' + str(t_wait) + ' seconds for the field sweep...')
        while self.magnet_status() != 'IDLE':
            pass

    def _set_control_Bz_param(self, z: float) -> None:
        s = self.magnet_sweeprate()
        x = round(self.Bx(), 4)
        y = round(self.By(), 4)
        self.write('SET:SYS:VRM:COO:CART:RVST:MODE:RATE:RATE:' + str(s) +
                   ':VSET:[' + str(x) + ' ' + str(y) + ' ' + str(z) + ']\r\n')
        self.write('SET:SYS:VRM:ACTN:RTOS\r\n')
        # just to give an time estimate, +10s for overhead
        t_wait = self.magnet_sweep_time() * 60 + 10
        print('Please wait ' + str(t_wait) + ' seconds for the field sweep...')
        while self.magnet_status() != 'IDLE':
            pass

    def _get_named_channels(self) -> None:
        allchans_str = self.ask('READ:SYS:DR:CHAN')
        allchans = allchans_str.replace('STAT:SYS:DR:CHAN:', '', 1).split(':')
        for ch in allchans:
            msg = 'READ:SYS:DR:CHAN:%s' % ch
            rep = self.ask(msg)
            if 'INVALID' not in rep and 'NONE' not in rep:
                alias, chan = rep.split(':')[-2:]
                self.chan_alias[alias] = chan
                self.add_parameter(name=alias,
                                   unit='K',
                                   get_cmd='READ:DEV:%s:TEMP:SIG:TEMP' % chan,
                                   get_parser=self._parse_temp)
                self.add_parameter(name=alias + '_status',
                                   get_cmd='READ:DEV:%s:TEMP:MEAS:ENAB' % chan,
                                   get_parser=self._parse_temp_stat,
                                   set_cmd=partial(self._set_named_temp_stat,chan),
                                   val_mapping={'on':  'ON', 'off': 'OFF'})

    def _set_named_temp_stat(self,chan,val):
        self.write('SET:DEV:{}:TEMP:MEAS:ENAB:{}'.format(chan, val))
        sleep(1)

    def _get_named_control_channel(self):
        chandict = self.chan_alias
        t = 'T'+ str(self._get_control_channel())
        for name, age in chandict.items():
            if age == t:
                return name

    def _set_named_control_channel(self, channame):
        self._set_control_channel(int(self.chan_alias[channame].split('T')[-1]))

    def _get_pressure_channels(self) -> None:
        chan_pressure_list = []
        for i in range(1, 7):
            chan = 'P%d' % i
            chan_pressure_list.append(chan)
            self.add_parameter(name=chan,
                               unit='bar',
                               get_cmd='READ:DEV:%s:PRES:SIG:PRES' % chan,
                               get_parser=self._parse_pres)
        self.chan_pressure = set(chan_pressure_list)

    def _get_valve_channels(self) -> None:
        chan_valve_list = []
        for i in range(1, 10):
            chan = 'V%d' % i
            chan_valve_list.append(chan)
            self.add_parameter(name=chan,
                               get_cmd='READ:DEV:%s:VALV:SIG:STATE' % chan,
                               get_parser=self._parse_valve,
                               set_cmd=partial(self._set_valve_status,chan),
                               val_mapping={'open':  'OPEN', 'closed': 'CLOSE'})
        self.chan_valve = set(chan_valve_list)

    def _set_valve_status(self,chan,val):
        self.write('SET:DEV:%s:VALV:SIG:STATE:%s' % (chan, val))
        sleep(1)

    def _get_temp_channel_names(self, file: str) -> None:
        config = configparser.ConfigParser()
        with open(file, encoding='utf16') as f:
            next(f)
            config.read_file(f)

        for section in config.sections():
            options = config.options(section)
            namestr = '"m_lpszname"'
            if namestr in options:
                chan_number = int(section.split('\\')[-1].split('[')[-1]) + 1
                # the names used in the register file are base 0 but the api and the gui
                # uses base one names so add one
                chan = 'T' + str(chan_number)
                name = config.get(section, '"m_lpszname"').strip("\"")
                self.chan_temp_names[chan] = {'name': name, 'value': None}

    def _get_temp_channels(self) -> None:
        chan_temps_list = []
        for i in range(1, 17):
            chan = 'T%d' % i
            chan_temps_list.append(chan)
            self.add_parameter(name=chan,
                               unit='K',
                               get_cmd='READ:DEV:%s:TEMP:SIG:TEMP' % chan,
                               get_parser=self._parse_temp)
            self.add_parameter(name=chan + '_status',
                               unit='K',
                               get_cmd='READ:DEV:%s:TEMP:MEAS:ENAB' % chan,
                               get_parser=self._parse_temp_stat,
                               set_cmd=partial(self._set_temp_stat,chan),
                               val_mapping={'on':  'ON', 'off': 'OFF'})
        self.chan_temps = set(chan_temps_list)

    def _set_temp_stat(self,chan,val):
        self.write('SET:DEV:{}:TEMP:MEAS:ENAB:{}'.format(chan, val))
        sleep(1)

    def _get_pid_channels(self) -> None:
        chan_pid_list = []
        for i, pid in enumerate(['P','I','D']):
            chan = pid
            chan_pid_list.append(chan)
            self.add_parameter(name='pid_' +chan,
                               unit='',
                               get_cmd=partial(self._get_pid,chan),
                               get_parser=self._parse_pid,
                               set_cmd=partial(self._set_pid,chan))
        self.chan_pid = set(chan_pid_list)

    def _get_pid(self,chan):
        cchan = self._get_control_channel()
        return(self.ask('READ:DEV:T{}:TEMP:LOOP:{}'.format(cchan,chan)).split(':')[-1])

    def _set_pid(self,chan,val):
        cchan = self._get_control_channel()
        self.write('SET:DEV:T{}:TEMP:LOOP:{}:{}'.format(cchan, chan, val))
        sleep(0.1)

    def _parse_action(self, msg: str) -> str:
        """ Parse message and return action as a string
        Args:
            msg: message string
        Returns
            action: string describing the action
        """
        action = msg[17:]
        if action == 'PCL':
            action = 'Precooling'
        elif action == 'EPCL':
            action = 'Empty precool loop'
        elif action == 'COND':
            action = 'Condensing'
        elif action == 'NONE':
            if self.MC.get() < 2:
                action = 'Circulating'
            else:
                action = 'Idle'
        elif action == 'COLL':
            action = 'Collecting mixture'
        else:
            action = 'Unknown'
        return action

    def _parse_status(self, msg: str) -> str:
        return msg[19:]

    def _parse_time(self, msg: str) -> str:
        return msg[14:]

    def _parse_temp(self, msg: str) -> Optional[float]:
        if 'NOT_FOUND' in msg:
            return None
        return float(msg.split('SIG:TEMP:')[-1].strip('K'))

    def _parse_temp_stat(self, msg: str) -> Optional[float]:
        if 'NOT_FOUND' in msg:
            return None
        return msg.split(':')[-1]

    def _parse_pres(self, msg: str) -> Optional[float]:
        if 'NOT_FOUND' in msg:
            return None
        return float(msg.split('SIG:PRES:')[-1].strip('mB')) / 1e3

    def _parse_valve(self, msg: str) -> Optional[float]:
        if 'NOT_FOUND' in msg:
            return None
        return msg.split(':')[-1]

    def _parse_pid(self, msg: str) -> Optional[float]:
        if 'NOT_FOUND' in msg:
            return None
        return msg.split(':')[-1]

    def _recv(self) -> str:
        return super()._recv().rstrip()
