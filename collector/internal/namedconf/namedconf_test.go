package namedconf

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadIncludes(t *testing.T) {
	dir := t.TempDir()
	conf := filepath.Join(dir, "named.conf")
	local := filepath.Join(dir, "named.conf.local")
	if err := os.WriteFile(conf, []byte(`
zone "example.com" { type master; file "db.example.com"; };
include "named.conf.local";
`), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(local, []byte(`zone "corp.internal" { type master; file "/var/named/db.corp"; };`), 0o644); err != nil {
		t.Fatal(err)
	}
	zones := Load(conf)
	byName := map[string]BindZone{}
	for _, z := range zones {
		byName[z.Name] = z
	}
	if byName["example.com"].FilePath == "" || byName["corp.internal"].FilePath != "/var/named/db.corp" {
		t.Fatalf("%#v", zones)
	}
}
