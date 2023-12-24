package com.example.wifidevsetup.lib;

import android.bluetooth.le.ScanResult;

public interface YDevIF {
    public void ydevBTDeviceFound(ScanResult result);
}
