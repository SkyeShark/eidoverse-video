"""A minimal HDF5 READER of our own (numpy only) for data files the Bestiary studies (H2b, 10-29: GNM's IdentitySampler
weights, a Keras .h5 written by h5py at its default 'earliest' format). Reads the subset such files use:
  superblock versions 0 and 1;
  version-1 object headers, with their continuation blocks;
  old-style groups: a symbol-table message pointing to a version-1 B-tree of SNOD nodes, the link names in a local heap;
  datasets laid out compact or contiguous (layout message version 3), on scalar or simple dataspaces;
  fixed-point and floating-point datatypes (either byte order), fixed-length strings, and variable-length strings held
  in the global heap;
  attributes (message versions 1-3).
Anything else (version-2 object headers, new-style groups with link messages or fractal heaps, chunked or filtered
data, compound and reference types, shared messages) raises NotImplementedError, so nothing is guessed.

It reads bytes and returns arrays and strings. It never evaluates anything a file holds: a model's JSON config comes
back as text, for the caller to parse as data.

    f = H5File(path)
    f.keys('/')                      the names under a group
    f.attrs('/model_weights')        {name: value}: numbers as arrays (scalars as numpy scalars), strings as str
    f.dataset('/a/b/kernel:0')       a numpy array in native byte order
    f.walk()                         every dataset path under the root, depth first

Format reference: The HDF Group, "HDF5 File Format Specification Version 3.0" (superblock, object header, B-tree v1,
symbol table node, local and global heap, dataspace / datatype / layout / attribute messages).
"""
import struct

import numpy as np

SIGNATURE = b'\x89HDF\r\n\x1a\n'
UNDEFINED = 0xFFFFFFFFFFFFFFFF
MSG_DATASPACE, MSG_DATATYPE, MSG_LAYOUT, MSG_FILTERS, MSG_ATTRIBUTE = 0x0001, 0x0003, 0x0008, 0x000B, 0x000C
MSG_CONTINUATION, MSG_SYMBOL_TABLE, MSG_LINK, MSG_LINK_INFO = 0x0010, 0x0011, 0x0006, 0x0002


def _pad8(n):
    return (n + 7) // 8 * 8


class H5File:
    def __init__(self, path):
        with open(path, 'rb') as fh:
            self.b = fh.read()
        b = self.b
        base = None
        for off in [0] + [512 * 2 ** k for k in range(24)]:
            if off + 8 <= len(b) and b[off:off + 8] == SIGNATURE:
                base = off
                break
        if base is None:
            raise ValueError(f'{path}: no HDF5 signature')
        ver = b[base + 8]
        if ver not in (0, 1):
            raise NotImplementedError(f'superblock version {ver}')
        self.so, self.sl = b[base + 13], b[base + 14]          # the sizes of offsets and of lengths
        o = base + (24 if ver == 0 else 28)
        self.base_addr = self._u(o, self.so)
        o += 4 * self.so                                        # base, free-space, end-of-file, driver addresses
        self.root = self._entry(o)

    # ------------------------------------------------------------------------------------------ primitives
    def _u(self, o, n):
        return int.from_bytes(self.b[o:o + n], 'little')

    def _addr(self, o):
        a = self._u(o, self.so)
        return a if a == UNDEFINED else a + self.base_addr

    def _cstr(self, o):
        e = self.b.index(b'\0', o)
        return self.b[o:e].decode('utf-8', 'replace')

    def _entry(self, o):
        """a symbol table entry: its link name's heap offset and its object header's address"""
        return dict(name_off=self._u(o, self.so), header=self._addr(o + self.so))

    # ------------------------------------------------------------------------------------------ object headers
    def _messages(self, addr):
        """the messages of the version-1 object header at addr: [(type, flags, data offset, size)]"""
        b = self.b
        if b[addr:addr + 4] == b'OHDR':
            raise NotImplementedError('version-2 object header')
        if b[addr] != 1:
            raise NotImplementedError(f'object header version {b[addr]}')
        size = struct.unpack_from('<I', b, addr + 8)[0]
        blocks = [(addr + 16, size)]                           # the 12-byte prefix, padded to 16
        out = []
        while blocks:
            start, ln = blocks.pop(0)
            p = start
            while p + 8 <= start + ln:
                mt, ms, mf = struct.unpack_from('<HHB', b, p)
                d = p + 8
                if mt == MSG_CONTINUATION:
                    blocks.append((self._addr(d), self._u(d + self.so, self.sl)))
                elif mt != 0:
                    out.append((mt, mf, d, ms))
                p = d + ms
        return out

    # ------------------------------------------------------------------------------------------ groups
    def _children(self, hdr):
        msgs = self._messages(hdr)
        for mt, mf, d, ms in msgs:
            if mt == MSG_SYMBOL_TABLE:
                btree, heap = self._addr(d), self._addr(d + self.so)
                return self._btree(btree, self._heap_data(heap))
        if any(mt in (MSG_LINK, MSG_LINK_INFO) for mt, _, _, _ in msgs):
            raise NotImplementedError('new-style group (link messages)')
        return None                                            # not a group

    def _heap_data(self, addr):
        b = self.b
        if b[addr:addr + 4] != b'HEAP':
            raise ValueError(f'no local heap at {addr}')
        return self._addr(addr + 8 + 2 * self.sl)

    def _btree(self, addr, heap):
        b = self.b
        if b[addr:addr + 4] != b'TREE':
            raise ValueError(f'no B-tree node at {addr}')
        if b[addr + 4] != 0:
            raise NotImplementedError('a raw-data (chunk) B-tree where a group B-tree was expected')
        level = b[addr + 5]
        used = struct.unpack_from('<H', b, addr + 6)[0]
        o = addr + 8 + 2 * self.so                              # past the two sibling addresses
        kids = []
        for _ in range(used):
            o += self.sl                                        # key i (a heap offset)
            kids.append(self._addr(o))
            o += self.so
        out = []
        for c in kids:
            out += self._btree(c, heap) if level > 0 else self._snod(c, heap)
        return out

    def _snod(self, addr, heap):
        b = self.b
        if b[addr:addr + 4] != b'SNOD':
            raise ValueError(f'no symbol table node at {addr}')
        n = struct.unpack_from('<H', b, addr + 6)[0]
        o = addr + 8
        out = []
        for _ in range(n):
            e = self._entry(o)
            out.append((self._cstr(heap + e['name_off']), e['header']))
            o += 2 * self.so + 24                               # name offset, header address, cache type, scratch-pad
        return out

    def _resolve(self, path):
        hdr = self.root['header']
        for part in [p for p in path.split('/') if p]:
            kids = self._children(hdr)
            if kids is None:
                raise KeyError(f'{path}: {part} is under a dataset')
            hdr = dict(kids)[part]
        return hdr

    # ------------------------------------------------------------------------------------------ messages
    def _dataspace(self, d):
        """the dims (a tuple; () for a scalar), or None for a null dataspace"""
        b = self.b
        ver, nd = b[d], b[d + 1]
        if ver == 1:
            o, kind = d + 8, (1 if nd else 0)
        elif ver == 2:
            o, kind = d + 4, b[d + 3]
        else:
            raise NotImplementedError(f'dataspace version {ver}')
        if kind == 2:
            return None
        return tuple(self._u(o + i * self.sl, self.sl) for i in range(nd))

    def _datatype(self, d):
        b = self.b
        cls = b[d] & 0x0F
        bits = b[d + 1] | (b[d + 2] << 8) | (b[d + 3] << 16)
        size = struct.unpack_from('<I', b, d + 4)[0]
        order = '>' if bits & 1 else '<'
        if cls == 0:
            return ('num', np.dtype(f'{order}{"i" if bits & 8 else "u"}{size}'))
        if cls == 1:
            if bits & 0x40:
                raise NotImplementedError('VAX byte order')
            return ('num', np.dtype(f'{order}f{size}'))
        if cls == 3:
            return ('str', size)
        if cls == 9:
            if bits & 0x0F == 1:
                return ('vstr', None)
            raise NotImplementedError('variable-length sequence')
        raise NotImplementedError(f'datatype class {cls}')

    def _layout(self, d):
        b = self.b
        ver, cls = b[d], b[d + 1]
        if ver != 3:
            raise NotImplementedError(f'layout message version {ver}')
        if cls == 0:
            return ('compact', d + 4, struct.unpack_from('<H', b, d + 2)[0])
        if cls == 1:
            return ('contiguous', self._addr(d + 2), self._u(d + 2 + self.so, self.sl))
        raise NotImplementedError('chunked layout')

    def _gheap(self, addr, idx):
        """the bytes of object idx in the global heap collection at addr"""
        b = self.b
        if b[addr:addr + 4] != b'GCOL':
            raise ValueError(f'no global heap collection at {addr}')
        end = addr + self._u(addr + 8, self.sl)
        o = addr + 8 + self.sl
        while o + 8 + self.sl <= end:
            hidx = struct.unpack_from('<H', b, o)[0]
            osz = self._u(o + 8, self.sl)
            if hidx == idx:
                return b[o + 8 + self.sl:o + 8 + self.sl + osz]
            if hidx == 0:
                break
            o += 8 + self.sl + _pad8(osz)
        raise KeyError(f'global heap object {idx} at {addr}')

    def _values(self, dt, shape, o, nbytes=None):
        n = int(np.prod(shape)) if shape else 1
        if dt[0] == 'num':
            a = np.frombuffer(self.b, dt[1], count=n, offset=o).astype(dt[1].newbyteorder('='))
            return a.reshape(shape) if shape else a[0]
        if dt[0] == 'str':
            sz = dt[1]
            vals = [self.b[o + i * sz:o + (i + 1) * sz].split(b'\0')[0].decode('utf-8', 'replace') for i in range(n)]
        else:
            step = 4 + self.so + 4
            vals = []
            for i in range(n):
                p = o + i * step
                ln = struct.unpack_from('<I', self.b, p)[0]
                ga = self._addr(p + 4)
                gi = struct.unpack_from('<I', self.b, p + 4 + self.so)[0]
                vals.append('' if ln == 0 else self._gheap(ga, gi)[:ln].decode('utf-8', 'replace'))
        return vals[0] if not shape else np.array(vals, dtype=object).reshape(shape)

    # ------------------------------------------------------------------------------------------ the API
    def keys(self, path='/'):
        kids = self._children(self._resolve(path))
        return [] if kids is None else [k for k, _ in kids]

    def is_group(self, path):
        return self._children(self._resolve(path)) is not None

    def attrs(self, path='/'):
        b = self.b
        out = {}
        for mt, mf, d, ms in self._messages(self._resolve(path)):
            if mt != MSG_ATTRIBUTE:
                continue
            ver = b[d]
            nsz, tsz, ssz = struct.unpack_from('<HHH', b, d + 2)
            if ver == 1:
                o = d + 8
                name = self._cstr(o)
                o += _pad8(nsz)
                td = o
                o += _pad8(tsz)
                sd = o
                o += _pad8(ssz)
            elif ver in (2, 3):
                o = d + (8 if ver == 2 else 9)
                name = self._cstr(o)
                o += nsz
                td = o
                o += tsz
                sd = o
                o += ssz
            else:
                raise NotImplementedError(f'attribute message version {ver}')
            out[name] = self._values(self._datatype(td), self._dataspace(sd), o)
        return out

    def dataset(self, path):
        shape = dt = lay = None
        for mt, mf, d, ms in self._messages(self._resolve(path)):
            if mf & 0x02 and mt in (MSG_DATATYPE, MSG_DATASPACE, MSG_LAYOUT):
                raise NotImplementedError('a shared message')
            if mt == MSG_DATASPACE:
                shape = self._dataspace(d)
            elif mt == MSG_DATATYPE:
                dt = self._datatype(d)
            elif mt == MSG_LAYOUT:
                lay = self._layout(d)
            elif mt == MSG_FILTERS:
                raise NotImplementedError('filtered data')
        if dt is None or lay is None:
            raise KeyError(f'{path} is not a dataset')
        if shape is None:
            return None
        if lay[0] == 'contiguous' and lay[1] == UNDEFINED:
            return np.zeros(shape, dt[1]) if dt[0] == 'num' else None
        return self._values(dt, shape, lay[1])

    def walk(self, path='/'):
        """every dataset path under path, depth first, in the file's own (B-tree) order"""
        out = []
        for name in self.keys(path):
            p = path.rstrip('/') + '/' + name
            if self.is_group(p):
                out += self.walk(p)
            else:
                out.append(p)
        return out
