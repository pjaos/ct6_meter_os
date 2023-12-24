package com.example.wifidevsetup.lib;

import android.bluetooth.BluetoothAdapter;
import android.content.DialogInterface;
import android.content.pm.PackageManager;
import android.os.Build;
import android.util.Log;
import android.view.animation.AlphaAnimation;
import android.view.animation.Animation;
import android.view.animation.LinearInterpolator;
import android.widget.Button;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;

import java.util.Vector;

/**
 * @brief A helper class for reusable Activity functionality.
 */
public class LibHelper {
    private final static int REQUEST_ENABLE_BT = 1;
    public static final String LOG_TAG = "#PJA: ";
    ActivityResultLauncher<String[]> multiplePermissionLauncher;
    private static boolean StopApp;
    private static Vector<AppCompatActivity> activityList = new Vector<AppCompatActivity>();

    /**
     * @brief Request the required app permissions.
     * @param appCompatActivity TAn AppCompatActivity instance.
     * @param permissions A List of Strings detailing the permissions to be requested.
     */
    public void requestPermissions(AppCompatActivity appCompatActivity, String[] permissions) {
        ActivityResultContracts.RequestMultiplePermissions multiplePermissionsContract = new ActivityResultContracts.RequestMultiplePermissions();
        multiplePermissionLauncher = appCompatActivity.registerForActivityResult(multiplePermissionsContract, isGranted -> {
            StaticResources.AppLibHelper.debug("Launcher result: " + isGranted.toString());
            if (isGranted.containsValue(false)) {
                StaticResources.AppLibHelper.debug("At least one of the permissions was not granted, launching again...");
                multiplePermissionLauncher.launch(permissions);
            }
        });
        askPermissions(permissions, multiplePermissionLauncher, appCompatActivity);
    }

    /**
     * @brief Ask user for permissions
     * @param permissions A List of Strings detailing the permissions to be requested.
     * @param multiplePermissionLauncher The instance to request the user response to authorise permissions.
     */
    private void askPermissions(String[] permissions, ActivityResultLauncher<String[]> multiplePermissionLauncher, AppCompatActivity appCompatActivity) {
        if (!hasPermissions(permissions, appCompatActivity)) {
            StaticResources.AppLibHelper.debug("Launching multiple contract permission launcher for ALL required permissions");
            multiplePermissionLauncher.launch(permissions);
        } else {
            StaticResources.AppLibHelper.debug("All permissions are already granted");
        }
    }

    /**
     * @brief Check if we have all the required permissions.
     * @param permissions  A List of Strings detailing the permissions to be requested.
     * @return True if we have all the required permissions, False if not.
     */
    private boolean hasPermissions(String[] permissions, AppCompatActivity appCompatActivity) {
        if (permissions != null) {
            for (String permission : permissions) {
                if (ActivityCompat.checkSelfPermission(appCompatActivity, permission) != PackageManager.PERMISSION_GRANTED) {
                    StaticResources.AppLibHelper.debug("Permission is not granted: " + permission);
                    return false;
                }
                StaticResources.AppLibHelper.debug("Permission already granted: " + permission);
            }
            return true;
        }
        return false;
    }

    public void checkAndEnableBlueTooth(AppCompatActivity appCompatActivity) {
        BluetoothAdapter bluetoothAdapter = BluetoothAdapter.getDefaultAdapter();
        if (bluetoothAdapter == null) {
            Toast.makeText(appCompatActivity, "Bluetooth NOT supported by this phone/tablet.", Toast.LENGTH_LONG).show();
            new AlertDialog.Builder(appCompatActivity)
                    .setTitle("Not compatible")
                    .setMessage("Your phone/tablet does not support Bluetooth. Therefore this ")
                    .setPositiveButton("Exit", new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface dialog, int which) {
                            System.exit(0);
                        }
                    })
                    .setIcon(android.R.drawable.ic_dialog_alert)
                    .show();
            appCompatActivity.finish();
            return;

        } else {
            // Use this check to determine whether Bluetooth classic is supported on the device.
            // Then you can selectively disable BLE-related features.
            if (!appCompatActivity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_BLUETOOTH)) {
                Toast.makeText(appCompatActivity, "Bluetooth required but is not is not supported by this device.", Toast.LENGTH_SHORT).show();
                appCompatActivity.finish();
                return;
            }
            // Use this check to determine whether BLE is supported on the device. Then
            // you can selectively disable BLE-related features.
            if (!appCompatActivity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) {
                Toast.makeText(appCompatActivity, "Bluetooth low energy required but is not is not supported by this device.", Toast.LENGTH_SHORT).show();
                appCompatActivity.finish();
                return;
            }

            if (bluetoothAdapter.isEnabled()) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {  // Only ask for these permissions on runtime when running Android 6.0 or higher
                    requestPermissions(appCompatActivity, LibConstants.APP_PERMISSION_LIST);
                }
            }
            else {
                new AlertDialog.Builder(appCompatActivity)
                        .setTitle("Enable Bluetooth")
                        .setMessage("Please enable Bluetooth and try again.")
                        .setPositiveButton("Exit", new DialogInterface.OnClickListener() {
                            public void onClick(DialogInterface dialog, int which) {
                                System.exit(0);
                            }
                        })
                        .setIcon(android.R.drawable.ic_dialog_alert)
                        .show();
            }
        }
    }

    /**
     * @brief Set a button flashing at the given rate.
     * @param button The Button instance.
     * @param milliSeconds The flash rate in milli seconds.
     * @return the Animation instance so that the flashing can be stopped by calling the stop() method.
     */
    public Animation flashButtton(Button button, int milliSeconds) {
        Animation mAnimation = new AlphaAnimation(1, 0);
        mAnimation.setDuration(milliSeconds);
        mAnimation.setInterpolator(new LinearInterpolator());
        mAnimation.setRepeatCount(Animation.INFINITE);
        mAnimation.setRepeatMode(Animation.REVERSE);
        button.startAnimation(mAnimation);
        return mAnimation;
    }

    /**
     * @brief Send debug message to the log.
     * @param message
     */
    public void debug(String message) {
        Log.d(LibHelper.LOG_TAG, message);
    }

    /**
     * @brief Send info message to the log.
     * @param message
     */
    public void info(String message) {
        Log.i(LibHelper.LOG_TAG, message);
    }

    /**
     * @brief Send info message to the log.
     * @param message
     */
    public void error(String message) {
        Log.e(LibHelper.LOG_TAG, message);
    }

    /**
     * Add an activity to the list of all the activities in the app.
     * This is used to shut down the app when required.
     * @param appCompatActivity
     */
    public static void AddActivity(AppCompatActivity appCompatActivity) {
        if( !activityList.contains(activityList) ) {
            activityList.add(appCompatActivity);
        }
    }

    /**
     * @brief Stop the app running.
     */
    public static void StopApp() {
        for( AppCompatActivity appCompatActivity : activityList ) {
            appCompatActivity.finishAndRemoveTask();
        }
        //StaticResources.BtleWrapper.stopScan();
    }
}
