package com.example.wifidevsetup;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.text.method.PasswordTransformationMethod;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.example.wifidevsetup.lib.StaticResources;
import com.example.wifidevsetup.lib.YDevBTLEWrapper;

public class Step4Activity extends AppCompatActivity implements TextView.OnEditorActionListener {
    public static final String SSID_NAME = "SSID_NAME";
    public static final String SSID_PASSWORD = "SSID_PASSWORD";
    private String ssid;
    private EditText pw;
    private EditText passwordField;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_step_4);

        passwordField = (EditText) findViewById(R.id.ssid_password);
        passwordField.setOnEditorActionListener(this);
        CheckBox showPWcheckBox = (CheckBox) findViewById(R.id.showPWcheckBox);
        showPWcheckBox.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                if( showPWcheckBox.isChecked() ) {
                    passwordField.setTransformationMethod(null);
                }
                else {
                    passwordField.setTransformationMethod(new PasswordTransformationMethod());
                }
            }
        });

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

    void nextActivity() {
        // If the user has entered a password
        String password = pw.getText().toString();
        if( password.length() > 0 ) {
            Intent intent = new Intent(this, Step5Activity.class);
            intent.putExtra(SSID_NAME, ssid);
            intent.putExtra(SSID_PASSWORD, password);
            startActivity(intent);
        }
    }

    void previousActivity() {
        Intent intent = new Intent(this, FirstActivity.class);
        startActivity(intent);
    }

    protected void onResume() {
        super.onResume();
        Intent i = getIntent();
        Bundle extras = i.getExtras();
        if (extras.containsKey(YDevBTLEWrapper.SSID)) {
            ssid = (String) extras.get(YDevBTLEWrapper.SSID);
            StaticResources.AppLibHelper.debug("selected ssid: "+ssid);
            TextView pwl = (TextView) findViewById(R.id.pw_label);
            pwl.setText("Enter the password for the " + ssid + " WiFi network.");
            pw = (EditText) findViewById(R.id.ssid_password);
            pw.setHint(ssid + " Password");
        }
        showSoftKeyboard(passwordField);
    }


    public void showSoftKeyboard(View view) {
        if(view.requestFocus()){
            InputMethodManager imm =(InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
            imm.toggleSoftInput(InputMethodManager.SHOW_FORCED, InputMethodManager.HIDE_IMPLICIT_ONLY);
        }
    }
    @Override
    public boolean onEditorAction(TextView textView, int i, KeyEvent keyEvent) {
        boolean consumed = false;
        if( i == EditorInfo.IME_ACTION_DONE ) {
            nextActivity();
            consumed = true;
        }
        return consumed;
    }
}