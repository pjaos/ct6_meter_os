package com.example.wifidevsetup.lib;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Context;
import android.content.Intent;
import android.widget.ProgressBar;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.nio.charset.StandardCharsets;
import java.util.Timer;
import java.util.TimerTask;

/**
 * @breif Responsible for wrapping up bluetooth low energy functionality to provide a simple
 * to use interface.
 */
public class YDevBTLEWrapper implements YDevIF, SerialListener {
    public static final String BT_CMD                   = "CMD";
    public static final String BT_CMD_WIFI_SCAN         = "WIFI_SCAN";
    public static final String BT_DEV_NAME_PREFIX       = "YDEV";
    public static final String SCAN_RESULT              = "SCAN_RESULT";
    public static final String WIFI_SCAN_COMPLETE       = "WIFI_SCAN_COMPLETE";
    public static final String SSID                     = "SSID";
    public static final String BT_CMD_STA_CONNECT       = "BT_CMD_STA_CONNECT";
    public static final String PASSWORD                 = "PASSWD";
    public static final String WIFI_CONNECTED           = "WIFI_CONNECTED";
    public static final String WIFI_NOT_CONNECTED       = "WIFI_NOT_CONNECTED";
    public static final String WIFI_CONFIGURED          = "WIFI_CONFIGURED";
    public static final String GET_IP                   = "GET_IP";
    public static final String IP_ADDRESS               = "IP_ADDRESS";
    public static final String DISABLE_BT               = "DISABLE_BT";
    public static final int UNDEFINED_STATE             = 0;
    public static final int SCAN_DEVICES_STATE          = 1;
    public static final int CHECK_WIFI_CONNECTED_STATE  = 2;

    private static BTLESerialSocket socket;
    private boolean stopBTScan;
    private Context context;
    private BluetoothManager bluetoothManager;
    private BluetoothAdapter bluetoothAdapter;
    private BluetoothLeScanner scanner;
    private BluetoothDevice btDevice;
    private JSONArray detectedNetworks;
    private ProgressBar progressBar;
    private Class nextActivityClass;
    private Timer wifiConnectTimer;
    private int state = UNDEFINED_STATE;
    private String deviceIPAddress;
    private String ssid;
    private TimerTask task;

    /**
     * @brief Provide a reference to a progress bar that provides the user with feedback.
     * @param progressBar A ProgressBar instance.
     */
    public void setProgressBar(ProgressBar progressBar) {
        this.progressBar = progressBar;
    }

    /**
     * @brief Set the reference to the next activity to be started when the current step in the
     *        process of connecting the devices WiFi is complete.
     * @param nextActivityClass The Activity class.
     */
    public void setNextActivityClass(Class nextActivityClass) { this.nextActivityClass=nextActivityClass; }

    /**
     * @brief Disconnect the socket to the bluetooth device if connected.
     */
    public void disconnect() {
        if( socket != null ) {
            socket.disconnect();
            socket = null;
        }
    }

    /**
     * @brief Stop Bluetooth scanning.
     */
    public void stopScan() {
        stopBTScan = true;
        StaticResources.AppLibHelper.debug("stopScan(): Disabled BlueTooth scanning.");
    }

    /**
     * @brief Update the progress bar if we have one.
     * @param value The value to set the progress bar to.
     */
    private void setProgress(int value) {
        if( progressBar != null ) {
            // We move through 5 states before we have a device connected.
            progressBar.setMax(5);
            //Set progress bar to first state
            progressBar.setProgress(value);
        }
    }
    /**
     * @brief called to find bluetooth devices at the start of the process of setting up the WiFi interface.
     */
    public void findDevices(Context context) {
        this.context = context;
        state = SCAN_DEVICES_STATE;
        detectedNetworks = new JSONArray();
        //Set progress bar to first state
        setProgress(1);
        bluetoothManager = (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        bluetoothAdapter = bluetoothManager.getAdapter();
        scanner = bluetoothAdapter.getBluetoothLeScanner();
        ScanSettings scanSettings = new ScanSettings.Builder().build();
        YDevIF accessYDevIF = this;
        scanner.startScan(null, scanSettings, new ScanCallback() {
            @Override
            public void onScanResult(int callbackType, ScanResult result) {
                super.onScanResult(callbackType, result);
                BluetoothDevice device = result.getDevice();
                String name = device.getName();
                if (name != null && name.startsWith(YDevBTLEWrapper.BT_DEV_NAME_PREFIX)) {
                    // Log message to highlight the fact that a bluetooth device has been found.
                    StaticResources.AppLibHelper.debug("Bluetooth device found: -------------------------------> "+name);
                    // Call the device found method to progress
                    accessYDevIF.ydevBTDeviceFound(result);
                }
                if (stopBTScan) {
                    scanner.stopScan(this);
                    StaticResources.AppLibHelper.debug("Stopped scanning for Bluetooth devices (stopBTScan="+stopBTScan+").");
                }
            }
        });
    }

    /**
     * @brief Called when a YDev device is found from the bluetooth device scan.
     * @param result
     */
    @Override
    public void ydevBTDeviceFound(ScanResult result) {
        setProgress(2);
        btDevice = result.getDevice();
        connect(context, this);
    }

    /**
     * @brief Connect to the bluetooth device found.
     */
    public void connect(Context thisContext, SerialListener serialListener) {
        try {
            disconnect();
            // Attempt to connect to the device
            socket = new BTLESerialSocket(thisContext.getApplicationContext(), btDevice);
            socket.connect(serialListener);
        } catch (IOException e) {
            Toast.makeText(context, "Failed to connect to "+ btDevice.getName(), Toast.LENGTH_LONG);
        }
    }

    /**
     * @brief Change the serial listener.
     * @param serialListener
     */
    public void setSerialListener(SerialListener serialListener) {
        socket.setListner(serialListener);
    }

    /**
     * @brief CAlled when a bluetooth connection is built.
     */
    @Override
    public void onSerialConnect() {
        setProgress(3);
        // Send a command to tell the device to scan for Wifi networks.
        JSONObject scanWiFiCmd = new JSONObject();
        try {
            if( state == SCAN_DEVICES_STATE ) {
                scanWiFiCmd.put(BT_CMD, BT_CMD_WIFI_SCAN);
                byte[] txBytes = scanWiFiCmd.toString().getBytes("UTF-8");
                socket.write(txBytes);
                setProgress(4);
                StaticResources.AppLibHelper.debug("Sent WiFi scan command");
            }
            else if( state == CHECK_WIFI_CONNECTED_STATE ) {
                scanWiFiCmd.put(BT_CMD, GET_IP);
                byte[] txBytes = scanWiFiCmd.toString().getBytes("UTF-8");
                socket.write(txBytes);
                setProgress(1);
                StaticResources.AppLibHelper.debug("Sent get IP address command");
            }
        }
        catch(UnsupportedEncodingException ex) {
            ex.printStackTrace();
        }
        catch(JSONException ex) {
            ex.printStackTrace();
        }
        catch(IOException ex) {
            ex.printStackTrace();
        }

    }

    /**
     * @brief Called when a failure to connect to a bluetooth device occurs.
     * @param e
     */
    @Override
    public void onSerialConnectError(Exception e) {
        e.printStackTrace();
    }

    /**
     * @brief Called when data is available from a bluetooth device.
     * @param data The bytes of data received from the device.
     */
    @Override
    public void onSerialRead(byte[] data) {
        StaticResources.AppLibHelper.debug("Serial RX data: "+data);
        setProgress(5);
        String rxString = new String(data, StandardCharsets.UTF_8);
        if( rxString.indexOf(YDevBTLEWrapper.WIFI_SCAN_COMPLETE)  >= 0 ) {
            StaticResources.AppLibHelper.debug(detectedNetworks.toString());
            if( nextActivityClass != null ) {
                //Move on to next activity now we have all the detected networks.
                Intent intent = new Intent(context, nextActivityClass);
                intent.putExtra(YDevBTLEWrapper.SCAN_RESULT, detectedNetworks.toString());
                context.startActivity(intent);
            }
        }
        else if( rxString.indexOf(YDevBTLEWrapper.WIFI_CONFIGURED)  >= 0 ) {
            StaticResources.AppLibHelper.debug("Device reports WiFi configuration received.");
        }
        else if( rxString.indexOf(YDevBTLEWrapper.WIFI_CONNECTED)  >= 0 ) {
            StaticResources.AppLibHelper.debug("Device reports WiFi connected.");
        }
        else if( rxString.indexOf(YDevBTLEWrapper.WIFI_NOT_CONNECTED)  >= 0 ) {
            StaticResources.AppLibHelper.debug("Device reports WiFi not connected.");
        }
        else if( rxString.indexOf(YDevBTLEWrapper.IP_ADDRESS)  >= 0 ) {
            getDeviceIPAddress(rxString);
        }
        else {
            addToDetectedNetworks(rxString);
        }
    }

    /**
     * @brief Add to the list of detected networks.
     * @param rxString The message received from the device over bluetooth.
     */
    private void addToDetectedNetworks(String rxString) {
        try {
            JSONObject networkObj = new JSONObject(rxString);
            detectedNetworks.put(networkObj);
        }
        catch( JSONException ex ) {
            ex.printStackTrace();
        }
    }

    /**
     * @brief Get the IP address of the device on the WiFi network.
     * @param rxString The message received from the device over bluetooth.
     */
    private void getDeviceIPAddress(String rxString) {
        setProgress(2);
        try {
            JSONObject jsonObject = new JSONObject(rxString);
            if( jsonObject.has(YDevBTLEWrapper.IP_ADDRESS) ) {
                deviceIPAddress = (String) jsonObject.get(YDevBTLEWrapper.IP_ADDRESS);
                StaticResources.AppLibHelper.debug("WiFi device IP address = "+deviceIPAddress);
                if( deviceIPAddress.length() > 0 ) {
                    // Set progress complete
                    setProgress(5);
                    // Send a message to the device to tell it to disable it's Bluetooth interface
                    JSONObject btCmd = new JSONObject();
                    btCmd.put(BT_CMD, DISABLE_BT);
                    byte[] txBytes = btCmd.toString().getBytes("UTF-8");
                    socket.write(txBytes);
                    StaticResources.AppLibHelper.debug("Sent disable bluetooth command to the device.");
                    // Disconnect from the BT device
                    disconnect();
                    if( nextActivityClass != null ) {
                        //Move on to next activity now the device has an IP address on the selected WiFi network.
                        Intent intent = new Intent(context, nextActivityClass);
                        intent.putExtra(YDevBTLEWrapper.SSID, ssid);
                        intent.putExtra(YDevBTLEWrapper.IP_ADDRESS, deviceIPAddress);
                        context.startActivity(intent);
                        // We only do this once
                        nextActivityClass = null;
                    }
                }
            }
        }
        catch(UnsupportedEncodingException ex ) {
            StaticResources.AppLibHelper.debug("JSON conversion (unsupported encoding) of "+rxString+" failed: "+ ex.getLocalizedMessage());
        }
        catch(JSONException ex ) {
            StaticResources.AppLibHelper.debug("JSON conversion of "+rxString+" failed: "+ ex.getLocalizedMessage());
        }
        catch(IOException ex ) {
            StaticResources.AppLibHelper.debug("Failed to send disable bluetooth message to device: "+ ex.getLocalizedMessage());
        }
    }

    /**
     * @brief Called when an IO error occurs on a bluetooth connection.
     * @param e The Exception generated.
     */
    @Override
    public void onSerialIoError(Exception e) {
        e.printStackTrace();
    }

    /**
     * @brief A Wifi connect timer is created when finally trying to connect
     *        the device to a WiFi network. This method can be called to cancel
     *        this process.
     */
    public void cancelwifiConnectTimer() {
        if( wifiConnectTimer != null ) {
            wifiConnectTimer.purge();
            wifiConnectTimer.cancel();
            wifiConnectTimer = null;
        }
    }

    /**
     * @brief Called at the end of the process to connect the device to a WiFi network.
     * @param context   The Activity context.
     * @param ssid      The WiFi SSI
     * @param password  The WiFi Password.
     */
    public void connectToWiFi(Context context, String ssid, String password) {
        StaticResources.AppLibHelper.debug("connectToWiFi(): ssid: "+ssid+" password: "+password);
        // Set the first step of connecting to the WiFi, set 3 of 5 steps
        setProgress(3);
        // Send a command to tell the device to scan for Wifi networks.
        JSONObject scanWiFiCmd = new JSONObject();
        try {
            scanWiFiCmd.put(BT_CMD, BT_CMD_STA_CONNECT);
            scanWiFiCmd.put(SSID, ssid);
            scanWiFiCmd.put(PASSWORD, password);
            byte[] txBytes = scanWiFiCmd.toString().getBytes("UTF-8");
            socket.write(txBytes);
            StaticResources.AppLibHelper.debug("Sent to device: ssid: "+ssid+" password: "+password);
            disconnect();
            StaticResources.AppLibHelper.debug("Disconnected Bluetooth.");
            this.ssid=ssid;
            this.context=context;
            state = CHECK_WIFI_CONNECTED_STATE;
            cancelwifiConnectTimer();
            ConnectTimerTask connectTimerTask = new ConnectTimerTask(this, context);
            wifiConnectTimer = new Timer("wifiConnectTimer");
            wifiConnectTimer.schedule(connectTimerTask, 5000, 3000);
        }
        catch(UnsupportedEncodingException ex) {
            ex.printStackTrace();
        }
        catch(JSONException ex) {
            ex.printStackTrace();
        }
        catch(IOException ex) {
            ex.printStackTrace();
        }
    }

    /**
     * @brief Stop the process of connecting to the WiFi.
     */
    public void stopWiFiConnectChecker() {
        cancelwifiConnectTimer();
    }

}
