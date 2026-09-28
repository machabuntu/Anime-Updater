#!/usr/bin/env python3
"""
Write an ``icuuc.dll`` for Wine that forwards to an official ICU build.

Qt6Core.dll on Windows imports the unversioned ICU that ships in System32 on
Windows 10 1703 and later. Wine has no such library, so PySide6 fails to load
and PyInstaller cannot even discover the Qt plugins. Official ICU builds carry
the same functions under versioned names (``ucnv_open_77``), so a DLL without
any code, only an export table of forwarders, bridges the two.

This is a build-machine aid only. PyInstaller treats System32 DLLs as part of
the OS and does not bundle it; real Windows uses its own icuuc.dll.

Usage:
    make_icu_forwarder.py OUTPUT_DLL ICUUC_VERSIONED_DLL
    make_icu_forwarder.py system32/icuuc.dll icu/bin64/icuuc77.dll
"""

import re
import struct
import sys
from pathlib import Path

SECTION_RVA = 0x1000
FILE_ALIGN = 0x200
SECT_ALIGN = 0x1000


def read_exports(path: Path):
    """Names exported by a PE32+ DLL."""
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    sections_count = struct.unpack_from('<H', data, pe + 6)[0]
    opt_size = struct.unpack_from('<H', data, pe + 20)[0]
    opt = pe + 24
    export_rva = struct.unpack_from('<I', data, opt + 112)[0]

    sections = []
    for i in range(sections_count):
        base = opt + opt_size + 40 * i
        vsize, vaddr, _raw_size, raw_ptr = struct.unpack_from('<IIII', data, base + 8)
        sections.append((vaddr, vsize, raw_ptr))

    def offset(rva: int) -> int:
        for vaddr, vsize, raw_ptr in sections:
            if vaddr <= rva < vaddr + vsize:
                return rva - vaddr + raw_ptr
        raise ValueError(f'RVA {rva:#x} is outside every section')

    edir = offset(export_rva)
    count, names_rva = struct.unpack_from('<I4xI', data, edir + 24)
    names = []
    table = offset(names_rva)
    for i in range(count):
        start = offset(struct.unpack_from('<I', data, table + 4 * i)[0])
        names.append(data[start:data.index(b'\0', start)].decode())
    return names


def build_forwarder(output: Path, target_module: str, forwards):
    """Write a code-less DLL; ``forwards`` maps export name -> target symbol."""
    names = sorted(forwards)
    n = len(names)
    eat_off = 40
    npt_off = eat_off + 4 * n
    ord_off = npt_off + 4 * n
    strings_off = ord_off + 2 * n

    strings = bytearray()

    def add(text: str) -> int:
        rva = SECTION_RVA + strings_off + len(strings)
        strings.extend(text.encode() + b'\0')
        return rva

    dll_name_rva = add(output.name)
    name_rvas = [add(name) for name in names]
    fwd_rvas = [add(f'{target_module}.{forwards[name]}') for name in names]

    section = bytearray(strings_off) + strings
    struct.pack_into('<IIHHIIIIIII', section, 0,
                     0, 0, 0, 0, dll_name_rva, 1, n, n,
                     SECTION_RVA + eat_off, SECTION_RVA + npt_off, SECTION_RVA + ord_off)
    for i in range(n):
        struct.pack_into('<I', section, eat_off + 4 * i, fwd_rvas[i])
        struct.pack_into('<I', section, npt_off + 4 * i, name_rvas[i])
        struct.pack_into('<H', section, ord_off + 2 * i, i)

    virt_size = len(section)
    raw_size = -(-virt_size // FILE_ALIGN) * FILE_ALIGN
    section += bytes(raw_size - virt_size)
    image_size = SECTION_RVA + -(-virt_size // SECT_ALIGN) * SECT_ALIGN

    dos = bytearray(64)
    dos[0:2] = b'MZ'
    struct.pack_into('<I', dos, 0x3C, 64)

    # AMD64, one section, 240 byte optional header, EXECUTABLE | LARGE_ADDRESS | DLL.
    coff = struct.pack('<4sHHIIIHH', b'PE\0\0', 0x8664, 1, 0, 0, 0, 240, 0x2022)

    opt = bytearray(240)
    struct.pack_into('<HBBIIIII', opt, 0, 0x20B, 14, 0, 0, raw_size, 0, 0, SECTION_RVA)
    struct.pack_into('<QIIHHHHHHIIIIHHQQQQII', opt, 24,
                     0x180000000, SECT_ALIGN, FILE_ALIGN, 6, 0, 0, 0, 6, 0,
                     0, image_size, FILE_ALIGN, 0, 3, 0x0160,
                     0x100000, 0x1000, 0x100000, 0x1000, 0, 16)
    struct.pack_into('<II', opt, 112, SECTION_RVA, virt_size)

    header = struct.pack('<8sIIIIIIHHI', b'.edata\0\0', virt_size, SECTION_RVA,
                         raw_size, FILE_ALIGN, 0, 0, 0, 0, 0x40000040)

    headers = bytes(dos) + coff + bytes(opt) + header
    output.write_bytes(headers + bytes(FILE_ALIGN - len(headers)) + bytes(section))


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    output, source = Path(sys.argv[1]), Path(sys.argv[2])
    match = re.fullmatch(r'(icuuc)(\d+)\.dll', source.name, re.IGNORECASE)
    if not match:
        print(f'Expected a versioned icuucNN.dll, got {source.name}')
        return 2
    suffix = f'_{match.group(2)}'

    forwards = {
        name[:-len(suffix)]: name
        for name in read_exports(source)
        if name.endswith(suffix)
    }
    build_forwarder(output, source.stem, forwards)
    print(f'Wrote {output}: {len(forwards)} exports forwarded to {source.name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
