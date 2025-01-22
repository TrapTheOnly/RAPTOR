$TTL 3600
@   IN  SOA ns1.example.com. admin.example.com. (
        2025012201 ; serial
        7200       ; refresh
        1800       ; retry
        1209600    ; expire
        3600       ; minimum
)
@         IN  NS   ns1.example.com.
@         IN  NS   ns2.example.com.

; WAF Source Records
@         IN  A    172.16.0.1
secure    IN  A    172.16.0.2

; Nginx Source Records
api       IN  A    192.168.0.1
frontend  IN  A    192.168.0.2

; Cloud Source Records
db        IN  A    10.0.0.1
cdn       IN  A    10.0.0.2
backup    IN  A    10.0.0.3

; Other Records (Optional)
www       IN  A    127.0.0.1
mail      IN  A    127.0.0.2
@         IN  MX   10 mail.example.com.