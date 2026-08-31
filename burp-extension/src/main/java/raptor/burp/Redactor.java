package raptor.burp;

import burp.api.montoya.http.message.HttpHeader;
import burp.api.montoya.http.message.requests.HttpRequest;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class Redactor {
    private static final int BODY_CAP = 16 * 1024;
    private static final int PAYLOAD_CAP = 200;
    private static final Set<String> SECRET_HEADERS = Set.of(
            "cookie", "set-cookie", "authorization", "proxy-authorization", "x-api-key",
            "x-auth-token", "x-access-token", "x-csrf-token"
    );
    private static final Set<String> STATIC_EXT = Set.of(
            ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
            ".woff", ".woff2", ".ttf", ".map", ".webp"
    );
    private static final Pattern JWT = Pattern.compile("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+");

    private Redactor() {}

    public static String normalizeHost(String host) {
        if (host == null) {
            return "";
        }
        String value = host.trim().toLowerCase(Locale.ROOT);
        if (value.startsWith("[") && value.contains("]")) {
            value = value.substring(1, value.indexOf(']'));
        }
        int colon = value.lastIndexOf(':');
        if (colon > 0 && value.indexOf(':') == colon) {
            value = value.substring(0, colon);
        }
        return value;
    }

    public static String pathOnly(String path) {
        if (path == null || path.isBlank()) {
            return "/";
        }
        String value = path.startsWith("/") ? path : "/" + path;
        int hash = value.indexOf('#');
        if (hash >= 0) {
            value = value.substring(0, hash);
        }
        return value;
    }

    public static boolean isStatic(String path) {
        String cleaned = pathOnly(path).split("\\?", 2)[0].toLowerCase(Locale.ROOT);
        for (String ext : STATIC_EXT) {
            if (cleaned.endsWith(ext)) {
                return true;
            }
        }
        return false;
    }

    public static String capBody(String body) {
        if (body == null || body.isEmpty()) {
            return "";
        }
        return body.length() > BODY_CAP ? body.substring(0, BODY_CAP) : body;
    }

    public static String capPayload(String value) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        String stripped = stripJwts(value);
        return stripped.length() > PAYLOAD_CAP ? stripped.substring(0, PAYLOAD_CAP) : stripped;
    }

    public static String stripJwts(String value) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        return JWT.matcher(value).replaceAll("[jwt]");
    }

    public static String queryOf(HttpRequest request) {
        try {
            String path = request.path();
            int q = path.indexOf('?');
            return q >= 0 ? path.substring(q + 1) : "";
        } catch (Exception ignored) {
            return "";
        }
    }

    public static String payloadGuess(String baseQuery, String query, String baseBody, String body) {
        String q = query == null ? "" : query;
        String bq = baseQuery == null ? "" : baseQuery;
        if (!q.equals(bq) && !q.isEmpty()) {
            return capPayload(q);
        }
        String b = body == null ? "" : body;
        String bb = baseBody == null ? "" : baseBody;
        if (b.equals(bb) || b.isEmpty()) {
            return "";
        }
        int i = 0;
        int n = Math.min(b.length(), bb.length());
        while (i < n && b.charAt(i) == bb.charAt(i)) {
            i++;
        }
        int from = Math.max(0, i - 16);
        return capPayload(b.substring(from));
    }

    public static String capBody(byte[] body) {
        if (body == null || body.length == 0) {
            return "";
        }
        return capBody(new String(body, StandardCharsets.UTF_8));
    }

    public static String redactHeadersJson(List<HttpHeader> headers) {
        StringBuilder out = new StringBuilder("{");
        boolean first = true;
        if (headers != null) {
            for (HttpHeader header : headers) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                String name = header.name();
                String value = SECRET_HEADERS.contains(name.toLowerCase(Locale.ROOT)) ? "[REDACTED]" : header.value();
                out.append('"').append(RaptorClient.jsonEscape(name)).append("\":\"")
                        .append(RaptorClient.jsonEscape(value)).append('"');
            }
        }
        return out.append('}').toString();
    }

    public static String dedupeKey(String tool, String method, String host, String path, String body) {
        String normalized = (body == null ? "" : body).replaceAll("\\s+", " ").trim();
        String raw = String.join("|",
                tool == null ? "" : tool.toLowerCase(Locale.ROOT),
                method == null ? "" : method.toUpperCase(Locale.ROOT),
                normalizeHost(host),
                pathOnly(path).split("\\?", 2)[0],
                normalized);
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (Exception exc) {
            return Integer.toHexString(raw.hashCode());
        }
    }

    public static String findJwt(String... parts) {
        for (String part : parts) {
            if (part == null) {
                continue;
            }
            Matcher matcher = JWT.matcher(part);
            if (matcher.find()) {
                return matcher.group();
            }
        }
        return "";
    }

    public static String hostOf(HttpRequest request) {
        try {
            return normalizeHost(request.httpService().host());
        } catch (Exception ignored) {
            return normalizeHost(header(request, "Host"));
        }
    }

    public static String header(HttpRequest request, String name) {
        try {
            return request.headerValue(name) == null ? "" : request.headerValue(name);
        } catch (Exception ignored) {
            return "";
        }
    }
}
