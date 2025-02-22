#!/bin/sh

if [ -z "$FTP_PASS" ]; then
  echo "FTP_PASS not set, generating random password..."
  export FTP_PASS=$(openssl rand -base64 32)
  echo "Generated FTP password: $FTP_PASS"
fi

exec python -m pyftpdlib -p 21 -w -u "${FTP_USER}" -P "${FTP_PASS}" -d "${FTP_DIRECTORY}"