#!/usr/bin/env bash
# Run a pinned, checksum-verified MCP Registry publisher command.

set -euo pipefail

readonly PUBLISHER_VERSION="1.8.1"

case "$(uname -s)_$(uname -m)" in
    Darwin_x86_64)
        PUBLISHER_ARCHIVE="mcp-publisher_darwin_amd64.tar.gz"
        PUBLISHER_SHA256="88126981225e7714fcc6b7a10cdba4a80ae5901e9740a8c06d0d5195c8bc294c"
        ;;
    Darwin_arm64)
        PUBLISHER_ARCHIVE="mcp-publisher_darwin_arm64.tar.gz"
        PUBLISHER_SHA256="e45e520892460732a4bdf37255576415d4a53ec171f8b913faf15bb1aef7cb77"
        ;;
    Linux_x86_64)
        PUBLISHER_ARCHIVE="mcp-publisher_linux_amd64.tar.gz"
        PUBLISHER_SHA256="a06c9096dcb9727c13555b6be26c7effa707b01f06a4c561ba7a3635443cf2cc"
        ;;
    Linux_aarch64)
        PUBLISHER_ARCHIVE="mcp-publisher_linux_arm64.tar.gz"
        PUBLISHER_SHA256="8dd75a6cf6845688b5d4e46df58d3ca26d5c8d233bb0626606e1db82c5e883e4"
        ;;
    *)
        echo "Unsupported platform: $(uname -s)_$(uname -m)" >&2
        exit 1
        ;;
esac

PUBLISHER_DIRECTORY="$(mktemp -d)"
trap 'rm -rf "$PUBLISHER_DIRECTORY"' EXIT

curl \
    --fail \
    --location \
    --output "$PUBLISHER_DIRECTORY/mcp-publisher.tar.gz" \
    "https://github.com/modelcontextprotocol/registry/releases/download/v${PUBLISHER_VERSION}/${PUBLISHER_ARCHIVE}"
printf '%s  %s\n' "$PUBLISHER_SHA256" "$PUBLISHER_DIRECTORY/mcp-publisher.tar.gz" \
    | shasum -a 256 --check --status
tar -xzf "$PUBLISHER_DIRECTORY/mcp-publisher.tar.gz" \
    -C "$PUBLISHER_DIRECTORY" \
    mcp-publisher
"$PUBLISHER_DIRECTORY/mcp-publisher" "$@"
