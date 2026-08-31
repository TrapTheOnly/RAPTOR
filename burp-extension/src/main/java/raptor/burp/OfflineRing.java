package raptor.burp;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;

public class OfflineRing {
    private static final long CAP = 5L * 1024 * 1024;
    private final Path file;

    public OfflineRing() {
        this.file = Path.of(System.getProperty("user.home"), ".raptor-burp", "queue.jsonl");
    }

    public synchronized void append(String json) {
        try {
            Files.createDirectories(file.getParent());
            if (Files.exists(file) && Files.size(file) > CAP) {
                List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
                int drop = Math.max(1, lines.size() / 2);
                Files.write(file, lines.subList(drop, lines.size()), StandardCharsets.UTF_8);
            }
            Files.writeString(file, json.replace('\n', ' ') + "\n", StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (Exception ignored) {
            // Never block Repeater on disk errors.
        }
    }

    public synchronized List<String> drain() {
        try {
            if (!Files.exists(file)) {
                return List.of();
            }
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            Files.deleteIfExists(file);
            List<String> kept = new ArrayList<>();
            for (String line : lines) {
                if (!line.isBlank()) {
                    kept.add(line);
                }
            }
            return kept;
        } catch (Exception ignored) {
            return List.of();
        }
    }
}
