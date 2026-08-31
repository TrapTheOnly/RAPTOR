package raptor.burp;

import burp.api.montoya.http.message.HttpRequestResponse;
import burp.api.montoya.http.message.requests.HttpRequest;
import burp.api.montoya.http.message.responses.HttpResponse;
import burp.api.montoya.scanner.audit.AuditIssueHandler;
import burp.api.montoya.scanner.audit.issues.AuditIssue;

import java.util.List;

public class ScannerListener implements AuditIssueHandler {
    private final RaptorClient client;
    private final EventBatcher batcher;

    public ScannerListener(RaptorClient client, EventBatcher batcher) {
        this.client = client;
        this.batcher = batcher;
    }

    @Override
    public void handleNewAuditIssue(AuditIssue issue) {
        if (!client.isStarted() || issue == null || issue.baseUrl() == null) {
            return;
        }
        String host;
        String path;
        try {
            java.net.URI uri = java.net.URI.create(String.valueOf(issue.baseUrl()));
            host = Redactor.normalizeHost(uri.getHost());
            path = Redactor.pathOnly(uri.getRawPath());
        } catch (Exception ignored) {
            return;
        }
        if (!client.hostAllowed(host)) {
            return;
        }
        String name = issue.name() == null ? "" : issue.name();
        String detail = issue.detail() == null ? "" : issue.detail();
        if (detail.length() > 800) {
            detail = detail.substring(0, 800);
        }
        String severity = issue.severity() == null ? "" : issue.severity().name();
        String confidence = issue.confidence() == null ? "" : issue.confidence().name();
        HttpRequest request = null;
        HttpResponse response = null;
        try {
            List<HttpRequestResponse> messages = issue.requestResponses();
            if (messages != null && !messages.isEmpty() && messages.get(0) != null) {
                request = messages.get(0).request();
                response = messages.get(0).response();
            }
        } catch (Exception ignored) {
            // Issue name still ships without HTTP.
        }
        if (request != null) {
            String json = EventJson.from("scanner", request, response, "");
            batcher.offer(EventJson.withIssue(json, name, severity, confidence, detail));
            return;
        }
        batcher.offer(EventJson.scannerFallback(host, path, name, severity, confidence, detail));
    }
}
