from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# creo la chiave privata del server
chiave = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# imposto il nome del server e leggo la data attuale
nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "server.netsec.lab")])
adesso = datetime.now(timezone.utc)

# creo un certificato autofirmato, valido da cinque minuti fa fino a trenta giorni da ora
certificato = (
    x509.CertificateBuilder()
    .subject_name(nome)
    .issuer_name(nome)
    .public_key(chiave.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(adesso - timedelta(minutes=5))
    .not_valid_after(adesso + timedelta(days=30))
    .add_extension(
        x509.SubjectAlternativeName([x509.DNSName("server.netsec.lab")]),
        critical=False
    )
    .sign(chiave, hashes.SHA256())
)

# salvo la chiave privata nella cartella corrente
with open("server.key", "wb") as file:
    file.write(chiave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()
    ))

# salvo il certificato nella cartella corrente
with open("server.crt", "wb") as file:
    file.write(certificato.public_bytes(serialization.Encoding.PEM))

print("Creati server.key e server.crt")