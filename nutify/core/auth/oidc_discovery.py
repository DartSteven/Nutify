"""Trusted OIDC discovery and optional dynamic client registration."""

from __future__ import annotations

import ipaddress
import json
import socket
from typing import Any, Dict
from urllib.parse import urlsplit

import requests


MAX_METADATA_BYTES = 1024 * 1024
REQUIRED_METADATA_URLS = ('authorization_endpoint', 'token_endpoint', 'jwks_uri')


class OIDCDiscoveryError(Exception):
    """Provider metadata or registration failed validation."""


def _validated_url(value: str, name: str, allow_http_loopback: bool = False) -> str:
    try:
        parsed = urlsplit(str(value or '').strip())
        parsed.port
    except ValueError as exc:
        raise OIDCDiscoveryError(f'{name} is not a valid URL') from exc
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise OIDCDiscoveryError(f'{name} must be an absolute HTTP(S) URL')
    if parsed.username or parsed.password or parsed.fragment:
        raise OIDCDiscoveryError(f'{name} must not contain credentials or a fragment')
    host = parsed.hostname.rstrip('.').casefold()
    is_loopback = host == 'localhost' or host.endswith('.localhost')
    try:
        is_loopback = is_loopback or ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    if parsed.scheme != 'https' and not (allow_http_loopback and is_loopback):
        raise OIDCDiscoveryError(f'{name} must use HTTPS')
    return parsed.geturl()


def _resolved_addresses(hostname: str) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise OIDCDiscoveryError('Provider hostname could not be resolved') from exc
    addresses = {ipaddress.ip_address(record[4][0].split('%', 1)[0]) for record in records}
    if not addresses:
        raise OIDCDiscoveryError('Provider hostname did not resolve to an address')
    return addresses


def _enforce_network_policy(url: str, allow_private_network: bool) -> None:
    parsed = urlsplit(url)
    for address in _resolved_addresses(parsed.hostname or ''):
        if address.is_link_local or address.is_multicast or address.is_unspecified or address.is_reserved:
            raise OIDCDiscoveryError('Provider resolves to a prohibited network address')
        if not allow_private_network and not address.is_global:
            raise OIDCDiscoveryError('Private-network providers require explicit administrator approval')


def _request_json(
    method: str,
    url: str,
    *,
    allow_private_network: bool,
    allow_http_loopback: bool = False,
    headers: Dict[str, str] | None = None,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    safe_url = _validated_url(url, 'Provider endpoint', allow_http_loopback)
    _enforce_network_policy(safe_url, allow_private_network)
    try:
        response = requests.request(
            method,
            safe_url,
            headers={'Accept': 'application/json', **(headers or {})},
            json=payload,
            timeout=(4, 8),
            allow_redirects=False,
            stream=True,
        )
    except requests.RequestException as exc:
        raise OIDCDiscoveryError('Provider request failed') from exc
    if 300 <= response.status_code < 400:
        raise OIDCDiscoveryError('Provider redirects are not accepted during configuration')
    if not response.ok:
        raise OIDCDiscoveryError(f'Provider returned HTTP {response.status_code}')
    try:
        declared_length = int(response.headers.get('Content-Length', '0') or 0)
    except (TypeError, ValueError) as exc:
        raise OIDCDiscoveryError('Provider returned an invalid Content-Length') from exc
    if declared_length > MAX_METADATA_BYTES:
        raise OIDCDiscoveryError('Provider response is too large')
    content = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        content.extend(chunk)
        if len(content) > MAX_METADATA_BYTES:
            raise OIDCDiscoveryError('Provider response is too large')
    try:
        data = json.loads(content.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise OIDCDiscoveryError('Provider returned invalid JSON') from exc
    if not isinstance(data, dict):
        raise OIDCDiscoveryError('Provider returned an invalid JSON object')
    return data


def discover_provider(
    issuer: str,
    *,
    allow_private_network: bool = False,
    allow_http_loopback: bool = False,
) -> Dict[str, Any]:
    safe_issuer = _validated_url(issuer, 'Issuer', allow_http_loopback)
    if urlsplit(safe_issuer).query:
        raise OIDCDiscoveryError('Issuer must not contain a query string')
    metadata_url = f'{safe_issuer.rstrip("/")}/.well-known/openid-configuration'
    metadata = _request_json(
        'GET',
        metadata_url,
        allow_private_network=allow_private_network,
        allow_http_loopback=allow_http_loopback,
    )
    if str(metadata.get('issuer') or '') != safe_issuer:
        raise OIDCDiscoveryError('Discovery issuer does not exactly match configured issuer')
    for name in REQUIRED_METADATA_URLS:
        endpoint = _validated_url(str(metadata.get(name) or ''), name, allow_http_loopback)
        _enforce_network_policy(endpoint, allow_private_network)
    jwks = _request_json(
        'GET',
        str(metadata['jwks_uri']),
        allow_private_network=allow_private_network,
        allow_http_loopback=allow_http_loopback,
    )
    if not isinstance(jwks.get('keys'), list) or not jwks['keys']:
        raise OIDCDiscoveryError('Provider JWKS does not contain signing keys')
    registration_endpoint = str(metadata.get('registration_endpoint') or '').strip()
    if registration_endpoint:
        registration_endpoint = _validated_url(registration_endpoint, 'registration_endpoint', allow_http_loopback)
        _enforce_network_policy(registration_endpoint, allow_private_network)
    response_types = list(metadata.get('response_types_supported') or [])
    grant_types = list(metadata.get('grant_types_supported') or ['authorization_code'])
    code_flow_supported = 'code' in response_types and 'authorization_code' in grant_types
    if not code_flow_supported:
        raise OIDCDiscoveryError('Provider does not support the Authorization Code flow')
    return {
        'issuer': str(metadata['issuer']),
        'registration_endpoint': registration_endpoint,
        'registration_supported': bool(registration_endpoint),
        'scopes_supported': list(metadata.get('scopes_supported') or []),
        'code_flow_supported': True,
    }


def register_dynamic_client(
    discovery: Dict[str, Any],
    *,
    redirect_uri: str,
    client_name: str,
    initial_access_token: str = '',
    allow_private_network: bool = False,
    allow_http_loopback: bool = False,
) -> Dict[str, str]:
    endpoint = str(discovery.get('registration_endpoint') or '')
    if not endpoint:
        raise OIDCDiscoveryError('Provider does not advertise Dynamic Client Registration')
    headers = {}
    if initial_access_token:
        headers['Authorization'] = f'Bearer {initial_access_token}'
    response = _request_json(
        'POST',
        endpoint,
        allow_private_network=allow_private_network,
        allow_http_loopback=allow_http_loopback,
        headers=headers,
        payload={
            'application_type': 'web',
            'client_name': str(client_name or 'Nutify')[:80],
            'redirect_uris': [redirect_uri],
            'grant_types': ['authorization_code'],
            'response_types': ['code'],
            'token_endpoint_auth_method': 'client_secret_basic',
        },
    )
    client_id = str(response.get('client_id') or '').strip()
    client_secret = str(response.get('client_secret') or '').strip()
    if not client_id or not client_secret:
        raise OIDCDiscoveryError('Provider registration response omitted client credentials')
    return {'client_id': client_id, 'client_secret': client_secret}
