#!/usr/bin/env python

"""Simple Bytes Editor / Binary Stream Editor.

Usage:
    bsed --file source[,target] --edit editor_action [editor_action_1 [editor_action_2]
        edit_action: target_offset:source_data:[data_length[:operation]]
        operation: can be either "overwrite" or "copy". Default: overwrite

Copyright (c) 2018, Timothy Lin
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the "Simple Binary Stream Editor" project."""


from __future__ import print_function

import os
import re
import sys
import shlex
import argparse


def ShlexSplit(shstr, splitters={','}, escape=''):
    """Syntactically split a string with specified splitters, which honors its sub-strings
       in the quotation marks."""

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
    """Adjust the length of a byte-string to meet the byte-width with leading padding "0" regardless of its endianess.

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
    """ Conversion from a hex-digit byte-string to the network-byte-order hex-digit byte-array.

    bstr - the byte string.\n
    width - the data length, counted in byte."""

    bstr, blen = LengthAdjust(bstr, width)
    return bytearray([int(bstr[b*2:(b+1)*2], base=0x10) for b in range(int(blen/2))])


def Le2N(bstr, width=0):
    """ Conversion from the little-endian hex-digit byte-array to the network-byte-order hex-digit byte-array.

    bstr - the byte string.\n
    width - the data length, counted in byte."""

    bstr, blen = LengthAdjust(bstr, width)
    return Bs2Ba(''.join(reversed([bstr[b*2:(b+1)*2] for b in range(int(blen/2))])))


def LeInt(source, width=0):
    """Conversion from a normal decimal-digit string to the network-byte-order hex-digit byte-array.

    bstr - the byte string.\n
    width - the data length, counted in byte."""

    if sys.byteorder == 'little':
        return Le2N(hex(int(source)), width)
    else:
        return Bs2Ba(hex(int(source)))


def Guid2N(gstr):
    """Conversion from a UUID string to to the network-byte-order hex-digit byte-array"""

    # The canonical 8-4-4-4-12 format GUID string:
    # 123e4567-e89b-12d3-a456-426655440000
    # xxxxxxxx-xxxx-Mxxx-Nxxx-xxxxxxxxxxxx 
    gs = gstr.split('-')
    try:
        if len(gs) != 5: raise Exception('')
        return Le2N(gs[0], 4) + Le2N(gs[1], 2) + Le2N(gs[2], 2) + Bs2Ba(gs[3], 2) + Bs2Ba(gs[4], 6)
    except Exception:
        raise Exception('Incorrect Guid format:%s' % gstr)


def SafeEval(evalstr, default=None, globalz=None, localz=None):
    """A safer wrapper for eval()"""

    if not globalz:
        globalz = {}
    if not localz:
        localz = {}
    try:
        return eval(evalstr, globalz, localz)
    except SyntaxError:
        return default if default else evalstr


class EditorAction(object):
    """The editor's action"""
    def __init__(self, edstr):
        self.target_offset = None
        self.source_data = None
        self.length = None
        self.operation = 'overwrite'
        self.hexdata = None
        self.from_offset = None
        self.encoding = 'utf-8'
        eds = ShlexSplit(edstr, {':'})
        try:
            self.target_offset = SafeEval(eds[0]) if eds[0] else None
            self.source_data = eds[1]
            self.length = SafeEval(eds[2]) if eds[2] else None
            self.operation = eds[3]
        except IndexError:
            pass

        if not self.source_data:
            raise Exception('Error')

        data_x = self.source_data.lower().split('=')

        def strx(data):
            if data.startswith('"') and self.source_data.endswith('"'):
                return bytearray(data[1:-1], encoding=self.encoding)
            else:
                return bytearray(data, encoding=self.encoding)
        def intx(data, width):
            if data_data.startswith('0x'):
                return Le2N(data[2:], width)
            else:
                return LeInt(data, width)

        if len(data_x) == 1:
            self.hexdata = strx(self.source_data)
        elif len(data_x) == 2:
            data_type, data_data = data_x

            if data_type in {'i8', 'int8', 'integer8'}:
                self.hexdata = intx(data_data, 1)
            elif data_type in {'i16', 'int16', 'integer16'}:
                self.hexdata = intx(data_data, 2)
            elif data_type in {'i32', 'int32', 'integer32'}:
                self.hexdata = intx(data_data, 4)
            elif data_type in {'i32', 'int64', 'integer64'}:
                self.hexdata = intx(data_data, 8)
            elif data_type in {'i128', 'int128', 'integer128'}:
                self.hexdata = intx(data_data, 16)
                # NEWREL: what else?
                # NEWREL: use RE: '(i|int|integer)(\d+)'
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
            raise Exception('Invalid data type or format:%s.' % self.source_data)

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
            if (member is None) or (not isinstance(member, int)):
                return '%s' % str(member)
            else:
                return '0x%X(%d)' % (member, member)
        return '\n'.join([
            '  target offset    : %s' % _repr(self.target_offset),
            '  source data      : %s' % str(self.source_data),
            '  length           : %s' % _repr(self.length),
            '  operation        : %s' % self.operation,
        ])


class CommandArgument(argparse.ArgumentParser):
    def __init__(self, usage=''):
        if not usage:
            usage = 'bsed --file source[,target] --edit editor_action [editor_action_1 [editor_action_2]'
        argparse.ArgumentParser.__init__(self, usage=usage, prefix_chars='-/', fromfile_prefix_chars='@', add_help=False)
        self.add_argument('-f', '--file', dest='file', metavar='File', nargs='+', help='Specify the source file and the optional target file.')
        self.add_argument('-e', '--edit', dest='edit', metavar='Edit', nargs='+', help='The editor action that consists of offset:data[:length:[operation]]')
        args, __unknown = self.parse_known_args(sys.argv[1:])

        self.edits = []
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
            try:
                self.edits += [EditorAction(ed)]
            except Exception:
                self.specific_help = 'Invalid editor action:%s' % ed
                raise
        self.need_help = ''
        
    def help(self):
        if arg.specific_help:
            print('Argument error: %s\n' % arg.specific_help)
        if arg.need_help:
            print('%s' % arg.need_help)
        sys.exit(1)

    def __repr__(self):
        strs = []
        strs += ['Source File: %s' % self.input_file]
        strs += ['Target File: %s' % self.output_file]
        strs += ['Editor Action%s:' % ('s' if len(self.edits)>1 else '')]
        for ed in self.edits:
            strs += [str(ed), '']
        return '\n'.join(strs)


class Editor(object):
    """A UTF-8 editor"""
    
    def __init__(self, input_file, output_file=None):
        self.input_file = input_file
        self.output_file = output_file if output_file else input_file
        with open(input_file, 'rb') as fin:
            self.content = bytearray(fin.read())
        self.changed = False
        self.PreviousAction = None

    def overwrite(self, action):
        dlen = min(action.length, len(self.content) - action.target_offset)
        if dlen < 1:
            return # Ignore the overrun error. Or, what shall we do?
        # BUGBUG: boundary-hit is not verify.
        self.content[action.target_offset:action.target_offset+dlen] = action.hexdata[:dlen]
        self.changed = True
        
    def copyover(self, action):
        if action.from_offset is not None:
            data = self.content[action.from_offset:action.from_offset+action.length]
        else:
            return  # TODO: the source content could be derived from a source file.
        if len(data) < 1:
            return # Ignore the overrun error. Or, what shall we do?
        # BUGBUG: boundary-hit is not verify.
        self.content[action.target_offset:action.target_offset+len(data)] = data
        self.changed = True
    
    def edit(self, action):
        if action.target_offset in {None, '+'} and self.PreviousAction:
            action.target_offset = self.PreviousAction.target_offset
            if action.target_offset in {None, '+'}:
                raise Exception('Invalid target offset')
            action.target_offset += self.PreviousAction.length

        if action.operation == 'overwrite':
            self.overwrite(action)
        elif action.operation in {'copy', 'copyover'}:
            self.copyover(action)
        #elif action.operation == 'insert':
        #    self.insert(action)
        else:
            print('Unsupported editor action: %s' % action.operation)
        self.PreviousAction = action

    def commit(self):
        """Apply the changes to the target file."""

        if self.changed:
            with open(self.output_file, 'wb') as fout:
                fout.write(self.content)


    #def __exit__(self ,type, value, traceback):
    #    pass


if __name__ == '__main__':
    arg = CommandArgument()
    if arg.need_help:
        arg.help()
        sys.exit(1)

    input_file = arg.input_file
    output_file = arg.output_file if arg.output_file else arg.input_file
    ed = Editor(input_file, output_file)
    for ar in arg.edits:
        ed.edit(ar)
    ed.commit()
        
    print('%s' % str(arg))