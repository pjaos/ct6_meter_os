package com.example.wifidevsetup.lib;

public interface SerialListener {
    public void onSerialConnect      ();
    public void onSerialConnectError (Exception e);
    public void onSerialRead         (byte[] data);
    public void onSerialIoError      (Exception e);
}