'''
##############################################

            Settings handler :O
            Also does I2C for TC
            and fuel mix.

##############################################
'''
import board, busio
from adafruit_mcp4728 import MCP4728 #DELETE

class Setting:
    def __init__(self,rule:tuple[str,int,int,int],default:int):
        self.rule: tuple[str,int,int,int] = rule
        self.value:int = default

class SettingGroup:
    def __init__(self, name: str, settings: list[Setting]):
        self.name: str = name
        self.settings: list[Setting] = settings

class Preset:
    def __init__(self,name:str,settings:list):
        self.name:str = name
        self.settings:list = settings
     

class SettingsHandler:
    def __init__(self):
        self.selected_setting_idx = 0
        self.selected_group_idx = 0
        self.in_group_menu = False # False = scrolling groups, True = scrolling within a group

        ''' This block can be removed once CAN is the only needed interface'''
        self.gear = -1

        self.i2c = busio.I2C(board.SCL, board.SDA) # Physical pins 5 and 3
        self.mcp4728 = None

        self.re_init_i2c_bus()
        ''''''

        # Presets consist of:
        # name: string
        # settings: list of values to set the setting
        # It is iterable by insertion order just like a list
        self.preset_mapping = ["FuelMix", "TC", "AeroMode", "AeroSens", "AeroBal", "AeroShift"]
        self.presets = [ # [FM, TC, AM, ASense, AB, #AShift FA]
            Preset("Default",  [0 ,11,0 ,0 ,0 ,0]),
            Preset("Dry Base", [0 ,8 ,1 ,0 ,0 ,0]),
            Preset("Dry Accel",[0 ,11,2 ,0 ,0 ,0]),
            Preset("Dry End",  [0 ,8 ,1 ,0 ,0 ,0]),
            Preset("Wet Base", [0 ,4 ,0 ,0 ,0 ,0]),
            Preset("Wet Accel",[0 ,4 ,2 ,0 ,0 ,0]),
            Preset("Wet End" , [0 ,4 ,1 ,-2,0 ,0]) # Maybe endurance does use active aero but with a super low sensitivity?
        ] 

        ################### NEW SETTINGS CODE #######################
        ''' There now exists multiple "setting groups" which can be added or removed. 
        These groups are not compatible with the old system, specifically in terms of presets
        and adjustments'''
        self.groups = [
            SettingGroup("Engine", [
                Setting(("FuelMix", 1, -10, 10), 0),
            ]),
            SettingGroup("TC", [
                Setting(("TC", -1, 1, 11), 11), # DELETE THIS
                Setting(("TC_Lat", -1, 1, 11), 11),
                Setting(("TC_Long", -1, 1, 11), 11),
                Setting(("TC_Cut", -1, 1, 11), 11),
                Setting(("TC_Comp", -1, 1, 11), 11),
            ]),
            SettingGroup("Aero", [
                Setting(("AeroMode", 1, 0, 3), 0),
                Setting(("AeroSens", 1, -2, 2), 0),
                Setting(("AeroBal", 1, -6, 6), 0),
                Setting(("AeroShift", 1, -5, 5), 0),
            ]),
            SettingGroup("System", [
                Setting(("Brightness", 10, 10, 150), 100),
                Setting(("Presets", 1, 0, 8), 0),
            ])
        ]

        # Dynamic name-based lookup table for settings. This allows the preset system to work
        self.settings_by_name: dict[str, Setting] = {}
        for group in self.groups:
            for setting in group.settings:
                self.settings_by_name[setting.rule[0]] = setting

    ''' DEPRECIATED, untested new version, won't be needed on TR27'''
    def re_init_i2c_bus(self):
        try:
            if not hasattr(self, 'i2c') or self.i2c is None:
                self.i2c = busio.I2C(board.SCL, board.SDA)
            self.mcp4728 = MCP4728(self.i2c)
            self.mcp4728.channel_d.value = 0
        except Exception as e:
            self.mcp4728 = None


    # --- Menu Navigation  ---
    ''' NEW CODE '''
    def scroll_menu(self, up: bool) -> str:
        """Scrolls either groups or settings depending on menu depth state."""
        step = 1 if up else -1
        
        if not self.in_group_menu:
            # Scroll through groups
            self.selected_group_idx = (self.selected_group_idx + step) % len(self.groups)
            return f"Group: {self.groups[self.selected_group_idx].name}"
        else:
            # Scroll through settings within the active group
            group = self.groups[self.selected_group_idx]
            self.selected_setting_idx = (self.selected_setting_idx + step) % len(group.settings)
            return f"Setting: {group.settings[self.selected_setting_idx].rule[0]}"

    def toggle_menu_depth(self) -> str:
        """Simulates clicking into a group or backing out of it."""
        if not self.in_group_menu:
            self.in_group_menu = True
            self.selected_setting_idx = 0
            active_setting = self.groups[self.selected_group_idx].settings[0].rule[0]
            return f"Entered {self.groups[self.selected_group_idx].name}. Selected: {active_setting}"
        else:
            self.in_group_menu = False
            return f"Exited to Groups. Selected: {self.groups[self.selected_group_idx].name}"

    def get_current_setting(self) -> Setting | None:
        """Helper to safely fetch the currently highlighted setting object."""
        if self.in_group_menu:
            return self.groups[self.selected_group_idx].settings[self.selected_setting_idx]
        return None
    
        
    ''' DEPRECIATED, untested new version, won't be needed on TR27'''
    def output_to_ECU(self):
        fuel_setting = self.settings_by_name["FuelMix"].value
        tc_setting = self.settings_by_name["TC"].value

        tc_target = (11 - tc_setting) * 6553

        if fuel_setting == 0:
            fuel_target = 0
        else:
            fuel_target = 3120 + (3120 * (10 - fuel_setting))

        if self.mcp4728 is None:
            self.re_init_i2c_bus()
        if self.mcp4728 is not None:
            try:
                self.mcp4728.channel_a.value = tc_target
                self.mcp4728.channel_b.value = fuel_target
            except Exception as e:
                print(f"DAC Error: {e}")

    ''' DEPRECIATED, untested new version, won't be needed on TR27'''
    def output_gear_to_ECU(self, gear, neutral, n_button=0):
        if neutral:
            gear_target = 1 * 9362
        elif not gear:
            gear_target = 0
        elif gear == 1 and n_button:
            gear_target = 9362 * 7
        elif gear == 1:
            gear_target = 0
        else:
            gear_target = gear * 9362

        self.gear = gear
        
        if self.mcp4728 is None:
            self.re_init_i2c_bus()
        if self.mcp4728 is not None:
            try:
                self.mcp4728.channel_d.value = gear_target
            except Exception as e:
                print(f"Gear DAC Error: {e}")
        
    ''' NEW CODE '''
    def commit_preset(self) -> tuple[str, dict] | None:
        current_setting = self.get_current_setting()
        if current_setting and current_setting.rule[0] == "Presets":
            chosen_preset_index = current_setting.value
            result: dict[str, int] = {}
            preset_values = self.presets[chosen_preset_index].settings
            
            # Map values explicitly via names instead of structural indices
            for name, val in zip(self.preset_mapping, preset_values):
                if name in self.settings_by_name:
                    self.settings_by_name[name].value = val
                    result[name] = val
                    
            return (self.presets[chosen_preset_index].name, result)
        return None

    def adjust_setting(self, up: bool) -> tuple[str, int] | None:
        setting = self.get_current_setting()
        if not setting:
            return None  # Cannot adjust values while looking at the top-level Group menu
            
        name, inc, mini, maxi = setting.rule
        curr = setting.value
        if not up:
            inc = -inc
        curr = curr + inc

        if name != "Presets":
            setting.value = max(min(curr, maxi), mini)
        else:
            setting.value = curr % len(self.presets)
            
        self.output_to_ECU() # DELETE
        return (name, setting.value)