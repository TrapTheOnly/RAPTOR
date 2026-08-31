package raptor.burp;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RaptorClientTest {
    @Test
    void reusesAgentOnlyForTheBoundWaveToken() {
        assertFalse(RaptorClient.shouldReuseAgent("", "old", "new"));
        assertFalse(RaptorClient.shouldReuseAgent("agent", "northwind-token", "test-token"));
        assertFalse(RaptorClient.shouldReuseAgent("agent", "", "test-token"));
        assertTrue(RaptorClient.shouldReuseAgent("agent", "same-token", "same-token"));
        assertTrue(RaptorClient.shouldReuseAgent("agent", "same-token", ""));
    }

    @Test
    void extractsWaveMetaAndHostsFromHeartbeatJson() {
        String json = "{\"ok\":true,\"wave_id\":42,\"wave_name\":\"Test wave\","
                + "\"hosts\":[\"app.test.local\",\"api.test.local\"]}";
        assertEquals(42, RaptorClient.extractJsonInt(json, "wave_id"));
        assertEquals("Test wave", RaptorClient.extractJsonString(json, "wave_name"));
        assertEquals(
                java.util.List.of("app.test.local", "api.test.local"),
                RaptorClient.extractJsonStringArray(json, "hosts")
        );
    }

    @Test
    void parsesDraftsFromAgentPayload() {
        String json = "{\"drafts\":[{\"id\":\"f-1\",\"title\":\"GET /admin on app\"},"
                + "{\"title\":\"Older draft\",\"id\":\"f-2\"}]}";
        java.util.List<RaptorClient.Draft> drafts = RaptorClient.parseDrafts(json);
        assertEquals(2, drafts.size());
        assertEquals("f-1", drafts.get(0).id());
        assertEquals("GET /admin on app", drafts.get(0).title());
        assertEquals("f-2", drafts.get(1).id());
    }

    @Test
    void payloadGuessPrefersQueryDiff() {
        assertEquals("id=2", Redactor.payloadGuess("id=1", "id=2", "{}", "{}"));
        assertTrue(Redactor.payloadGuess("", "", "a=1", "a=1").isEmpty());
        assertEquals("name=ada", Redactor.payloadGuess("", "", "user=bob", "name=ada"));
    }

    @Test
    void stripsCompactJwtsFromBodies() {
        String token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhIn0.signature";
        assertEquals("Bearer [jwt]", Redactor.stripJwts("Bearer " + token));
    }
}
