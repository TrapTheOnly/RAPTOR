package axfr

import (
	"github.com/miekg/dns"
	"raptor-collector/internal/zone"
	"strings"
	"time"
)

func Transfer(zoneName, server, tsigName, tsigSecret, algorithm string) ([]zone.Record, error) {
	msg := new(dns.Msg)
	msg.SetAxfr(dns.Fqdn(zoneName))
	tr := &dns.Transfer{DialTimeout: 15 * time.Second, ReadTimeout: 15 * time.Second}
	if tsigName != "" && tsigSecret != "" {
		algo := dns.HmacSHA256
		switch strings.ToLower(algorithm) {
		case "hmac-sha1":
			algo = dns.HmacSHA1
		case "hmac-sha512":
			algo = dns.HmacSHA512
		}
		msg.SetTsig(dns.Fqdn(tsigName), algo, 300, time.Now().Unix())
		tr.TsigSecret = map[string]string{dns.Fqdn(tsigName): tsigSecret}
	}
	env, err := tr.In(msg, server)
	if err != nil {
		return nil, err
	}
	var text strings.Builder
	for e := range env {
		if e.Error != nil {
			return nil, e.Error
		}
		for _, rr := range e.RR {
			text.WriteString(rr.String())
			text.WriteByte('\n')
		}
	}
	return zone.Parse(text.String(), zoneName), nil
}
