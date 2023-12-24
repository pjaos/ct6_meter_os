package com.example.wifidevsetup.lib;

import android.content.Context;

import java.util.TimerTask;

/**
 * @brief A Timer task responsible for connecting to a bluetooth device.
 */
public class ConnectTimerTask extends TimerTask {
    YDevBTLEWrapper yDevBTLEWrapper;
    Context context;
    SerialListener serialListener;

    /**
     * @brief Constructor
     * @param yDevBTLEWrapper The YDevBTLEWrapper instance that contains the connect method.
     * @param context         The context for the activity currently running.
     */
    public ConnectTimerTask(YDevBTLEWrapper yDevBTLEWrapper, Context context) {
        this.yDevBTLEWrapper=yDevBTLEWrapper;
        this.context = context;
        this.serialListener = serialListener;
    }

    /**
     * @brief The wifiConnectTimer execution method to check if the WiFi is connected.
     */
    public void run() {
        try {
            //Attempt to connect to the bluetooth interface.
            yDevBTLEWrapper.connect(context, yDevBTLEWrapper);
        }
        catch(Exception e) {
            e.printStackTrace();
        }
    }

}
