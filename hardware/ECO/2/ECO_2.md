# Issue
If the /power_cycle REST interface command is used the CT6 board does not
always measure power on the CT ports when it comes back up. The
/power_cycle command causes the 3V3 rail to be turned off on the CT6
unit. The problem is that this rail does not drop for long enough to
allow the CT6 board to power cycle correctly. The change detailed here
extends the holdoff time to ~ 5 seconds which stops this symptom occuring.

# ASSY
This ECO can be applied to ASSY0398 CT6 (top level assy) versions 1.9.
When the change is applied the board label should become V3.1. Bumped from 
v1.9 to v3.1 so that top level assy version is not confused with the PCB
version.

# Workaround
If the /power_cycle command is used and the CT6 unit stops measuring AC power
the user must pull the AC power connector from the CT6 unit, wait at least
5 seconds before reconnecting the AC power.

# Modification
To resolve this the capacitor and resistor that determine the power cycle
hold off period are changed as detailed below.

1 - Remove C22 (1uf) and replace with a 10uf capacitor.
2 - Remove R1 (1M) and replace with a 2.2M resistor.

# Status
Applied
