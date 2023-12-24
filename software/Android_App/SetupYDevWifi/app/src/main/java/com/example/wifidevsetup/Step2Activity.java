package com.example.wifidevsetup;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import androidx.appcompat.app.AppCompatActivity;

import com.example.wifidevsetup.lib.AutoProgressBarUpdater;
import com.example.wifidevsetup.lib.StaticResources;

/**
 * @brief Responsible for triggering WiFi network scan.
 */
public class Step2Activity extends AppCompatActivity {
    private ProgressBar progressBar;
    private Button nextButton;
    private AutoProgressBarUpdater autoProgressBarUpdater;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_step_2);

        Button backButton = (Button) findViewById(R.id.back_button);
        backButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                previousActivity();
            }
        });
        Button cancelButton = (Button) findViewById(R.id.cancel_button);
        // Exit app
        cancelButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                // Exit app
                StaticResources.AppLibHelper.StopApp();
            }
        });
        nextButton = (Button) findViewById(R.id.next_button);
        // Get reference to the progress bar
        progressBar = (ProgressBar) findViewById(R.id.progressbar1);
        // Ensure the lib knows about all the activities sop that they can be shut down when the app exits
        StaticResources.AppLibHelper.AddActivity(this);
    }

    void previousActivity() {
        autoProgressBarUpdater.stop();
        Intent intent = new Intent(this, FirstActivity.class);
        startActivity(intent);
    }

    /**
     * @brief Start a Bluetooth LE scan on resume.
     */
    protected void onResume() {
        super.onResume();
        // We only proceed to the next step if the device WiFi is enabled.
        nextButton.setEnabled(false);
        // Set this so that the progress bar gets updated
        StaticResources.BtleWrapper.setProgressBar(progressBar);
        // Set this so that the next activity gets started when the connected (via bluetooth)
        // YDev device has scanned for WiFi networks and has a list of these to allow
        // the user to select the one they wish to connect to.
        StaticResources.BtleWrapper.setNextActivityClass(Step3Activity.class);
        StaticResources.BtleWrapper.findDevices(this);
    }

}