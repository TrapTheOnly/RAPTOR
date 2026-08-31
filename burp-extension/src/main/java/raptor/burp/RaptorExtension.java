package raptor.burp;

import burp.api.montoya.BurpExtension;
import burp.api.montoya.MontoyaApi;

public class RaptorExtension implements BurpExtension {
    @Override
    public void initialize(MontoyaApi api) {
        api.extension().setName("RAPTOR");
        RaptorClient client = new RaptorClient(api);
        EventBatcher batcher = new EventBatcher(client);
        api.userInterface().registerSuiteTab("RAPTOR", new RaptorPanel(api, client, batcher));
        api.http().registerHttpHandler(new IngestHttpHandler(client, batcher));
        api.userInterface().registerContextMenuItemsProvider(new RaptorContextMenu(api, client));
        try {
            api.scanner().registerAuditIssueHandler(new ScannerListener(client, batcher));
        } catch (Throwable ignored) {
            api.logging().logToOutput("RAPTOR: Scanner listener not available (Community Edition).");
        }
        api.logging().logToOutput("RAPTOR Burp Live loaded. Start from this tab — RAPTOR never dials Burp.");
    }
}
