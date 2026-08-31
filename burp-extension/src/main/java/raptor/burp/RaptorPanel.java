package raptor.burp;

import burp.api.montoya.MontoyaApi;

import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingUtilities;
import java.awt.BorderLayout;
import java.awt.FlowLayout;
import java.awt.GridLayout;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class RaptorPanel extends JPanel {
    private final RaptorClient client;
    private final JTextArea status = new JTextArea(5, 40);
    private final ScheduledExecutorService heartbeats = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread thread = new Thread(r, "raptor-burp-heartbeat");
        thread.setDaemon(true);
        return thread;
    });

    public RaptorPanel(MontoyaApi api, RaptorClient client, EventBatcher batcher) {
        this.client = client;
        client.setStatusSink(text -> SwingUtilities.invokeLater(() -> status.setText(text)));
        setLayout(new BorderLayout(12, 12));
        setBorder(BorderFactory.createEmptyBorder(16, 16, 16, 16));

        JTextField url = new JTextField(client.url(), 40);
        JTextField token = new JTextField(client.enrollToken(), 40);
        JButton start = new JButton("Start");
        JButton stop = new JButton("Stop");
        stop.setEnabled(false);

        status.setLineWrap(true);
        status.setWrapStyleWord(true);
        status.setEditable(false);
        status.setOpaque(false);
        status.setBorder(null);
        status.setText("Stopped. RAPTOR never opens Burp — you Start here.");
        JScrollPane statusScroll = new JScrollPane(status);
        statusScroll.setBorder(null);
        statusScroll.setHorizontalScrollBarPolicy(JScrollPane.HORIZONTAL_SCROLLBAR_NEVER);

        JPanel form = new JPanel(new GridLayout(0, 1, 6, 6));
        form.add(new JLabel("RAPTOR URL (the deployment testers already use)"));
        form.add(url);
        form.add(new JLabel("Wave token (minted on the wave page — raptor_burp_enroll_…)"));
        form.add(token);

        JPanel buttons = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        buttons.add(start);
        buttons.add(stop);

        add(form, BorderLayout.NORTH);
        add(statusScroll, BorderLayout.CENTER);
        add(buttons, BorderLayout.SOUTH);

        start.addActionListener(event -> {
            client.setUrl(url.getText());
            client.setEnrollToken(token.getText());
            start.setEnabled(false);
            status.setText("Starting…");
            new Thread(() -> {
                try {
                    String message = client.start();
                    SwingUtilities.invokeLater(() -> {
                        status.setText(message);
                        stop.setEnabled(true);
                    });
                } catch (Exception exc) {
                    SwingUtilities.invokeLater(() -> {
                        status.setText("Start failed: " + exc.getMessage());
                        start.setEnabled(true);
                    });
                }
            }, "raptor-burp-start").start();
        });
        stop.addActionListener(event -> {
            client.stop();
            batcher.flush();
            start.setEnabled(true);
            stop.setEnabled(false);
            status.setText("Stopped. This wave stays saved until you paste a different token and Start.");
        });

        heartbeats.scheduleAtFixedRate(() -> {
            if (!client.isStarted()) {
                return;
            }
            try {
                client.heartbeat();
                SwingUtilities.invokeLater(() -> status.setText(client.statusLine("Live.")));
            } catch (Exception exc) {
                SwingUtilities.invokeLater(() -> status.setText("Heartbeat failed: " + exc.getMessage()));
            }
        }, 60, 60, TimeUnit.SECONDS);
    }
}
