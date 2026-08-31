package raptor.burp;

import burp.api.montoya.MontoyaApi;
import burp.api.montoya.http.message.HttpRequestResponse;
import burp.api.montoya.http.message.requests.HttpRequest;
import burp.api.montoya.ui.contextmenu.ContextMenuEvent;
import burp.api.montoya.ui.contextmenu.ContextMenuItemsProvider;

import javax.swing.JMenuItem;
import javax.swing.JOptionPane;
import java.awt.Component;
import java.util.ArrayList;
import java.util.List;

public class RaptorContextMenu implements ContextMenuItemsProvider {
    private final MontoyaApi api;
    private final RaptorClient client;

    public RaptorContextMenu(MontoyaApi api, RaptorClient client) {
        this.api = api;
        this.client = client;
    }

    @Override
    public List<Component> provideMenuItems(ContextMenuEvent event) {
        HttpRequestResponse message = selected(event);
        if (message == null || message.request() == null) {
            return List.of();
        }
        JMenuItem auth = new JMenuItem("Send as authentication request");
        auth.addActionListener(ignored -> sendAuth(message.request()));
        JMenuItem jwt = new JMenuItem("Send JWT");
        jwt.addActionListener(ignored -> sendJwt(message.request()));
        JMenuItem evidence = new JMenuItem("Send as evidence");
        evidence.addActionListener(ignored -> sendEvidence(message));
        List<Component> items = new ArrayList<>();
        items.add(auth);
        items.add(jwt);
        items.add(evidence);
        return items;
    }

    private void sendAuth(HttpRequest request) {
        if (!client.isStarted()) {
            warn("Start RAPTOR from the RAPTOR tab first.");
            return;
        }
        AuthTemplateDialog.Result result = AuthTemplateDialog.show(api.userInterface().swingUtils().suiteFrame(), request);
        if (result == null) {
            return;
        }
        try {
            client.sendAuthTemplate(result.rawRequest(), result.host(), result.method(), result.path(),
                    result.placeholderMap(), result.extractRule());
            info("Stored the authentication request. Values come from security details notes, not this live body.");
        } catch (Exception exc) {
            warn("Could not store the authentication request: " + exc.getMessage());
        }
    }

    private void sendJwt(HttpRequest request) {
        if (!client.isStarted()) {
            warn("Start RAPTOR from the RAPTOR tab first.");
            return;
        }
        String jwt = Redactor.findJwt(
                Redactor.header(request, "Authorization"),
                Redactor.header(request, "Cookie"),
                request.bodyToString()
        );
        if (jwt.isEmpty()) {
            warn("No JWT found in Authorization, Cookie, or the request body.");
            return;
        }
        try {
            client.sendJwt(Redactor.hostOf(request), Redactor.pathOnly(request.path()), jwt);
            info("Queued the Kali JWT suite. RAPTOR will open a proposal, not a finding.");
        } catch (Exception exc) {
            warn("Could not queue the JWT job: " + exc.getMessage());
        }
    }

    private void sendEvidence(HttpRequestResponse message) {
        if (!client.isStarted()) {
            warn("Start RAPTOR from the RAPTOR tab first.");
            return;
        }
        try {
            List<RaptorClient.Draft> drafts = client.listDrafts();
            String findingId = EvidenceDialog.pickFindingId(api.userInterface().swingUtils().suiteFrame(), drafts);
            if (findingId == null) {
                return;
            }
            String json = EventJson.from("repeater", message.request(), message.response(), "");
            String response = client.sendEvidence(json, findingId);
            String id = RaptorClient.extractJsonString(response, "finding_id");
            client.announce(id.isEmpty() ? "Draft filed." : "Draft filed " + id + ".");
        } catch (Exception exc) {
            warn("Could not file evidence: " + exc.getMessage());
        }
    }

    private HttpRequestResponse selected(ContextMenuEvent event) {
        try {
            if (event.messageEditorRequestResponse().isPresent()) {
                return event.messageEditorRequestResponse().get().requestResponse();
            }
        } catch (Exception ignored) {
            // Fall through to the selection list.
        }
        try {
            List<HttpRequestResponse> selected = event.selectedRequestResponses();
            if (selected != null && !selected.isEmpty()) {
                return selected.get(0);
            }
        } catch (Exception ignored) {
            return null;
        }
        return null;
    }

    private void warn(String message) {
        JOptionPane.showMessageDialog(api.userInterface().swingUtils().suiteFrame(), message, "RAPTOR", JOptionPane.WARNING_MESSAGE);
    }

    private void info(String message) {
        JOptionPane.showMessageDialog(api.userInterface().swingUtils().suiteFrame(), message, "RAPTOR", JOptionPane.INFORMATION_MESSAGE);
    }
}
