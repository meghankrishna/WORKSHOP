package com.bootcamp.demoapp;

import android.Manifest;
import android.app.Activity;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Color;
import android.graphics.Typeface;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.telephony.TelephonyManager;
import android.util.Base64;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Bootcamp Demo App.
 *
 * A harmless app whose only job is to USE the Android features we study, one
 * button each, so an instructor can show a monitor (Frida hooks) catching them
 * and an emulator condition (battery, GPS, network) changing what the app sees.
 *
 * Nothing leaves the device except one GET request to https://example.com.
 */
public class MainActivity extends Activity {

    private static final int REQ_PERMS = 1;
    private static final int BG = Color.parseColor("#F4F8F6");
    private static final int GREEN = Color.parseColor("#138A63");
    private static final int DARK = Color.parseColor("#10252B");

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final SimpleDateFormat clock = new SimpleDateFormat("HH:mm:ss", Locale.US);

    private TextView statusView;
    private TextView logView;
    private ScrollView logScroll;

    private LocationManager locationManager;
    private LocationListener locationListener;
    private Location lastLocation;
    private long lastNetworkMs = -1;
    private String lastNetworkNote = "not tried yet";

    // ------------------------------------------------------------------ UI --

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        requestPermissionsIfNeeded();
        log("Ready. Tap a button, or 'Run ALL'.");
    }

    @Override
    protected void onResume() {
        super.onResume();
        ui.post(refreshStatus);
    }

    @Override
    protected void onPause() {
        super.onPause();
        ui.removeCallbacks(refreshStatus);
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                getResources().getDisplayMetrics());
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        root.setPadding(dp(16), dp(24), dp(16), dp(12));

        TextView title = new TextView(this);
        title.setText("Bootcamp Demo App");
        title.setTextSize(22);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(DARK);
        root.addView(title);

        statusView = new TextView(this);
        statusView.setTextSize(13);
        statusView.setTypeface(Typeface.MONOSPACE);
        statusView.setTextColor(Color.WHITE);
        statusView.setBackgroundColor(DARK);
        statusView.setPadding(dp(12), dp(10), dp(12), dp(10));
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        sp.topMargin = dp(8);
        root.addView(statusView, sp);

        // buttons: two per row
        String[][] buttons = {
                {"1  Files", "files"}, {"2  Network", "network"},
                {"3  Location", "location"}, {"4  Phone info", "phone"},
                {"5  Saved settings", "prefs"}, {"6  Database", "database"},
                {"7  Encryption", "crypto"}, {"8  Run a command", "command"},
                {"9  Installed apps", "packages"}, {"Run ALL", "all"},
        };
        for (int i = 0; i < buttons.length; i += 2) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.addView(makeButton(buttons[i][0], buttons[i][1], false));
            row.addView(makeButton(buttons[i + 1][0], buttons[i + 1][1], buttons[i + 1][1].equals("all")));
            root.addView(row);
        }

        Button clear = new Button(this);
        clear.setText("Clear log");
        clear.setAllCaps(false);
        clear.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                logView.setText("");
            }
        });
        root.addView(clear);

        logView = new TextView(this);
        logView.setTextSize(12);
        logView.setTypeface(Typeface.MONOSPACE);
        logView.setTextColor(DARK);
        logScroll = new ScrollView(this);
        logScroll.addView(logView);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        lp.topMargin = dp(6);
        root.addView(logScroll, lp);

        setContentView(root);
    }

    private Button makeButton(String label, final String action, boolean highlight) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
        if (highlight) {
            b.setBackgroundColor(GREEN);
            b.setTextColor(Color.WHITE);
        }
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        b.setLayoutParams(p);
        b.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                run(action);
            }
        });
        return b;
    }

    private void run(String action) {
        switch (action) {
            case "files": doFiles(); break;
            case "network": doNetwork(); break;
            case "location": doLocation(); break;
            case "phone": doPhone(); break;
            case "prefs": doPrefs(); break;
            case "database": doDatabase(); break;
            case "crypto": doCrypto(); break;
            case "command": doCommand(); break;
            case "packages": doPackages(); break;
            case "all":
                log("=== Run ALL ===");
                doFiles(); doNetwork(); doLocation(); doPhone(); doPrefs();
                doDatabase(); doCrypto(); doCommand(); doPackages();
                break;
            default: break;
        }
    }

    // ----------------------------------------------------- live status panel --

    private final Runnable refreshStatus = new Runnable() {
        @Override
        public void run() {
            statusView.setText(buildStatus());
            ui.postDelayed(this, 2000);
        }
    };

    private String buildStatus() {
        StringBuilder sb = new StringBuilder();

        // battery: level from BatteryManager, charging state from the sticky broadcast
        try {
            BatteryManager bm = (BatteryManager) getSystemService(Context.BATTERY_SERVICE);
            int level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
            Intent b = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            int plugged = b == null ? 0 : b.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0);
            sb.append("Battery  : ").append(level).append("%  ")
                    .append(plugged != 0 ? "(charging)" : "(on battery)").append('\n');
        } catch (Exception e) {
            sb.append("Battery  : ").append(e.getClass().getSimpleName()).append('\n');
        }

        // location: last fix we received
        if (lastLocation != null) {
            sb.append(String.format(Locale.US, "Location : %.4f, %.4f%n",
                    lastLocation.getLatitude(), lastLocation.getLongitude()));
        } else {
            sb.append("Location : no fix yet (tap 3 Location)\n");
        }

        // network: speed the system reports + how long our last request took
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            Network n = cm.getActiveNetwork();
            NetworkCapabilities caps = n == null ? null : cm.getNetworkCapabilities(n);
            if (caps == null) {
                sb.append("Network  : offline\n");
            } else {
                sb.append("Network  : ").append(caps.getLinkDownstreamBandwidthKbps()).append(" kbps down\n");
            }
        } catch (Exception e) {
            sb.append("Network  : ").append(e.getClass().getSimpleName()).append('\n');
        }
        sb.append("Last GET : ").append(lastNetworkMs >= 0 ? lastNetworkMs + " ms" : lastNetworkNote);
        return sb.toString();
    }

    // -------------------------------------------------------------- actions --

    /** FILESYSTEM: File.exists, FileOutputStream, FileInputStream */
    private void doFiles() {
        try {
            String[] paths = {"/sdcard/Download", "/system/etc/hosts", "/data/local/tmp/does-not-exist"};
            for (String p : paths) {
                log("File.exists(" + p + ") -> " + new File(p).exists());
            }
            File note = new File(getFilesDir(), "note.txt");
            FileOutputStream out = new FileOutputStream(note);
            out.write("hello from the bootcamp demo".getBytes("UTF-8"));
            out.close();
            FileInputStream in = new FileInputStream(note);
            byte[] buf = new byte[64];
            int n = in.read(buf);
            in.close();
            log("wrote and read note.txt (" + n + " bytes)");
        } catch (Exception e) {
            log("files: " + e);
        }
    }

    /** NETWORK: URL, openConnection, getResponseCode (on a background thread) */
    private void doNetwork() {
        log("network: GET https://example.com ...");
        new Thread(new Runnable() {
            @Override
            public void run() {
                long t0 = System.currentTimeMillis();
                try {
                    URL url = new URL("https://example.com");
                    HttpURLConnection c = (HttpURLConnection) url.openConnection();
                    c.setConnectTimeout(10000);
                    c.setReadTimeout(10000);
                    int code = c.getResponseCode();
                    InputStream in = c.getInputStream();
                    byte[] buf = new byte[4096];
                    int total = 0, n;
                    while ((n = in.read(buf)) > 0) total += n;
                    in.close();
                    lastNetworkMs = System.currentTimeMillis() - t0;
                    lastNetworkNote = "";
                    logLater("network: HTTP " + code + ", " + total + " bytes in " + lastNetworkMs + " ms");
                } catch (Exception e) {
                    lastNetworkMs = -1;
                    lastNetworkNote = "failed (" + e.getClass().getSimpleName() + ")";
                    logLater("network: " + e);
                }
            }
        }).start();
    }

    /** LOCATION: LocationManager.getLastKnownLocation / requestLocationUpdates */
    private void doLocation() {
        if (!hasLocationPermission()) {
            log("location: permission needed, please allow it");
            requestPermissionsIfNeeded();
            return;
        }
        try {
            if (locationManager == null) {
                locationManager = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
            }
            Location l = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
            if (l != null) {
                lastLocation = l;
                log(String.format(Locale.US, "location: last known %.4f, %.4f", l.getLatitude(), l.getLongitude()));
            } else {
                log("location: no last known fix yet");
            }
            if (locationListener == null) {
                locationListener = new LocationListener() {
                    @Override
                    public void onLocationChanged(Location loc) {
                        // the emulator repeats the same fix every second;
                        // only write a log line when the position really moves
                        boolean moved = lastLocation == null
                                || Math.abs(lastLocation.getLatitude() - loc.getLatitude()) > 0.00005
                                || Math.abs(lastLocation.getLongitude() - loc.getLongitude()) > 0.00005;
                        lastLocation = loc;
                        if (moved) {
                            log(String.format(Locale.US, "location: moved to %.4f, %.4f",
                                    loc.getLatitude(), loc.getLongitude()));
                        }
                    }

                    @Override public void onProviderEnabled(String provider) { }
                    @Override public void onProviderDisabled(String provider) { }
                    @Override public void onStatusChanged(String provider, int status, Bundle extras) { }
                };
                locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000, 0, locationListener);
                log("location: listening for updates (change it with: adb emu geo fix <lon> <lat>)");
            }
        } catch (SecurityException e) {
            log("location: " + e);
        } catch (Exception e) {
            log("location: " + e);
        }
    }

    /** TELEPHONY + DEVICE INFO: TelephonyManager, Settings.Secure. Some calls are
     *  refused on purpose to show how exceptions are recorded. */
    private void doPhone() {
        TelephonyManager tm = (TelephonyManager) getSystemService(Context.TELEPHONY_SERVICE);
        log("phone: network operator = " + tm.getNetworkOperatorName());
        log("phone: SIM operator = " + tm.getSimOperatorName());
        try {
            log("phone: line number = " + tm.getLine1Number());
        } catch (SecurityException e) {
            log("phone: getLine1Number refused (" + e.getClass().getSimpleName() + ")");
        }
        try {
            log("phone: device id = " + tm.getDeviceId());
        } catch (SecurityException e) {
            log("phone: getDeviceId refused (" + e.getClass().getSimpleName() + ")");
        }
        log("device: android id = " + Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID));
    }

    /** SHARED PREFERENCES: write then read */
    private void doPrefs() {
        try {
            SharedPreferences sp = getSharedPreferences("demo", MODE_PRIVATE);
            sp.edit().putString("token", "abc123-demo-token").putBoolean("logged_in", true).apply();
            log("prefs: saved token and logged_in");
            log("prefs: token = " + sp.getString("token", "none"));
            log("prefs: logged_in = " + sp.getBoolean("logged_in", false));
        } catch (Exception e) {
            log("prefs: " + e);
        }
    }

    /** DATABASE: SQLite create / insert / query */
    private void doDatabase() {
        SQLiteDatabase db = null;
        try {
            db = openOrCreateDatabase("demo.db", MODE_PRIVATE, null);
            db.execSQL("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT)");
            ContentValues cv = new ContentValues();
            cv.put("text", "note at " + clock.format(new Date()));
            db.insert("notes", null, cv);
            Cursor c = db.rawQuery("SELECT COUNT(*) FROM notes", null);
            c.moveToFirst();
            log("database: notes table now has " + c.getInt(0) + " row(s)");
            c.close();
        } catch (Exception e) {
            log("database: " + e);
        } finally {
            if (db != null) db.close();
        }
    }

    /** CRYPTOGRAPHY: AES encrypt a message */
    private void doCrypto() {
        try {
            SecretKeySpec key = new SecretKeySpec("0123456789abcdef".getBytes("UTF-8"), "AES");
            Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
            cipher.init(Cipher.ENCRYPT_MODE, key, new IvParameterSpec(new byte[16]));
            byte[] enc = cipher.doFinal("secret message".getBytes("UTF-8"));
            log("crypto: encrypted -> " + Base64.encodeToString(enc, Base64.NO_WRAP));
        } catch (Exception e) {
            log("crypto: " + e);
        }
    }

    /** PROCESS: Runtime.exec */
    private void doCommand() {
        try {
            Process p = Runtime.getRuntime().exec(new String[]{"getprop", "ro.product.model"});
            BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()));
            String line = r.readLine();
            r.close();
            log("command: getprop ro.product.model -> " + line);
        } catch (Exception e) {
            log("command: " + e);
        }
    }

    /** PACKAGE INFO: list installed apps */
    private void doPackages() {
        try {
            int n = getPackageManager().getInstalledPackages(0).size();
            log("packages: " + n + " apps visible");
        } catch (Exception e) {
            log("packages: " + e);
        }
    }

    // ---------------------------------------------------------- permissions --

    private boolean hasLocationPermission() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestPermissionsIfNeeded() {
        requestPermissions(new String[]{
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.READ_PHONE_STATE}, REQ_PERMS);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        log("permissions updated");
    }

    // -------------------------------------------------------------- logging --

    private void log(final String msg) {
        android.util.Log.i("BootcampDemo", msg); // also visible with: adb logcat -s BootcampDemo
        final String line = clock.format(new Date()) + "  " + msg + "\n";
        if (Looper.myLooper() == Looper.getMainLooper()) {
            append(line);
        } else {
            ui.post(new Runnable() {
                @Override
                public void run() {
                    append(line);
                }
            });
        }
    }

    private void logLater(String msg) {
        log(msg);
    }

    private void append(String line) {
        logView.append(line);
        // keep the log short so it never grows without limit
        CharSequence all = logView.getText();
        if (all.length() > 6000) {
            logView.setText(all.subSequence(all.length() - 4000, all.length()));
        }
        logScroll.post(new Runnable() {
            @Override
            public void run() {
                logScroll.fullScroll(View.FOCUS_DOWN);
            }
        });
    }
}
