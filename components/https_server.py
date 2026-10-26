"""Optional HTTPS for phones - user-requested Oct 2026: Android installs
this app full screen (a real PWA, see components/pwa.py) only over HTTPS.
Ported from a fork's smartscopes/https.py (nhat-bui-dk, Sep 2026).

How it works:
  * A certificate authority (CA) signs a server certificate for this
    PC's addresses (LAN, Tailscale, localhost, <name>.local). The server
    certificate is signed again at startup whenever an address changes,
    the CA changes, or it nears its end - the phone never needs a new
    setup for that.
  * The CA is Dwarfium's when its folder is given (user-asked Oct 2026:
    "j'ai deja un certificat racine sur Dwarfium") - CADwarfiumCert.pem
    + CADwarfiumKey.pem, made by Dwarfium's createSSLcert: a phone that
    trusts Dwarfium already trusts this app. Else this app's own CA,
    limited (name constraints) to private networks, Tailscale, localhost
    and *.local: its key, if stolen, cannot impersonate a public site.
    Dwarfium's CA has no such limit - its key must stay on this PC.
  * A small TLS relay listens on HTTPS_PORT (8443) and passes the bytes
    on to the normal HTTP server: plain HTTP and the PC's window are
    unchanged, websockets go through.

Files in ~/.astro_dwarf_session/https/ (ASTRO_DWARF_CERT_DIR to move
them); the settings (on/off, Dwarfium's folder) in https.json there.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import ipaddress
import json
import logging
import os
import socket
import ssl
from pathlib import Path

log = logging.getLogger(__name__)

CERT_DIR = Path(os.environ.get("ASTRO_DWARF_CERT_DIR", Path.home() / ".astro_dwarf_session" / "https"))
HTTPS_PORT = int(os.environ.get("ASTRO_DWARF_HTTPS_PORT", "8443"))

DWARFIUM_CA_CERT = "CADwarfiumCert.pem"
DWARFIUM_CA_KEY = "CADwarfiumKey.pem"

_CA_DAYS = 3650
_SERVER_DAYS = 397          # Chrome's limit for a server certificate
_RENEW_BEFORE_DAYS = 30
# 100.64.0.0/10: Tailscale (user-asked Oct 2026, the phone away from home)
_PRIVATE_NETS = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10",
                 "127.0.0.0/8", "169.254.0.0/16")

_server: asyncio.base_events.Server | None = None
_target: tuple[str, int] | None = None
# The relay's own port toward the HTTP server -> the phone's address: the
# HTTP server sees every relayed request come from 127.0.0.1, this tells
# who really asked (see peer_of()).
_peers: dict[int, str] = {}
_last_error = ""


# --- settings ------------------------------------------------------------------------

def _settings_path() -> Path:
    return CERT_DIR / "https.json"


def load_settings() -> dict:
    try:
        return json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(**values) -> None:
    settings = {**load_settings(), **values}
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    _settings_path().write_text(json.dumps(settings, indent=2), encoding="utf-8")


def is_enabled() -> bool:
    return bool(load_settings().get("enabled"))


def is_running() -> bool:
    return _server is not None and _server.is_serving()


def last_error() -> str:
    return _last_error


def find_dwarfium_ca(folder: str) -> tuple[Path, Path] | None:
    """Dwarfium's CA (certificate, key) in `folder` or its cert/ subfolder
    (a Dwarfium run from its sources keeps them there), or None. `folder`
    may also be one of the two files."""
    if not folder:
        return None
    base = Path(folder.strip().strip('"')).expanduser()
    if base.is_file():
        base = base.parent
    for place in (base, base / "cert"):
        cert, key = place / DWARFIUM_CA_CERT, place / DWARFIUM_CA_KEY
        if cert.is_file() and key.is_file():
            return cert, key
    return None


def _ca_files() -> tuple[Path, Path, bool]:
    """(certificate, key, is Dwarfium's) of the CA in use."""
    found = find_dwarfium_ca(load_settings().get("dwarfium_dir", ""))
    if found:
        return found[0], found[1], True
    return CERT_DIR / "ca.crt", CERT_DIR / "ca.key", False


def ca_cert_path() -> Path:
    return _ca_files()[0]


def uses_dwarfium_ca() -> bool:
    return _ca_files()[2]


# --- addresses -----------------------------------------------------------------------

def local_ips() -> list[str]:
    """This PC's private IPv4 addresses (LAN, Tailscale), the main one first."""
    ips: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent for a UDP connect
            ips.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    private = [ipaddress.ip_network(n) for n in _PRIVATE_NETS]
    return [ip for ip in dict.fromkeys(ips)
            if not ip.startswith("127.") and any(ipaddress.ip_address(ip) in n for n in private)]


def _dns_names() -> list[str]:
    host = socket.gethostname().split(".")[0].lower()
    return ["localhost", f"{host}.local"]


def https_urls() -> list[str]:
    return ([f"https://{ip}:{HTTPS_PORT}/" for ip in local_ips()]
            + [f"https://{_dns_names()[1]}:{HTTPS_PORT}/"])


# --- certificates --------------------------------------------------------------------

def _write_private(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _create_ca() -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    host = socket.gethostname().split(".")[0]
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"Astro Dwarf Session local CA ({host})")])
    now = dt.datetime.now(dt.timezone.utc)
    permitted = [x509.IPAddress(ipaddress.ip_network(n)) for n in _PRIVATE_NETS]
    permitted += [x509.DNSName("localhost"), x509.DNSName("local")]
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=_CA_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                     content_commitment=False, key_encipherment=False,
                                     data_encipherment=False, key_agreement=False,
                                     encipher_only=False, decipher_only=False), critical=True)
        # Non-critical for compatibility; Android and Chrome enforce it anyway
        .add_extension(x509.NameConstraints(permitted_subtrees=permitted, excluded_subtrees=None),
                       critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    _write_private(CERT_DIR / "ca.key", key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (CERT_DIR / "ca.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _server_cert_ok(ips: list[str], ca_cert) -> bool:
    from cryptography import x509

    path = CERT_DIR / "server.crt"
    if not path.exists() or not (CERT_DIR / "server.key").exists():
        return False
    try:
        cert = x509.load_pem_x509_certificate(path.read_bytes())
        cert.verify_directly_issued_by(ca_cert)  # signed by the CA in use
    except Exception:
        return False
    if cert.not_valid_after_utc - dt.datetime.now(dt.timezone.utc) < dt.timedelta(days=_RENEW_BEFORE_DAYS):
        return False
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    have = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    return set(ips) <= have and set(_dns_names()) <= set(san.get_values_for_type(x509.DNSName))


def _issue_server_cert(ips: list[str], ca_cert, ca_key) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    sans = [x509.DNSName(n) for n in _dns_names()]
    sans += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ["127.0.0.1", *ips]]
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, _dns_names()[1])]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=_SERVER_DAYS))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
    )
    # The CA's own key identifier, when it has one (Dwarfium's has none: a
    # computed one could then mismatch, the chain is found by its name)
    try:
        ski = ca_cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
        cert = cert.add_extension(x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ski),
                                  critical=False)
    except x509.ExtensionNotFound:
        pass
    cert = cert.sign(ca_key, hashes.SHA256())
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    _write_private(CERT_DIR / "server.key", key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (CERT_DIR / "server.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    log.info("HTTPS: server certificate for %s", ", ".join(ips + _dns_names()))


def ensure_certificates() -> None:
    """A valid server certificate for the current addresses, signed by the
    CA in use (this app's own CA created the first time). Raises on a
    CA that can't be read."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    cert_path, key_path, dwarfium = _ca_files()
    if not dwarfium and not cert_path.exists():
        _create_ca()
    ca_cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    ips = local_ips()
    if not _server_cert_ok(ips, ca_cert):
        ca_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        _issue_server_cert(ips, ca_cert, ca_key)


# --- TLS relay -----------------------------------------------------------------------

def peer_of(client_host: str, client_port: int) -> str | None:
    """The address that really asked, for a request the relay passed on
    (it comes from 127.0.0.1) - None for any other request."""
    if client_host not in ("127.0.0.1", "::1"):
        return None
    return _peers.get(client_port)


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError, asyncio.IncompleteReadError, ssl.SSLError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def start_relay(target_port: int | None = None, target_host: str = "127.0.0.1") -> None:
    """Starts the HTTPS relay when it is enabled (no-op when already running)."""
    global _server, _target, _last_error
    if target_port is not None:
        _target = (target_host, target_port)
    if is_running() or not is_enabled() or _target is None:
        return
    host, port = _target
    try:
        await asyncio.to_thread(ensure_certificates)
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(CERT_DIR / "server.crt", CERT_DIR / "server.key")
    except Exception as exc:
        _last_error = f"{type(exc).__name__}: {exc}"
        log.warning("HTTPS: certificates not ready (%s)", _last_error)
        return

    async def handle(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        try:
            upstream_r, upstream_w = await asyncio.open_connection(host, port)
        except OSError:
            client_w.close()
            return
        own_port = upstream_w.get_extra_info("sockname")[1]
        peer = client_w.get_extra_info("peername")
        _peers[own_port] = peer[0] if peer else "127.0.0.1"
        try:
            await asyncio.gather(_pipe(client_r, upstream_w), _pipe(upstream_r, client_w))
        finally:
            _peers.pop(own_port, None)

    try:
        _server = await asyncio.start_server(handle, "0.0.0.0", HTTPS_PORT, ssl=ctx)
    except OSError as exc:
        _last_error = f"port {HTTPS_PORT}: {exc}"
        log.warning("HTTPS: cannot listen on %s", _last_error)
        return
    _last_error = ""
    log.info("HTTPS: https://%s:%s/ -> http://%s:%s/",
             (local_ips() or ["localhost"])[0], HTTPS_PORT, host, port)


async def stop_relay() -> None:
    global _server
    if _server is not None:
        _server.close()
        try:
            await asyncio.wait_for(_server.wait_closed(), 2)
        except asyncio.TimeoutError:
            pass  # open connections (a phone's websocket) close with the app
        _server = None


async def restart_relay() -> None:
    """After the settings changed: stopped, then started again if enabled
    (a new CA signs a new server certificate)."""
    await stop_relay()
    await start_relay()


def register(port: int, host: str) -> None:
    """Call once at startup (astro_dwarf_ui.py), with the HTTP server's own
    port and host: the relay starts with the app when enabled, and the
    CA's certificate is served at /https/ca.crt for the phones."""
    from fastapi.responses import FileResponse, PlainTextResponse
    from nicegui import app

    target = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host

    @app.get("/https/ca.crt")
    def _ca_cert():
        path = ca_cert_path()
        if not is_enabled() or not path.exists():
            return PlainTextResponse("HTTPS is not enabled", status_code=404)
        return FileResponse(path, media_type="application/x-x509-ca-cert",
                            filename="dwarfium-ca.crt" if uses_dwarfium_ca() else "astro-dwarf-session-ca.crt")

    async def _start() -> None:
        await start_relay(port, target)

    app.on_startup(_start)
    app.on_shutdown(stop_relay)
