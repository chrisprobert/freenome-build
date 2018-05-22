#!/bin/bash
cp /etc/ssl/certs/ssl-cert-snakeoil.pem "${PGDATA}"/server.crt
cp /etc/ssl/private/ssl-cert-snakeoil.key "${PGDATA}"/server.key
chown -R postgres:postgres "${PGDATA}"
chmod 740 "${PGDATA}"/server.key
perl -i -pe  "s/ssl = 'off'/ssl = 'on'/g" "$PGDATA/postgresql.conf"
