# V7.5 Release notes
- Add a Scan tab to the ct6_configurator. This allows the user to scan for any 
  CT6 devices on the LAN. Each CT6 device can be remotely power cycled if required.
- Add ct6_configurator log file to ~/test_logs. Each time the ct6_configurator 
  is started a log file (E.G ct6_configurator_20240610095521.log) file is created.
  The filename includes the datetime stamp of the ct6_configurator launch time.
- ct6_db_store: Change memory usage message from a info to debug level message.

# V7.4 Release notes

- Updated CT6 firmware to allow it to be configured to send data to MQTT servers.
  This allows integration with third party software such as ioBroker.
- Windows support added. Previously the server software apps only ran on
  Linux platforms.
- Added GUI tool to allow configuration and recovery of CT6 devices.
- Updated documentation files as required for above changes.
- Increased width of power report table in the CT6 dashboard (ct6_dash app)
  so that all days of the week are visible when Firefox and google chrome 
  browsers are used.
