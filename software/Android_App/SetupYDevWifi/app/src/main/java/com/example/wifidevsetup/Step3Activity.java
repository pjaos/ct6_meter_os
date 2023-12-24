package com.example.wifidevsetup;

import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.ListView;
import androidx.appcompat.app.AppCompatActivity;

import com.example.wifidevsetup.lib.StaticResources;
import com.example.wifidevsetup.lib.YDevBTLEWrapper;

import org.json.JSONArray;
import org.json.JSONException;

import java.util.Vector;

/**
 * @brief The YDev default WiFi AP has been detected.
 * This step is responsible for connecting to the AP.
 */
public class Step3Activity extends AppCompatActivity implements AdapterView.OnItemClickListener {
    ListView listView;
    int selectedSSID = -1;
    Vector<String> ssidList;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_step_3);

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
        Button nextButton = (Button) findViewById(R.id.next_button);
        nextButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                nextActivity();
            }
        });
        // Ensure the lib knows about all the activities sop that they can be shut down when the app exits
        StaticResources.AppLibHelper.AddActivity(this);
    }

    /**
     * @brief Receive the WiFi scan response.
     */
    protected void onResume() {
        super.onResume();
        // Get the scan result argument passed by the previous step
        Intent i = getIntent();
        Bundle extras = i.getExtras();
        if (extras.containsKey(YDevBTLEWrapper.SCAN_RESULT)) {
            String networksString = (String) extras.get(YDevBTLEWrapper.SCAN_RESULT);
            try {
                ssidList = new Vector<String>();
                JSONArray detectedNetworks = new JSONArray(networksString);
                for (int index = 0; index < detectedNetworks.length(); index++) {
                    if( detectedNetworks.getJSONObject(index).has("SSID") ) {
                        String ssid = (String)detectedNetworks.getJSONObject(index).get("SSID");
                        if( ssid.length() > 0 ) {
                            ssidList.add(ssid);
                        }
                    }
                }
                ArrayAdapter arrayAdapter = new ArrayAdapter(this, R.layout.listview, ssidList.toArray());
                listView = (ListView) findViewById(R.id.list);
                listView.setAdapter(arrayAdapter);
                listView.setOnItemClickListener(this);
            }
            catch( JSONException ex ) {
                ex.printStackTrace();
            }
        }
    }

    /**
     * Select an item in the list
     * @param adapterView
     * @param view
     * @param i
     * @param l
     */
    @Override
    public void onItemClick(AdapterView<?> adapterView, View view, int i, long l) {
        // Deselect all list elements
        for(int a = 0; a < adapterView.getChildCount(); a++)
        {
            adapterView.getChildAt(a).setBackgroundColor(Color.TRANSPARENT);
        }
        selectedSSID = i;
        // Select this one
        view.setBackgroundColor(Color.DKGRAY);
    }

    protected void onPause() {
        super.onPause();
    }

    void nextActivity() {
        if( selectedSSID != -1 ) {
            // Move to next step
            Intent intent = new Intent(this, Step4Activity.class);
            intent.putExtra(YDevBTLEWrapper.SSID, ssidList.get(selectedSSID));
            startActivity(intent);
        }
    }

    void previousActivity() {
        Intent intent = new Intent(this, FirstActivity.class);
        startActivity(intent);
    }

}