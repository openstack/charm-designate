#!/bin/bash

apt-get install --yes bind9
mv /etc/bind/named.conf.options /etc/bind/named.conf.options.org.$$
mv /etc/bind/named.conf.local /etc/bind/named.conf.local.$$
BASTION_IP="10.5.17.29"
IP=$(ip -4 addr show eth0 | awk '/inet/ {print $2}' | sed -e 's!/.*!!')
REV=$(echo $IP | awk 'BEGIN{FS="."} {print $3 "." $2 "." $1}')
LAST_OCTET=$(echo $IP | awk 'BEGIN{FS="."} {print $4}')
UNAME=$(uname -n)
cat << EOF > /etc/bind/named.conf.options
options {
        directory "/var/cache/bind";

        // If there is a firewall between you and nameservers you want
        // to talk to, you may need to fix the firewall to allow multiple
        // ports to talk.  See http://www.kb.cert.org/vuls/id/800113

        // If your ISP provided one or more IP addresses for stable 
        // nameservers, you probably want to use them as forwarders.  
        // Uncomment the following block, and insert the addresses replacing 
        // the all-0's placeholder.

        forwarders {
            $BASTION_IP;
        };

        //========================================================================
        // If BIND logs error messages about the root key being expired,
        // you will need to update your keys.  See https://www.isc.org/bind-keys
        //========================================================================
        dnssec-validation auto;

        auth-nxdomain no;    # conform to RFC1035
        listen-on-v6 { any; };
};
EOF

cat << EOF > /etc/bind/named.conf.local
// forward zone
zone "openstacklocal." {
    type master;
    file "/etc/bind/db.openstacklocal.com";
};
// reverse zone
zone "${REV}.in-addr.arpa" {
    type master;
    notify no;
    file "/etc/bind/db.10";
};
EOF
TTL='$TTL'

cat << EOF > /etc/bind/db.openstacklocal.com
;
; BIND data forward DNS sample for deployment on top of serverstack
;
$TTL    604800
@ IN      SOA      ${UNAME}.openstacklocal. root.${UNAME}.openstacklocal. (
                      201511161         ; Serial
                         604800         ; Refresh
                          86400         ; Retry
                        2419200         ; Expire
                         604800 )       ; Negative Cache TTL
;
@                     IN      NS      ${UNAME}.openstacklocal.
${UNAME}  IN      A       ${IP}
EOF
cat << EOF > /etc/bind/db.10
;
; BIND reverse data file DNS sample for deployment on top of serverstack
;
$TTL    604800
@   IN    SOA     ${UNAME}.openstacklocal. root.${UNAME}.openstacklocal. (
                      201511161         ; Serial
                         604800         ; Refresh
                          86400         ; Retry
                        2419200         ; Expire
                         604800 )       ; Negative Cache TTL
;
@       IN      NS      ${UNAME}.
${LAST_OCTET}      IN      PTR     ${UNAME}.openstacklocal.
EOF

echo "nameserver 127.0.0.1" > /etc/resolvconf/resolv.conf.d/head

/etc/init.d/bind9 restart
