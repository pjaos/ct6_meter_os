# V8.0 Changes
- Add ability to set the ct6_configurator app server bind address and port.

# V7.9 Changes
- Change Windows and Linux installers to use poetry rather than pipenv

# V7.8 Changes
- Add the ability to calibrate individual ports current measurements from the GUI.

# V7.7 Changes
- Use default config if the config loaded from the users home folder is corrupted.
- Disable encrypted configuration as it uses the id_rsa ssh key. Using the id_rsa key does
  not work if the ~/.ssh/id_rsa private key file is not present. Therefore workaround this
  for the moment by using non encrypted local configuration.
- Add Linux installer that includes the initial log file created message in the log window.
- Update the documentation to show the new ct6_configurator (nicegui) UI.
- Report the log file created when the ct6_configurator is started.

# V7.6 Changes
- Re implement the ct6_configurator using the nicegui python module.
- Added an extra tab that allows the user to re calibrate the CT6 AC voltage measurement
    so that users whoi use a differemnt AC power supply can easily recalibrate a CT6 device.

# V7.5 Changes
- Add a Scan tab to the ct6_configurator. This allows the user to scan for any 
  CT6 devices on the LAN. Each CT6 device can be remotely power cycled if required.
- Add ct6_configurator log file to ~/test_logs. Each time the ct6_configurator 
  is started a log file (E.G ct6_configurator_20240610095521.log) file is created.
  The filename includes the datetime stamp of the ct6_configurator launch time.
- ct6_db_store: Change memory usage message from a info to debug level message.

# V7.4 Changes

- Updated CT6 firmware to allow it to be configured to send data to MQTT servers.
  This allows integration with third party software such as ioBroker.
- Windows support added. Previously the server software apps only ran on
  Linux platforms.
- Added GUI tool to allow configuration and recovery of CT6 devices.
- Updated documentation files as required for above changes.
- Increased width of power report table in the CT6 dashboard (ct6_dash app)
  so that all days of the week are visible when Firefox and google chrome 
  browsers are used.
