import datetime
import ipaddress

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def create_certs(
    country,
    common_name,
    organization="BlueRPC",
    validity: datetime.timedelta = datetime.timedelta(weeks=5000),
    key_size=2048,
    signing_key: rsa.RSAPrivateKey | None = None,
    issuer_cert: x509.Certificate | None = None
) -> (rsa.RSAPrivateKey, x509.Certificate):
    """
    Helper to create certificates for bluerpc

    Args:
        country: the country name
        common_name: the common name, if generating for a worker, make sure to set it as the worker ip
        organization: the organization name
        validity: the period of validity for this cert
        key_size: the key size
        signing_key: the key to be used to sign the certificate, use the key from a CA or leave empty to create a self-signed cert
        issuer_cert: the certificated corresponding to the signing key
    Returns:
        (rsa.RSAPrivateKey, x509.Certificate): a tuple of the private key and the certificate
    """
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    if issuer_cert:
        issuer = issuer_cert.subject
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + validity)
    )
    try:
        ip = ipaddress.ip_address(common_name)
        ext = x509.SubjectAlternativeName([x509.IPAddress(ip)])
        builder = builder.add_extension(ext, True)
    except ValueError:
        pass
    cert = builder.sign(signing_key or key, hashes.SHA256())
    return (key, cert)


def serialize_certs(data: rsa.RSAPrivateKey | x509.Certificate) -> bytes:
    """
    Helper to serialize a private key or a certificate

    Args:
        data: an RSAPrivateKey or a Certificate object
    Returns:
        bytes: a PEM encoded file
    """
    if isinstance(data, rsa.RSAPrivateKey):
        return data.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    else:
        return data.public_bytes(serialization.Encoding.PEM)


def create_keystore(
    key: rsa.RSAPrivateKey,
    cert: x509.Certificate,
    ca_cert: x509.Certificate,
    password: str
):
    """
    Helper to create a keystore with the key/cert of a worker and the CA cert

    Args:
        key: the private key of the worker
        cert: the certificate of the worker (signed by the CA)
        ca_cert: the CA cert
        password: the password of the pfx
        name: the name of the pfx
    Returns:
        bytes: the pfx file
    """
    return serialization.pkcs12.serialize_key_and_certificates(
        b"bluerpc",
        key,
        cert,
        [ca_cert],
        serialization.BestAvailableEncryption(password.encode("utf-8")),
    )


def load_certs(
    key: bytes | None, cert: bytes | None
) -> (rsa.RSAPrivateKey | None, x509.Certificate | None):
    """
    Helper to load certificates from bytes

    Args:
        key: a PEM encoded key
        cert: a PEM encoded cert
    Returns:
        (rsa.RSAPrivateKey|None, x509.Certificate|None): a tuple of the private key and the certificate
    """
    return (
        serialization.load_pem_private_key(key, None) if key else None,
        x509.load_pem_x509_certificate(cert) if cert else None,
    )
