package com.example.wifidevsetup;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.view.animation.Animation;
import android.widget.Button;
import androidx.appcompat.app.AppCompatActivity;

import com.example.wifidevsetup.lib.StaticResources;

/**
 * @brief Responsible for telling the user to press the WiFi button on the device
 * to get it into setup mode (WiFi AP mode with default SSID and password).
 */
public class FirstActivity extends AppCompatActivity {
    Animation buttonFlashAnimation;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_first);

        Button backButton = (Button) findViewById(R.id.back_button);
        // We can't go back from the first step
        backButton.setEnabled(false);
        Button cancelButton = (Button) findViewById(R.id.cancel_button);
        // Exit app
        cancelButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                // Exit app
                StaticResources.AppLibHelper.StopApp();
            }
        });
        Button nextButton = (Button) findViewById(R.id.next_button);
        nextButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                nextActivity();
            }
        });

        // Check that we can use bluetooth. This requests the required permissions and
        // checks that bluetooth is enabled on this android device.
        StaticResources.AppLibHelper.checkAndEnableBlueTooth(this);
        // Ensure the lib knows about all the activities sop that they can be shut down when the app exits
        StaticResources.AppLibHelper.AddActivity(this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        StaticResources.BtleWrapper.disconnect();
        // Start the button flashing to indicate the expected rate of flash of the LED on the device.
        buttonFlashAnimation = StaticResources.AppLibHelper.flashButtton((Button) findViewById(R.id.button), 100);
    }

    @Override
    protected void onPause() {
        super.onPause();
        if( buttonFlashAnimation != null ) {
            buttonFlashAnimation.cancel();
            StaticResources.AppLibHelper.debug("onPause(): Stopped button flash animation.");
        }
    }

    void nextActivity() {
        Intent intent = new Intent(this, Step2Activity.class);
        startActivity(intent);
    }

}