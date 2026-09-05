package org.miigaik.geocalc;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;

import com.chaquo.python.PyException;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;

public class MainActivity extends AppCompatActivity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        File exportDir = new File(getFilesDir(), "exports");
        if (!exportDir.exists()) {
            exportDir.mkdirs();
        }
        Python.getInstance().getModule("bridge")
                .callAttr("set_export_dir", exportDir.getAbsolutePath());

        webView = new WebView(this);
        setContentView(webView);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient());
        webView.addJavascriptInterface(new GeocalcJs(this), "Geocalc");
        webView.loadUrl("file:///android_asset/index.html");
    }

    public void openExportedFile(String path, String mime) {
        File file = new File(path);
        if (!file.exists()) {
            Toast.makeText(this, "Файл не найден", Toast.LENGTH_LONG).show();
            return;
        }
        Uri uri = FileProvider.getUriForFile(
                this, getPackageName() + ".fileprovider", file);
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, mime);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            startActivity(Intent.createChooser(intent, "Открыть"));
        } catch (Exception error) {
            Toast.makeText(this, error.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    public static class GeocalcJs {
        private final MainActivity activity;

        GeocalcJs(MainActivity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public String ogz(String payload) {
            try {
                return Python.getInstance().getModule("bridge")
                        .callAttr("solve_ogz", payload).toString();
            } catch (PyException error) {
                return errorJson(error.getMessage());
            }
        }

        @JavascriptInterface
        public String polar(String payload) {
            try {
                return Python.getInstance().getModule("bridge")
                        .callAttr("solve_polar", payload).toString();
            } catch (PyException error) {
                return errorJson(error.getMessage());
            }
        }

        @JavascriptInterface
        public String exportFile(String payload, String kind) {
            try {
                String path = Python.getInstance().getModule("bridge")
                        .callAttr("export_bundle", payload, kind).toString();
                String mime = "application/pdf";
                if ("kml".equals(kind)) {
                    mime = "application/vnd.google-earth.kml+xml";
                } else if ("map".equals(kind)) {
                    mime = "text/html";
                }
                String finalMime = mime;
                activity.runOnUiThread(() -> activity.openExportedFile(path, finalMime));
                return "{\"ok\":true,\"path\":\"" + path.replace("\\", "\\\\") + "\"}";
            } catch (PyException error) {
                return errorJson(error.getMessage());
            }
        }

        private String errorJson(String message) {
            if (message == null) {
                message = "Ошибка вычисления";
            }
            return "{\"error\":\"" + message.replace("\"", "'").replace("\n", " ") + "\"}";
        }
    }
}
