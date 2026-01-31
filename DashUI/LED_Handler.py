'''
####################################################

                    LED DRIVER

####################################################
'''
import board
import neopixel
import time

'''BOARD SETUP NEEDS TO HAPPEN HERE'''

'''
                        LED index layout
        12  11  10  9  8  7  6  5  4  3 Tachometer
        13                            2 Top row
        14            Screen          1 Middle row
        15                            0

        Alert hierarchy:
        Top left: TC > Neutral dynamic > Neutral static > Oil       Top Right: TC > Neutral Dynamic > Low drag > Oil

                        Middle: TC > Neutral dynamic > Coolant BAD > Coolant > Battery > Fuel > Oil

                                        Bottom: TC > Neutral dynamic > Oil

        Priority lists (should all be mutually exclusive):
        0: Tach green/yellow/red, warn oil
        1: Tach blue, neutral static, warn fuel, alert low drag
        2: Warn battery
        3: Warn coolant
        4: Warn coolant bad
        5: TC
        6: Neutral Dynamic
'''

class LedBehavior:
    def __init__(self, color, freq_hz=0, priority=0, default_blink=True):
        self.color = color          # (r, g, b)
        self.freq = freq_hz         # How fast should this fluctuate?
        self.priority = priority    # Lower number = lower priority
        #self.enabled = False        # Is the behavior active and should be shown?
        self.last_toggle = 0.0        # Last time the frequency flipped this on/off
        self.on_state = True        # This keeps track of whether the LEDs are toggled on or off
        self.default_blink=default_blink

class LedController:
    class LedPresets:
        # For blinking use 3Hz
        # Tachometer
        TACH_GREEN = LedBehavior((0,50,0), 0, 0)
        TACH_YELLOW = LedBehavior((50,50,0), 0, 0)
        TACH_RED = LedBehavior((150,0,0), 0, 0)
        TACH_BLUE = LedBehavior((10,50,35), 6, 1) # All tachometer priorities are the same, but this one overrides all of them
        # Neutral
        ALERT_NEUTRAL_STATIC = LedBehavior((50,50,50), 0, 1)
        ALERT_NEUTRAL_DYNAMIC = LedBehavior((50,50,50), 3, 6, False) # All LEDs BLINK white
        # Oil warning
        WARN_OIL = LedBehavior((150, 0, 0), 0, 99) # ALL LEDs SOLID red
        # Middle row warnings
        WARN_COOLANT = LedBehavior((100,25,0), 0, 3)
        WARN_COOLANT_BAD = LedBehavior((100,25,0), 3, 4) # Version of coolant for if very hot. Highest priority of all non-oil warnings
        WARN_BATTERY = LedBehavior((50,50,0), 0, 2)
        WARN_FUEL = LedBehavior((50,50,0), 3, 1)
        # Other alerts
        ALERT_LOWDRAG = LedBehavior((0,50,0), 0, 1) 
        ALERT_TC = LedBehavior((50,0,50), 0, 5) # Most realtime of all the alerts, least likely to persist

    def __init__(self, num_leds): # Takes in the length of the LED array as an input
        self.pixels = neopixel.NeoPixel(board.D18, num_leds, auto_write=False) # Use GPIO 18. Hardware PWM 0. Physical pin 12.
        self.behaviors: dict[int,list[LedBehavior]] = {}           # dict of {led: {behaviors}}
        #self.timer = QTimer()
        #self.timer.timeout.connect(self.update)
        #self.timer.start(40)          # 25 Hz update rate
        self.last_update = time.monotonic()

    def add_behavior(self, leds:list, behavior:LedBehavior):
        #behavior.enabled = True
        #behavior.on_state = True      # ensure starts ON
        #behavior.last_toggle = time.monotonic()
        for led in leds:
            if led not in self.behaviors:
                self.behaviors[led] = []
            if behavior not in self.behaviors.get(led, []):
                self.behaviors[led].append(behavior)

    def clear_behavior(self, leds:list, behavior:LedBehavior):
        for led in leds:
            if led in self.behaviors and behavior in self.behaviors.get(led, []):
                behavior.on_state = behavior.default_blink
                behavior.last_toggle = time.monotonic()  
                self.behaviors[led].remove(behavior)

    def apply_brightness(self,color,brightness) -> tuple[int,int,int]:
        brightness = int((brightness/100)*255) # Convert brightness to a scaling value. The 255 is divided out below
        # This function just calculates the brightness and clamps to 255.
        r = brightness * color[0] // 255 # Integer division
        g = brightness * color[1] // 255
        b = brightness * color[2] // 255
        return (r,g,b)

    def update(self, brightness):
        now = time.monotonic()
        led_colors = [(0,0,0) for _ in range(len(self.pixels))]

        active = {}
        # find active behaviors by LED and choose highest priority
        for led in self.behaviors:
            highest_priority = -1
            #if not beh.enabled:
            #    continue
            for beh in self.behaviors.get(led, []):
                if beh.priority > highest_priority:
                    # handle blinking
                    if beh.freq > 0:
                        period = 1.0 / beh.freq
                        if now - beh.last_toggle >= period / 2:
                            beh.on_state = not beh.on_state
                            beh.last_toggle = now
                    else:
                        beh.on_state = True

                    # assign color if ON and highest priority
                    if beh.on_state:
                        highest_priority = beh.priority
                        active[led] = beh.color #(beh, beh.color)

        # fill LEDs
        for led, color in active.items():
            led_colors[led] = self.apply_brightness(color, brightness)

        self.pixels[:] = led_colors
        #print(f"Pixels: {led_colors}")
        self.pixels.show()