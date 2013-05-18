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

    input = [[0 for x in xrange(64)]for x in xrange(128)] # Display buffer [x][y]

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
        

    def begin(self):
        self.gpio.delay(1) # 1ms
	self.reset()
        self.command(0x0ae) # display off, sleep mode
	self.command(0x0b3, 0x033) # set display clock divide ratio/oscillator frequency (set clock as 135 frames/sec)
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

    def draw_buffer(self):
	# Each column is a nibble. Two columns are joined together in a byte. Bit shift odd rows and merge with even rows.
	displayBuffer = [[0 for x in xrange(64)] for x in xrange(64)]
	xInput = 0
        x = 0
        y = 0
        for x in range(0,64,1):
                # Build vertical
                for y in range(0,64,1):
                        displayBuffer[x][y] = (self.input[x*2][y] << 4) + self.input[x*2+1][y]

        #led.reset_position()
        # write columns
        for i in range(0, 64, 1):
                self.data(displayBuffer[i])

    def update_buffer(self,startX,startY, data = []):
        xCounterOffset = 0
        yCounterOffset = 0
        for pos in range(0,len(data),1):
                self.input[startX + xCounterOffset][startY+yCounterOffset] = data[pos]
                xCounterOffset += 1

