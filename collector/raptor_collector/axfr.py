"""Optional AXFR export with TSIG."""

from typing import List, Optional

from raptor_collector.zone import ResourceRecord, parse_zone_records


def axfr_zone(
    zone: str,
    nameserver: str,
    *,
    tsig_name: str = "",
    tsig_secret: str = "",
    tsig_algorithm: str = "hmac-sha256",
    timeout: float = 15.0,
) -> List[ResourceRecord]:
    try:
        import dns.query
        import dns.zone
        import dns.tsigkeyring
        import dns.tsig
    except ImportError as exc:
        raise RuntimeError("dnspython is required for AXFR") from exc

    keyring = None
    algorithm = None
    if tsig_name and tsig_secret:
        keyring = dns.tsigkeyring.from_text({tsig_name: tsig_secret})
        algorithm = getattr(dns.tsig, tsig_algorithm.replace("-", "_").upper(), dns.tsig.HMAC_SHA256)

    transferred = dns.zone.from_xfr(
        dns.query.xfr(
            nameserver,
            zone,
            keyring=keyring,
            keyalgorithm=algorithm,
            timeout=timeout,
            lifetime=timeout,
        )
    )
    text = transferred.to_text(relative=False)
    return parse_zone_records(text, zone)
