# -*- coding: utf-8 -*-
from qcodes import IPInstrument
from qcodes.utils.validators import Enum, Ints

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
    """

    def __init__(
            self,
            name: str,
            address: None,
            port: None,
            terminator: str = '\r\n',
            timeout: float = 1,
            pid = None,
            **kwargs):
        super().__init__(name, address=address, port=port,
                         terminator=terminator, timeout=timeout, **kwargs)
        self.add_parameter(name='status',
                           label='Status',
                           get_cmd=self.LEMON_status)
        for i in [1, 2]:
            self.add_parameter(f'nv{i}_mode',
                               label=f'Needle valve {i} mode',
                               get_cmd=f'NV{i} MODE?',
                               get_parser=self.get_parser,
                               #get_cmd=self.read_NV1mode,
                               set_cmd=f'NV{i} MODE={{}}',
                               val_mapping={'auto':  'AUTO', 'manual': 'MANUAL'})
            self.add_parameter(f'nv{i}_PID',
                               label=f'Needle valve {i} P',
                               get_cmd=f'NV{i} PID?',
                               get_parser=self.get_PID_parser,
                               #get_cmd=self.read_NV1mode,
                               set_cmd=f'NV{i} PID={{}}',
                               #val_mapping={'auto':  'AUTO', 'manual': 'MANUAL'})

        self.LEMON_connect()
        self.connect_message()
        
    def get_parser(self, val):
        return val.strip('\r\n').split('=')[1]

    def get_PID_parser(self, val):
        return val.strip('\r\n').split('=')[1].split(',')

    def ask_custom(self, val):
        return self.ask(val).strip('\r\n')

    
    # LEMON commands ---------------------------------------------------------------------------   
    def LEMON_connect(self):
        self.ask_custom('CONNECT LEMON')
        
    def LEMON_disconnect(self):
        self.ask_custom('DISCONNECT LEMON')

    def LEMON_status(self):
        return self.ask_custom('LEMON CONNECTED?')

    # Needle valve commands --------------------------------------------------------------------
    # Needle valve mode, can be AUTO or MANUAL    

    def read_NV1mode(self):
        return self.ask_custom('NV1 MODE?').split('=')[1]  
  
    def read_NV2mode(self):
        return self.ask_custom('NV2 MODE?').split('=')[1]  
    
    # Needle valve manual output set value as percentage
    def read_NV1manout(self):
        return self.ask_custom('NV1 MAN OUT?').split('=')[1] 
    
    def read_NV2manout(self):
        return self.ask_custom('NV2 MAN OUT?').split('=')[1]    


#--------------------------------
#--------------------------------
#--------------------------------    
    # Needle valve setpoint in mbar
    def read_NV1setp(self):
        self.s.sendall(('NV1 SETPOINT?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)    
    
    def read_NV2setp(self):
        self.s.sendall(('NV2 SETPOINT?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)    
        
    # Needle valve PID settings as a list [P, I, D]
    def read_NV1PID(self):
        self.s.sendall(('NV1 PID?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        resp = resp.split(',')
        for i in range(3):
            resp[i] = float(resp[i])
        return resp     
    
    def read_NV2PID(self):
        self.s.sendall(('NV1 PID?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        resp = resp.split(',')
        for i in range(3):
            resp[i] = float(resp[i])
        return resp 

    # Needle valve setpoint in mbar
    def read_NV1outp(self):
        self.s.sendall(('NV OUTPUT 1?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)    
    
    def read_NV2outp(self):
        self.s.sendall(('NV OUTPUT 2?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)      
    
    # Heaters commands --------------------------------------------------------------------------
    # Heater mode, can be AUTO or MANUAL    
    def read_H1mode(self):
        self.s.sendall(('HEATER1 MODE?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp    
  
    def read_H2mode(self):
        self.s.sendall(('HEATER2 MODE?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp     
    
    # Heater channel, returns the chosen control channel   
    def read_H1chan(self):
        self.s.sendall(('HEATER1 CHAN?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp    
  
    def read_H2chan(self):
        self.s.sendall(('HEATER2 CHAN?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp     
    
    # Heater channel manual output, returns output as percentage  
    def read_H1manout(self):
        self.s.sendall(('HEATER1 MAN OUT?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)
  
    def read_H2manout(self):
        self.s.sendall(('HEATER2 MAN OUT?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)      
    
    # Heater channel setpoint, returns value in Kelvin
    def read_H1setp(self):
        self.s.sendall(('HEATER1 SETPOINT?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)
  
    def read_H2setp(self):
        self.s.sendall(('HEATER2 SETPOINT?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)   
    
    # Write heater setpoints
    def write_H2setp(self, val):
        self.s.sendall(('HEATER2 SETPOINT=' + str(val) + '\r\n').encode())
        resp = self.s.recv(1024).decode()
        self.s.sendall(('HEATER2 SET VALUES\r\n').encode())
        resp = self.s.recv(1024).decode()
    
    # Heater channel ramp rate, returns value in Kelvin/minute
    def read_H1rate(self):
        self.s.sendall(('HEATER1 RAMP?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)
  
    def read_H2rate(self):
        self.s.sendall(('HEATER2 RAMP?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)     
    
    # Heater PID settings as a list [P, I, D]
    def read_H1PID(self):
        self.s.sendall(('HEATER1 PID?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        resp = resp.split(',')
        for i in range(3):
            resp[i] = float(resp[i])
        return resp     
    
    def read_H2PID(self):
        self.s.sendall(('HEATER2 PID?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        resp = resp.split(',')
        for i in range(3):
            resp[i] = float(resp[i])
        return resp      
    
    # Heater channel range, returns OFF, LOW, MED, HIGH
    def read_H1range(self):
        self.s.sendall(('HEATER1 RANGE?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp
  
    def read_H2range(self):
        self.s.sendall(('HEATER2 RANGE?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp     
    
    # Heater channel ramp enabled, returns OFF, ON
    def read_H1ramp(self):
        self.s.sendall(('HEATER1 SETPOINT RAMP?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp
  
    def read_H2ramp(self):
        self.s.sendall(('HEATER2 SETPOINT RAMP?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp     
    
    # Gas box commands --------------------------------------------------------------------------
    # Valve status, can be CLOSED, OPEN    
    def read_SV1(self):
        self.s.sendall(('GB SV1?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp    

    def read_SV2(self):
        self.s.sendall(('GB SV2?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   

    def read_SV3(self):
        self.s.sendall(('GB SV3?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   

    def read_SV4(self):
        self.s.sendall(('GB SV4?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   

    def read_pump(self):
        self.s.sendall(('GB PUMP?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   

    # Dump pressure in mbar
    def read_dump(self):
        self.s.sendall(('DUMP PRESSURE?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)       

    # Sample space pressure in mbar
    def read_samp(self):
        self.s.sendall(('SAMPLE SPACE PRESSURE?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)  
    
    # Circulation pressure in mbar
    def read_circ(self):
        self.s.sendall(('CIRCULATION PRESSURE?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)  
    
    # Temperature commands --------------------------------------------------------------------------
    # Read temperature channels, value in Kelvin   
    def read_tempA(self):
        self.s.sendall(('TEMPERATURE A?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp    
    
    def read_tempB(self):
        self.s.sendall(('TEMPERATURE B?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   
    
    def read_tempC(self):
        self.s.sendall(('TEMPERATURE C?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   
    
    def read_tempD1(self):
        self.s.sendall(('TEMPERATURE D1?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   
    
    def read_tempD2(self):
        self.s.sendall(('TEMPERATURE D2?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   
    
    def read_tempD3(self):
        self.s.sendall(('TEMPERATURE D3?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   
    
    def read_tempD4(self):
        self.s.sendall(('TEMPERATURE D4?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   
    
    def read_tempD5(self):
        self.s.sendall(('TEMPERATURE D5?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp   
    
    # Magnet commands --------------------------------------------------------------------------
    # Magnet lower sweep current limit, value in Ampere  
    def read_maglow(self):
        self.s.sendall(('MAGNET LOWER SWEEP?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)     

    # Magnet upper sweep current limit, value in Ampere   
    def read_magupp(self):
        self.s.sendall(('MAGNET LOWER SWEEP?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)     

    # Magnet voltage limit, value in Volt 
    def read_magvolt(self):
        self.s.sendall(('MAGNET VOLTAGE?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)    
    
    # Magnet current ranges, value in Ampere 
    def read_magrange0(self):
        self.s.sendall(('MAGNET RANGE 0?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)     

    def read_magrange1(self):
        self.s.sendall(('MAGNET RANGE 1?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp) 

    def read_magrange2(self):
        self.s.sendall(('MAGNET RANGE 2?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp) 

    # Magnet current range rates, value in Ampere/second 
    def read_magrate0(self):
        self.s.sendall(('MAGNET RATE 0?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)     

    def read_magrate1(self):
        self.s.sendall(('MAGNET RATE 1?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp) 

    def read_magrate2(self):
        self.s.sendall(('MAGNET RATE 2?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp)

    # Magnet sweep mode 
    def read_magmode(self):
        self.s.sendall(('MAGNET SWEEP?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp

    # Magnet output field, value in Tesla
    def read_magfield(self):
        self.s.sendall(('MAGNET FIELD?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp) 

    # Magnet power supply output current, value in Ampere
    def read_magoutpcurr(self):
        self.s.sendall(('MAGNET OUTPUT CURRENT?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp) 

    # Magnet lead current, value in Ampere
    def read_magleadcurr(self):
        self.s.sendall(('MAGNET CURRENT?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return float(resp) 

    # Magnet quench status, can be QUENCH, NO QUENCH
    def read_magquench(self):
        self.s.sendall(('MAGNET QUENCH?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp 

    # Magnet persistent mode heater, can be ON, OFF
    def read_magheater(self):
        self.s.sendall(('MAGNET HEATER?\r\n').encode())
        resp = self.s.recv(1024).decode().split('=')[1].strip('\r\n')
        return resp 
