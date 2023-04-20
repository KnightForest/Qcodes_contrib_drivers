from qcodes import VisaInstrument
from qcodes import IPInstrument
from qcodes.utils.validators import Enum

from functools import partial

import visa
import logging
import time
import re
import math

class Cryomagnetics_4G_IP(IPInstrument):
    r"""
    Cryomagnetics 4G driver
    Uses TCP/IP socket to communicate with the device.
    
    Version 0.9 (2022-03-01)
    Joost Ridderbos - Researcher at ICE/QTM & NE
    University of Twente
    j.ridderbos@utwente.nl
    """
    def __init__(self,
                 name: str,
                 address: str,
                 port=None,
                 terminator='\r\n',
                 write_confirmation=False, 
                 axes=None, # Array of axis names, one per channel (internal PSUs in unit). Examples: ['z'], ['x','y']
                 channels=None, # Array of channels with length axes (number of internal PSUs in unit). For single channel: [1], for two channels: [1,2]
                 heaters=None, # Array of Booleans with length axes, indicating whether the axis/channel has a heater. Example: [False,True]
                 reset=False, # Resets instrument upon connecting
                 timeout=3, # Timeout for communcation with driver
                 heaterwait = 30, # Waiting time for the heater to switch on or off. This is a low limit!
                 margin=5e-4, # Margin of field in T for the magnet to be considered at setpoint 
                 curr_margin=2e-3, # Margin of current in A for the magnet to be considered at setpoint 
                 **kwargs):
        super().__init__(name, address=address, port=port, terminator=terminator,
                         timeout=timeout, write_confirmation=write_confirmation, **kwargs)
        
        self.visa_handle.read_termination = terminator

        if len(heaters) != len(axes):
            raise ValueError('Heater must be specified for every axis')
        if len(channels) != len(axes):
            raise ValueError('Channel must be specified for every axis')
        self._axes = [x.lower() for x in axes]
        self._address = address
        self._heaterdict = dict(zip(self._axes, heaters))
        self._channeldict = dict(zip(self._axes, channels))
        #print(self._heaterdict,self._channeldict)
        
        self._field_units = ['kG','T']
        for ax in range(len(self._axes)):
    
            ax_name = self._axes[ax]
            

            self.add_parameter(ax_name+'_lowlim',
                               get_cmd=partial(self._get_lowlim, ax_name),
                               set_cmd=partial(self._set_lowlim, ax_name),
                               unit='kG',
                               snapshot_exclude=True)
            #, snapshotable=False) 
            self.add_parameter(ax_name+'_uplim',
                               get_cmd=partial(self._get_uplim, ax_name),
                               set_cmd=partial(self._set_uplim, ax_name),
                               unit='kG',
                               snapshot_exclude=True)
            #, snapshotable=False) 
            self.add_parameter(ax_name+'_field',
                               get_cmd=partial(self._get_field, ax_name),
                               get_parser=None,
                               set_cmd=partial(self._set_field, ax_name),
                               unit='T')
            self.add_parameter(ax_name+'_field_persistent',
                               get_cmd=partial(self._get_field, ax_name),
                               get_parser=None,
                               set_cmd=partial(self._set_field_persistent, ax_name),
                               unit='T')
            self.add_parameter(ax_name+'_psufield',
                               get_cmd=partial(self._get_psufield, ax_name),
                               get_parser=None,
                               unit='T')
            self.add_parameter(ax_name+'_current',
                               get_cmd=partial(self._get_curr, ax_name),
                               get_parser=None,
                               set_cmd=partial(self._set_curr, ax_name),
                               unit='A')
            self.add_parameter(ax_name+'_display_unit',
                               get_cmd=partial(self._get_unit, ax_name),
                               get_parser=None,
                               set_cmd=partial(self._set_unit, ax_name),
                               val_mapping={'kG': 'kG', 'T': 'T', 'G': 'A'})
            self.add_parameter(ax_name+'_drivemode',
                               get_cmd=partial(self._get_drivemode, ax_name),
                               get_parser=None,
                               set_cmd=partial(self._set_drivemode, ax_name),
                               val_mapping={'ampere': 'A', 'field': 'T'})
            self.add_parameter(ax_name+'_heater',
                               get_cmd=partial(self._get_heater, ax_name),
                               get_parser=None,
                               set_cmd=partial(self._set_heater, ax_name),
                               val_mapping={'on': 'ON', 'off': 'OFF'})

        if reset:
            self.reset()
            
        self.MARGIN = margin
        self.CURR_MARGIN = curr_margin 
        self.RE_ANS = re.compile(r'(-?\d*\.?\d*)([a-zA-Z]+)')
        self.HEATERWAIT = heaterwait
        self.connect_message()
        
    def get_idn(self):
        """ Return the Instrument Identifier Message """
        idstr = self.ask('*IDN?')
        idparts = [p.strip() for p in idstr.split(',', 4)][:]
        return dict(zip(('vendor', 'model', 'serial', 'firmware'), idparts))

    def reset(self):
        self.write('*RST')

    def _select_channel(self, axis):
        #print(self._channeldict[axis])
        if self._channeldict[axis] not in [1,2]:
            raise ValueError('Unknown axis %s' % axis)
        self.write('CHAN {:0}'.format(self._channeldict[axis]))

    def _get_unit(self, axis):
       self._select_channel(axis)
       ans = self.ask_custom('UNITS?')
       return ans
       
    def _set_unit(self, axis, val):
        self._select_channel(axis)
        if self._get_drivemode(axis) == 'T' and val == 'A':
            print('Error: cannot set display units to \'G\'. Change to ampere drivemode'.format(val))
        elif self._get_drivemode(axis) == 'A' and val in self._field_units:
            print('Error: cannot set display units to \'{}\'. Change to field drivemode'.format(val))
        else:
            self.write('UNITS {}'.format(val))

    def _get_drivemode(self, axis):
        self._select_channel(axis)
        unit = self.ask_custom('UNITS?')
        if unit != 'A':
            return 'T'
        else:
            return unit
       
    def _set_drivemode(self, axis, val):
        self._select_channel(axis)
        self.write('UNITS {}'.format(val))
        time.sleep(0.1)
            
    def local(self):
        self.write('LOCAL')

    def remote(self):
        self.write('REMOTE')

    def ask_custom(self, cmd):
        """
        The instrument first returns the command we sent, and then the response
        """
        while True:
            try:
                res = self.ask(cmd).split(self.visa_handle.read_termination)[0]
                break
            except Exception as e:
                print('Communication error: ', e, ' Query repeated..')
                pass
        return res
    
    def get_magnetout(self, axis):
        while True:
            self._select_channel(axis)
            ans=self.ask_custom('IMAG?')
            time.sleep(0.01)
            ans=self.ask_custom('IMAG?')
            m = self.RE_ANS.match(ans)
            
            val, unit = m.groups((0,1))
            try:
                val = float(val)
                return val, unit
            except:
                print("Error: val is not a float.")
                time.sleep(0.1)
                pass

    def get_psuout(self, axis):
        while True:
            self._select_channel(axis)
            
            ans=self.ask_custom('IOUT?')
            m = self.RE_ANS.match(ans)
            
            val, unit = m.groups((0,1))
            try:
                val = float(val)
                return val, unit
            except:
                print("Error: val is not a float.")
                time.sleep(0.1)
                pass

    def _get_psufield(self, axis):
        val,unit = self.get_psuout(axis)
        if unit == 'A':
            print('Power supply in ampere mode, switch to field drivemode')
            pass
        else:
            return val*0.1 #kG to T
            
    def _get_psucurrent(self, axis):
        val,unit = self.get_psuout(axis)
        if unit != 'A':
            print('Power supply in field mode, switch to ampere drivemode')
            pass
        else:
            return val

    def _get_field(self, axis):
        val,unit = self.get_magnetout(axis)
        if unit == 'A':
            print('Power supply in ampere mode, switch to field drivemode')
            pass
        else:
            return val*0.1 #kG to T

    def heatercontrol(self, axis, status, heatersync=True):
        if self._get_drivemode(axis) == 'A':
            margin=2e-3
        else:
            margin=1e-4

        if heatersync:
            heaterlist = []
            for x in self._heaterdict.items():
                if x[1]:
                    heaterlist.append(x[0])
        if heatersync == False and self._heaterdict[axis]:
            heaterlist = [axis]
        #print('heaterlist',heaterlist)
        for axis in heaterlist:
            if status == 'ON':
                #print(self._get_heater(axis)) # 
                if self._get_heater(axis) == 'OFF': # If heater is off, start checks
                    psuval = self.get_psuout(axis)[0]
                    magval = self.get_magnetout(axis)[0]
                    print(psuval,magval)
                    if psuval != magval: # Check if PSU and coil match
                        print('Heater is off, matching PSU with magnets in lead..')
                        if magval > psuval: # If not, match PSU and coil
                            self._set_uplim(axis, magval)
                            self._sweep_up(axis, fast=True)
                        else:
                            self._set_lowlim(axis, magval)
                            self._sweep_down(axis, fast=True)
                        while math.fabs(magval - self.get_psuout(axis)[0]) > margin:
                            time.sleep(0.50)
                        print('PSU and coil matched.')
                    print('Turning heater on...')
                    self._set_heater(axis, 'on')
            if status == 'OFF':
                self._set_heater(axis,'OFF')
            if status == 'ZERO':
                self._set_heater(axis,'OFF')
                self.zero(axis,fast=True)

    def _set_field_persistent(self, axis, val, heatersync=True, zeroleads=True):
        self._set_field(axis,val, persistent=True, heatersync=heatersync, zeroleads=zeroleads)
    
    def _set_field(self, axis, val, wait=True, persistent=False, heatersync=True, zeroleads=False):
        field,unit = self.get_magnetout(axis)
        
        if unit == 'A':
            print('Power supply in ampere mode, switch to field drivemode')
            pass
        else:
            fieldtesla = 0.1*field #Converting magnetout from kG to T
            self._select_channel(axis)
            
            # Only relevant if heater is present
            if True in self._heaterdict.values():
                self.heatercontrol(axis,'ON',heatersync)
            if val > fieldtesla:
                self._set_uplim(axis, 10*val) #Setting uplim in kG
                self._sweep_up(axis, fast=False)
            else:
                self._set_lowlim(axis, 10*val) #Setting uplim in kG
                self._sweep_down(axis, fast=False)
            if persistent:
                while math.fabs(val - self._get_field(axis)) > 1e-4:
                    time.sleep(0.50)
                self.heatercontrol(axis,'OFF',heatersync)
                if zeroleads:
                    self.heatercontrol(axis,'ZERO',heatersync)
            elif wait:
                while math.fabs(val - self._get_field(axis)) > self.MARGIN:
                    time.sleep(0.50)
            return True

    def _get_curr(self, axis):
        val,unit = self.get_magnetout(axis)
        if unit != 'A':
            print('Power supply in field mode, switch to ampere drivemode')
            pass
        else:
            return val

    def _set_curr(self, axis, val, wait=True):
        curr,unit = self.get_magnetout(axis)
            
        if unit != 'A':
            print('Power supply in field mode, switch to ampere drivemode')
            pass
        else:
            self._select_channel(axis)
            # Only relevant if heater is present
            if True in self._heaterdict.values():
                self.heatercontrol(axis,'ON',heatersync)
            if val > curr:
                self._set_uplim(axis, val) #Setting uplim in kG
                self._sweep_up(axis, fast=False)
            else:
                self._set_lowlim(axis, val) #Setting uplim in kG
                self._sweep_down(axis, fast=False)
            if persistent:
                while math.fabs(val - self._get_curr(axis)) > 2e-3:
                    time.sleep(0.50)
                self.heatercontrol(axis,'OFF',heatersync)
                if zeroleads:
                    self.heatercontrol(axis,'ZERO',heatersync)
            elif wait:
                while math.fabs(val - self._get_curr(axis)) > self.CURR_MARGIN:
                    time.sleep(0.50)
            return True


            # Only relevant if heater is present
            if self._heaterdict[axis]: # Checks if axis has heater
                #print(self._get_heater(axis)) # 
                if self._get_heater(axis) == 'OFF': # If heater is off, start checks
                    psuval = self._get_psucurrent(axis)
                    magval = self._get_current(axis)
                    # print(psuval,magval)
                    if psuval != magval: # Check if PSU and coil match
                        print('Heater is off, matching PSU with magnets in lead..')
                        if magval > psuval: # If not, match PSU and coil
                            print(psuval,magval)
                            self._set_uplim(axis, magval)
                            self._sweep_up(axis, fast=True)
                        else:
                            self._set_lowlim(axis, magval)
                            self._sweep_down(axis, fast=True)
                        if wait:
                            while math.fabs(magval - self._get_psucurrent(axis)) > 1e-5:
                                time.sleep(0.50)
                        print('PSU and coil matched.')
                    print('Turning heater on...')
                    self._set_heater(axis, 'on')

            if val > curr:
                self._set_uplim(axis, val)
                self._sweep_up(axis, fast=False)
            else:
                self._set_lowlim(axis, val)
                self._sweep_down(axis, fast=False)
            if wait:
                while math.fabs(val - self._get_current(axis)) > self.MARGIN:
                    time.sleep(0.50)
            return True

    def _get_sweep(self, axis):
        self._select_channel(axis)
        ans = self.ask_custom('SWEEP?')
        return ans
        
    def _set_sweep(self, axis, cmd):
        self._select_channel(axis)
        cmd = cmd.upper()
        if cmd not in ['UP SLOW', 'UP FAST', 'DOWN SLOW', 'DOWN FAST', 'PAUSE', 'ZERO SLOW', 'ZERO FAST']:
            logging.warning('Invalid sweep mode selected')
            return False
        self.write('SWEEP %s' % cmd)
      
    def _sweep_up(self, axis, fast=False):
        if not fast:
            cmd = 'UP SLOW'
        else:
            cmd = 'UP FAST'
        return self._set_sweep(axis, cmd)

    def _sweep_down(self, axis, fast=False):
        if not fast:
            cmd = 'DOWN SLOW'
        else:
            cmd = 'DOWN FAST'
        return self._set_sweep(axis, cmd)
      
    def _get_lowlim(self, axis):
        self._select_channel(axis)
        ans = self.ask_custom('LLIM?')
        m = self.RE_ANS.match(ans)
        val, unit = m.groups((0,1))
        return val

    def _set_lowlim(self, axis, val): 
        self._select_channel(axis)
        self.write('LLIM %f' % val)

    def _get_uplim(self, axis):
        self._select_channel(axis)
        ans = self.ask_custom('ULIM?')
        m = self.RE_ANS.match(ans)
        val, unit = m.groups((0,1))
        return val

    def _set_uplim(self, axis, val):
        self._select_channel(axis)
        self.write('ULIM %f' % val)

    def _get_heater(self, axis):
        self._select_channel(axis)
        ans = self.ask('PSHTR?')
        if len(ans) > 0 and ans[0] == '1':
            return 'ON'
        else:
            return 'OFF'

    def _set_heater(self, axis, val, heaterwait=None):
        if heaterwait==None:
            heaterwait = self.HEATERWAIT
        self._select_channel(axis)
        time.sleep(5)
        self.write('PSHTR %s' % val)
        time.sleep(heaterwait)

    def pause(self, axis):
        self.set('sweep%s' % axis, 'PAUSE')
#
    def zero(self, axis, wait=True, fast=False):
        if not fast:
            cmd = 'ZERO SLOW'
        else:
            cmd = 'ZERO FAST'
        self._set_sweep(axis, cmd)
        if wait:
            while abs(self.get_psuout(axis)[0]) > 1e-6:
                time.sleep(0.50)

    def shutdown(self, wait=True, fast=False):
        self.heatercontrol(self._axes[0],'ON', heatersync=True)
        for ax in self._axes:
            print('Zeroing {} axis'.format(ax))
            self.zero(ax, wait=wait, fast=False)
        for ax in self._axes:
            print('Turning {} axis heater off'.format(ax))
            self._set_heater(ax,'OFF')
        print('Shutdown succesful.')
#
#    def do_get_rate0(self, axis):
#        self._select_channel(axis)
#        ans = self._visa.ask('RATE? 0')
#        return float(ans)
#
#    def do_get_rate1(self, axis):
#        self._select_channel(axis)
#        ans = self._visa.ask('RATE? 1')
#        return float(ans)
#
#    def do_set_rate0(self, rate, axis):
#        self._select_channel(axis)
#        self._visa.write('RATE 0 %.03f\n' % rate)
#
#    def do_set_rate1(self, rate, axis):
#        self._select_channel(axis)
#        self._visa.write('RATE 1 %.03f\n' % rate)
