'''
########################################################

                    CAN INTEGRATION 

########################################################
'''

from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
import can
import statistics
can.rc['interface'] = 'socketcan'
can.rc['channel'] = 'can0'
can.rc['bitrate'] = 500000
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
            try:
                self.bus.send(msg_240)
                self.bus.send(msg_241)
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
                case 0x238: # Critical Info 
                    parsed = {
                        "RPM": int.from_bytes(message.data[0:2], "little"), # Notice! This is the first two bytes of data! The second value 
                                                                          # is NOT included in the index. This is indices 0 and 1
                        "Coolant": int.from_bytes(message.data[2:4], "little", signed=True), # Technically coolant could be subzero
                        "Oil": int.from_bytes(message.data[4:6], "little")/10, # Certain Values are multiplied by 10 before being sent. Typically if there is one place after the decimal
                        "Battery": int.from_bytes(message.data[6:8], "little")/10,
                    }
                    self.update(parsed)
                case 0x239: # Aux Engine Info
                    parsed = {
                        "Engine_Speed": int.from_bytes(message.data[0:2], "little"),
                        "TPS": int.from_bytes(message.data[2:4], "little")/10,
                        "Lambda": message.data[4]/100, # Lambda is multiplied by 100 before being sent as it has 2 places after the decimal.
                        "Fuel": message.data[5], # Fuel PSI
                        "Neutral": message.data[6]
                    }
                    self.update(parsed)
                    # Gear calculation
                    output_speed = self.values.get("Engine_Speed", 0)       
                    rpm = self.values.get("RPM", 0)
                    neutral = self.values.get("Neutral", 0)
                    gear = self.values.get("Gear", 0)
                    speed = self.values.get("Speed", 0)
                    tps = self.values.get("TPS", 0)
                    if rpm > 500 and output_speed > 1 and speed > 1 and neutral != 1:
                        if tps > 20:
                            gear_ratio = rpm/(speed*(self.final_drive)/(60*3.1415*0.00026))
                        else:
                            gear_ratio = rpm/output_speed
                        self.EWMA = self.EWMA*(7/8) + gear_ratio*(1/8) # for K = 8 EWMA filtering. Approx 2-300ms response time at full engine load
                        #ratios = [5.805, 4.222, 3.519, 3.048, 2.753, 2.550]
                        #tolerance = [(0.03,0.03),(0.03,0.03),(0.02, 0.02),(0.02,0.02),(0.01,0.01),(0.01,0.01)] #(tolerance_down, tolerance_up)
                        buckets = [(6,5), (4.5,4), (3.9,3.3), (3.2,2.9), (2.85,2.65), (2.6,2.4)] # Bucket tolerances, same layout as ^
                        if gear_ratio < 6: # Reject unreasonable values. This likely indicates clutch pulled
                            for i in range(0,6):
                                if buckets[i][1] < self.EWMA < buckets[i][0]: # EWMA bucket checks
                                #if 1 - tolerance[i][1] < gear_ratio/ratios[i] < 1 + tolerance[i][0]:
                                    gear = i + 1
                                    break
                    else:
                        gear = 0
                    self.update({"Gear": gear})
                    #self.update({"Gear": gear})
                case 0x23A: # Wheel and Brake Info
                    parsed = {
                        "FBrakePSI": int.from_bytes(message.data[0:2], "little")/10,
                        "RBrakePSI": int.from_bytes(message.data[2:4], "little")/10,
                        "WSFR": message.data[4],
                        "WSFL": message.data[5],
                        "WSRR": message.data[6],
                        "WSRL": message.data[7],
                        "Speed": self.average(message.data[6],message.data[7])
                    }
                    self.update(parsed)
                    
                    # Brake bias calculation
                    fbp = float(self.values.get("FBrakePSI", 0.0) or 0.0)*2.025
                    rbp = float(self.values.get("RBrakePSI", 0.0) or 0.0)*0.735
                    denom = (fbp+rbp)
                    if fbp > 50 and rbp > 50 and denom != 0:
                        bbal_calc = fbp*100/denom 
                    else:
                        bbal_calc = self.values.get("BrakeBal", 0)/10 or 0.0 # Use previous brake balance if one exists
                    self.update({"BrakeBal": int(bbal_calc*10)})
                case 0x23B: # Misc info 2
                    parsed = {
                        "IMUX": int.from_bytes(message.data[0:2], "little", signed=True)/100,
                        "IMUY": int.from_bytes(message.data[2:4], "little", signed=True)/100,
                        "IMUZ": int.from_bytes(message.data[4:6], "little", signed=True)/100,
                        "Odometer": int.from_bytes(message.data[6:8], "little", signed=True)/10,
                    }
                    self.update(parsed)
                case 0x23C: # TC Comp/Cut Status from ECU
                    parsed = {
                        "TC_Comp": int.from_bytes(message.data[0:2], "little")/10,
                        "TC_Cut": int.from_bytes(message.data[2:4], "little")/10
                    }
                    self.update(parsed)
                case 0x2B0: # Steering Angle
                    parsed = {
                        "SteerAngle": int.from_bytes(message.data[0:2], "little", signed=True)/10
                    }
                    self.update(parsed)
                case 0x2: # FSM State
                    parsed = {
                        "DRS": message.data[0] # FSM State, 0 = high drag, 2 = low drag
                    }
                    self.update(parsed)
                case _: continue            # Default case, do nothing


        self.snapshot_ready.emit(CanWrapper(self.values.copy()))
            
    # Note:
    # int.from_bytes is only needed in the case of a string of bytes
    # representing an integer, not for a single byte. "big" indicates that the bytes are expected to be in Big Endian format, i.e the hex
    # number 0x12345678 is represented as 12 34 56 78 in big endian format (so index 0 has 12, index 1 has 34, etc...) whereas they
    # are ordered 78 56 34 12 in little endian format (which is commonly used in modern computer memory addressing).