"""
Flatten EIP-712 TypedData into a list of (label, value) pairs for the confirm screen.

Nested structs are indented. Arrays show index as label suffix, e.g. "token[0]".
"""
from dataclasses import dataclass
from typing import Any

from eip712.parser import TypedData


@dataclass
class DisplayField:
    label: str
    value: str
    indent: int = 0


def flatten(typed_data: TypedData) -> list[DisplayField]:
    """Return a flat list of DisplayField from a TypedData object."""
    fields: list[DisplayField] = []

    # Domain header
    fields.append(DisplayField(label="Domain", value="", indent=0))
    for k, v in typed_data.domain.items():
        fields.append(DisplayField(label=_label(k), value=str(v), indent=1))

    # Message header
    fields.append(DisplayField(label=typed_data.primary_type, value="", indent=0))
    _flatten_struct(
        typed_data.primary_type,
        typed_data.message,
        typed_data.types,
        fields,
        indent=1,
    )
    return fields


def _flatten_struct(
    type_name: str,
    message: dict,
    types: dict,
    out: list[DisplayField],
    indent: int,
) -> None:
    if type_name not in types:
        return
    for field in types[type_name]:
        fname = field["name"]
        ftype = field["type"]
        value = message.get(fname)
        _flatten_value(fname, ftype, value, types, out, indent)


def _flatten_value(
    label: str,
    ftype: str,
    value: Any,
    types: dict,
    out: list[DisplayField],
    indent: int,
) -> None:
    import re
    # Array types
    if ftype.endswith("]"):
        base = re.sub(r"\[.*\]$", "", ftype)
        out.append(DisplayField(label=_label(label), value="", indent=indent))
        if isinstance(value, list):
            for i, item in enumerate(value):
                _flatten_value(f"{label}[{i}]", base, item, types, out, indent + 1)
        return

    # Struct types
    if ftype in types:
        out.append(DisplayField(label=_label(label), value=f"({ftype})", indent=indent))
        if isinstance(value, dict):
            _flatten_struct(ftype, value, types, out, indent + 1)
        return

    # Primitive — just display as string
    out.append(DisplayField(label=_label(label), value=_format_value(ftype, value), indent=indent))


def _label(name: str) -> str:
    """Convert camelCase field name to Title Case label."""
    import re
    s = re.sub(r"([A-Z])", r" \1", name).strip()
    return s[0].upper() + s[1:] if s else name


def _format_value(ftype: str, value: Any) -> str:
    if value is None:
        return ""
    if ftype == "address":
        return str(value)
    if ftype in ("uint256", "int256") and isinstance(value, int) and value > 10**15:
        # Format large ETH amounts as ETH
        eth = value / 10**18
        return f"{eth:.6f} (raw: {value})"
    return str(value)
