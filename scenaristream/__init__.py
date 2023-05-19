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
import sys
import os

from pathlib import Path
from enum import IntEnum, Enum
from struct import unpack, pack
from typing import Generator, Union, Optional

class MUIType(IntEnum):
    VIDEO = 0x01
    AUDIO = 0x02
    GRAPHICS=0x03

#TextST should also be MUIType.GRAPHICS, but what is the header? 'TS'?
class StreamHeader(Enum):
    PG = b'PG'
    IG = b'IG'
    TS = b'TS' #!!! This is likely incorrect, see above comment !!!

class BDGraphicSegment(IntEnum):
    PDS = 0x14
    ODS = 0x15
    PCS = 0x16
    WDS = 0x17
    ICS = 0x18 #IGS
    END = 0x80
    TDIALOG = 0x81 #TextST
    TSTYLE  = 0x82 #TextST

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
        try:
            header = StreamHeader(header)
        except:
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
        assert MAGIC in [b'PG', b'IG'], "Don't know how to parse this file. (if TextST, file an issue with the sample)"
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

#%% Scenarist BD format parser
class EsMuiStream:
    def __init__(self, mui_file: Union[str, Path], pes_file: Union[str, Path]) -> None:
        if not os.path.exists(mui_file) or not os.path.exists(pes_file):
            raise FileNotFoundError("Missing MUI or xES file.")

        #MUI files are lightweight, read it all at once.
        with open(mui_file, 'rb') as f:
            self._mui_data = f.read()
        self._pes_file = pes_file

        assert self.type == MUIType.GRAPHICS, f"Not a MUI Graphics file, got '{self.type}'"
        assert self.__class__._mui_tail() == self._mui_data[-14:], "MUI tail signature not found."
        self._mui_data = self._mui_data[:-14]

    @property
    def type(self) -> MUIType:
        return MUIType(self._mui_data[3])

    @staticmethod
    def get_timestamps(tc_bytestring: bytes) -> bytes:
        #Convert the proprietary timestamps to standard PTS and DTS
        dts = (unpack(">I", tc_bytestring[:4])[0] - 27e6)/45e3
        dts += (tc_bytestring[4] >> 7)/90e3
        ov_cnt = tc_bytestring[4] & 0x7F
        #for each overflow, we add 2**32/128
        pts = ((unpack(">I", tc_bytestring[5:])[0])/128 + (1 << 25)*ov_cnt - 27e6)/45e3
        return pack(">I", round(pts*90e3)) + pack(">I", round(dts*90e3))

    @staticmethod
    def encode_timestamps(pts: int, dts: int) -> bytes:
        #Convert PTS and DTS to cryptic scenarist format
        payload = bytearray(b'\x00'*9)
        payload[4] |= 0x80*bool(dts % 2) #accuracy
        sdts = int(dts/2 + 27e6)
        payload[:4] = pack(">I", sdts)

        spts = int((pts/2 + 27e6)*128)
        assert (spts >> 32) <= 0x7F, "Timestamp overflow."
        payload[4] |= 0x7F & (spts >> 32)

        payload[5:] = pack(">I", spts & ((1 << 32) -1))
        return payload

    def gen_segments(self) -> Generator[bytes, None, None]:
        valid_segments = [pgst for pgst in BDGraphicSegment]
        index = 4
        with open(self._pes_file, 'rb') as pes:
            while self._mui_data[index:]:
                segment_type = self._mui_data[index]
                assert segment_type in valid_segments

                index += 1
                block_length = unpack(">I", self._mui_data[index:(index:=index+4)])[0]

                header = __class__.get_timestamps(self._mui_data[index:(index:=index+9)])

                segment_data = pes.read(block_length)
                if len(segment_data) < block_length:
                    segment_data += pes.read(block_length-len(segment_data))
                    assert len(segment_data) == block_length, "IO error or incomplete ES file."
                assert segment_data[0] == segment_type, "Segment type mismatch between MUI and ES."
                yield header + segment_data
        return None

    def segments(self) -> list[bytes]:
        return [seg for seg in self.gen_segments()]

    @classmethod
    def _mui_tail(cls) -> bytes:
        return bytes([0xFF] + [0x00]*13)

    @classmethod
    def segment_writer(cls, es_file: Union[str, Path], mui_file: Optional[Union[str, Path]] = None) -> Generator[None, None, None]:
        if mui_file is None:
            ext = '.' + ('MUI' if str(es_file).endswith('ES') else 'mui')
            mui_file = str(es_file) + ext

        esf = open(es_file, 'wb')
        mui = open(mui_file, 'wb')

        mui.write(bytes([0x00, 0x00, 0x00, MUIType.GRAPHICS]))

        try:
            segment = yield
            while segment is not None:
                segment = bytes(segment)
                esf.write(segment[10:])
                mui.write(segment[10:11] + pack(">I", unpack(">H", segment[11:13])[0]+3))
                mui.write(cls.encode_timestamps(*unpack(">" + "I"*2, segment[2:10])))
                segment = yield
            mui.write(cls._mui_tail())
        except Exception as e:
            print(f"Aborted, critical error while writing ES+MUI: '{e}'")
        mui.close()
        esf.close()
        yield None

    @classmethod
    def convert_to_esmui(cls, stream_file: Union[str, Path], es_file: Union[str, Path], mui_file: Optional[Union[str, Path]] = None) -> None:
        """
        Convert a raw stream to a MuiFile.
        """
        stream = StreamFile(stream_file)

        if mui_file is None:
            ext = '.' + ('MUI' if str(es_file).endswith('ES') else 'mui')
            mui_file = str(es_file) + ext

        esf = open(es_file, 'wb')
        mui = open(mui_file, 'wb')

        mui.write(bytes([0x00, 0x00, 0x00, MUIType.GRAPHICS]))

        try:
            for sc, segment in enumerate(stream.gen_segments()):
                #Write segment without length and timing data
                esf.write(segment[10:])
                #Write header (segment type, length+3, )
                mui.write(segment[10:11] + pack(">I", unpack(">H", segment[11:13])[0]+3))
                mui.write(cls.encode_timestamps(*unpack(">" + "I"*2, segment[2:10])))
            #write tail
            mui.write(bytes([0xFF] + [0x00]*13))
            print(f"Converted {sc} segments.")
        except Exception as e:
            print(f"Critical error while writing ES+MUI: '{e}'")
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
