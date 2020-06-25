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

class Cryomagnetics_4G(VisaInstrument):


    def __init__(self, name: str, address: str, axes=('Z','Y'), terminator="\n", baudrate=9600, serial=True, reset=False,**kwargs,):

        super().__init__(name=name, address=address, terminator=terminator, **kwargs)
		
        self.visa_handle.read_termination="\n"
        self.visa_handle.write_termination  ="\n"

        if serial:
            self.visa_handle.baud_rate = 9600
            self.visa_handle.parity = visa.constants.Parity.none
            self.visa_handle.stop_bits = visa.constants.StopBits.one
            self.visa_handle.data_bits = 8
            self.visa_handle.flow_control = 0
        
		
        self._axes = {}
        
        for i in range(len(axes)):
            self._axes[i] = axes[i]
            
        self._address = address
        
        for ax in self._axes:
    
            ax_name = axes[ax].lower()    
#            self.add_parameter(ax_name+'_sweep')
#                val_mapping={'UP', 'UP FAST', 'DOWN', 'DOWN FAST', 'PAUSE', 'ZERO'))
    
#            self.add_parameter(ax_name+'_lowlim',
#                               get_cmd=partial(self._get_lowlim, ax),
#                               set_cmd=partial(self._set_lowlim,ax),
#                               unit='kG') 
#    
#            self.add_parameter(ax_name+'_uplim',
#                               get_cmd=partial(self._get_uplim, ax),
#                               set_cmd=partial(self._set_uplim, ax),
#                               unit='kG')
    
            self.add_parameter(ax_name+'_field',
                               get_cmd=partial(self.get_magnetout, ax_name),
                               get_parser=float,
                               set_cmd=partial(self._set_field, ax_name),
                               unit='T')

        if reset:
            self.reset()
            
        self.UNITS = ['A', 'G']
        self.MARGIN = 0.001  # 1 Gauss
        self.RE_ANS = re.compile(r'(-?\d*\.?\d*)([a-zA-Z]+)')

    def reset(self):
        self._visa.write('*RST')

    def _select_channel(self, channel):
        for i, v in self._axes.items():
            if v == channel.upper():
                self.write_custom('CHAN {:0}'.format(i+1))
                return True
        raise ValueError('Unknown axis %s' % channel)



    def local(self):
        self.write_custom('LOCAL')

    def remote(self):
        self.write_custom('REMOTE')


    def ask_custom(self, cmd):
        """
        The instrument first returns the command we sent, and then the response
        """
        return self.ask(cmd)

    def write_custom(self, cmd):
        """
        The instrument first returns the command we sent, and then the response
        """
        self.write(cmd)
        return
    
    def get_magnetout(self, channel):
        self._select_channel(channel)
        ans=self.ask_custom('IMAG?')
        m = self.RE_ANS.match(ans)
        
        val, unit = m.groups((0,1))
        try:
            val = float(val)
        except:
            val = None
            
        return val

#    def get_supplyout(self, channel):
#        self._select_channel(channel)
#        ans = self.ask_custom('IOUT?\n')
#        return ans

    def get_sweep(self, channel):
        self._select_channel(channel)
        ans = self.ask_custom('SWEEP?')
        return ans

    def set_sweep(self, channel, cmd):
        self._select_channel(channel)
        cmd = cmd.upper()
        if cmd not in ['UP', 'UP FAST', 'DOWN', 'DOWN FAST', 'PAUSE', 'ZERO']:
            logging.warning('Invalid sweep mode selected')
            return False
        self.write_custom('SWEEP %s' % cmd)

    def sweep_up(self, channel, fast=False):
        cmd = 'UP'
        if fast:
            cmd += ' FAST'
        return self.set_sweep(channel, cmd)

    def sweep_down(self, channel, fast=False):
        cmd = 'DOWN'
        if fast:
            cmd += ' FAST'
        return self.set_sweep(channel, cmd)

    def get_lowlim(self, channel):
        self._select_channel(channel)
        ans = self._visa.ask('LLIM?')
        return self._check_ans_unit(ans, channel)

    def set_lowlim(self, channel, val):
        self._select_channel(channel)
        self.write_custom('LLIM %f' % val)

    def _get_uplim(self, channel):
        self._select_channel(channel)
        ans = self._visa.ask('ULIM?')
        return self._check_ans_unit(ans, channel)

    def set_uplim(self, channel, val):
        self._select_channel(channel)
        self.write_custom('ULIM %f' % val)

    def _get_field(self, channel):
        self._select_channel(channel)
        ans = self.ask_custom('IMAG?')
        return ans
    
    def _set_field(self, channel, val, wait=True):
        
        self._select_channel(channel)

#        if not self.get('heater%s' % channel, query=False):
#            logging.warning('Unable to sweep field when heater off')
#            return False

        cur_magnet = 0.1*self.get_magnetout(channel) # in Tesla

        if val > cur_magnet:
            self.set_uplim(channel, 10*val)
            self.sweep_up(channel)
        else:
            self.set_lowlim(channel, 10*val)
            self.sweep_down(channel)

        if wait:
            while math.fabs(val - 0.1*self.get_magnetout(channel)) > self.MARGIN:
                time.sleep(0.050)

        return True

#    def pause(self):
#        for ax in self._axes.values():
#            self.set('sweep%s' % ax, 'PAUSE')
#
#    def zero(self):
#        for ax in self._axes.values():
#            self.set('sweep%s' % ax, 'ZERO')
        
    #    def do_get_units(self, channel):
#        self._select_channel(channel)
#        ans = self._visa.ask('UNITS?')
#        self._update_units(ans, channel)
#        return ans
#
#    def do_set_units(self, unit, channel):
#        if unit not in self.UNITS:
#            logging.error('Trying to set invalid unit: %s', unit)
#            return False
#        self._select_channel(channel)
#        self._visa.write('UNITS %s' % unit)
#        self._update_units(unit, channel)
#
#    def _check_ans_unit(self, ans, channel):
#        m = self.RE_ANS.match(ans)
#        if not m:
#            logging.warning('Unable to parse answer: %s', ans)
#            return False
#
#        val, unit = m.groups((0,1))
#        try:
#            val = float(val)
#        except:
#            val = None
#
#        set_unit = self.get('units%s' % channel, query=False)
#        if set_unit == 'G':
#            set_unit = 'kG'
#        if unit != set_unit:
#            logging.warning('Returned units (%s) differ from set units (%s)!',
#                unit, set_unit)
#            return None
#
#        return val

#    def do_get_rate0(self, channel):
#        self._select_channel(channel)
#        ans = self._visa.ask('RATE? 0')
#        return float(ans)
#
#    def do_get_rate1(self, channel):
#        self._select_channel(channel)
#        ans = self._visa.ask('RATE? 1')
#        return float(ans)
#
#    def do_set_rate0(self, rate, channel):
#        self._select_channel(channel)
#        self._visa.write('RATE 0 %.03f\n' % rate)
#
#    def do_set_rate1(self, rate, channel):
#        self._select_channel(channel)
#        self._visa.write('RATE 1 %.03f\n' % rate)

#    def do_get_heater(self, channel):
#        self._select_channel(channel)
#        ans = self._visa.ask('PSHTR?')
#        if len(ans) > 0 and ans[0] == '1':
#            return True
#        else:
#            return False
#
#    def do_set_heater(self, on, channel):
#        if on:
#            text = 'ON'
#        else:
#            text = 'OFF'
#
#        self._select_channel(channel)
#        self._visa.write('PSHTR %s' % text)