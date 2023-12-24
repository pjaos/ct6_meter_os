package com.example.wifidevsetup.lib;

import android.widget.ProgressBar;

import java.util.Timer;
import java.util.TimerTask;

/**
 * @brief Auto update a progress bar for a task thats expected to take a predictable time.
 */
public class AutoProgressBarUpdater extends TimerTask {
    int percentageComplete;
    ProgressBar progressBar;
    Timer timer;
    int maxSeconds;

    /**
     * @brief Constructor
     * @param progressBar The progress bar to be adjusted.
     * @param maxSeconds The max number of seconds we expect the task to take.
     */
    public AutoProgressBarUpdater(ProgressBar progressBar, int maxSeconds) {
        this.progressBar=progressBar;
        this.maxSeconds=maxSeconds;
    }

    /**
     * @brief Get the timer delay in
     * @param maxSeconds The maximum time for the task to complete.
     * @return
     */
    public void start() {
        int msPerPercent = (maxSeconds*1000)/100;
        timer = new Timer();
        timer.schedule(this, msPerPercent, msPerPercent);
    }

    public void stop() {
        if( timer != null ) {
            timer.cancel();
            timer = null;
        }
    }

    /**
     * @brief Called every time the timer fires to provide user indication of how far through a WiFi scan we are.
     */
    public void run() {
        percentageComplete++;
        if( percentageComplete <= 100 && progressBar != null ) {
            progressBar.setProgress(percentageComplete);
        }

    }
}
