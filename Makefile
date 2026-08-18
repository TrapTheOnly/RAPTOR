COLLECTOR_VERSION ?= 1.1.0
LDFLAGS := -s -w -X main.Version=$(COLLECTOR_VERSION)

.PHONY: collector-dist
collector-dist:
	mkdir -p collector/dist
	cd collector && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags "$(LDFLAGS)" -o dist/raptor-collector-linux-amd64 ./cmd/raptor-collector
	cd collector && CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags "$(LDFLAGS)" -o dist/raptor-collector-linux-arm64 ./cmd/raptor-collector
	cd collector && CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags "$(LDFLAGS)" -o dist/raptor-collector-windows-amd64.exe ./cmd/raptor-collector
