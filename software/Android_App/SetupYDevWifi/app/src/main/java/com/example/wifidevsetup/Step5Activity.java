package com.example.wifidevsetup;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.example.wifidevsetup.lib.AutoProgressBarUpdater;
import com.example.wifidevsetup.lib.StaticResources;
import com.example.wifidevsetup.lib.YDevBTLEWrapper;

public class Step5Activity extends AppCompatActivity {
    private AutoProgressBarUpdater autoProgressBarUpdater;
    private TextView textView3;
    private String ssidName;
    private String ssidPassword;
    private YDevBTLEWrapper btleWrapper;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_step5);
        textView3 = (TextView) findViewById(R.id.textView3);
        // Exit app
        Button cancelButton = (Button) findViewById(R.id.cancel_button);
        cancelButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                // Exit app
                StaticResources.AppLibHelper.StopApp();
            }
        });
        Button backButton = (Button) findViewById(R.id.back_button);
        backButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                previousActivity();
            }
        });

        Intent i = getIntent();
        Bundle extras = i.getExtras();
        if (extras.containsKey(Step4Activity.SSID_NAME)) {
            ssidName = (String) extras.get(Step4Activity.SSID_NAME);
        }
        if (extras.containsKey(Step4Activity.SSID_PASSWORD)) {
            ssidPassword = (String) extras.get(Step4Activity.SSID_PASSWORD);
        }
        // Ensure the lib knows about all the activities sop that they can be shut down when the app exits
        StaticResources.AppLibHelper.AddActivity(this);
    }

    /**
     * @brief Go all the way back to the first activity if the back button is pressed.
     */
    void previousActivity() {
        StaticResources.BtleWrapper.setNextActivityClass(null);
        StaticResources.BtleWrapper.stopWiFiConnectChecker();
        Intent intent = new Intent(this, FirstActivity.class);
        startActivity(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        connectDeviceToWifiNetwork();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if( autoProgressBarUpdater != null ) {
            autoProgressBarUpdater.stop();
        }
        if( btleWrapper != null ) {
            btleWrapper.cancelwifiConnectTimer();
        }
    }

    /**
     * @brief Now we have the SSID and the ssid password, connect to the WiFi network.
     */
    private void connectDeviceToWifiNetwork() {
        btleWrapper = StaticResources.BtleWrapper;

        ProgressBar progressBar = (ProgressBar) findViewById(R.id.progressBar2);
        autoProgressBarUpdater = new AutoProgressBarUpdater(progressBar, 30);
        autoProgressBarUpdater.start();

        // We don't want the BT wrapper to control the progress bar.
        btleWrapper.setProgressBar(null);

        textView3.setText("Connecting device to "+ssidName);
        btleWrapper.setNextActivityClass(LastActivity.class);
        btleWrapper.connectToWiFi(this, ssidName, ssidPassword);
    }

}