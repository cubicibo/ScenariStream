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

from scenaristream import EsMuiStream
from scenaristream.__metadata__ import __author__, __version__

import os
import sys
from pathlib import Path
from argparse import ArgumentParser
from typing import NoReturn

#%% Main code
if __name__ == '__main__':
    def exit_msg(msg: str, is_error: bool = True) -> NoReturn:
        if msg != '':
            print(msg)
        sys.exit(is_error)
    ####exit_msg

    parser = ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-s", "--stream", type=str, help="Input (sup, mnu) to convert to xES+MUI.", default='')
    group.add_argument("-x", "--xes", type=str, help="Input xES to convert.", default='')

    parser.add_argument("-m", "--mui", type=str, help="Input MUI associated to xES to convert.", default='')

    parser.add_argument('-v', '--version', action='version', version=f"(c) {__author__}, v{__version__}")
    parser.add_argument("-o", "--output",  type=str, required=True)
    args = parser.parse_args()

    if args.stream == '' and args.xes == '' and args.mui == '':
        exit_msg("No input provided, exiting.")
    elif (args.mui != '' or args.xes != '') and args.stream != '':
        exit_msg("Using conflicting args --mui and --stream, exiting.")

    if args.xes != '' and args.mui == '':
        if os.path.exists(args.xes + '.mui'):
            args.mui = args.xes + '.mui'
        elif os.path.exists(args.xes + '.MUI'):
            args.mui = args.xes + '.MUI'
        else:
            exit_msg("xES provided but no MUI, exiting.")
    elif args.mui != '' and args.xes == '':
        if os.path.exists('.'.join(args.mui.split('.')[:-1])):
            args.xes = '.'.join(args.mui.split('.')[:-1])
        else:
            exit_msg("MUI provided but no xES, exiting.")
    if not Path(args.output).parent.exists():
        exit_msg("Parent directory of output file does not exist, exiting.")

    if args.stream:
        if not os.path.exists(args.stream):
            exit_msg("Input file does not exist, exiting.")

        if not args.output.strip().lower().endswith('es'):
            exit_msg("Desired output format is not xES? Exiting.")

        print("Converting to xES+MUI...")
        EsMuiStream.convert_to_esmui(args.stream, args.output, args.output + '.mui')
        exit_msg("", is_error=False)
    elif args.mui:
        print("Converting from xES+MUI...")
        emf = EsMuiStream(args.mui, args.xes)
        emf.convert_to_stream(args.output)
        exit_msg("", is_error=False)
    exit_msg("Failed parsing args.")
####if
