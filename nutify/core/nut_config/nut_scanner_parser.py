"""
Helpers to parse `nut-scanner` output and preserve stable USB identity fields.
"""

from __future__ import annotations

import os
import re

SECTION_PATTERN = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KEY_VALUE_PATTERN = re.compile(r"^\s*(?:#\s*)?([A-Za-z0-9_.-]+)\s*=\s*(.+?)\s*$")

USB_TOPOLOGY_WARNING_LINES = (
    "# WARNING: The bus, device and busport parameters are commented out to prevent reconnection issues.",
    "# When USB devices are disconnected and reconnected, these values often change,",
    "# which can cause NUT to fail finding the UPS. Leave them commented for better reliability.",
)


def parse_nut_scanner_devices(output):
    """Parse `nut-scanner` output into device dictionaries consumable by the setup wizard."""
    if not isinstance(output, str) or not output.strip():
        return []

    devices = []
    current_device = None

    for raw_line in output.splitlines():
        section_match = SECTION_PATTERN.match(raw_line)
        if section_match:
            if current_device:
                _finalize_device(current_device)
                devices.append(current_device)
            current_device = _create_empty_device(section_match.group(1))
            current_device["_raw_lines"].append(raw_line.rstrip())
            continue

        if current_device is None:
            continue

        current_device["_raw_lines"].append(raw_line.rstrip())
        key, value = _parse_key_value_line(raw_line)
        if key:
            _apply_parsed_key_value(current_device, key, value)

    if current_device:
        _finalize_device(current_device)
        devices.append(current_device)

    _enrich_devices_from_linux_usb_inventory(devices)
    return devices


def combined_preview_config(devices):
    """Return representative combined config text for the preview panel."""
    if not isinstance(devices, list) or not devices:
        return ""
    return str(devices[0].get("raw_config") or "")


def _create_empty_device(name):
    return {
        "name": str(name or "").strip() or "unknown",
        "driver": None,
        "port": None,
        "desc": f"Detected {str(name or '').strip() or 'device'}",
        "raw_config": None,
        "vendorid": None,
        "productid": None,
        "vendor": None,
        "model": None,
        "serial": None,
        "bus": None,
        "device": None,
        "busport": None,
        "_raw_lines": [],
    }


def _finalize_device(device):
    raw_lines = list(device.get("_raw_lines") or [])
    device["raw_config"] = _build_preview_raw_config(raw_lines)
    device.pop("_raw_lines", None)


def _parse_key_value_line(raw_line):
    line = str(raw_line or "").strip()
    if not line:
        return None, None

    match = KEY_VALUE_PATTERN.match(line)
    if not match:
        return None, None

    key = str(match.group(1) or "").strip().lower()
    value = _sanitize_conf_value(match.group(2) or "")
    if not key:
        return None, None
    return key, value


def _sanitize_conf_value(raw_value):
    value = _strip_inline_comment(str(raw_value or "").strip())
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1].strip()
    return value.strip()


def _strip_inline_comment(raw_value):
    value = str(raw_value or "")
    quote = None
    result = []
    for char in value:
        if char in ("'", '"'):
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
        if char == "#" and quote is None:
            break
        result.append(char)
    return "".join(result).strip()


def _apply_parsed_key_value(device, key, value):
    if key in {"driver"}:
        device["driver"] = value
    elif key in {"port"}:
        device["port"] = value
    elif key in {"desc", "description"}:
        device["desc"] = value or device.get("desc")
    elif key in {"vendor"}:
        device["vendor"] = value
    elif key in {"product", "model"}:
        device["model"] = value
    elif key in {"vendorid", "vendor_id"}:
        device["vendorid"] = value.upper()
    elif key in {"productid", "product_id"}:
        device["productid"] = value.upper()
    elif key in {"serial", "serialnumber", "serial_number", "serialno"}:
        device["serial"] = value
    elif key in {"bus"}:
        device["bus"] = value
    elif key in {"device"}:
        device["device"] = value
    elif key in {"busport", "bus_port"}:
        device["busport"] = value


def _build_preview_raw_config(raw_lines):
    if not raw_lines:
        return ""

    rendered = []
    for line in raw_lines:
        stripped = str(line or "").strip()
        if stripped and not stripped.startswith("#"):
            key, _ = _parse_key_value_line(stripped)
            if key in {"bus", "device", "busport"}:
                indent = str(line or "")[: len(str(line or "")) - len(str(line or "").lstrip())]
                rendered.append(f"{indent}# {stripped}")
                continue
        rendered.append(str(line or ""))

    has_warning = any("WARNING: The bus, device and busport parameters are commented out" in line for line in rendered)
    if not has_warning:
        rendered.extend(USB_TOPOLOGY_WARNING_LINES)
    return "\n".join(rendered).strip()


def _enrich_devices_from_linux_usb_inventory(devices):
    if not isinstance(devices, list) or not devices:
        return

    inventory = _read_linux_usb_inventory()
    if not inventory:
        return

    used_inventory_indexes = set()
    usb_indexes = [idx for idx, device in enumerate(devices) if _is_usb_device(device)]
    if not usb_indexes:
        return

    for device_index in usb_indexes:
        device = devices[device_index]
        candidate_indexes = _candidate_inventory_indexes(device, inventory, used_inventory_indexes)
        matched_index = _match_inventory_index(device, inventory, candidate_indexes)
        if matched_index is None:
            continue
        _merge_device_with_inventory(device, inventory[matched_index])
        used_inventory_indexes.add(matched_index)

    _assign_remaining_devices_by_order(devices, inventory, used_inventory_indexes)


def _assign_remaining_devices_by_order(devices, inventory, used_inventory_indexes):
    groups = {}
    for idx, device in enumerate(devices):
        if not _is_usb_device(device):
            continue
        if str(device.get("serial") or "").strip():
            continue

        key = (
            _normalize_identifier(device.get("vendorid")),
            _normalize_identifier(device.get("productid")),
        )
        groups.setdefault(key, []).append((idx, device))

    for group_key, group_devices in groups.items():
        if not group_devices:
            continue

        available_candidates = []
        for inv_idx, inventory_item in enumerate(inventory):
            if inv_idx in used_inventory_indexes:
                continue
            if group_key[0] and _normalize_identifier(inventory_item.get("vendorid")) != group_key[0]:
                continue
            if group_key[1] and _normalize_identifier(inventory_item.get("productid")) != group_key[1]:
                continue
            available_candidates.append((inv_idx, inventory_item))

        if len(group_devices) != len(available_candidates) or not available_candidates:
            continue

        hinted = []
        for device_index, device in group_devices:
            order_hint = _extract_numeric_suffix(device.get("name"))
            if order_hint is None:
                hinted = []
                break
            hinted.append((order_hint, device_index, device))

        if len(hinted) != len(group_devices):
            continue

        hinted.sort(key=lambda item: item[0])
        available_candidates.sort(
            key=lambda item: (
                _to_int(item[1].get("bus")) if _to_int(item[1].get("bus")) is not None else 10**9,
                _to_int(item[1].get("device")) if _to_int(item[1].get("device")) is not None else 10**9,
                _normalize_busport(item[1].get("busport")),
                str(item[1].get("serial") or ""),
            )
        )

        for hinted_device, candidate in zip(hinted, available_candidates):
            _, _, device = hinted_device
            inv_idx, inventory_item = candidate
            _merge_device_with_inventory(device, inventory_item)
            used_inventory_indexes.add(inv_idx)


def _candidate_inventory_indexes(device, inventory, used_inventory_indexes):
    results = []
    for idx, inventory_item in enumerate(inventory):
        if idx in used_inventory_indexes:
            continue
        if not _matches_vendor_product(device, inventory_item):
            continue
        results.append(idx)
    return results


def _match_inventory_index(device, inventory, candidate_indexes):
    if not candidate_indexes:
        return None

    serial = str(device.get("serial") or "").strip().lower()
    if serial:
        serial_matches = [idx for idx in candidate_indexes if str(inventory[idx].get("serial") or "").strip().lower() == serial]
        if len(serial_matches) == 1:
            return serial_matches[0]

    busport = _normalize_busport(device.get("busport"))
    if busport:
        busport_matches = [idx for idx in candidate_indexes if _normalize_busport(inventory[idx].get("busport")) == busport]
        if len(busport_matches) == 1:
            return busport_matches[0]

    bus_value = _to_int(device.get("bus"))
    device_value = _to_int(device.get("device"))
    if bus_value is not None and device_value is not None:
        bus_device_matches = [
            idx
            for idx in candidate_indexes
            if _to_int(inventory[idx].get("bus")) == bus_value and _to_int(inventory[idx].get("device")) == device_value
        ]
        if len(bus_device_matches) == 1:
            return bus_device_matches[0]

    if len(candidate_indexes) == 1:
        return candidate_indexes[0]
    return None


def _merge_device_with_inventory(device, inventory_item):
    if not str(device.get("serial") or "").strip():
        device["serial"] = inventory_item.get("serial") or device.get("serial")

    if not str(device.get("vendor") or "").strip():
        device["vendor"] = inventory_item.get("vendor") or device.get("vendor")
    if not str(device.get("model") or "").strip():
        device["model"] = inventory_item.get("product") or device.get("model")

    if not str(device.get("vendorid") or "").strip():
        device["vendorid"] = inventory_item.get("vendorid") or device.get("vendorid")
    if not str(device.get("productid") or "").strip():
        device["productid"] = inventory_item.get("productid") or device.get("productid")

    if not str(device.get("bus") or "").strip():
        device["bus"] = inventory_item.get("bus") or device.get("bus")
    if not str(device.get("device") or "").strip():
        device["device"] = inventory_item.get("device") or device.get("device")
    if not str(device.get("busport") or "").strip():
        device["busport"] = inventory_item.get("busport") or device.get("busport")


def _is_usb_device(device):
    driver = str(device.get("driver") or "").strip().lower()
    if "usb" in driver:
        return True
    return bool(str(device.get("vendorid") or "").strip() and str(device.get("productid") or "").strip())


def _matches_vendor_product(device, inventory_item):
    device_vendor = _normalize_identifier(device.get("vendorid"))
    device_product = _normalize_identifier(device.get("productid"))
    inventory_vendor = _normalize_identifier(inventory_item.get("vendorid"))
    inventory_product = _normalize_identifier(inventory_item.get("productid"))

    if device_vendor and inventory_vendor and device_vendor != inventory_vendor:
        return False
    if device_product and inventory_product and device_product != inventory_product:
        return False
    return True


def _normalize_identifier(value):
    return str(value or "").strip().upper()


def _extract_numeric_suffix(value):
    match = re.search(r"(\d+)\s*$", str(value or "").strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _to_int(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text, 10)
    except ValueError:
        return None


def _normalize_busport(value):
    text = str(value or "").strip()
    if not text:
        return ""
    parts = re.findall(r"\d+", text)
    if not parts:
        return text.lower()
    normalized = [str(int(part, 10)) for part in parts]
    return ".".join(normalized)


def _read_linux_usb_inventory():
    base_path = "/sys/bus/usb/devices"
    if not os.path.isdir(base_path):
        return []

    inventory = []
    for entry in sorted(os.listdir(base_path)):
        entry_path = os.path.join(base_path, entry)
        if not os.path.isdir(entry_path):
            continue

        vendor_id = _read_text_file(os.path.join(entry_path, "idVendor")).upper()
        product_id = _read_text_file(os.path.join(entry_path, "idProduct")).upper()
        if not vendor_id or not product_id:
            continue

        busnum = _read_text_file(os.path.join(entry_path, "busnum"))
        devnum = _read_text_file(os.path.join(entry_path, "devnum"))
        devpath = _read_text_file(os.path.join(entry_path, "devpath"))

        inventory.append(
            {
                "vendorid": vendor_id,
                "productid": product_id,
                "vendor": _read_text_file(os.path.join(entry_path, "manufacturer")),
                "product": _read_text_file(os.path.join(entry_path, "product")),
                "serial": _read_text_file(os.path.join(entry_path, "serial")),
                "bus": _to_padded_int_string(busnum),
                "device": _to_padded_int_string(devnum),
                "busport": devpath or "",
            }
        )

    return inventory


def _read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception:
        return ""


def _to_padded_int_string(value):
    parsed = _to_int(value)
    if parsed is None:
        return ""
    return f"{parsed:03d}"

