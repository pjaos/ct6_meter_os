package com.example.wifidevsetup;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.example.wifidevsetup.lib.StaticResources;
import com.example.wifidevsetup.lib.YDevBTLEWrapper;

public class LastActivity extends AppCompatActivity implements View.OnClickListener {
    private TextView finalTextView;
    private String ssid;
    private String ipAddress;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_last);

        finalTextView = (TextView) findViewById(R.id.finalTextView);

        Intent i = getIntent();
        Bundle extras = i.getExtras();
        if ( extras.containsKey(YDevBTLEWrapper.SSID) && extras.containsKey(YDevBTLEWrapper.IP_ADDRESS)  ) {
            ssid = (String) extras.get(YDevBTLEWrapper.SSID);
            ipAddress = (String) extras.get(YDevBTLEWrapper.IP_ADDRESS);
            StaticResources.AppLibHelper.debug("The device is connected to "+ssid+" and has the IP address of "+ipAddress);
            // Set simple user message that does not include the IP address
            finalTextView.setText("The device is now connected to "+ssid);
            finalTextView.setOnClickListener(this);
        }


        Button next_button = (Button) findViewById(R.id.next_button);
        // Exit app
        next_button.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                // Exit app
                StaticResources.AppLibHelper.StopApp();
            }
        });
        // Ensure the lib knows about all the activities sop that they can be shut down when the app exits
        StaticResources.AppLibHelper.AddActivity(this);
    }

    void previousActivity() {
        Intent intent = new Intent(this, Step2Activity.class);
        startActivity(intent);
    }

    /**
     * If the user clicks on the text add the device IP address to the message.
     * @param view
     */
    @Override
    public void onClick(View view) {
        String message = "???";
        String currentMessage = finalTextView.getText().toString();
        if( currentMessage.indexOf(ipAddress) == -1 ) {
            message = "The device is connected to " + ssid + " and has the IP address of " + ipAddress;
        }
        else {
            message = "The device is connected to "+ssid;
        }
        finalTextView.setText(message);
    }
}
