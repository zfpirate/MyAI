
"""Lecteur de pages Web avec extraction des dates et protections réseau."""

import ipaddress
import json
import socket

from datetime import datetime, date
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


MAX_CONTENT_LENGTH = 1_000_000
MAX_TEXT_LENGTH = 12_000
MIN_TEXT_LENGTH = 120
TIMEOUT = 12
MAX_REDIRECTS = 4

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def is_safe_host(hostname):
    """Refuse les destinations locales, privées ou réservées."""

    if not hostname:
        return False

    hostname = hostname.rstrip(".").lower()

    if hostname == "localhost" or hostname.endswith(".localhost"):
        return False

    if hostname.endswith(".local"):
        return False

    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(
                    hostname,
                    None,
                    type=socket.SOCK_STREAM,
                )
            ]
        except (socket.gaierror, ValueError, OSError):
            return False

    if not addresses:
        return False

    return all(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_reserved
        for address in addresses
    )


def validate_url(url):
    """Vérifie le protocole, les identifiants et l'adresse."""

    try:
        parsed = urlsplit(url)

        if parsed.scheme.lower() not in ("http", "https"):
            return False

        if not parsed.hostname:
            return False

        if parsed.username or parsed.password:
            return False

        if not is_safe_host(parsed.hostname):
            return False

        return True

    except (ValueError, TypeError):
        return False


def parse_date(value):
    """Convertit une date reconnue en YYYY-MM-DD."""

    if not value:
        return None

    value = str(value).strip()

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        return parsed.date().isoformat()
    except ValueError:
        pass

    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(value)
        return parsed.date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def find_jsonld_dates(data):
    """Cherche les dates dans les données JSON-LD."""

    found = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key in ("datePublished", "dateCreated"):
                parsed = parse_date(value)

                if parsed:
                    found.append(parsed)

            elif isinstance(value, (dict, list)):
                found.extend(find_jsonld_dates(value))

    elif isinstance(data, list):
        for item in data:
            found.extend(find_jsonld_dates(item))

    return found


def extract_publication_dates(soup):
    """Extrait les dates de publication et de modification."""

    published = []
    modified = []

    published_keys = [
        ("property", "article:published_time"),
        ("property", "og:published_time"),
        ("name", "date"),
        ("name", "pubdate"),
        ("name", "publishdate"),
        ("name", "datepublished"),
        ("name", "dc.date"),
        ("name", "dcterms.date"),
        ("itemprop", "datePublished"),
    ]

    modified_keys = [
        ("property", "article:modified_time"),
        ("property", "og:updated_time"),
        ("name", "last-modified"),
        ("itemprop", "dateModified"),
    ]

    for attribute, value in published_keys:
        tag = soup.find("meta", attrs={attribute: value})

        if tag:
            parsed = parse_date(tag.get("content"))

            if parsed:
                published.append(parsed)

    for attribute, value in modified_keys:
        tag = soup.find("meta", attrs={attribute: value})

        if tag:
            parsed = parse_date(tag.get("content"))

            if parsed:
                modified.append(parsed)

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    ):
        try:
            data = json.loads(script.string or script.get_text())
            published.extend(find_jsonld_dates(data))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    for tag in soup.find_all("time", attrs={"datetime": True}):
        parsed = parse_date(tag.get("datetime"))

        if parsed:
            published.append(parsed)

    published_date = min(published) if published else None
    modified_date = max(modified) if modified else None

    return published_date, modified_date


def clean_element(element):
    """Supprime les éléments sans intérêt dans une zone de contenu."""

    for unwanted in element.find_all([
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "button",
    ]):
        unwanted.decompose()

    for unwanted in element.find_all(
        attrs={"aria-hidden": "true"}
    ):
        unwanted.decompose()

    return element


def extract_page_text(soup):
    """Extrait prioritairement le contenu principal de la page."""

    selectors = [
        "article",
        "main",
        '[role="main"]',
        ".article-content",
        ".post-content",
        ".entry-content",
        ".content",
    ]

    candidates = []

    for selector in selectors:
        for element in soup.select(selector):
            candidate = BeautifulSoup(
                str(element),
                "html.parser",
            )

            clean_element(candidate)

            text = " ".join(
                candidate.get_text(" ", strip=True).split()
            )

            if len(text) >= MIN_TEXT_LENGTH:
                candidates.append(text)

    if candidates:
        return max(candidates, key=len)

    fallback = BeautifulSoup(str(soup), "html.parser")
    clean_element(fallback)

    text = " ".join(
        fallback.get_text(" ", strip=True).split()
    )

    return text


def error_result(message):
    return {
        "status": "error",
        "message": message,
        "url": None,
        "title": None,
        "published_date": None,
        "modified_date": None,
        "content": "",
    }


def read_webpage(url):
    """Télécharge une page HTML en contrôlant chaque redirection."""

    if not isinstance(url, str):
        return error_result("URL invalide.")

    current_url = url.strip()

    for redirect_number in range(MAX_REDIRECTS + 1):

        if not validate_url(current_url):
            return error_result(
                "Destination Web refusée pour des raisons de sécurité."
            )

        try:
            with requests.get(
                current_url,
                headers=HEADERS,
                timeout=TIMEOUT,
                stream=True,
                allow_redirects=False,
            ) as response:

                if response.is_redirect or response.is_permanent_redirect:
                    location = response.headers.get("Location")

                    if not location:
                        return error_result(
                            "Redirection sans destination."
                        )

                    if redirect_number >= MAX_REDIRECTS:
                        return error_result("Trop de redirections.")

                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()

                content_type = response.headers.get(
                    "Content-Type", ""
                ).lower()

                if "text/html" not in content_type:
                    return error_result(
                        "Cette ressource n'est pas une page HTML."
                    )

                content_length = response.headers.get("Content-Length")

                if content_length:
                    try:
                        if int(content_length) > MAX_CONTENT_LENGTH:
                            return error_result("Page trop volumineuse.")
                    except ValueError:
                        pass

                content = bytearray()

                for chunk in response.iter_content(chunk_size=8192):
                    content.extend(chunk)

                    if len(content) > MAX_CONTENT_LENGTH:
                        return error_result("Page trop volumineuse.")

                final_url = response.url
                encoding = response.encoding or "utf-8"

            html = bytes(content).decode(
                encoding,
                errors="replace",
            )

            soup = BeautifulSoup(html, "html.parser")

            published_date, modified_date = (
                extract_publication_dates(soup)
            )

            title = (
                soup.title.get_text(" ", strip=True)
                if soup.title
                else "Sans titre"
            )

            text = extract_page_text(soup)

            if len(text) < MIN_TEXT_LENGTH:
                return {
                    "status": "error",
                    "message": (
                        "Contenu insuffisant dans le HTML reçu. "
                        "La page nécessite peut-être JavaScript "
                        "ou bloque les lecteurs automatisés."
                    ),
                    "url": final_url,
                    "title": title[:300],
                    "published_date": published_date,
                    "modified_date": modified_date,
                    "content": text[:MAX_TEXT_LENGTH],
                }

            return {
                "status": "success",
                "url": final_url,
                "title": title[:300],
                "published_date": published_date,
                "modified_date": modified_date,
                "content": text[:MAX_TEXT_LENGTH],
            }

        except requests.RequestException as error:
            return error_result(
                f"Impossible de lire la page : {error}"
            )

        except Exception as error:
            return error_result(
                f"Erreur de lecture : {error}"
            )

    return error_result(
        "Impossible de suivre cette redirection."
    )
