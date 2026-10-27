'''
########################################################

                    CAN INTEGRATION (Motec Version)

########################################################
'''
# TODO: TC Stuff from motec since it's not a standard message

from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
import can
import statistics
can.rc['interface'] = 'socketcan'
can.rc['channel'] = 'can0'
can.rc['bitrate'] = 1000000
from can.interface import Bus

class CanWrapper:
    def __init__(self, values: dict):
        self.values = values

    def get(self, key, default=0):
        return self.values.get(key,default)

# CAN storage class that contains a dictionary of various CAN values. This way values are stored in a common location so that
# all dashboard pages can access them when needed.
class CanCommon(QObject):
    snapshot_ready = pyqtSignal(CanWrapper)
    update_values_request = pyqtSignal(dict)

    def __init__(self): 
        super().__init__() # Has to initialize its parent class. Otherwise QThread has no clue wtf to do with this thing
        # Create a dict of values to store the current inputs
        self.values = {"TC": 11, "Brightness": 100}#, "FArb": 6}
        self.bus = None
        self.timer = None
        self.update_values_request.connect(self.update)
        self.EWMA = 0.0
        self.final_drive = 36/11
    
    def average(self, *args):
            return (sum(args))/len(args)

# Adds a value to the stored CAN values. Values are in the format of a python dict, for example {"a": 1} stores that key a = 1
    def update(self, data: dict):
        self.values.update(data)

    # Start this worker!
    def start(self):
        self.timer = QTimer()
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.poll)
        self.timer.timeout.connect(self.transmit_info)
        self.timer.start()
        self.bus = Bus()

    def stop(self):
        if self.timer is not None:
            self.timer.stop()

    def transmit_info(self):
        if self.bus is not None:
            msg_240 = can.Message(
                arbitration_id=0x240,     # CAN ID
                data=[
                    self.values.get("FuelMix", 0) & 0xFF,
                    self.values.get("TC", 11) & 0xFF,
                    self.values.get("AeroMode", 0) & 0xFF,
                    self.values.get("AeroSens", 0) & 0xFF,
                    self.values.get("AeroBal", 0) & 0xFF,
                    self.values.get("AeroShift", 0) & 0xFF
                    #self.values.get("FArb", 6) & 0xFF
                ],
                is_extended_id=False
            )
            msg_241 = can.Message(
                arbitration_id=0x241,     # CAN ID
                data=[
                    self.values.get("Gear", 0) & 0xFF,
                    self.values.get("BrakeBal", 0) & 0xFF
                ],
                is_extended_id=False
            )
            msg_242 = can.Message(
                arbitration_id=0x242,
                data=[
                    self.values.get("RWS_Mode", 0) & 0xFF,
                    self.values.get("RWS_Fixed_Gain", 0) & 0xFF
                ],
                is_extended_id=False
            )
            try:
                self.bus.send(msg_240)
                self.bus.send(msg_241)
                self.bus.send(msg_242)
                self.values.update({"BusOut":1})
            except can.CanError:
                self.values.update({"BusOut":0})
    
    def poll(self):
        #print("polling CAN")
        while self.bus is not None:
            message = self.bus.recv(timeout=0)
            if not message:
                #print("no messages")
                break
            match message.arbitration_id: 
                # Match statement. Here we will list out all of the CAN Ids that we are using and parse the corresponding data.
                # See the CAN Protocol in the user manual for details
                case 0x640:
                    parsed = {
                        "RPM": int.from_bytes(message.data[0:2], "big"), # Notice! This is the first two bytes of data! The second value 
                                                                          # is NOT included in the index. This is indices 0 and 1
                        #MAP
                        #IAT
                        "TPS": int.from_bytes(message.data[6:8], "big")/10,
                    }
                    self.update(parsed)
                case 0x641:
                    parsed = {
                        # Fuel Lambda Target
                        "Fuel": int.from_bytes(message.data[4:6], "big")*0.145038/10, # Fuel PSI
                        # Engine Efficiency
                    }
                    self.update(parsed)
                case 0x644:
                    parsed = {
                        # A bunch of cut/comp stuff for fuel/ignition
                        "Oil": int.from_bytes(message.data[6:8], "big")*0.145038/10,
                    }
                    self.update(parsed)
                case 0x648:
                    parsed = {
                        "WSFL": (int.from_bytes(message.data[0:2], "big")/10)*0.621371, # KPH to MPH
                        "WSFR": (int.from_bytes(message.data[2:4], "big")/10)*0.621371,
                        "WSRL": (int.from_bytes(message.data[4:6], "big")/10)*0.621371,
                        "WSRR": (int.from_bytes(message.data[6:8], "big")/10)*0.621371,
                    }
                    self.update(parsed)
                case 0x649: # TC Comp/Cut Status from ECU
                    parsed = {
                        "Coolant": int((int.from_bytes(message.data[0:1], "big") -40)*1.8 + 32), # C to F
                        "Battery": int.from_bytes(message.data[5:6], "big")/10
                    }
                    self.update(parsed)
                case 0x64C:
                    warnings = int.from_bytes(message.data[5:6], "big")
                    parsed = {
                        "Warn_SRC" : int.from_bytes(message.data[4:5], "big"), # This tells us exactly what is wrong
                        "Fuel_warn" : warnings&0b00000001,
                        # Crank Pressure
                        # Blank
                        "Oil_warn" : warnings&0b00001000,
                        # Oil Temp
                        "Engine_Speed_warn" : warnings&0b00100000,
                        # Coolant Pressure
                        "Coolant_warn" : warnings&0b10000000,
                        "Knock_warn" : int.from_bytes(message.data[6:7], "big")&0b10000000,
                    }
                    self.update(parsed)
                
                case 0x64D:
                    parsed = {
                        "Fuel_State": int.from_bytes(message.data[3:4], "big")&0b00001111,
                        "Gear": (lambda x: x - 16 if x & 8 else x)(message.data[6] & 0x0F),
                        "Eng_Speed_Lim_State": int.from_bytes(message.data[7:8], "big")
                    }
                    self.update(parsed)
                case 0x64E:
                    parsed = {
                        "Neutral" : int.from_bytes(message.data[3:4], "big")&0b00000001
                        # Also contains pit and launch switch states
                    }
                    self.update(parsed)
                # 0x650: Driver switch info
                case 0x651:
                    parsed = {
                        "Lambda" : int.from_bytes(message.data[0:1], "big")/100
                    }
                case 0x655:
                    parsed = {
                        "FBrakePSI" : int.from_bytes(message.data[0:2], "big", signed=True)*0.145038,
                        "RBrakePSI" : int.from_bytes(message.data[2:4], "big", signed=True)*0.145038,
                    }
                    self.update(parsed)
                    # Brake bias calculation
                    fbp = float(self.values.get("FBrakePSI", 0.0) or 0.0)*2.025
                    rbp = float(self.values.get("RBrakePSI", 0.0) or 0.0)*0.735
                    denom = (fbp+rbp)
                    if fbp > 50 and rbp > 50 and denom != 0:
                        bbal_calc = fbp*100/denom 
                        self.EWMA = self.EWMA*(7/8) + bbal_calc*10*(1/8)
                    #else:
                    #    bbal_calc = self.values.get("BrakeBal", 0)/10 or 0.0 # Use previous brake balance if one exists
                    # Do not update the moving average if we're not actively braking
                    self.update({"BrakeBal": int(self.EWMA)})
                case 0x656:
                    parsed = {
                        "SteerAngle" : int.from_bytes(message.data[0:2], "big", signed=True)/10
                    }
                    self.update(parsed)
                case 0x657:
                    parsed = {
                        "Engine_Speed" : int.from_bytes(message.data[6:8], "big")
                    }
                    self.update(parsed)
                case 0x658:
                    parsed = {
                        "IMUY" : int.from_bytes(message.data[0:2], "big", signed=True)/1000,
                        "IMUX" : int.from_bytes(message.data[2:4], "big", signed=True)/1000,
                        "IMUZ" : int.from_bytes(message.data[4:6], "big", signed=True)/1000,
                    }
                    self.update(parsed)
                case 0x659:
                    parsed = {
                        "Speed" : int.from_bytes(message.data[4:6], "big", signed=True)/10 # KPH, 
                        # fastest front wheel speed unless locked, in which case GPS speed is used
                    }
                    self.update(parsed)
                # 0x65B: Lap time info
                # 0x65C: Extra driver rotary switch info
                case 0x6B1:
                    parsed = {
                        "Trans_Slip_warn" : int.from_bytes(message.data[6:7], "big")&0b10000000 # Triggered if RPM too much relatiev to output
                    }
                    self.update(parsed)
                case 0x940: # Pit2Car Line 1
                    parsed = {
                        "P2C_Line1" : int.from_bytes(message.data, "little")
                    }
                    self.update(parsed)
                case 0x941: # Pit2Car Line 2
                    parsed = {
                        "P2C_Line2" : int.from_bytes(message.data, "little")
                    }
                    self.update(parsed)
                case 0x942: # Pit2Car Metadata
                    parsed = {
                        "P2C_Message_No": int.from_bytes(message.data[0:2], "little"),
                        "P2C_Color": int.from_bytes(message.data[2:3], "little"),
                        "P2C_Duration": int.from_bytes(message.data[3:5], "little") # in 0.1s intervals
                    }
                    self.update(parsed)
                case _: continue            # Default case, do nothing


        self.snapshot_ready.emit(CanWrapper(self.values.copy()))
            
    # Note:
    # int.from_bytes is only needed in the case of a string of bytes
    # representing an integer, not for a single byte. "big" indicates that the bytes are expected to be in Big Endian format, i.e the hex
    # number 0x12345678 is represented as 12 34 56 78 in big endian format (so index 0 has 12, index 1 has 34, etc...) whereas they
    # are ordered 78 56 34 12 in little endian format (which is commonly used in modern computer memory addressing).