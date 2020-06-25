# -*- coding: utf-8 -*-
"""
Created on Fri Mar 30 13:56:22 2018

based on https://github.com/wakass/neqstlab/blob/master/instrument_plugins/Cryomagnetics_4G.py
and mercury IPS driver
"""

from qcodes import VisaInstrument
from qcodes.utils.validators import Enum

from functools import partial

import visa
import logging
import time
import re
import math
from qcodes import IPInstrument

class Cryomagnetics_4G_IP(IPInstrument): 

    def __init__(self, name, address=None, port=None, terminator='\r\n', reset=False,
                 tmpfile=None, timeout=3, write_confirmation=False, axes=None, margin=5e-4, curr_margin=2e-3, **kwargs):
        super().__init__(name, address=address, port=port, terminator=terminator,
                         timeout=timeout, write_confirmation=write_confirmation, **kwargs)
        self.read_termination='\r\n'
        self._axes = {}
        for i in range(len(axes)):
            self._axes[i] = axes[i]
        self._address = address
        self._field_units = ['kG','T']
        
        for ax in self._axes:
    
            ax_name = axes[ax].lower()    
            # self.add_parameter(ax_name+'_sweep')
               # val_mapping={'UP', 'UP FAST', 'DOWN', 'DOWN FAST', 'PAUSE', 'ZERO'))
            self.add_parameter(ax_name+'_lowlim',
                               get_cmd=partial(self._get_lowlim, ax),
                               set_cmd=partial(self._set_lowlim,ax),
                               unit='kG',
                               snapshot_exclude=True)
            #, snapshotable=False) 
            self.add_parameter(ax_name+'_uplim',
                               get_cmd=partial(self._get_uplim, ax),
                               set_cmd=partial(self._set_uplim, ax),
                               unit='kG',
                               snapshot_exclude=True)
            #, snapshotable=False) 
            self.add_parameter(ax_name+'_field',
                               get_cmd=partial(self._get_field, ax_name),
                               get_parser=None,
                               set_cmd=partial(self._set_field, ax_name),
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

        if reset:
            self.reset()
            
        self.MARGIN = margin  # 0.5 Gauss = 5e-4 kG = 5e-5 T = 0.05 mT
        self.CURR_MARGIN = curr_margin  # 2 mA 
        self.RE_ANS = re.compile(r'(-?\d*\.?\d*)([a-zA-Z]+)')
        self.connect_message()
        
    def get_idn(self):
        """ Return the Instrument Identifier Message """
        idstr = self.ask('*IDN?')
        idparts = [p.strip() for p in idstr.split(',', 4)][:]
        return dict(zip(('vendor', 'model', 'serial', 'firmware'), idparts))

    def reset(self):
        self._visa.write('*RST')

    def _select_channel(self, channel):
        if (len(self._axes)>1):
            
            for i, v in self._axes.items():
                
                if v == channel.upper():
                    self.write('CHAN {:0}'.format(i+1))
                    return True
            raise ValueError('Unknown axis %s' % channel)

    def _get_unit(self, channel):
       self._select_channel(channel)
       ans = self.ask_custom('UNITS?')
       return ans
       
    def _set_unit(self, channel, val):
        self._select_channel(channel)
        if self._get_drivemode(channel) == 'T' and val == 'A':
            print('Error: cannot set display units to \'G\'. Change to ampere drivemode'.format(val))
        elif self._get_drivemode(channel) == 'A' and val in self._field_units:
            print('Error: cannot set display units to \'{}\'. Change to field drivemode'.format(val))
        else:
            self.write('UNITS {}'.format(val))

    def _get_drivemode(self, channel):
        self._select_channel(channel)
        unit = self.ask_custom('UNITS?')
        if unit is not 'A':
            return 'T'
        else:
            return unit
       
    def _set_drivemode(self, channel, val):
        self._select_channel(channel)
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
        return self.ask(cmd).split(self.read_termination)[0]
    
    def get_magnetout(self, channel):
        while True:
            self._select_channel(channel)
            
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

    def _get_field(self, channel):
        val,unit = self.get_magnetout(channel)
        if unit is 'A':
            print('Power supply in ampere mode, switch to field drivemode')
            pass
        else:
            return val*0.1 #kG to T
    
    def _set_field(self, channel, val, wait=True):
        fieldval,unit = self.get_magnetout(channel)
        if unit is 'A':
            print('Power supply in ampere mode, switch to field drivemode')
            pass
        else:
            self._select_channel(channel)
            if 10*val > fieldval:
                self._set_uplim(channel, 10*val)
                self._sweep_up(channel)
            else:
                self._set_lowlim(channel, 10*val)
                self._sweep_down(channel)
            if wait:
                while math.fabs(val - 0.1*self.get_magnetout(channel)[0]) > self.MARGIN:
                    time.sleep(0.50)
            return True

    def _get_curr(self, channel):
        val,unit = self.get_magnetout(channel)
        if unit is not 'A':
            print('Power supply in field mode, switch to ampere drivemode')
            pass
        else:
            return val

    def _set_curr(self, channel, val, wait=True):
        currval,unit = self.get_magnetout(channel)
        if unit is not 'A':
            print('Power supply in field mode, switch to ampere drivemode')
            pass
        else:
            self._select_channel(channel)
            if val > currval:
                self._set_uplim(channel, val)
                self._sweep_up(channel)
            else:
                self._set_lowlim(channel, val)
                self._sweep_down(channel)
            if wait:
                while math.fabs(val - self.get_magnetout(channel)[0]) > self.CURR_MARGIN:
                    time.sleep(0.50)
            return True

    def _get_sweep(self, channel):
        self._select_channel(channel)
        ans = self.ask_custom('SWEEP?')
        return ans
        
    def _set_sweep(self, channel, cmd):
        self._select_channel(channel)
        cmd = cmd.upper()
        if cmd not in ['UP', 'UP FAST', 'DOWN', 'DOWN FAST', 'PAUSE', 'ZERO']:
            logging.warning('Invalid sweep mode selected')
            return False
        self.write('SWEEP %s' % cmd)

    def _sweep_up(self, channel, fast=False):
        cmd = 'UP'
        if fast:
            cmd += ' FAST'
        return self._set_sweep(channel, cmd)

    def _sweep_down(self, channel, fast=False):
        cmd = 'DOWN'
        if fast:
            cmd += ' FAST'
        return self._set_sweep(channel, cmd)

    def _get_lowlim(self, channel):
        self._select_channel(channel)
        ans = self._visa.ask_custom('LLIM?')
        return self._check_ans_unit(ans, channel)

    def _set_lowlim(self, channel, val):
        if channel=='z':
              self.write('LLIM %f' % val)
        else:    
         self._select_channel(channel)
         self.write('LLIM %f' % val)

    def _get_uplim(self, channel):
        self._select_channel(channel)
        ans = self._visa.ask_custom('ULIM?')
        return self._check_ans_unit(ans, channel)

    def _set_uplim(self, channel, val):
        if channel=='z':
            self.write('ULIM %f' % val)
        else: 
         self._select_channel(channel)
         self.write('ULIM %f' % val)