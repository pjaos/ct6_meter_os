# Issue
If the AC power is removed and reconnected within about 3 seconds on some 
boards prior to V2.1 the ATM90E32 devices did not reset correctly. 
If this occured then some channels (usually CT1 - CT3) did not 
read AC power.

# Workaround
If boards prior to V2.1 are powered down they should be left off for at 
least 5 seconds before the power is applied again.

# Modification
To resolve this the ATM90E32 device reset pins were connected to a GPIO 
pin (19) on the MCU (Pico W). Boards of version 1.6 to 2.0 can be upgraded
to V2.1 by applying the modification below.

1 - Remove C23 and C40
2 - Connect MCU (Pico W) pin 25 (GPI19) to C23 pad that is not connected to GND.
3 - Connect MCU (Pico W) pin 25 (GPI19) to C40 pad that is not connected to GND.
