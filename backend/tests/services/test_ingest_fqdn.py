from app.services.ingest.fqdn import normalize_fqdn


def test_normalize_fqdn_apex_and_relative():
    assert normalize_fqdn("@", "example.com") == "example.com"
    assert normalize_fqdn("www", "example.com") == "www.example.com"


def test_normalize_fqdn_trailing_dot_is_absolute():
    assert normalize_fqdn("www.example.com.", "example.com") == "www.example.com"
    assert normalize_fqdn("mail.other.org.", "example.com") == "mail.other.org"


def test_normalize_fqdn_does_not_double_append_origin():
    assert normalize_fqdn("www.example.com", "example.com") == "www.example.com"
