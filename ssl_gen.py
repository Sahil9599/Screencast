"""
Generate a self-signed SSL certificate for Mirror Cast.
This allows getDisplayMedia() to work on mobile browsers
which require a secure context (HTTPS).
"""

import os
import subprocess
import sys


def generate_ssl_cert(cert_dir='.'):
    """Generate self-signed SSL cert using Python's ssl module."""
    cert_file = os.path.join(cert_dir, 'cert.pem')
    key_file = os.path.join(cert_dir, 'key.pem')

    # Skip if already exists
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print('[SSL] Certificate already exists, skipping generation.')
        return cert_file, key_file

    try:
        # Try using cryptography library (more reliable)
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime

        print('[SSL] Generating self-signed certificate...')

        # Generate key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # Generate cert
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, u"Mirror Cast"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Mirror Cast Local"),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(u"localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                    x509.IPAddress(ipaddress.IPv4Address("192.168.137.1")),
                    x509.IPAddress(ipaddress.IPv4Address("192.168.1.1")),
                    x509.IPAddress(ipaddress.IPv4Network("192.168.0.0/16")),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        # Write key
        with open(key_file, 'wb') as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        # Write cert
        with open(cert_file, 'wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print(f'[SSL] Certificate saved: {cert_file}')
        print(f'[SSL] Key saved: {key_file}')
        return cert_file, key_file

    except ImportError:
        print('[SSL] cryptography library not found, using fallback...')
        return generate_ssl_fallback(cert_file, key_file)


def generate_ssl_fallback(cert_file, key_file):
    """Fallback: generate cert using OpenSSL command if available."""
    try:
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', key_file, '-out', cert_file,
            '-days', '365', '-nodes',
            '-subj', '/CN=MirrorCast/O=MirrorCastLocal'
        ], check=True, capture_output=True)
        print(f'[SSL] Certificate generated via OpenSSL')
        return cert_file, key_file
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('[SSL] ERROR: Could not generate SSL certificate.')
        print('[SSL] Install cryptography: pip install cryptography')
        return None, None


if __name__ == '__main__':
    import ipaddress
    cert, key = generate_ssl_cert()
    if cert:
        print(f'\nCert: {cert}\nKey: {key}')
    else:
        print('\nFailed to generate certificate.')
