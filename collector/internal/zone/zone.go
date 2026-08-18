package zone

import (
	"regexp"
	"strconv"
	"strings"
)

type Record struct {
	FQDN   string
	RRType string
	RData  string
	TTL    int
	Zone   string
}

var ttlRe = regexp.MustCompile(`(?i)^(\d+)([smhdw])?$`)

var classTokens = map[string]bool{"IN": true, "CH": true, "HS": true}
var keepTypes = map[string]bool{"A": true, "AAAA": true, "CNAME": true, "TXT": true, "MX": true, "NS": true, "SOA": true}

func NormalizeFQDN(name, origin string) string {
	rawName := strings.TrimSpace(name)
	rawOrigin := strings.TrimSuffix(strings.ToLower(strings.TrimSpace(origin)), ".")
	if rawName == "" || rawName == "@" || rawName == "." {
		return rawOrigin
	}
	absolute := strings.HasSuffix(rawName, ".")
	normalized := strings.ToLower(strings.TrimSuffix(rawName, "."))
	if normalized == "" {
		return rawOrigin
	}
	if absolute || rawOrigin == "" {
		return normalized
	}
	if normalized == rawOrigin || strings.HasSuffix(normalized, "."+rawOrigin) {
		return normalized
	}
	return normalized + "." + rawOrigin
}

func parseTTL(token string) (int, bool) {
	m := ttlRe.FindStringSubmatch(strings.TrimSpace(token))
	if m == nil {
		return 0, false
	}
	value, _ := strconv.Atoi(m[1])
	mult := 1
	switch strings.ToLower(m[2]) {
	case "m":
		mult = 60
	case "h":
		mult = 3600
	case "d":
		mult = 86400
	case "w":
		mult = 604800
	}
	return value * mult, true
}

func stripComment(line string) string {
	inQuote := false
	var b strings.Builder
	for _, r := range line {
		if r == '"' {
			inQuote = !inQuote
			b.WriteRune(r)
			continue
		}
		if r == ';' && !inQuote {
			break
		}
		b.WriteRune(r)
	}
	return strings.TrimRight(b.String(), " \t")
}

func unfold(text string) []string {
	depth := 0
	var buf []string
	var lines []string
	for _, raw := range strings.Split(text, "\n") {
		stripped := stripComment(raw)
		if strings.TrimSpace(stripped) == "" && depth == 0 {
			continue
		}
		depth += strings.Count(stripped, "(") - strings.Count(stripped, ")")
		buf = append(buf, strings.ReplaceAll(strings.ReplaceAll(stripped, "(", " "), ")", " "))
		if depth <= 0 {
			joined := strings.Join(trimAll(buf), " ")
			if strings.TrimSpace(joined) != "" {
				lines = append(lines, strings.TrimSpace(joined))
			}
			buf = nil
			depth = 0
		}
	}
	if len(buf) > 0 {
		joined := strings.Join(trimAll(buf), " ")
		if strings.TrimSpace(joined) != "" {
			lines = append(lines, strings.TrimSpace(joined))
		}
	}
	return lines
}

func trimAll(parts []string) []string {
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if s := strings.TrimSpace(p); s != "" {
			out = append(out, s)
		}
	}
	return out
}

var tokenRe = regexp.MustCompile(`"[^"]*"|\S+`)

func Parse(text, origin string) []Record {
	current := NormalizeFQDN(origin, "")
	var defaultTTL int
	lastOwner := ""
	var records []Record
	for _, line := range unfold(text) {
		upper := strings.ToUpper(line)
		if strings.HasPrefix(upper, "$ORIGIN") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				current = NormalizeFQDN(parts[1], current)
				lastOwner = current
			}
			continue
		}
		if strings.HasPrefix(upper, "$TTL") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				if ttl, ok := parseTTL(parts[1]); ok {
					defaultTTL = ttl
				}
			}
			continue
		}
		if strings.HasPrefix(line, "$") {
			continue
		}
		tokens := tokenRe.FindAllString(line, -1)
		if len(tokens) == 0 {
			continue
		}
		owner := lastOwner
		idx := 0
		ttl := defaultTTL
		if !classTokens[strings.ToUpper(tokens[0])] {
			if _, isTTL := parseTTL(tokens[0]); !isTTL {
				maybe := strings.ToUpper(strings.Trim(tokens[0], `"`))
				if !keepTypes[maybe] {
					owner = NormalizeFQDN(tokens[0], current)
					idx = 1
				}
			}
		}
		if idx < len(tokens) {
			if parsed, ok := parseTTL(tokens[idx]); ok {
				ttl = parsed
				idx++
			}
		}
		if idx < len(tokens) && classTokens[strings.ToUpper(tokens[idx])] {
			idx++
		}
		if idx >= len(tokens) {
			continue
		}
		rrtype := strings.ToUpper(strings.Trim(tokens[idx], `"`))
		idx++
		if !keepTypes[rrtype] {
			if owner != "" {
				lastOwner = owner
			}
			continue
		}
		var rdataParts []string
		for _, tok := range tokens[idx:] {
			rdataParts = append(rdataParts, strings.Trim(tok, `"`))
		}
		rdata := strings.TrimSpace(strings.Join(rdataParts, " "))
		fqdn := owner
		if fqdn == "" {
			fqdn = lastOwner
		}
		if fqdn == "" {
			fqdn = current
		}
		if fqdn == "" || rdata == "" {
			continue
		}
		records = append(records, Record{FQDN: fqdn, RRType: rrtype, RData: rdata, TTL: ttl, Zone: current})
		lastOwner = fqdn
	}
	return records
}

func SOASerial(records []Record) string {
	for _, rec := range records {
		if rec.RRType != "SOA" {
			continue
		}
		parts := strings.Fields(rec.RData)
		if len(parts) >= 3 {
			if _, err := strconv.Atoi(parts[2]); err == nil {
				return parts[2]
			}
		}
	}
	return ""
}

func ToPayload(records []Record) []map[string]any {
	out := make([]map[string]any, 0, len(records))
	for _, rec := range records {
		item := map[string]any{"fqdn": rec.FQDN, "rrtype": rec.RRType, "rdata": rec.RData}
		if rec.TTL > 0 {
			item["ttl"] = rec.TTL
		}
		out = append(out, item)
	}
	return out
}
