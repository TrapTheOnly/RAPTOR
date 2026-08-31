package raptor.burp;

import burp.api.montoya.http.message.requests.HttpRequest;

import javax.swing.ButtonGroup;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JRadioButton;
import javax.swing.JTextField;
import java.awt.Component;
import java.awt.GridLayout;

public final class AuthTemplateDialog {
    private AuthTemplateDialog() {}

    public record Result(String rawRequest, String host, String method, String path,
                         String placeholderMap, String extractRule) {}

    public static Result show(Component parent, HttpRequest request) {
        JRadioButton userPass = new JRadioButton("Username and password fields in this request", true);
        JRadioButton tokenAlready = new JRadioButton("Token is already in a header");
        ButtonGroup group = new ButtonGroup();
        group.add(userPass);
        group.add(tokenAlready);
        JTextField userPath = new JTextField("body.form.username");
        JTextField passPath = new JTextField("body.form.password");
        JTextField extractType = new JTextField("header");
        JTextField extractName = new JTextField("Authorization");

        JPanel panel = new JPanel(new GridLayout(0, 1, 4, 4));
        panel.add(new JLabel("RAPTOR stores this request as a template. Live secrets are stripped."));
        panel.add(userPass);
        panel.add(tokenAlready);
        panel.add(new JLabel("Username field path"));
        panel.add(userPath);
        panel.add(new JLabel("Password field path"));
        panel.add(passPath);
        panel.add(new JLabel("Token extract type (header, cookie, json)"));
        panel.add(extractType);
        panel.add(new JLabel("Token extract name or JSON path"));
        panel.add(extractName);

        int choice = JOptionPane.showConfirmDialog(
                parent, panel, "Send as authentication request", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE);
        if (choice != JOptionPane.OK_OPTION) {
            return null;
        }
        String raw = stripLiveSecrets(request.toString(), userPath.getText(), passPath.getText());
        String placeholders = tokenAlready.isSelected()
                ? "{\"mode\":\"token_header\"}"
                : "{\"username\":\"" + RaptorClient.jsonEscape(userPath.getText())
                + "\",\"password\":\"" + RaptorClient.jsonEscape(passPath.getText()) + "\"}";
        String extract = "{\"type\":\"" + RaptorClient.jsonEscape(extractType.getText())
                + "\",\"name\":\"" + RaptorClient.jsonEscape(extractName.getText()) + "\"}";
        return new Result(
                raw,
                Redactor.hostOf(request),
                request.method(),
                Redactor.pathOnly(request.path()),
                placeholders,
                extract
        );
    }

    static String stripLiveSecrets(String raw, String userPath, String passPath) {
        String out = raw == null ? "" : raw;
        out = replaceField(out, lastSegment(userPath), "{{username}}");
        out = replaceField(out, lastSegment(passPath), "{{password}}");
        return out;
    }

    private static String lastSegment(String path) {
        if (path == null || path.isBlank()) {
            return "";
        }
        String[] parts = path.split("[.\\[\\]]");
        return parts[parts.length - 1];
    }

    private static String replaceField(String raw, String field, String placeholder) {
        if (field == null || field.isBlank()) {
            return raw;
        }
        return raw.replaceAll("(?i)(" + java.util.regex.Pattern.quote(field) + "\\s*[=:]\\s*)([^&\\s\"]+)",
                "$1" + placeholder);
    }
}
