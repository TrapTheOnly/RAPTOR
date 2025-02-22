#!/bin/sh

if [ -z "$FTP_USER_PASS" ]; then
  echo "FTP_USER_PASS not set, generating random password..."
  export FTP_USER_PASS=$(openssl rand -base64 32)
  echo "Generated FTP password: $FTP_USER_PASS"
fi

exec python -m pyftpdlib -p 21 -w -u "${FTP_USER_NAME}" -P "${FTP_USER_PASS}" -d "${FTP_DIRECTORY}"