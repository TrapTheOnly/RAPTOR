package zone

import "testing"

func TestTrailingDotIsAbsolute(t *testing.T) {
	recs := Parse("$ORIGIN example.com.\nwww.example.com. IN A 10.0.0.2\n", "example.com")
	if len(recs) != 1 || recs[0].FQDN != "www.example.com" {
		t.Fatalf("got %#v", recs)
	}
}

func TestSOASerialFolded(t *testing.T) {
	text := `
$ORIGIN example.com.
@ IN SOA ns1.example.com. hostmaster.example.com. (
    2024020202
    3600 600 86400 3600 )
`
	recs := Parse(text, "example.com")
	if SOASerial(recs) != "2024020202" {
		t.Fatalf("serial=%q records=%#v", SOASerial(recs), recs)
	}
}
