import board
import busio
from adafruit_mcp4728 import MCP4728

# 1. Slow down the bus to 10kHz to overcome any perfboard capacitance
i2c = busio.I2C(board.SCL, board.SDA, frequency=10000)

try:
    # 2. Be very explicit with the address
    # 0x60 is standard, but try 0x64 if you suspect the A4 variant
    dac = MCP4728(i2c, address=0x60) 
    
    # 3. Use 16-bit mid-scale (exactly 32768) to see if you get ~2.5V
    # If this works, your math/scaling was the issue.
    print("Setting all channels to 0V...")
    dac.channel_a.value = 0
    dac.channel_b.value = 0
    dac.channel_c.value = 0
    dac.channel_d.value = 0
    print("Success!")
    
    # 4. Save this to EEPROM so they don't default to 5V on next boot
    print("Setting EEPROMs...")
    dac.save_settings()
    print("Success! Power cycle DAC to test!")
    
except Exception as e:
    print(f"Hardware unreachable: {e}")