# CT6 Hardware

## Schematic

The schematic was created against the requirements for the project with reference
to the data sheets for the various parts.

![alt text](images/schematic_top_level.png "CT6 Top Level Schematic")

![alt text](images/schematic_microcontroller.png "CT6 Microcontroller Schematic")

![alt text](images/schematic_channel_a.png "CT6 Channel A Schematic")

![alt text](images/schematic_channel_b.png "CT6 Channel B Schematic")

## PCB
The PCB was created from the above schematic. The final PCB is shown
below.

![alt text](images/pcb.png "CT6 PCB")

# Current transformer

This project is designed to use only the YHDC SCT013 100A 0-1V split core current transformer as shown below.

![alt text](images/ct.jpg "Current Transformer")

These can be plugged into ports 1 - 6 to provide up to six separate bi directional measurements of AC power. When clipping the current transformer around the live AC wire the face shown above should be on the AC supply (grid) side. It may be possible to use other current transformers but the calibration mechanism has only been tested with these current transformers.

## Case
The Case was designed using [FreeCad](https://www.freecad.org/). The various
parts of the case are shown below.

![alt text](images/box.png "CT6 Main Box")

![alt text](images/display_holder.png "CT6 Display Holder")

![alt text](images/top.png "CT6 End Cap")

![alt text](images/switch_and_led_plate.png "CT6 Switch an LED light Pipe Plate")

The two small holes in the above part are drilled using a 1.8mm drill bit. Then a length of clear PETG filament is inserted
into the hole. Each end is then cut off to create light pipes.

![alt text](images/button.png "CT6 Button")

The [case](case) folder contains the FreeCad (0.20.2) design files for this project.

### Dissembling a CT6 unit

Some info on how to take a CT6 unit apart if you want access to the PCB can be found here [here](README_DISSEMBLY.md)

## Power Supply
This project requires the use of an AC - AC supply. The CT6 PCB assembly is calibrated using the power supply detailed below.

![alt text](images/test_psu.jpg "CT6 PSU")

[AC - AC Power supply](https://www.ebay.co.uk/itm/235232679606)

Note !!!

The power supply must output an AC voltage between 9 and 16 volts with a 2.1 mm DC DC barrel connector. A DC power supply will not power the unit. A calibration process is required for the power supply fitted to the unit to ensure the voltage and power measurements are correct.
