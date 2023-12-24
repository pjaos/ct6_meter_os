package com.example.wifidevsetup.lib;

import android.Manifest;

public class LibConstants {
    // All the permissions required for the app should be detailed here
    public static String APP_PERMISSION_LIST[] = {  Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.BLUETOOTH,
            Manifest.permission.BLUETOOTH_ADMIN };

    public static final String DEFAULT_YDEV_WIFI_PASSWORD = "12345678";
    public static final String DEFAULT_YDEV_DEVICE_AP_ADDRESS = "192.168.4.1";
    public static final int YDEV_REST_PORT = 8080;
    public static final int ANDROID_10_API_VERSION = 29;
}
