#----------------------------------------------------------------------
# ssd1325.py
# ported from Guy Carpenter's SSD1306 library: https://github.com/guyc/py-gaugette
#
# This library is for the Newhaven 128x64 SPI monochrome OLED NHD-2.7-12864UCY3, 
# though it should work with any SSD1325 controller
#   http://www.newhavendisplay.com/nhd2712864ucy3-p-3621.html
#
# The code is mostly a translation of Newhaven's reference notes for a 128x64:
#   https://www.newhavendisplay.com/app_notes/OLED_2_7_12864.txt
#
# The values are referenced from Newhaven's spec sheet, and have been tweaked
# for stability: 
#   http://www.newhavendisplay.com/specs/NHD-2.7-12864UCY3.pdf
#
# The datasheet for the SSD1325 is available at
#   http://www.newhavendisplay.com/app_notes/SSD1325.pdf
#
# WiringPi pinout reference
#   https://projects.drogon.net/raspberry-pi/wiringpi/pins/
#
# wiringPi has been replaced with wiringPi2. Pins are the same, but you need the new library:
#   https://github.com/Gadgetoid/WiringPi2-Python
#
#
# Notes from Guy Carpenter from SSD1306 library:
#
# Some important things to know about this device and SPI:
#
# - The SPI interface has no MISO connection.  It is write-only.
#
# - The spidev xfer and xfer2 calls overwrite the output buffer
#   with the bytes read back in during the SPI transfer.
#   Use writebytes instead of xfer to avoid having your buffer overwritten.
#
# - The D/C (Data/Command) line is used to distinguish data writes
#   and command writes - HIGH for data, LOW for commands.  To be clear,
#   the attribute bytes following a command opcode are NOT considered data,
#   data in this case refers only to the display memory buffer.
#   keep D/C LOW for the command byte including any following argument bytes.
#   Pull D/C HIGH only when writting to the display memory buffer.
#   
# - The pin connections between the Raspberry Pi and OLED module are:
#
#      RPi     SSD1325
#      CE0   -> CS
#      GPIO2 -> RST   (to use a different GPIO set reset_pin to wiringPi pin no)
#      GPIO1 -> D/C   (to use a different GPIO set dc_pin to wiringPi pin no)
#      SCLK  -> CLK
#      MOSI  -> DATA
#      3.3V  -> VIN
#            -> 3.3Vo
#      GND   -> GND
#----------------------------------------------------------------------

import spidev
import wiringpi2
import sys

class SSD1325:

    # Class constants are externally accessible as gaugette.ssd1325.SSD1325.CONST
    # or my_instance.CONST

    # TODO - insert underscores to rationalize constant names

    EXTERNAL_VCC   = 0x1
    SWITCH_CAP_VCC = 0x2
    SET_LOW_COLUMN        = 0x00
    SET_HIGH_COLUMN       = 0x10
    SET_MEMORY_MODE       = 0x20
    SET_COL_ADDRESS       = 0x15
    SET_ROW_ADDRESS       = 0x75
    RIGHT_HORIZ_SCROLL    = 0x26
    LEFT_HORIZ_SCROLL     = 0x27
    VERT_AND_RIGHT_HORIZ_SCROLL = 0x29
    VERT_AND_LEFT_HORIZ_SCROLL = 0x2A
    DEACTIVATE_SCROLL     = 0x2E
    ACTIVATE_SCROLL       = 0x2F
    SET_START_LINE        = 0xA1
    SET_CONTRAST          = 0x81
    CHARGE_PUMP           = 0x8D
    SEG_REMAP             = 0xA0
    SET_VERT_SCROLL_AREA  = 0xA3
    DISPLAY_ALL_ON_RESUME = 0xA4
    DISPLAY_ALL_ON        = 0xA5
    NORMAL_DISPLAY        = 0xA4
    INVERT_DISPLAY        = 0xA7
    DISPLAY_OFF           = 0xA6
    DISPLAY_ON            = 0xAF
    COM_SCAN_INC          = 0xC0
    COM_SCAN_DEC          = 0xC8
    SET_DISPLAY_OFFSET    = 0xA2
    SET_COM_PINS          = 0xDA
    SET_VCOM_DETECT       = 0xBE
    SET_DISPLAY_CLOCK_DIV = 0xB3
    SET_PRECHARGE         = 0xBC
    SET_MULTIPLEX         = 0xA8
    SET_MASTER_CONFIG     = 0xAD
    SET_VSL               = 0x0D
    SET_PHASE_LENGTH      = 0xB1
    SET_FRAME_FREQUENCY   = 0xB2
    SET_GRAY_SCALE_TABLE  = 0xB8
    SET_CURRENT_RANGE     = 0x84
    SET_REMAP_FORMAT      = 0xA0
    GA_OPTION             = 0x23
    

    MEMORY_MODE_HORIZ = 0x00
    MEMORY_MODE_VERT  = 0x01
    MEMORY_MODE_PAGE  = 0x02

    # Device name will be /dev/spidev-{bus}.{device}
    # dc_pin is the data/commmand pin.  This line is HIGH for data, LOW for command.
    # We will keep d/c low and bump it high only for commands with data
    # reset is normally HIGH, and pulled LOW to reset the display

    def __init__(self, bus=0, device=0, dc_pin=1, reset_pin=2, buffer_rows=64, buffer_cols=128, rows=64, cols=128):
	self.cols = cols
	self.rows = rows
	self.buffer_rows = buffer_rows
	self.dc_pin = dc_pin
	self.reset_pin = reset_pin
	self.spi = spidev.SpiDev()
	self.spi.open(bus, device)
	self.spi.max_speed_hz = 32000000
	self.gpio = wiringpi2.GPIO(wiringpi2.GPIO.WPI_MODE_PINS)
	self.gpio.pinMode(self.reset_pin, self.gpio.OUTPUT)
	self.gpio.digitalWrite(self.reset_pin, self.gpio.HIGH)
	self.gpio.pinMode(self.dc_pin, self.gpio.OUTPUT)
	self.gpio.digitalWrite(self.dc_pin, self.gpio.LOW)
	self.col_offset = 0
	self.flipped = False

    def reset(self):
	self.gpio.digitalWrite(self.reset_pin, self.gpio.LOW)
	self.gpio.delay(100) # 10ms
	self.gpio.digitalWrite(self.reset_pin, self.gpio.HIGH)

    def command(self, *bytes):
        # already low
        self.gpio.digitalWrite(self.dc_pin, self.gpio.LOW) 
        self.spi.writebytes(list(bytes))
	self.gpio.digitalWrite(self.dc_pin, self.gpio.HIGH)	

    def data(self, bytes):
        self.gpio.digitalWrite(self.dc_pin, self.gpio.HIGH)
        self.spi.writebytes(bytes)
        self.gpio.digitalWrite(self.dc_pin, self.gpio.LOW)
        
    def begin(self, vcc_state = SWITCH_CAP_VCC):
        self.gpio.delay(1) # 1ms
	self.reset()
        self.command(0x0ae) # display off, sleep mode
	self.command(0x0b3, 0x33) # set display clock divide ratio/oscillator frequency (set clock as 135 frames/sec)
#	self.command(0x0b3, 0x091) # set display clock divide ratio/oscillator frequency (set clock as 135 frames/sec)
        self.command(0x0a8, 0x03f) # multiplex ratio: 0x03f * 1/64 duty
        self.command(0x0a2, 0x04c) # display offset, shift mapping ram counter
        self.command(0x0a1, 0x000) # display start line
        self.command(0x0ad, 0x002) # master configuration: disable embedded DC-DC, enable internal VCOMH
	self.command(0x0a0, 0x056) # remap configuration, vertical address increment, enable nibble remap (upper nibble is left)
	self.command(0x086) # full current range (0x084, 0x085, 0x086)
	self.command(0x0b8) # set gray scale table
	self.command(0x01, 0x011, 0x022, 0x032, 0x043, 0x054, 0x077, 0x077) # Pulse width for gray scale table
        self.command(0x081, 0x040) # contrast, brightness, 0..128, Newhaven: 0x040
	self.command(0x0b2, 0x031) # frame frequency (row period)
	self.command(0x0b1, 0x055) # phase length
        self.command(0x0bc, 0x010) # pre-charge voltage level
	self.command(0x0b4, 0x002) # set pre-charge compensation level (not documented in the SDD1325 datasheet, but used in the NHD init seq.)
	self.command(0x0b0, 0x028) # enable pre-charge compensation (not documented in the SDD1325 datasheet, but used in the NHD init seq.)
        self.command(0x0be, 0x01c) # VCOMH voltage
	self.command(0x0bf, 0x002 | 0x00d) # VSL voltage level (not documented in the SDD1325 datasheet, but used in the NHD init seq.)
	self.command(0x0a5) # all pixel on
	self.command(0x0af) # display on
	self.command(0x0a4) # normal display mode
	self.command(0x075,0x00,0x3F) # set max row to 64
	self.command(0x015,0x00,0x3F) # set max column to 64
	self.command(0x24,0x00,0x00,0x3F,0x3F,0x00)

    def display_off(self):
	self.command(0x0a6)

    def display_on(self):
	self.command(0x0a4)

    def reset_position(self):
	self.command(0x24, 0x00, 0x00, 0x3F, 0x3F, 0x00)
