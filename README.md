# ScenariStream
Scenarist BD MUI+Elementary Stream <-> SUP, MNU conversion tool.

## Brief
ScenariStream is a python utility to perform bidirectional conversion between proprietary Scenarist project files (MUI+xES) and raw stream files like SUP/PGS and MNU/IGS.

For example, this tool can convert custom SUP or IGS files so they can be imported in Scenarist. On the other hand, Scenarist BD assets can be converted in the other direction for usage in other tools like BDEdit, tsMuxer, etc! The conversion is 100% bijective: all data and timestamps are preserved.

## Limitations
- Timestamp wrap-around is not implemented/tested. You should not try to convert files with durarions longer than 5 hours.
- TextST support is possible but voluntarily blocked. I don't know how are structured raw TextST stream files.
- Only Scenarist MUI for graphic props are allowed (PGS, TextST, IGS…) but chances are other MUI assets (audio, video) can be converted too with some tweaks.

## Usage:
If you would just like the client without thinking:
`python3 client.py PARAMETERS -o output_file`<br>

You can also install the small package and import the internal classes with `from scenaristream import EsMuiStream, StreamFile`.<br>
`EsMuiStream` parses a xES+MUI stream. `StreamFile` parses a raw stream like PG (SUP) or IG (MNU).

### Parameters
`-s --stream <file>` – Input raw stream file (SUP-PGS or MNU-IGS).<br>
`-x --xes <file>` – Input Scenarist Elementary Stream file (PES or IES).<br>
`-m --mui <file>` – Input Scenarist MUI file. Mandatory with xES, else empty!

### Output
`-o --output <file>` – Output file with extension. The format is inferred from the extension. For Scenarist output, only the xES file should be specified. The .MUI file is always generated aside.

### Note
The user is responsible for using the proper extension when converting to Scenarist xES+MUI format. The output extension should be .PES (.IES) when converting from .SUP (.MNU, respectively).

### Example usage
The command below converts a .SUP file to a PES+MUI Scenarist project.<br>
`python3 client.py -s subtitles.sup -o ./project/subtitles.pes`<br>
In the project folder, subtitles.pes and subtitles.pes.mui will be created.