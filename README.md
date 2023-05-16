# ScenariStream
Scenarist BD MUI+Elementary Stream <-> SUP, MNU conversion tool.

## Brief
ScenariStream is a small python utility to do bidirectional conversion between proprietary Scenarist project files (MUI+xES) and raw stream files like SUP/PGS and MNU/IGS.

With this tool, it is now possible to import custom SUP files into Scenarist. Conversely, it allows to reuse assets made with Scenarist in other tools like BDEdit. It is 100% bijective and preserve all data and timestamps.

## Limitations
- Timestamp wrap-around is not implemented. You should not try to convert files with durarions longer than 4 hours or so.
- TextST support is possible but voluntarily blocked. I don't know how are structured raw TextST stream files.
- Only Scenarist MUI for graphic props are allowed (PGS, TextST, IGS…) but maybe other MUI assets (audio, video) work as well.

## Usage:
`python3 scenaristream.py PARAMETERS -o output_file`

### PARAMETERS
`-s --stream <file>` – Input raw stream file (SUP-PGS or MNU-IGS).<br>
`-x --xes <file>` – Input Scenarist Elementary Stream file (PES or IES).<br>
`-m --mui <file>` – Input Scenarist MUI file. Compulsory with xES, else empty!

### Output
`-o --output <file>` – Output. The format is inferred from the given extension. For Scenarist output (MUI+ES), you must specify only the xES file. The MUI file is automatically written aside with the ".mui" extension appended. You are responsible for selecting the proper extension (.PES, .IES, ...)
