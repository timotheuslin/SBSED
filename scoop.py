#!/usr/bin/env python

"""Scoop Editor - copy a specified portion of a binary file

Usage:
    scoop source-file target-file:start-offset:size

The 2-Clause BSD License:
https://opensource.org/licenses/BSD-2-Clause

Copyright (c) 2021, Timothy Lin
All rights reserved.
"""

import os
import sys
import shlex


def shlex_split(shstr, splitters=None, escape=''):
    """Syntactically split a string with specified splitters, which honors its sub-strings
       in the quotation marks."""

    if splitters is None:
        splitters = {','}
    lex = shlex.shlex(shstr)
    lex.escape = escape
    lex.commenters = ''
    parms = ['']
    for tok in list(lex):
        tok = tok.strip()
        if tok not in splitters:
            parms[-1] += tok
        else:
            parms += ['']
    return parms


def scoop(source, target, offset, size):
    """ copy a specified portion of a binary file """

    truncated = False
    try:
        source_size = os.path.getsize(source)
    except FileNotFoundError:
        return 1, f'Invalid source: {source}'

    if offset > source_size:
        return 1, f"offset: {offset} is not less than the source file's size: {source_size}"

    if (offset+size) > source_size:
        truncated = True
        size = source_size - offset
    try:
        with open(source, 'rb') as fin:
            fin.seek(offset)
            content = fin.read(size)
    except Exception:
        return 1, f'Invalid source: {source}'

    try:
        with open(target, 'wb') as fout:
            fout.write(content)
    except Exception:
        return 1, f'Invalid target: {target}'

    return 0, '' if not truncated else f'  but *truncated* as {size} byte{"s" if size>1 else ""}'


def usage(msg):
    """ Usage """

    if msg:
        print(f"Error: {msg}\n")
    print("Usage: scoop SOURCE-file TARGET-file:scoop-OFFSET:scoop-SIZE")


if __name__ == '__main__':
    ERROR_MSG = None
    try:
        source_file = sys.argv[1]
        target3 = shlex_split(sys.argv[2], ',:')
        if len(target3) != 3:
            ERROR_MSG = f'Invalid target:{sys.argv[2]}'
        TARGET_FILE = target3[0]
        ERROR_MSG = f'Start-offset is not a valid integer: {target3[1]}'
        start_offset = int(target3[1], base=0)
        if start_offset <=0:
            raise
        ERROR_MSG = f'Size is not a valid integer: {target3[2]}'
        size0 = int(target3[2], base=0)
        if size0 <=0:
            raise
        ERROR_MSG = None
    except IndexError:
        if ERROR_MSG is None:
            ERROR_MSG = ''
    except Exception:
        if ERROR_MSG is None:
            ERROR_MSG = 'Invalid argument'

    if (ERROR_MSG is not None) or (sys.argv[1].lower() in {'-h', '--help'}):
        usage(ERROR_MSG)
        sys.exit(1)

    ret = scoop(source_file, TARGET_FILE, start_offset, size0)
    if ret[0] == 0:
        print(
            f'COPY {source_file} TO {TARGET_FILE} FROM {start_offset} '
            f'WITH {size0} byte{"s" if size0>1 else ""}'
        )
    if ret[1]:
        print(ret[1])

    sys.exit(ret[0])
