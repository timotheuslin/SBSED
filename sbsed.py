#!/usr/bin/env python

# -*- coding: utf-8 -*-
# pylint: disable=invalid-name, line-too-long, too-many-nested-blocks, too-many-branches, too-many-locals
# pylint: disable=logging-fstring-interpolation, redefined-outer-name
# pylint: disable=broad-except, logging-not-lazy
# pylint: disable=eval-used
# pylint: disable=too-few-public-methods
# pylint: disable=consider-using-with
#

"""Simple Bytes Editor / Binary Stream Editor.

Usage:
    sbsed --file source[,target] --edit editor_action [editor_action_1 [editor_action_2]
        edit_action: target_offset:source_data:[data_length[:operation]]
        operation: can be either "overwrite" or "copy". Default: overwrite

The 2-Clause BSD License:
https://opensource.org/licenses/BSD-2-Clause

Copyright (c) 2018, Timothy Lin
All rights reserved.
"""

import re
import sys
import math
import shlex
import argparse
import traceback

verbose_threshold = 1

def debug_message(msg, verbose=1):
    """ print debug message according to the threshold setting """
    if verbose > verbose_threshold:
        print(msg)

def ShlexSplit(shstr, splitters=None, escape=''):
    """Syntactically split a string with specified splitters, which honors its sub-strings
       in the quotation marks."""

    if splitters is None:
        splitters = {','}
    lex = shlex.shlex(shstr)
    lex.escape = escape
    lex.commenters = ''
    parms = ['']
    for dp in list(lex):
        dp = dp.strip()
        if dp not in splitters:
            parms[-1] += dp
        else:
            parms += ['']
    return parms


def LengthAdjust(bstr, width=0):
    """Adjust the length of a byte-string to meet the byte-width with leading padding "0"
        regardless of its endianness.

    bstr - the byte string.\n
    width - the data length, counted in byte."""

    blen = width*2 if width else len(bstr)
    if blen%2:
        bstr = '0' + bstr
        blen += 1
    if blen > len(bstr):
        bstr = '0' * (blen - len(bstr)) + bstr
    return bstr, blen


def Bs2Ba(bstr, width=0):
    """Conversion from a hex-digit byte-string to the network-byte-order hex-digit byte-array.

    bstr - the byte string.\n
    width - the data length, counted in byte."""

    bstr, blen = LengthAdjust(bstr, width)
    return bytearray([int(bstr[b*2:(b+1)*2], base=0x10) for b in range(int(blen/2))])


def Le2N(bstr, width=0):
    """Conversion from the little-endian hex-digit byte-array to the network-byte-order
        hex-digit byte-array.

    bstr - the byte string.\n
    width - the data length, counted in byte."""

    bstr, blen = LengthAdjust(bstr, width)
    return Bs2Ba(''.join(reversed([bstr[b*2:(b+1)*2] for b in range(int(blen/2))])))


def LeInt(source, width=0):
    """Conversion from a normal decimal-digit string to the network-byte-order hex-digit
        byte-array.

    bstr - the byte string.\n
    width - the data length, counted in byte."""

    if sys.byteorder == 'little':
        return Le2N(hex(int(source)), width)
    return Bs2Ba(hex(int(source)))


def Guid2N(gstr):
    """Conversion from a UUID string to to the network-byte-order hex-digit byte-array."""

    # The canonical 8-4-4-4-12 format GUID string:
    # 123e4567-e89b-12d3-a456-426655440000
    # xxxxxxxx-xxxx-Mxxx-Nxxx-xxxxxxxxxxxx
    gs = gstr.split('-')
    try:
        if len(gs) != 5:
            raise Exception('')
        return Le2N(gs[0], 4) + Le2N(gs[1], 2) + Le2N(gs[2], 2) + Bs2Ba(gs[3], 2) + Bs2Ba(gs[4], 6)
    except Exception:
        print(f'Error: Incorrect GUID format: {gstr}')
        raise


def ParseInteger(evstr):
    """Parse a integer"""

    if evstr in {'+'}:
        return evstr
    #try:
    return int(eval(evstr, {}, {}))
    #except (SyntaxError, NameError) as ex:
    #    raise

class EditorAction():
    """The editor's action."""
    def __init__(self, edstr):
        self.target_offset = None
        self.source_data = None
        self.length = None
        self.operation = 'overwrite'
        self.hexdata = None
        self.from_offset = None
        self.encoding = 'utf-8'
        eds = ShlexSplit(edstr, {':'})
        debug_message(f'{str(eds)}')
        try:
            self.target_offset = ParseInteger(eds[0])
            self.source_data = eds[1]
            self.length = ParseInteger(eds[2])
            self.operation = eds[3].lower()
        except IndexError:
            pass

        if not self.source_data:
            raise Exception('Error')

        data_x = self.source_data.lower().split('=')

        def strx(data):
            if data.startswith('"') and data.endswith('"'):
                data = data[1:-1]
            return bytearray(data, encoding=self.encoding)
        def intx(data, width):
            if data_data.startswith('0x'):
                return Le2N(data[2:], width)
            return LeInt(data, width)

        if len(data_x) == 1:
            self.hexdata = strx(self.source_data)
        elif len(data_x) == 2:
            data_type, data_data = data_x
            if not data_type or not data_data:
                raise Exception(f'Incorrect source data: [{self.source_data}]')

            intz = re.match(r'(i|int|integer)(\d+)', data_type)
            if intz:
                # Handle these integers: i8, int8, intger8, i16, int16, integer 16....
                # Note: integer9 would be treated as integer16
                self.hexdata=intx(data_data, int(math.ceil(int(intz.group(2))/8.)))
            elif data_type in {'b', 'bytes'}:
                if data_data.startswith('0x'):
                    self.hexdata = Bs2Ba(data_data[2:])
            elif data_type in {'g', 'guid'}:
                self.hexdata = Guid2N(data_data)
                # NEWREL: Format check?
                # NEWREL: Shall we cover GUID with "big-endian"?
                # self.hexdata = Bs2Ba(data_data.replace('-', ''))
            elif data_type in {'s', 'string'}:
                self.hexdata = strx(data_data)
            elif data_type in {'from'}:
                self.hexdata = strx(data_data)
                self.from_offset = int(data_data, base=0)
        if not self.hexdata:
            raise Exception(f'Invalid data type or format: {self.source_data}')

        if isinstance(self.length, int):
            remain_len = self.length - len(self.hexdata)
            if remain_len > 0:
                self.hexdata += bytearray(remain_len)
            # NOTE: when the length of hexdata > the specified length,
            # its the editor's choice to either truncate or append the hexdata's content.
        elif self.length is None:
            self.length = len(self.hexdata)


    def __repr__(self):
        def _repr(member):
            if member in {None, '+'}:
                return 'auto'
            if isinstance(member, int):
                if member < 10:
                    return f'{member}'
                return f'{member:d}(0x{member:X})'
            return str(member)
        return '\n'.join([
            f'  target offset    : {_repr(self.target_offset)}',
            f'  source data      : {str(self.source_data)}',
            f'  length           : {_repr(self.length)}',
            f'  operation        : {self.operation}',
        ])


class CommandArgument(argparse.ArgumentParser):
    """The editor's argument"""
    def __init__(self, usage=''):
        if not usage:
            usage = 'bsed --file source[,target] --edit editor_action [editor_action_1 [editor_action_2]'
        argparse.ArgumentParser.__init__(self, usage=usage, prefix_chars='-/', fromfile_prefix_chars='@', add_help=False)
        self.add_argument('-f', '--file', dest='file', metavar='File', nargs='+', help='Specify the source file and the optional target file.')
        self.add_argument('-e', '--edit', dest='edit', metavar='Edit', nargs='+', help='The editor action that consists of offset:data[:length:[operation]]')
        self.add_argument('-x', '--auto_extend', action='store_true', help="Automatically extend the file size when writing data over the file boundary.")
        #self.add_argument('-d', '--dry-run', action='store_true', help="Dry run.")
        args, __unknown = self.parse_known_args(sys.argv[1:])

        if __unknown:
            self.specific_help = f'Surplus arguments: {__unknown}'

        self.edits = []
        self.auto_extend = args.auto_extend
        self.specific_help = ''
        self.need_help = self.format_help()
        if not args.file:
            self.specific_help = 'No specified file.'
            return
        if not args.edit:
            self.specific_help = 'No specified editor action.'
            return

        parms = ShlexSplit(','.join(args.file))
        if len(parms) > 2:
            self.specific_help = 'Too many specified files.'
            return
        self.input_file = parms[0]
        if len(parms) == 2:
            self.output_file = parms[1]
        else:
            self.output_file = ''

        for ed in args.edit:
            debug_message(f'ed: {str(ed)}')
            try:
                self.edits += [EditorAction(ed)]
            except Exception:
                self.specific_help = f'Invalid editor action: {ed}'
                raise #Exception('')
        self.need_help = ''

    def help(self):
        """ print  help message """
        print('Binary Steam Editor version 1.0\n')
        if self.specific_help:
            print(f'Argument error: {self.specific_help}\n' )
        if self.need_help:
            print(self.need_help)
        sys.exit(1)

    def __repr__(self):
        strs = []
        strs += [f'Source File: {self.input_file}']
        strs += [f'Target File: {self.output_file if self.output_file else self.input_file}']
        strs += [f'Editor Action{"s" if len(self.edits)>1 else ""}:']
        for ed in self.edits:
            strs += [str(ed), '']
        return '\n'.join(strs)


class Editor():
    """A UTF-8 editor"""

    def __init__(self, input_file, output_file=None, auto_extend=False):
        self.input_file = input_file
        self.output_file = output_file if output_file else input_file
        self.auto_extend = auto_extend
        self.content = bytearray()
        self.changed = 0
        self.previous_action = None
        try:
            self.content = bytearray(open(input_file, 'rb').read())
        except FileNotFoundError:
            if not self.auto_extend:
                raise

    def overwrite(self, action):
        """ overwrite a block of content """
        debug_message(f'action.target_offset: {action.target_offset}')
        debug_message(f'action.from_offset:   {action.from_offset}')
        debug_message(f'action.length:        {action.length}')
        debug_message(f'action.source_data:   {str(action.source_data)}')

        if action.from_offset is not None:
            data = self.content[action.from_offset:action.from_offset+action.length]
            dlen = len(data)
        #elif action.from_file is not None:
        #    pass
        else:
            debug_message(f'auto_extend: {self.auto_extend}')
            lenx = action.target_offset + action.length - len(self.content)
            if lenx > 0 and self.auto_extend:
                self.content.extend(bytearray(lenx))
            dlen = min(action.length, len(self.content) - action.target_offset)
            if dlen < 1:
                return # BUGBUG
            data = action.hexdata[:dlen]
        if self.content[action.target_offset:action.target_offset+dlen] != data:
            self.content[action.target_offset:action.target_offset+dlen] = data
            self.changed += 1

    def edit(self, action):
        """ apply the editor's action """
        if action.target_offset in {None, '+'} and self.previous_action:
            action.target_offset = self.previous_action.target_offset
            if action.target_offset in {None, '+'}:
                raise Exception('Invalid target offset')
            action.target_offset += self.previous_action.length

        if action.operation in {'overwrite', 'copy'}:
            self.overwrite(action)
        else:
            print(f'Unsupported editor action: {action.operation}')
        self.previous_action = action

    def commit(self):
        """Apply the changes to the target file."""

        if not self.changed:
            print('No modification.')
            return
        with open(self.output_file, 'wb') as fout:
            fout.write(self.content)
        print(f'{self.changed} change{"s" if self.changed>1 else ""} updated.')

if __name__ == '__main__':
    arg = CommandArgument()
    if arg.need_help:
        arg.help()
        sys.exit(1)

    input_file = arg.input_file
    output_file = arg.output_file if arg.output_file else arg.input_file
    try:
        ed = Editor(input_file, output_file, auto_extend=arg.auto_extend)
    except IOError:
        traceback.print_exc()
        sys.exit(2)

    print(str(arg))

    for ar in arg.edits:
        ed.edit(ar)
    ed.commit()

    sys.exit(0)
