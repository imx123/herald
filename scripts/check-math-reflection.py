#!/usr/bin/env python3
"""Check the JLaTeXMath reflection contract in a minified APK, without dependencies.

Run against assembleDev/assembleRelease output. A debug APK does not exercise R8.
The original 0.13.0 release fails this check: its macro constructor/method are gone.
"""

import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path


MACRO = "Lorg/scilab/forge/jlatexmath/NewCommandMacro;"
PUBLIC = 0x1
STATIC = 0x8
ABSTRACT = 0x400


class Dex:
    def __init__(self, data):
        if data[:4] != b"dex\n":
            raise ValueError("Expected a standard DEX file")
        self.data = data
        self.strings = []
        for index in range(self.u32(56)):
            offset = self.u32(self.u32(60) + index * 4)
            _, offset = self.uleb(offset)
            end = data.index(b"\0", offset)
            self.strings.append(data[offset:end].decode("utf-8", errors="replace"))
        self.types = [self.strings[self.u32(self.u32(68) + i * 4)] for i in range(self.u32(64))]

    def u32(self, offset):
        return struct.unpack_from("<I", self.data, offset)[0]

    def uleb(self, offset):
        value = 0
        for shift in range(0, 35, 7):
            byte = self.data[offset]
            offset += 1
            value |= (byte & 0x7f) << shift
            if not byte & 0x80:
                return value, offset
        raise ValueError("Invalid DEX ULEB128 value")

    def prototype(self, index):
        offset = self.u32(76) + index * 12
        result = self.types[self.u32(offset + 4)]
        parameters_offset = self.u32(offset + 8)
        parameters = []
        if parameters_offset:
            for i in range(self.u32(parameters_offset)):
                type_index = struct.unpack_from("<H", self.data, parameters_offset + 4 + i * 2)[0]
                parameters.append(self.types[type_index])
        return result, parameters

    def macro_definition(self):
        for index in range(self.u32(96)):
            offset = self.u32(100) + index * 32
            if self.types[self.u32(offset)] == MACRO:
                return self.u32(offset + 4), self.methods(self.u32(offset + 24))
        return None

    def methods(self, offset):
        if not offset:
            return []
        counts = []
        for _ in range(4):
            count, offset = self.uleb(offset)
            counts.append(count)
        for _ in range(counts[0] + counts[1]):
            _, offset = self.uleb(offset)  # field index delta
            _, offset = self.uleb(offset)  # access flags
        result = []
        for count in counts[2:]:  # direct and virtual method indices reset separately
            method_index = 0
            for _ in range(count):
                delta, offset = self.uleb(offset)
                method_index += delta
                flags, offset = self.uleb(offset)
                code_offset, offset = self.uleb(offset)
                method_offset = self.u32(92) + method_index * 8
                prototype_index = struct.unpack_from("<H", self.data, method_offset + 2)[0]
                name = self.strings[self.u32(method_offset + 4)]
                return_type, parameters = self.prototype(prototype_index)
                result.append((name, flags, code_offset, return_type, parameters))
        return result


def check(apk):
    definitions = []
    with zipfile.ZipFile(apk) as archive:
        for name in archive.namelist():
            if re.fullmatch(r"classes\d*\.dex", name):
                definition = Dex(archive.read(name)).macro_definition()
                if definition is not None:
                    definitions.append(definition)
    if len(definitions) != 1:
        raise ValueError("NewCommandMacro must survive R8 with its original class name (found %d)" % len(definitions))
    flags, methods = definitions[0]
    if not flags & PUBLIC or flags & ABSTRACT:
        raise ValueError("NewCommandMacro must remain a public, concrete class")
    constructor = any(
        name == "<init>" and access & PUBLIC and code and returns == "V" and not params
        for name, access, code, returns, params in methods
    )
    if not constructor:
        raise ValueError("NewCommandMacro's public no-argument constructor was removed")
    callback = any(
        name == "executeMacro" and access & PUBLIC and not access & (STATIC | ABSTRACT) and code
        and returns == "Ljava/lang/String;" and len(params) == 2
        and params[0].startswith("L") and params[1] == "[Ljava/lang/String;"
        for name, access, code, returns, params in methods
    )
    # TeXParser itself may be renamed; the library passes its class literal to reflection.
    if not callback:
        raise ValueError("NewCommandMacro.executeMacro(TeXParser, String[]) was removed or renamed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    try:
        check(args.apk)
    except (OSError, ValueError, struct.error, IndexError, zipfile.BadZipFile) as error:
        print("FAIL: %s" % error, file=sys.stderr)
        return 1
    print("PASS: minified APK retains the JLaTeXMath macro constructor and reflection callback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
