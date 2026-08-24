from app.integrations.keycloak.client import KeycloakClient
from app.integrations.keycloak.constants import (
    FIRST_BROKER_AUTO_LINK,
    FIRST_BROKER_DETECT_EXISTING,
    FIRST_BROKER_FLOW,
)


def _copied_flow_executions():
    return [
        {
            "id": "review",
            "providerId": "idp-review-profile",
            "requirement": "REQUIRED",
            "level": 0,
            "index": 0,
        },
        {
            "id": "create-flow",
            "authenticationFlow": True,
            "displayName": "User creation or linking",
            "requirement": "REQUIRED",
            "level": 0,
            "index": 1,
        },
        {
            "id": "auto-link",
            "providerId": FIRST_BROKER_AUTO_LINK,
            "requirement": "ALTERNATIVE",
            "level": 0,
            "index": 2,
        },
    ]


class _FakeBrokerClient(KeycloakClient):
    def __init__(self, executions, aliases=None, idps=None):
        super().__init__()
        self.executions = [dict(row) for row in executions]
        self.flow_ids = {FIRST_BROKER_FLOW: "flow-1"} if aliases is None or FIRST_BROKER_FLOW in aliases else {}
        if aliases is not None:
            self.flow_ids = {alias: f"flow-{alias}" for alias in aliases}
        self.idps = {row["alias"]: dict(row) for row in (idps or [])}
        self.posts = []
        self.deleted_flows = []
        self.created_flows = []
        self.idp_flow_updates = []

    def json(self, method, path, expected=None, **kwargs):
        if path == "/authentication/flows":
            return [{"alias": alias, "id": flow_id} for alias, flow_id in self.flow_ids.items()]
        if path == f"/authentication/flows/{FIRST_BROKER_FLOW}/executions":
            return [dict(row) for row in self.executions]
        if path == "/identity-provider/instances":
            return [dict(row) for row in self.idps.values()]
        if path.startswith("/identity-provider/instances/"):
            alias = path.rsplit("/", 1)[-1]
            return dict(self.idps[alias]) if alias in self.idps else None
        return []

    def request(self, method, path, json=None, expected=None, **kwargs):
        payload = json or {}
        if method == "POST" and path == "/authentication/flows":
            alias = str(payload.get("alias") or "")
            self.created_flows.append(alias)
            self.flow_ids[alias] = f"flow-{alias}"
            self.executions = []
            return None
        if method == "DELETE" and path.startswith("/authentication/flows/"):
            flow_id = path.rsplit("/", 1)[-1]
            self.deleted_flows.append(flow_id)
            alias = next((name for name, value in self.flow_ids.items() if value == flow_id), None)
            if alias:
                self.flow_ids.pop(alias, None)
            self.executions = []
            return None
        if method == "POST" and path.endswith("/executions/execution"):
            provider = str(payload.get("provider") or "")
            self.posts.append(provider)
            self.executions.append(
                {
                    "id": provider,
                    "providerId": provider,
                    "requirement": "DISABLED",
                    "level": 0,
                    "index": len([row for row in self.executions if int(row.get("level") or 0) == 0]),
                }
            )
            return None
        if method == "PUT" and path.endswith("/executions"):
            for row in self.executions:
                if row.get("id") == payload.get("id"):
                    row["requirement"] = payload.get("requirement")
            return None
        if method == "PUT" and path.startswith("/identity-provider/instances/"):
            alias = path.rsplit("/", 1)[-1]
            self.idps[alias] = dict(payload)
            self.idp_flow_updates.append((alias, payload.get("firstBrokerLoginFlowAlias")))
            return None
        return None


def test_first_broker_flow_recreates_copied_flow_as_detect_then_auto_link():
    client = _FakeBrokerClient(
        _copied_flow_executions(),
        idps=[{"alias": "test-oidc", "firstBrokerLoginFlowAlias": FIRST_BROKER_FLOW}],
    )
    assert client.ensure_raptor_first_broker_flow() == FIRST_BROKER_FLOW
    assert client.deleted_flows == ["flow-1"]
    assert client.created_flows == [FIRST_BROKER_FLOW]
    assert client.posts == [FIRST_BROKER_DETECT_EXISTING, FIRST_BROKER_AUTO_LINK]
    enabled = client._top_level_enabled_executions(client.executions)
    assert [row["providerId"] for row in enabled] == [FIRST_BROKER_DETECT_EXISTING, FIRST_BROKER_AUTO_LINK]
    assert [row["requirement"] for row in enabled] == ["REQUIRED", "REQUIRED"]
    assert client.idp_flow_updates[-1] == ("test-oidc", FIRST_BROKER_FLOW)


def test_first_broker_flow_creates_clean_flow_when_missing():
    client = _FakeBrokerClient([], aliases=[])
    assert client.ensure_raptor_first_broker_flow() == FIRST_BROKER_FLOW
    assert client.created_flows == [FIRST_BROKER_FLOW]
    assert client.posts == [FIRST_BROKER_DETECT_EXISTING, FIRST_BROKER_AUTO_LINK]


def test_first_broker_flow_leaves_clean_flow_alone():
    client = _FakeBrokerClient(
        [
            {
                "id": "detect",
                "providerId": FIRST_BROKER_DETECT_EXISTING,
                "requirement": "REQUIRED",
                "level": 0,
                "index": 0,
            },
            {
                "id": "link",
                "providerId": FIRST_BROKER_AUTO_LINK,
                "requirement": "REQUIRED",
                "level": 0,
                "index": 1,
            },
        ]
    )
    assert client.ensure_raptor_first_broker_flow() == FIRST_BROKER_FLOW
    assert client.deleted_flows == []
    assert client.created_flows == []
    assert client.posts == []
