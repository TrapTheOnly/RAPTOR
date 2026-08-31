package raptor.burp;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class EventBatcher {
    private final RaptorClient client;
    private final ConcurrentLinkedQueue<String> queue = new ConcurrentLinkedQueue<>();
    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread thread = new Thread(r, "raptor-burp-ingest");
        thread.setDaemon(true);
        return thread;
    });

    public EventBatcher(RaptorClient client) {
        this.client = client;
        executor.scheduleAtFixedRate(this::flush, 2, 2, TimeUnit.SECONDS);
    }

    public void offer(String eventJson) {
        if (eventJson == null || eventJson.isBlank()) {
            return;
        }
        queue.add(eventJson);
        if (queue.size() >= 50) {
            flush();
        }
    }

    public void flush() {
        List<String> batch = new ArrayList<>();
        String item;
        while (batch.size() < 50 && (item = queue.poll()) != null) {
            batch.add(item);
        }
        if (!batch.isEmpty()) {
            client.ingest(batch);
        }
    }
}
