//go:build linux

package service

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCopyExecutableRoundTrip(t *testing.T) {
	dir := t.TempDir()
	src := filepath.Join(dir, "src")
	dst := filepath.Join(dir, "dst")
	if err := os.WriteFile(src, []byte("#!/bin/sh\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := copyExecutable(src, dst); err != nil {
		t.Fatal(err)
	}
	got, err := os.ReadFile(dst)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "#!/bin/sh\n" {
		t.Fatalf("copied bytes = %q", got)
	}
	if err := copyExecutable(dst, dst); err != nil {
		t.Fatal(err)
	}
}
