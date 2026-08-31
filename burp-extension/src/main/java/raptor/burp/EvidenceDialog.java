package raptor.burp;

import javax.swing.JComboBox;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import java.awt.Component;
import java.awt.GridLayout;
import java.util.List;

public final class EvidenceDialog {
    private EvidenceDialog() {}

    /** null cancelled, empty string new draft, otherwise finding id */
    public static String pickFindingId(Component parent, List<RaptorClient.Draft> drafts) {
        if (drafts == null || drafts.isEmpty()) {
            return "";
        }
        String[] labels = new String[drafts.size() + 1];
        labels[0] = "New draft finding";
        for (int i = 0; i < drafts.size(); i++) {
            RaptorClient.Draft draft = drafts.get(i);
            String id = draft.id() == null ? "" : draft.id();
            String shortId = id.length() > 8 ? id.substring(0, 8) : id;
            String title = draft.title() == null || draft.title().isBlank() ? shortId : draft.title();
            labels[i + 1] = title + " (" + shortId + ")";
        }
        JComboBox<String> box = new JComboBox<>(labels);
        JPanel panel = new JPanel(new GridLayout(0, 1, 4, 4));
        panel.add(new JLabel("Attach this request/response to a draft, or file a new one."));
        panel.add(box);
        int choice = JOptionPane.showConfirmDialog(
                parent, panel, "Send as evidence", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE);
        if (choice != JOptionPane.OK_OPTION) {
            return null;
        }
        int idx = box.getSelectedIndex();
        if (idx <= 0) {
            return "";
        }
        return drafts.get(idx - 1).id();
    }
}
