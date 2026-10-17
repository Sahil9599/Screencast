"""
Mirror Cast - Screen Mirroring Server
Casts mobile screen to PC over hotspot using WebRTC.
No internet required - works entirely on local network.
Runs on HTTPS so getDisplayMedia() works on mobile browsers.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
os.environ['PYTHONIOENCODING'] = 'utf-8'

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import socket
import ssl
import ipaddress

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mirror-cast-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Track connected clients
clients = {'sender': None, 'receiver': None}


def get_local_ip():
    """Get the local IP address of this machine (works with hotspot)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # This doesn't actually send data - just determines the local IP
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def ensure_ssl_cert():
    """Generate self-signed SSL certificate if not present."""
    cert_file = os.path.join(os.path.dirname(__file__), 'cert.pem')
    key_file = os.path.join(os.path.dirname(__file__), 'key.pem')

    if os.path.exists(cert_file) and os.path.exists(key_file):
        print('  [SSL] Using existing certificate.')
        return cert_file, key_file

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime

        print('  [SSL] Generating self-signed certificate...')

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, u"Mirror Cast"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Local"),
        ])

        # Build SAN with common local network IPs
        san_entries = [
            x509.DNSName(u"localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]
        # Add common hotspot/LAN subnets
        for prefix in ["192.168.", "10.0.", "172.16."]:
            for i in range(0, 256):
                if prefix == "192.168.":
                    san_entries.append(x509.IPAddress(ipaddress.IPv4Address(f"{prefix}{i}.1")))
                    if i in [0, 1, 137, 43, 49]:
                        for j in range(2, 20):
                            san_entries.append(x509.IPAddress(ipaddress.IPv4Address(f"{prefix}{i}.{j}")))

        # Add actual local IP
        local_ip = get_local_ip()
        try:
            san_entries.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
        except Exception:
            pass

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
            .sign(key, hashes.SHA256())
        )

        with open(key_file, 'wb') as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        with open(cert_file, 'wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print(f'  [SSL] Certificate generated successfully!')
        return cert_file, key_file

    except ImportError:
        print('  [SSL] ERROR: cryptography library needed.')
        print('  [SSL] Run: pip install cryptography')
        sys.exit(1)


# ─── Routes ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    ip = get_local_ip()
    return render_template('index.html', ip=ip, port=PORT)


@app.route('/sender')
def sender():
    return render_template('sender.html')


@app.route('/receiver')
def receiver():
    return render_template('receiver.html')


# ─── WebRTC Signaling via SocketIO ────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    print(f'[+] Client connected: {request.sid}')


@socketio.on('register')
def handle_register(data):
    role = data.get('role', 'unknown')
    clients[role] = request.sid
    print(f'[OK] {role.upper()} registered: {request.sid}')
    # Notify the other side
    emit('peer-status', {'role': role, 'status': 'connected'}, broadcast=True, include_self=False)


@socketio.on('offer')
def handle_offer(data):
    """Forward WebRTC offer from sender to receiver."""
    print('[->] Forwarding offer: sender -> receiver')
    emit('offer', data, broadcast=True, include_self=False)


@socketio.on('answer')
def handle_answer(data):
    """Forward WebRTC answer from receiver to sender."""
    print('[<-] Forwarding answer: receiver -> sender')
    emit('answer', data, broadcast=True, include_self=False)


@socketio.on('ice-candidate')
def handle_ice_candidate(data):
    """Forward ICE candidates between peers."""
    emit('ice-candidate', data, broadcast=True, include_self=False)


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    role = None
    for r, s in clients.items():
        if s == sid:
            role = r
            clients[r] = None
            break
    print(f'[-] {(role or "unknown").upper()} disconnected: {sid}')
    emit('peer-disconnected', {'role': role}, broadcast=True, include_self=False)


@socketio.on('stop-sharing')
def handle_stop_sharing():
    """Notify receiver that sender stopped sharing."""
    emit('stop-sharing', broadcast=True, include_self=False)


# ─── Main ─────────────────────────────────────────────────────────────

PORT = 8080

if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            PORT = int(sys.argv[1])
        except ValueError:
            pass

    ip = get_local_ip()

    # Generate SSL certificate
    cert_file, key_file = ensure_ssl_cert()

    addr = f"https://{ip}:{PORT}"
    print("")
    print("  =========================================")
    print("    Mirror Cast - Screen Mirroring Server")
    print("    (HTTPS Enabled for Screen Capture)")
    print("  =========================================")
    print("")
    print(f"  Server:     {addr}")
    print(f"  Receiver:   {addr}/receiver   (PC browser)")
    print(f"  Sender:     {addr}/sender     (Mobile browser)")
    print("")
    print("  NOTE: Browser will show security warning.")
    print("  Click 'Advanced' -> 'Proceed' to continue.")
    print("")
    print("  Steps:")
    print("    1. PC ka hotspot ON karo")
    print("    2. Mobile ko hotspot se connect karo")
    print("    3. PC pe /receiver kholo")
    print("    4. Mobile pe /sender kholo")
    print("    5. 'Start Casting' dabao - bas ho gaya!")
    print("")
    print("  =========================================")
    print("")

    socketio.run(app, host='0.0.0.0', port=PORT, debug=False,
                 certfile=cert_file, keyfile=key_file)
