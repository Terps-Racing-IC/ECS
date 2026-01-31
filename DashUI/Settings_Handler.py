'''
##############################################

            Settings handler :O
            Also does I2C for TC
            and fuel mix.

##############################################
'''
import board, busio
#from adafruit_mcp4725 import MCP4725
from adafruit_mcp4728 import MCP4728

class Setting:
    def __init__(self,rule:tuple[str,int,int,int],default:int):
        self.rule: tuple[str,int,int,int] = rule
        self.value:int = default

class Preset:
    def __init__(self,name:str,settings:list):
        self.name:str = name
        self.settings:list = settings
     

class SettingsHandler:
    def __init__(self):
        self.selected = 0

        self.gear = 0

        self.i2c = busio.I2C(board.SCL, board.SDA) # Physical pins 5 and 3
        '''
        #For individual DACs
        self.dac_fm = MCP4725(self.i2c, address=0x62)
        self.dac_tc = MCP4725(self.i2c, address=0x63)
        '''
        # For combined DAC:
        self.mcp4728 =  MCP4728(self.i2c) # If the MCP4728 is actually an MCP4728A4, then include additional parameter 0x64
        # Presets consist of:
        # name: string
        # settings: list of values to set the setting
        # It is iterable by insertion order just like a list
        self.presets = [ # [FM, TC, AM, ASense, AB, #AShift FA]
            Preset("Default", [0,11,0,0,0,0,6]),
            Preset("Accl Dry",[0,11,2,0,0,0,6]),
            Preset("Accl Wet",[0,11,2,0,0,0,6]),
            Preset("Skid Dry",[0,11,0,0,0,0,6]),
            Preset("Skid Wet",[0,11,0,0,0,0,6]),
            Preset("Ax Dry",  [0,11,1,0,0,0,6]),
            Preset("Ax Wet",  [0,11,0,0,0,0,6]),
            Preset("End Dry" ,[0,11,1,0,0,0,6]),
            Preset("End Wet" ,[0,11,0,0,0,0,6]) # Maybe endurance does use active aero but with a super low sensitivity?
        ]
        # Setting consists of:  
        # rule: ("Setting Name (CAN Name)", increment, min, max) 
        # value: current value <- this is the default value when the setting is created 
        # This keeps track of the current value
        self.settings:list[Setting] = [
            Setting(("FuelMix",1,-10,10),0),
            Setting(("TC",-1,1,11),11), # 11 = off
            Setting(("AeroMode",1,0,2),0),
            Setting(("AeroSens",1,-2,2),0),
            Setting(("AeroBal",1,-5,5),0),
            Setting(("AeroBalShift",1,-5,5),0)
            Setting(("FArb",1,1,10),6),
            # SETTINGS WHICH ARE NOT CHANGED BY PRESET: PRESET MUST BE THE LAST ENTRY
            Setting(("Brightness",10,10,150),100), # this shouldn't be changed when the preset is selected either
            Setting(("Presets",1,0,8),0), # 9 total presets. Default and then 2 per event
        ]

    def update_selected(self,setting) -> str|None:
        self.selected = setting
        if self.selected < len(self.settings):
            return self.settings[self.selected].rule[0] 
        else: 
            return None
        
    def output_to_ECU(self):
        #return
        fuel_setting = self.settings[0].value
        tc_setting = self.settings[1].value # This way, setting 10 = 0, setting -10 = 20

        #FOR INDIVIDUAL tc_target = (11 - tc_setting) * 409 # setting 10 = 409, setting 1 = 4090. OFF = 0
        tc_target = (11 - tc_setting) * 6553
        # Map the tc setting between 0 and VDD. Position 11 is off, so make that 0V.
        # Voltage increases and TC target slip decreases.

        # Fuel setting is mapped so that 0 is neutral compensation adjustment. A small voltage offset is provided
        if fuel_setting == 0:
            fuel_target = 0
        else: #fuel_setting > 0: # LEAN
            #FOR INDIVIDUAL fuel_target = 195 + (195 * (10-fuel_setting))
            fuel_target = 3120 + (3120 * (10-fuel_setting)) 
            '''
            195 + (195 * (10 - 10))     = 195  for 10% RICH         3120 + (3120 * (10 - 10))       = 3120 for 10%  RICH
            195 + (195 * (10 - 1))      = 1950 for 1%  RICH         3120 + (3120 * (10 - 1))        = 31200 for 1%  RICH
            195 + (195 * (10 - 0))      = 2145 for 0%       UNUSED  3120 + (3120 * (10 - 0))        = 34320 for 0%      UNUSED
            195 + (195 * (10 - (-1)))   = 2340 for 1%  LEAN         3120 + (3120 * (10 - (-1)))     = 37440 for 1%  LEAN
            195 + (195 * (10 - (-10)))  = 4095 for 10% LEAN         3120 + (3120 * (10 - (-10)))    = 65520 for 10% LEAN
            '''
        '''
        #For individual DACs
        self.dac_tc.raw_value = tc_target 
        self.dac_fm.raw_value = fuel_target
        '''
        #For combined DAC:
        self.mcp4728.channel_a.value = tc_target
        self.mcp4728.channel_b.value = fuel_target

    def output_gear_to_ECU(self, gear, neutral, n_button):
        # Whenever the calculated gear changes or the neutral button is pressed, output this in voltage form to the ECU.
        # If the car is in first and the neutral button is held, use a special gear voltage to the ECU that allows it to shift consistently to neutral.
        # Should increment by 9362 per position for 8 total positions with the first being 0.
        '''
        PE3 gear position possibilities
        1 = 1st gear        4 = 4th gear
        N/0 = Neutral       5 = 5th gear
        2 = 2nd gear        6 = 6th gear
        3 = 3rd gear        7 = 1st to neutral
        '''
        if neutral:
            gear_target = 1*9362
        elif not gear:
            gear_target = 0 # If the gear cannot be calculated (gear = 0) assume first gear for cut time.
        elif gear == 1 and n_button:
            gear_target = 9362*7
        elif gear == 1:
            gear_target = 0
        else:
            gear_target = gear * 9362
        self.mcp4728.channel_c.value = gear_target
        
    def commit_preset(self) -> tuple[str,dict]|None:
        if self.selected == len(self.settings) - 1:
            chosen_preset_index = self.settings[len(self.settings)-1].value # Always corresponds to "Presets"
            result:dict[str,int] = {}
            for index in range(len(self.settings)-2): # -2 here since we don't want to overwrite the selected preset or brightness
                # setting v         list of presets v  last setting's value dictates preset v   setting to update v
                self.settings[index].value = self.presets[chosen_preset_index].settings[index]
                result.update({self.settings[index].rule[0]: self.settings[index].value})
            return (self.presets[chosen_preset_index].name, result)
        return None

    def adjust_setting(self, up: bool) -> tuple[str,int]|None:
        if self.selected < len(self.settings):
            setting = self.settings[self.selected]
            name, inc, mini, maxi = setting.rule
            curr = setting.value
            if not up: # increment is negative if we're not going up.
                inc = -inc
            curr = curr + inc

            if name != "Presets":
                setting.value = max(min(curr, maxi), mini)
            # If we are adjusting presets, cycle to the next one:
            else: # name == "Presets"
                setting.value = curr % len(self.presets) # This allows presets to cycle back on themselves
            self.output_to_ECU() # After performing the value update, make sure to re-address the DAC
            return (name, setting.value)
        return None