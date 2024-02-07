# Issue
Most Pico W boards would work ok when connected to the CT6 hardware.
However some Pico W units would restart occasionally without warning.

It was found that the current drawn by Pico W units can vary by a factor
of up to 4. When high current units were installed the ripple voltage
across C2 could get large enough to disrupt the 3V3 rail causing it to
drop to ~ 1.5v. Therefore this ECO increases C2 from 220uf to 470uf
which means the C2 ripple voltage reaches a max of 4v which is within
margin when the AC supply used is 9V (the lowest supported).

The voltage of C2 has been reduced from 50v to 35v as this allows
the same size capacitor to be used as C2 can be no high than 16mm
to fit in the case.

# ASSY
Move the top level assembly to version 3.2.

# Workaround
Use a Pico W that draws a lower current. This is not very useful in most
situations, therefore it is recommended that this ECO is applied.

# Modification
Remove C2 (220uf 50v) and fit a 470uf 35v capacitor.

# Status
Applied
