package namedconf

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

type BindZone struct {
	Name     string
	FilePath string
	Type     string
}

var (
	zoneRe    = regexp.MustCompile(`(?is)zone\s+"([^"]+)"\s*(?:in\s+)?\{(.*?)\};`)
	fileRe    = regexp.MustCompile(`(?i)\bfile\s+"([^"]+)"`)
	typeRe    = regexp.MustCompile(`(?i)\btype\s+(\w+)`)
	includeRe = regexp.MustCompile(`(?i)\binclude\s+"([^"]+)"\s*;`)
	blockCmt  = regexp.MustCompile(`(?s)/\*.*?\*/`)
	lineCmt1  = regexp.MustCompile(`(?m)//.*$`)
	lineCmt2  = regexp.MustCompile(`(?m)#.*$`)
)

func stripComments(text string) string {
	text = blockCmt.ReplaceAllString(text, " ")
	text = lineCmt1.ReplaceAllString(text, " ")
	return lineCmt2.ReplaceAllString(text, " ")
}

func Parse(text, confDir string) []BindZone {
	cleaned := stripComments(text)
	var zones []BindZone
	for _, match := range zoneRe.FindAllStringSubmatch(cleaned, -1) {
		name := strings.ToLower(strings.TrimSuffix(strings.TrimSpace(match[1]), "."))
		body := match[2]
		filePath := ""
		if fm := fileRe.FindStringSubmatch(body); fm != nil {
			filePath = fm[1]
			if !filepath.IsAbs(filePath) && confDir != "" {
				filePath = filepath.Clean(filepath.Join(confDir, filePath))
			}
		}
		ztype := ""
		if tm := typeRe.FindStringSubmatch(body); tm != nil {
			ztype = strings.ToLower(tm[1])
		}
		zones = append(zones, BindZone{Name: name, FilePath: filePath, Type: ztype})
	}
	return zones
}

func Load(confPath string) []BindZone {
	seen := map[string]bool{}
	var zones []BindZone
	var walk func(string)
	walk = func(path string) {
		abs, err := filepath.Abs(path)
		if err != nil || seen[abs] {
			return
		}
		seen[abs] = true
		raw, err := os.ReadFile(abs)
		if err != nil {
			return
		}
		dir := filepath.Dir(abs)
		zones = append(zones, Parse(string(raw), dir)...)
		for _, inc := range includeRe.FindAllStringSubmatch(stripComments(string(raw)), -1) {
			included := inc[1]
			if !filepath.IsAbs(included) {
				included = filepath.Join(dir, included)
			}
			walk(included)
		}
	}
	walk(confPath)
	return zones
}
