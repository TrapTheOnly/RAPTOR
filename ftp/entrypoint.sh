#!/bin/sh

if [ -z "$FTP_USER_PASS" ]; then
  echo "FTP_USER_PASS not set, generating random password..."
  export FTP_USER_PASS=$(openssl rand -base64 32)
else
  echo "Using provided FTP_USER_PASS"
fi

export FTP_USER_NAME=${FTP_USER_NAME:-ftpuser}

exec /run.sh