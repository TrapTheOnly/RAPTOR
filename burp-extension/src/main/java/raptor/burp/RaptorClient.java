package raptor.burp;

import burp.api.montoya.MontoyaApi;
import burp.api.montoya.persistence.Preferences;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

public class RaptorClient {
    private static final int BODY_CAP = 16 * 1024;
    private final MontoyaApi api;
    private final Preferences prefs;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(8)).build();
    private final AtomicBoolean started = new AtomicBoolean(false);
    private final CopyOnWriteArrayList<String> hosts = new CopyOnWriteArrayList<>();
    private final Set<String> seenKeys = ConcurrentHashMap.newKeySet();
    private final OfflineRing ring;
    private volatile String agentToken = "";
    private volatile int waveId = 0;
    private volatile String waveName = "";
    private volatile Consumer<String> statusSink;

    public record Draft(String id, String title) {}

    public RaptorClient(MontoyaApi api) {
        this.api = api;
        this.prefs = api.persistence().preferences();
        this.ring = new OfflineRing();
        this.agentToken = prefs.getString("raptor.agentToken");
        if (this.agentToken == null) {
            this.agentToken = "";
        }
    }

    public String url() {
        String value = prefs.getString("raptor.url");
        return value == null ? "" : value.trim();
    }

    public void setUrl(String url) {
        prefs.setString("raptor.url", url == null ? "" : url.trim().replaceAll("/+$", ""));
    }

    public String enrollToken() {
        String value = prefs.getString("raptor.enrollToken");
        return value == null ? "" : value.trim();
    }

    public void setEnrollToken(String token) {
        prefs.setString("raptor.enrollToken", token == null ? "" : token.trim());
    }

    public boolean isStarted() {
        return started.get();
    }

    public List<String> hosts() {
        return List.copyOf(hosts);
    }

    public int waveId() {
        return waveId;
    }

    public String waveName() {
        return waveName;
    }

    static boolean shouldReuseAgent(String savedAgentToken, String boundEnrollToken, String currentEnrollToken) {
        if (savedAgentToken == null || savedAgentToken.isBlank()) {
            return false;
        }
        String current = currentEnrollToken == null ? "" : currentEnrollToken.trim();
        if (current.isEmpty()) {
            return true;
        }
        String bound = boundEnrollToken == null ? "" : boundEnrollToken.trim();
        return !bound.isEmpty() && current.equals(bound);
    }

    public boolean hostAllowed(String host) {
        String target = Redactor.normalizeHost(host);
        if (target.isEmpty()) {
            return false;
        }
        for (String allowed : hosts) {
            if (target.equals(allowed) || target.endsWith("." + allowed) || allowed.endsWith("." + target)) {
                return true;
            }
        }
        return false;
    }

    public synchronized String start() throws Exception {
        String base = url();
        if (base.isEmpty()) {
            throw new IllegalStateException("Set the RAPTOR URL first.");
        }
        String currentEnroll = enrollToken();
        if (shouldReuseAgent(agentToken, boundEnrollToken(), currentEnroll)) {
            try {
                heartbeat();
                started.set(true);
                return statusLine("Reconnected to saved session.");
            } catch (Exception ignored) {
                forgetAgent();
            }
        } else if (!agentToken.isEmpty()) {
            forgetAgent();
        }
        if (currentEnroll.isEmpty()) {
            throw new IllegalStateException("Paste a wave token from RAPTOR.");
        }
        String hostname = java.net.InetAddress.getLocalHost().getHostName();
        String body = "{\"token\":\"" + jsonEscape(currentEnroll) + "\",\"hostname\":\"" + jsonEscape(hostname)
                + "\",\"burp_version\":\"" + jsonEscape(String.valueOf(api.burpSuite().version())) + "\"}";
        String response = post("/burp/v1/enroll", body, currentEnroll);
        agentToken = extractJsonString(response, "token");
        if (agentToken.isEmpty()) {
            throw new IllegalStateException("Enroll did not return an agent token.");
        }
        prefs.setString("raptor.agentToken", agentToken);
        prefs.setString("raptor.boundEnrollToken", currentEnroll);
        applyWaveMeta(response);
        heartbeat();
        started.set(true);
        flushRing();
        return statusLine("Started.");
    }

    public synchronized void stop() {
        started.set(false);
    }

    public synchronized void heartbeat() throws Exception {
        String response = post("/burp/v1/heartbeat", "{}", currentToken());
        String rotated = extractJsonString(response, "token");
        if (!rotated.isEmpty()) {
            agentToken = rotated;
            prefs.setString("raptor.agentToken", agentToken);
        }
        applyWaveMeta(response);
        hosts.clear();
        hosts.addAll(extractJsonStringArray(response, "hosts"));
    }

    public void ingest(List<String> eventsJson) {
        if (eventsJson == null || eventsJson.isEmpty() || !started.get()) {
            return;
        }
        String body = "{\"events\":[" + String.join(",", eventsJson) + "]}";
        try {
            post("/burp/v1/ingest", body, currentToken());
            flushRing();
        } catch (Exception exc) {
            ring.append(body);
            api.logging().logToOutput("RAPTOR ingest queued offline: " + exc.getMessage());
        }
    }

    public String sendAuthTemplate(String rawRequest, String host, String method, String path,
                                   String placeholderMap, String extractRule) throws Exception {
        String body = "{\"host\":\"" + jsonEscape(host) + "\",\"method\":\"" + jsonEscape(method)
                + "\",\"path\":\"" + jsonEscape(path) + "\",\"raw_request\":\"" + jsonEscape(rawRequest)
                + "\",\"placeholder_map\":" + placeholderMap + ",\"extract_rule\":" + extractRule + "}";
        return post("/burp/v1/auth-template", body, currentToken());
    }

    public String sendJwt(String host, String path, String jwt) throws Exception {
        String body = "{\"host\":\"" + jsonEscape(host) + "\",\"path\":\"" + jsonEscape(path)
                + "\",\"jwt\":\"" + jsonEscape(jwt) + "\"}";
        return post("/burp/v1/jwt", body, currentToken());
    }

    public List<Draft> listDrafts() throws Exception {
        return parseDrafts(get("/burp/v1/drafts", currentToken()));
    }

    public String sendEvidence(String eventJson, String findingId) throws Exception {
        String body = eventJson == null ? "{}" : eventJson.trim();
        if (findingId != null && !findingId.isBlank() && body.endsWith("}")) {
            body = body.substring(0, body.length() - 1)
                    + ",\"finding_id\":\"" + jsonEscape(findingId) + "\"}";
        }
        return post("/burp/v1/evidence", body, currentToken());
    }

    public void setStatusSink(Consumer<String> sink) {
        this.statusSink = sink;
    }

    public void announce(String message) {
        String line = statusLine(message);
        Consumer<String> sink = statusSink;
        if (sink != null) {
            sink.accept(line);
        }
        api.logging().logToOutput(line);
    }

    public boolean rememberKey(String key) {
        return seenKeys.add(key);
    }

    private String boundEnrollToken() {
        String value = prefs.getString("raptor.boundEnrollToken");
        return value == null ? "" : value.trim();
    }

    private void forgetAgent() {
        agentToken = "";
        waveId = 0;
        waveName = "";
        prefs.setString("raptor.agentToken", "");
        prefs.setString("raptor.boundEnrollToken", "");
        hosts.clear();
        seenKeys.clear();
        ring.drain();
    }

    private void applyWaveMeta(String json) {
        int parsed = extractJsonInt(json, "wave_id");
        if (parsed > 0) {
            waveId = parsed;
        }
        String name = extractJsonString(json, "wave_name");
        if (!name.isEmpty()) {
            waveName = name;
        }
    }

    public String statusLine(String prefix) {
        StringBuilder line = new StringBuilder(prefix == null ? "" : prefix.trim());
        if (waveId > 0 || !waveName.isEmpty()) {
            if (!line.isEmpty() && line.charAt(line.length() - 1) != '.') {
                line.append('.');
            }
            line.append(" Wave");
            if (!waveName.isEmpty()) {
                line.append(" ").append(waveName);
            }
            if (waveId > 0) {
                line.append(" (#").append(waveId).append(")");
            }
            line.append('.');
        }
        if (hosts.isEmpty()) {
            line.append(" No in-scope hosts yet.");
            return line.toString().trim();
        }
        line.append(" Hosts (").append(hosts.size()).append("): ").append(String.join(", ", hosts));
        return line.toString().trim();
    }

    private String currentToken() {
        return agentToken.isEmpty() ? enrollToken() : agentToken;
    }

    private void flushRing() {
        List<String> pending = ring.drain();
        for (String item : pending) {
            try {
                post("/burp/v1/ingest", item, currentToken());
            } catch (Exception exc) {
                ring.append(item);
                break;
            }
        }
    }

    private String post(String path, String json, String token) throws Exception {
        return send("POST", path, json, token);
    }

    private String get(String path, String token) throws Exception {
        return send("GET", path, null, token);
    }

    private String send(String method, String path, String json, String token) throws Exception {
        String base = url();
        if (base.isEmpty()) {
            throw new IllegalStateException("RAPTOR URL is empty.");
        }
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(base + path))
                .timeout(Duration.ofSeconds(20));
        if ("GET".equals(method)) {
            builder.GET();
        } else {
            builder.header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json == null ? "{}" : json));
        }
        if (token != null && !token.isEmpty()) {
            builder.header("X-Burp-Token", token);
            builder.header("Authorization", "Bearer " + token);
        }
        HttpResponse<String> response = http.send(builder.build(), HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() >= 400) {
            throw new IllegalStateException("HTTP " + response.statusCode() + " " + response.body());
        }
        return response.body() == null ? "" : response.body();
    }

    static List<Draft> parseDrafts(String json) {
        List<Draft> out = new ArrayList<>();
        if (json == null) {
            return out;
        }
        int key = json.indexOf("\"drafts\"");
        if (key < 0) {
            return out;
        }
        int start = json.indexOf('[', key);
        int end = json.indexOf(']', start + 1);
        if (start < 0 || end < 0) {
            return out;
        }
        String block = json.substring(start, end + 1);
        int i = 0;
        while (true) {
            int obj = block.indexOf('{', i);
            if (obj < 0) {
                break;
            }
            int close = block.indexOf('}', obj);
            if (close < 0) {
                break;
            }
            String object = block.substring(obj, close + 1);
            String id = extractJsonString(object, "id");
            String title = extractJsonString(object, "title");
            if (!id.isEmpty()) {
                out.add(new Draft(id, title.isEmpty() ? id : title));
            }
            i = close + 1;
        }
        return out;
    }

    static String jsonEscape(String value) {
        if (value == null) {
            return "";
        }
        String trimmed = value.length() > BODY_CAP ? value.substring(0, BODY_CAP) : value;
        return trimmed.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
    }

    static String extractJsonString(String json, String key) {
        if (json == null) {
            return "";
        }
        String needle = "\"" + key + "\"";
        int idx = json.indexOf(needle);
        if (idx < 0) {
            return "";
        }
        int colon = json.indexOf(':', idx + needle.length());
        int quote = json.indexOf('"', colon + 1);
        if (quote < 0) {
            return "";
        }
        int end = json.indexOf('"', quote + 1);
        return end < 0 ? "" : json.substring(quote + 1, end);
    }

    static int extractJsonInt(String json, String key) {
        if (json == null || key == null) {
            return 0;
        }
        String needle = "\"" + key + "\"";
        int idx = json.indexOf(needle);
        if (idx < 0) {
            return 0;
        }
        int colon = json.indexOf(':', idx + needle.length());
        if (colon < 0) {
            return 0;
        }
        int i = colon + 1;
        while (i < json.length() && Character.isWhitespace(json.charAt(i))) {
            i++;
        }
        int start = i;
        if (i < json.length() && json.charAt(i) == '-') {
            i++;
        }
        while (i < json.length() && Character.isDigit(json.charAt(i))) {
            i++;
        }
        if (i == start || (json.charAt(start) == '-' && i == start + 1)) {
            return 0;
        }
        try {
            return Integer.parseInt(json.substring(start, i));
        } catch (NumberFormatException ignored) {
            return 0;
        }
    }

    static List<String> extractJsonStringArray(String json, String key) {
        if (json == null) {
            return List.of();
        }
        String needle = "\"" + key + "\"";
        int idx = json.indexOf(needle);
        if (idx < 0) {
            return List.of();
        }
        int start = json.indexOf('[', idx);
        int end = json.indexOf(']', start + 1);
        if (start < 0 || end < 0) {
            return List.of();
        }
        String[] parts = json.substring(start + 1, end).split(",");
        java.util.ArrayList<String> out = new java.util.ArrayList<>();
        for (String part : parts) {
            String cleaned = part.trim().replace("\"", "");
            if (!cleaned.isEmpty()) {
                out.add(cleaned.toLowerCase(Locale.ROOT));
            }
        }
        return out;
    }
}
