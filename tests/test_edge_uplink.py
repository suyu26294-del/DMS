import edge_service.edge_server as edge_server


def test_default_uplink_is_http(monkeypatch):
    monkeypatch.setattr(edge_server, "EDGE_UPLINK", "http")
    srv = edge_server.EdgeServer()
    assert srv.uplink.__class__.__name__ == "HttpUplink"


def test_mqtt_uplink_selected(monkeypatch):
    monkeypatch.setattr(edge_server, "EDGE_UPLINK", "mqtt")
    srv = edge_server.EdgeServer()
    assert srv.uplink.__class__.__name__ == "MqttUplink"
