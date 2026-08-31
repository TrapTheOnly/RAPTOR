package raptor.burp;

import burp.api.montoya.http.message.requests.HttpRequest;
import burp.api.montoya.http.message.responses.HttpResponse;

public final class EventJson {
    private EventJson() {}

    public static String from(String tool, HttpRequest request, HttpResponse response, String payload) {
        String host = Redactor.hostOf(request);
        String rawBody = request.bodyToString() == null ? "" : request.bodyToString();
        String body = Redactor.stripJwts(Redactor.capBody(rawBody));
        String query = Redactor.stripJwts(Redactor.queryOf(request));
        int status = 0;
        int length = 0;
        String responseBody = "";
        String responseHeaders = "{}";
        String rawResponse = "";
        if (response != null) {
            status = response.statusCode();
            length = response.body() == null ? 0 : response.body().length();
            rawResponse = response.bodyToString() == null ? "" : response.bodyToString();
            responseBody = Redactor.stripJwts(Redactor.capBody(rawResponse));
            try {
                responseHeaders = Redactor.redactHeadersJson(response.headers());
            } catch (Exception ignored) {
                responseHeaders = "{}";
            }
        }
        boolean jwtPresent = !Redactor.findJwt(
                Redactor.header(request, "Authorization"),
                Redactor.header(request, "Cookie"),
                rawBody,
                rawResponse
        ).isEmpty();
        String key = Redactor.dedupeKey(tool, request.method(), host, request.path(), body);
        StringBuilder out = new StringBuilder(256);
        out.append("{\"tool\":\"").append(RaptorClient.jsonEscape(tool))
                .append("\",\"method\":\"").append(RaptorClient.jsonEscape(request.method()))
                .append("\",\"host\":\"").append(RaptorClient.jsonEscape(host))
                .append("\",\"path\":\"").append(RaptorClient.jsonEscape(Redactor.pathOnly(request.path())))
                .append("\",\"query\":\"").append(RaptorClient.jsonEscape(query))
                .append("\",\"status\":").append(status)
                .append(",\"length\":").append(length)
                .append(",\"dedupe_key\":\"").append(key)
                .append("\",\"jwt_present\":").append(jwtPresent ? "true" : "false")
                .append(",\"payload\":\"").append(RaptorClient.jsonEscape(Redactor.capPayload(payload)))
                .append("\",\"headers\":").append(Redactor.redactHeadersJson(request.headers()))
                .append(",\"body\":\"").append(RaptorClient.jsonEscape(body))
                .append("\",\"response_headers\":").append(responseHeaders)
                .append(",\"response_body\":\"").append(RaptorClient.jsonEscape(responseBody))
                .append("\"}");
        return out.toString();
    }

    public static String withIssue(String json, String name, String severity, String confidence, String detail) {
        if (json == null || json.isEmpty() || !json.endsWith("}")) {
            return json;
        }
        return json.substring(0, json.length() - 1)
                + ",\"name\":\"" + RaptorClient.jsonEscape(name)
                + "\",\"severity\":\"" + RaptorClient.jsonEscape(severity)
                + "\",\"confidence\":\"" + RaptorClient.jsonEscape(confidence)
                + "\",\"detail\":\"" + RaptorClient.jsonEscape(detail) + "\"}";
    }

    public static String scannerFallback(String host, String path, String name, String severity,
                                         String confidence, String detail) {
        String key = Redactor.dedupeKey("scanner", "GET", host, path, name + "|" + detail);
        return "{\"tool\":\"scanner\",\"method\":\"GET\",\"host\":\"" + RaptorClient.jsonEscape(host)
                + "\",\"path\":\"" + RaptorClient.jsonEscape(path)
                + "\",\"name\":\"" + RaptorClient.jsonEscape(name)
                + "\",\"severity\":\"" + RaptorClient.jsonEscape(severity)
                + "\",\"confidence\":\"" + RaptorClient.jsonEscape(confidence)
                + "\",\"detail\":\"" + RaptorClient.jsonEscape(detail)
                + "\",\"dedupe_key\":\"" + key + "\"}";
    }
}
