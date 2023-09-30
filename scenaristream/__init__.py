#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIT License

Copyright (c) 2023 cubicibo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

#%% Library
import os

from typing import Generator, Union, Optional, Type
from dataclasses import dataclass
from pathlib import Path
from struct import unpack, pack
from enum import IntEnum, Enum

class MUIType(IntEnum):
    VIDEO    = 0x01
    AUDIO    = 0x02
    GRAPHICS = 0x03
    TEXT     = 0x04
####

class StreamHeader(Enum):
    PG = b'PG'
    IG = b'IG'
    MPEG_TS = bytes([0x00, 0x00, 0x01, 0xBF])
####

class GraphicSegment(IntEnum):
    PDS = 0x14 #PGS+IGS
    ODS = 0x15 #PGS+IGS
    PCS = 0x16
    WDS = 0x17 #PGS
    ICS = 0x18 #IGS
    END = 0x80 #PGS+IGS
####

class TextSegment(IntEnum):
    STYLE  = 0x81
    DIALOG = 0x82
####

class TSMask(IntEnum):
    RAWES = (1 << 32) - 1
    MPEGTS = (1 << 33) - 1
####

class TSClock(IntEnum):
    STC = int(27e6)
    PTS = int(90e3)

class TSOffset(IntEnum):
    RAWES = int(90e3)
    MUIES = int(54e6)
####

#%% Raw stream format (tsMuxer, SUPer, avs2bdnxml)
class StreamFile:
    """
    Represents a .SUP, .MNU, .TextST file that contains a (valid) stream.
    """
    def __init__(self, fp: Union[Path, str], **kwargs) -> None:
        assert os.path.exists(fp), "File does not exist."
        self.file = fp
        self.bytes_per_read = int(kwargs.pop('bytes_per_read', 1*1024**2))
        assert self.bytes_per_read > 0

    def get_header(self) -> StreamHeader:
        with open(self.file, 'rb') as f:
            header = f.read(2)
            long_header = f.read(2)
        try:
            header = StreamHeader(header)
        except:
            if header + long_header == StreamHeader.MPEG_TS:
                print("Found MPEG-TS header, assuming TextST.")
                header = StreamHeader.MPEG_TS
            else:
                raise AssertionError("File contains garbage or unknown stream type.")
        return header

    @property
    def file(self) -> str:
        return str(self._file)

    @file.setter
    def file(self, file: Union[Path, str]) -> None:
        if (file := Path(file)).exists():
            self._file = file
        else:
            raise OSError("File does not exist.")

    def gen_segments(self) -> Generator[bytes, None, None]:
        """
        Generator of segments. Stops when all segments in the
        file have been consumed. This is the parsing function.

        :yield: Every segment, in order, as they appear in the stream file.
        """
        MAGIC = self.get_header().value
        assert MAGIC in [b'PG', b'IG'], "Don't know how to parse this file. (if TextST, use the appropriate class)"
        HEADER_LEN = 13

        with open(self.file, 'rb') as f:
            buff = f.read(self.bytes_per_read)
            while buff:
                renew = False
                if len(buff) >= 2:
                    assert buff[:2] == MAGIC, "Encountered garbage in stream."
                if len(buff) >= HEADER_LEN:
                    segment_length = unpack(">H", buff[11:13])[0]
                    if len(buff) >= segment_length+HEADER_LEN:
                        yield buff[:segment_length+HEADER_LEN]
                        buff = buff[segment_length+HEADER_LEN:]
                    else:
                        renew = True
                else:
                    renew = True

                if renew or not buff:
                    if not (new_data := f.read(self.bytes_per_read)):
                        break
                    buff = buff + new_data
            ####while
        ####with
        return

    def segments(self) -> list[bytes]:
        """
        Get all segments contained in the file.
        """
        return list(self.gen_segments())
####StreamFile

class TextSTFile(StreamFile):
    def get_header(self) -> StreamHeader:
        """
        TextST files don't have clear formatting. This assume SubtitleEdit output format
        is the correct one, so we check for M2TS packet header and the ID of the first
        segment to ensure this is TextST.
        """
        with open(self.file, 'rb') as f:
            header = f.read(7)
        assert header[:4] == StreamHeader.MPEG_TS.value
        assert header[-1] in [TextSegment.STYLE, TextSegment.DIALOG]
        return StreamHeader.MPEG_TS

    def gen_segments(self) -> Generator[bytes, None, None]:
        """
        Generator of segments. Stops when all segments in the
        file have been consumed. This is the parsing function.

        :yield: Every segment, in order, as they appear in the stream file.
        """
        MAGIC = self.get_header().value
        header_len = len(MAGIC) + 2
        assert header_len == 6

        with open(self.file, 'rb') as f:
            buff = f.read(self.bytes_per_read)
            while buff:
                renew = False
                if len(buff) >= 2:
                    assert buff[:4] == MAGIC, "Encountered garbage in stream."
                if len(buff) >= header_len:
                    segment_length = unpack(">H", buff[header_len-2:header_len])[0]
                    if len(buff) >= segment_length+header_len:
                        #Sanity check, M2TS length should equal TextST one minus header
                        assert segment_length-3 == unpack(">H", buff[header_len+1:header_len+3])[0]
                        #Return packet with MPEG_TS header stripped.
                        yield buff[header_len:segment_length+header_len]
                        buff = buff[segment_length+header_len:]
                    else:
                        renew = True
                else:
                    renew = True

                if renew or not buff:
                    if not (new_data := f.read(self.bytes_per_read)):
                        break
                    buff = buff + new_data
            ####while
        ####with
        return
####TextSTFile

@dataclass
class TSContext:
    carry: int = 0
    offset: int = 0

    def __post_init__(self) -> None:
        self.carry = int(self.carry)
        self.offset = int(self.offset)
        self._prev_dts = (-1)*TSClock.PTS
        self._negative_possible = self.carry == 0

    @classmethod
    def from_dts(cls, dts: int) -> 'TSContext':
        ctx = cls((max(dts, 0) & TSMask.RAWES)//(TSMask.RAWES+1), TSClock.PTS)
        ctx._negative_possible = dts < 0
        return ctx

    @classmethod
    def from_float_dts(cls, dts: float) -> 'TSContext':
        ctx = cls(round(max(dts, 0.0)*TSClock.PTS)//(TSMask.RAWES+1), TSClock.PTS)
        ctx._negative_possible = dts < 0
        return ctx

    def get_full_range(self, pts: int, dts: int) -> tuple[int, int]:
        self.carry += (self._prev_dts + self.offset > dts + self.offset)

        if self._negative_possible and dts > TSMask.RAWES - self.offset:
            dts = -1 * ((-1*dts) & TSMask.RAWES)
            if pts > TSMask.RAWES - self.offset:
                pts = -1 * ((-1*pts) & TSMask.RAWES)
        elif pts > dts:
            self._negative_possible = False

        self._prev_dts = dts

        if not self._negative_possible and pts < dts:
            pts += TSMask.RAWES + 1
        return self.carry*(TSMask.RAWES+1) + dts, pts + self.carry*(TSMask.RAWES+1)
####

class TSPair:
    def __init__(self, dts: int, pts: int) -> None:
        self.dts, self.pts = dts, pts

    @classmethod
    def from_mui(cls, tc_bytestring: bytes) -> tuple[int, int]:
        # DTS has 33 bits and is defined on the 90 kHz clock
        # Remove ticks offset and shift by one bit as the DTS LSB is on the 4th byte.
        dts = (unpack(">I", tc_bytestring[:4])[0]) << 1
        dts += (tc_bytestring[4] >> 7)

        # PTS has 39 bits, whom 6 are unused, so we assume 33 bits.
        pts = (tc_bytestring[4] & 0x7F) << 32
        pts += unpack(">I", tc_bytestring[5:])[0]
        return cls(dts - TSOffset.MUIES, (pts >> 6) - TSOffset.MUIES)

    @classmethod
    def from_rawes(cls, tc_bytestring: bytes, ctx: Optional[TSContext] = None) -> tuple[int, int]:
        pts, dts = unpack(">" + "I"*2, tc_bytestring)
        if ctx is not None:
            return cls(*ctx.get_full_range(pts, dts))
        else:
            return cls(dts, pts)

    def to_mui(self) -> bytes:
        dts, pts = self.dts, self.pts
        dts = (dts + TSOffset.MUIES) & TSMask.MPEGTS
        pts = (pts + TSOffset.MUIES) & TSMask.MPEGTS

        payload = bytearray(b'\x00'*9)
        # encode DTS MSBs.LSB
        payload[:4] = pack(">I", (dts >> 1) & ((1 << 32) - 1))

        # encode PTS as 39 bits (easier than 33 bits in the middle of two bytes)
        payload[4:9] = pack(">Q", (pts << 6) & ((1 << 39) - 1))[3:]
        payload[4] |= ((dts & 0x1) << 7)
        return bytes(payload)

    def to_rawes(self) -> bytes:
        dts, pts = self.dts, self.pts
        return pack('>' + 2*'I', *map(lambda ts: ts & TSMask.RAWES, (pts, dts)))
####

#%% Scenarist BD format parser
class EsMuiStream:
    def __init__(self, mui_file: Union[str, Path], es_file: Union[str, Path]) -> None:
        if not os.path.exists(mui_file) or not os.path.exists(es_file):
            raise FileNotFoundError("Missing MUI or xES file.")

        #MUI files are lightweight, read it all at once.
        with open(mui_file, 'rb') as f:
            self._mui_data = f.read()
        self._es_file = es_file

        assert self.type in [MUIType.GRAPHICS, MUIType.TEXT], f"Not a support MUI file, got '{self.type}'"
        assert self.__class__._mui_tail() == self._mui_data[-14:], "MUI tail signature not found."
        self._mui_data = self._mui_data[:-14]

    @property
    def type(self) -> MUIType:
        return MUIType(self._mui_data[3])

    def gen_segments(self) -> Generator[bytes, None, None]:
        if self.type == MUIType.GRAPHICS:
            yield from self._gen_segments_graphics()
        elif self.type == MUIType.TEXT:
            yield from self._gen_segments_text()
        else:
            raise AssertionError(f"Unhandled MUI type '{self.type}'.")

    def _gen_segments_text(self) -> Generator[bytes, None, None]:
        valid_segments = [tseg for tseg in TextSegment]
        index = 4
        assert self.type == MUIType.TEXT, "Not a Text asset."
        with open(self._es_file, 'rb') as tes:
            while self._mui_data[index:]:
                segment_type = self._mui_data[index]
                assert segment_type in valid_segments

                index += 1
                block_length = unpack(">I", self._mui_data[index:(index:=index+4)])[0]

                assert self._mui_data[index:(index:=index+9)] == b'\x00'*9, "Encountered non-null timestamp in TES.MUI?!"
                segment_data = tes.read(block_length)
                if len(segment_data) < block_length:
                    segment_data += tes.read(block_length-len(segment_data))
                    assert len(segment_data) == block_length, "IO error or incomplete TES file."
                assert segment_data[0] == segment_type, "Segment type mismatch between MUI and TES."
                yield segment_data
        return None

    def _gen_segments_graphics(self) -> Generator[bytes, None, None]:
        valid_segments = [pgst for pgst in GraphicSegment]
        index = 4
        assert self.type == MUIType.GRAPHICS
        with open(self._es_file, 'rb') as pes:
            while self._mui_data[index:]:
                segment_type = self._mui_data[index]
                assert segment_type in valid_segments

                index += 1
                block_length = unpack(">I", self._mui_data[index:(index:=index+4)])[0]

                header = TSPair.from_mui(self._mui_data[index:(index:=index+9)]).to_rawes()
                segment_data = pes.read(block_length)
                if len(segment_data) < block_length:
                    segment_data += pes.read(block_length-len(segment_data))
                    assert len(segment_data) == block_length, "IO error or incomplete ES file."
                assert segment_data[0] == segment_type, "Segment type mismatch between MUI and ES."
                yield header + segment_data
        return None

    def segments(self) -> list[bytes]:
        return [seg for seg in self.gen_segments()]

    def check_integrity(self) -> bool:
        try:
            for seg in self.gen_segments(): ...
        except AssertionError as e:
            return False
        else:
            return True

    @classmethod
    def _mui_tail(cls) -> bytes:
        return bytes([0xFF] + [0x00]*13)

    @classmethod
    def _mui_header(cls, mui_type: MUIType) -> bytes:
        return bytes([0x00, 0x00, 0x00, int(mui_type)])

    @classmethod
    def segment_writer(cls,
            es_file: Union[str, Path],
            mui_file: Optional[Union[str, Path]] = None,
            mui_type: MUIType = MUIType.GRAPHICS,
            first_dts: float = -1.0,
        ) -> Generator[None, Type[bytes], None]:
        """
        Write segments as they arrive to manage memory efficiently.
        """
        if mui_file is None:
            ext = '.' + ('MUI' if str(es_file).endswith('ES') else 'mui')
            mui_file = str(es_file) + ext

        assert mui_type == MUIType.GRAPHICS, f"'{MUIType(mui_type)}' not yet supported in segment_writer."

        esf = open(es_file, 'wb')
        mui = open(mui_file, 'wb')
        mui.write(cls._mui_header(mui_type))

        ctx = TSContext.from_float_dts(first_dts)

        try:
            segment = yield
            while segment is not None:
                segment = bytes(segment)
                esf.write(segment[10:])
                mui.write(segment[10:11] + pack(">I", unpack(">H", segment[11:13])[0]+3))
                mui.write(TSPair.from_rawes(segment[2:10], ctx).to_mui())
                segment = yield
            mui.write(cls._mui_tail())
        except Exception as e:
            print(f"Aborted, critical error while writing ES+MUI: '{e}'")
        mui.close()
        esf.close()
        yield None

    @classmethod
    def convert_to_tesmui(cls,
            stream_file: Union[str, Path],
            es_file: Union[str, Path],
            mui_file: Optional[Union[str, Path]] = None
        ) -> None:
        stream = TextSTFile(stream_file)

        def shift_pts(pts: bytes):
            ticks = 0
            for byte in pts:
                ticks = (ticks << 8) + byte
            return ticks + TSOffset.MUIES

        def encode_pts(pts: int) -> bytes:
            return bytes([(pts >> (8*(4-k))) & 0xFF for k in range(5)])

        if mui_file is None:
            ext = '.' + ('MUI' if str(es_file).endswith('ES') else 'mui')
            mui_file = str(es_file) + ext

        esf = open(es_file, 'wb')
        mui = open(mui_file, 'wb')

        mui.write(cls._mui_header(MUIType.TEXT))

        try:
            for sc, segment in enumerate(stream.gen_segments()):
                length = unpack(">H", segment[1:3])[0]
                #Write segment without length and timing data
                if segment[0] == TextSegment.STYLE:
                    esf.write(segment[0:1] + bytes([length >> 8, length & 0xFF]) + segment[3:])
                elif segment[0] == TextSegment.DIALOG:
                    pts1 = encode_pts(shift_pts(segment[3:8]))
                    pts2 = encode_pts(shift_pts(segment[8:13]))
                    esf.write(segment[:3] + pts1 + pts2 + segment[13:])
                else:
                    raise AssertionError("Unknown segment found in TextST stream.")
                #Write header (segment type, length+3, mux_dts=0, mux_pts=0)
                mui.write(segment[0:1] + pack(">I", length+3) + b'\x00'*9)
            #write tail
            mui.write(cls._mui_tail())
            print(f"Converted {sc} segments.")
        except Exception as e:
            print(f"Critical error while writing PES+MUI: '{e}'")
        mui.close()
        esf.close()

    @classmethod
    def convert_to_pesmui(cls,
            stream_file: Union[str, Path],
            es_file: Union[str, Path],
            mui_file: Optional[Union[str, Path]] = None,
            first_dts: float = -1.0,
        ) -> None:
        """
        Convert a graphic stream to a MuiFile.
        """
        stream = StreamFile(stream_file)

        if mui_file is None:
            ext = '.' + ('MUI' if str(es_file).endswith('ES') else 'mui')
            mui_file = str(es_file) + ext

        esf = open(es_file, 'wb')
        mui = open(mui_file, 'wb')

        mui.write(bytes([0x00, 0x00, 0x00, MUIType.GRAPHICS]))

        ctx = TSContext.from_float_dts(first_dts)

        try:
            for sc, segment in enumerate(stream.gen_segments()):
                #Write segment without length and timing data
                esf.write(segment[10:])
                #Write header (segment type, length+3, )
                mui.write(segment[10:11] + pack(">I", unpack(">H", segment[11:13])[0]+3))
                mui.write(TSPair.from_rawes(segment[2:10], ctx).to_mui())
            #write tail
            mui.write(cls._mui_tail())
            print(f"Converted {sc} segments.")
        except Exception as e:
            print(f"Critical error while writing PES+MUI: '{e}'")
        mui.close()
        esf.close()

    def convert_to_stream(self, output: Union[str, Path], **kwargs) -> None:
        ext = output.lower().strip()
        if ext.endswith('sup') or ext.endswith('pgs'):
            _header = StreamHeader.PG.value
        elif ext.endswith('igs') or ext.endswith('mnu'):
            _header = StreamHeader.IG.value
        else:
            _header = kwargs.get('es_header', None)
            assert _header is not None, "Unspecified stream output format."
            assert _header in [header.value for header in StreamHeader], "Not a valid xES graphic stream."

        with open(output, 'wb') as out:
            for sc, segment in enumerate(self.gen_segments()):
                out.write(_header + segment)
            print(f"Converted {sc} segments.")
####EsMuiStream
