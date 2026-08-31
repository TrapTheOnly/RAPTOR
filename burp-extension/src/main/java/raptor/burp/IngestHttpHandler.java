package raptor.burp;

import burp.api.montoya.core.ToolType;
import burp.api.montoya.http.handler.HttpHandler;
import burp.api.montoya.http.handler.HttpRequestToBeSent;
import burp.api.montoya.http.handler.HttpResponseReceived;
import burp.api.montoya.http.handler.RequestToBeSentAction;
import burp.api.montoya.http.handler.ResponseReceivedAction;
import burp.api.montoya.http.message.requests.HttpRequest;

import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class IngestHttpHandler implements HttpHandler {
    private final RaptorClient client;
    private final EventBatcher batcher;
    private final Map<String, IntruderState> intruder = new ConcurrentHashMap<>();

    public IngestHttpHandler(RaptorClient client, EventBatcher batcher) {
        this.client = client;
        this.batcher = batcher;
    }

    @Override
    public RequestToBeSentAction handleHttpRequestToBeSent(HttpRequestToBeSent requestToBeSent) {
        return RequestToBeSentAction.continueWith(requestToBeSent);
    }

    @Override
    public ResponseReceivedAction handleHttpResponseReceived(HttpResponseReceived responseReceived) {
        if (!client.isStarted()) {
            return ResponseReceivedAction.continueWith(responseReceived);
        }
        ToolType tool;
        try {
            tool = responseReceived.toolSource().toolType();
        } catch (Exception ignored) {
            return ResponseReceivedAction.continueWith(responseReceived);
        }
        if (tool != ToolType.REPEATER && tool != ToolType.INTRUDER) {
            return ResponseReceivedAction.continueWith(responseReceived);
        }
        HttpRequest request = responseReceived.initiatingRequest();
        String host = Redactor.hostOf(request);
        if (!client.hostAllowed(host) || Redactor.isStatic(request.path())) {
            return ResponseReceivedAction.continueWith(responseReceived);
        }
        String body = request.bodyToString() == null ? "" : request.bodyToString();
        String responseBody = responseReceived.bodyToString() == null ? "" : responseReceived.bodyToString();
        String query = Redactor.queryOf(request);
        String toolName = tool == ToolType.REPEATER ? "repeater" : "intruder";
        int status = responseReceived.statusCode();
        int length = responseReceived.body() == null ? 0 : responseReceived.body().length();
        String payload = "";
        if (tool == ToolType.INTRUDER) {
            String keep = keepIntruder(host, request.method(), request.path(), query, body, status, length, responseBody);
            if (keep == null) {
                return ResponseReceivedAction.continueWith(responseReceived);
            }
            payload = keep;
        }
        batcher.offer(EventJson.from(toolName, request, responseReceived, payload));
        return ResponseReceivedAction.continueWith(responseReceived);
    }

    /** @return payload guess, or null to drop this sample */
    private String keepIntruder(String host, String method, String path, String query, String body,
                                int status, int length, String responseBody) {
        String attack = method.toUpperCase(Locale.ROOT) + "|" + host + "|" + Redactor.pathOnly(path).split("\\?", 2)[0];
        IntruderState state = intruder.computeIfAbsent(attack, ignored -> new IntruderState());
        synchronized (state) {
            if (!state.baseSent) {
                state.baseSent = true;
                state.baseLength = length;
                state.baseBody = body == null ? "" : body;
                state.baseQuery = query == null ? "" : query;
                return "";
            }
            if (state.samples >= 20) {
                return null;
            }
            boolean interesting = status >= 500
                    || Math.abs(length - state.baseLength) >= 64
                    || looksLikeError(body)
                    || looksLikeError(responseBody);
            if (!interesting) {
                return null;
            }
            state.samples += 1;
            return Redactor.payloadGuess(state.baseQuery, query, state.baseBody, body);
        }
    }

    private static boolean looksLikeError(String body) {
        String lowered = body == null ? "" : body.toLowerCase(Locale.ROOT);
        return lowered.contains("exception") || lowered.contains("traceback")
                || lowered.contains("sql syntax") || lowered.contains("stack trace")
                || lowered.contains("error");
    }

    private static final class IntruderState {
        private boolean baseSent;
        private int baseLength;
        private int samples;
        private String baseBody = "";
        private String baseQuery = "";
    }
}
