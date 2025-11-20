# __init__.py

import re

from .latex import LatexRenderer
from .text import Text, GeneratingText, EditingText
from .table import Table
from .code import Code
from .separator import Separator
from .thinking import Thinking
from collections import namedtuple

from .. import attachments
from ...sql_manager import generate_uuid, Instance as SQL

patterns = [
    ('code', re.compile(r'```([a-zA-Z0-9_+\-]*)\n(.*?)\n\s*```', re.DOTALL)),
    ('latex', re.compile(r'\\\[\n*?(.*?)\n*?\\\]|\$+\n*?(.*?)\$+\n*?', re.DOTALL)),
    ('table', re.compile(r'((?:\| *[^|\r\n]+ *)+\|)(?:\r?\n)((?:\|[ :]?-+[ :]?)+\|)((?:(?:\r?\n)(?:\| *[^|\r\n]+ *)+\|)+)', re.MULTILINE)),
    ('line', re.compile(r'^\s*-{3,}\s*$')), # For live rendering
    ('line', re.compile(r'\n-{3,}\n')) # For normal rendering
]

# Match holder
MatchBlock = namedtuple('MatchBlock', ['start', 'end', 'name', 'match'])

def text_to_block_list(content: str):
    matches = []

    # Collect all matches
    for name, pattern in patterns:
        for match in pattern.finditer(content):
            matches.append(MatchBlock(match.start(), match.end(), name, match))

    # Sort matches by their start position
    matches.sort(key=lambda m: m.start)

    blocks = []
    pos = 0

    for mb in matches:
        if pos < mb.start and content[pos:mb.start].strip():
            snippet = content[pos:mb.start]
            if blocks and isinstance(blocks[-1], Text):
                blocks[-1].append_content(snippet)
            else:
                blocks.append(Text(content=snippet))

        match = mb.match
        if mb.name == "code":
            if match.group(1).lower() == 'latex':
                blocks.append(LatexRenderer(content=match.group(2)))
            else:
                blocks.append(Code(content=match.group(2), language=match.group(1)))
        elif mb.name == "latex":
            expression = match.group(1) or match.group(2)
            if expression:
                if '\\' in expression:
                    blocks.append(LatexRenderer(content=expression))
                else:
                    if blocks and isinstance(blocks[-1], Text):
                        blocks[-1].append_content(expression)
                    else:
                        blocks.append(Text(content=expression))
        elif mb.name == "table":
            blocks.append(Table(content=content[mb.start:mb.end]))
        elif mb.name == "line":
            blocks.append(Separator())

        pos = mb.end

    # Remaining text after last match
    if pos < len(content):
        rest = content[pos:]
        if rest.strip():
            if blocks and isinstance(blocks[-1], Text):
                blocks[-1].append_content(rest)
            else:
                blocks.append(Text(content=rest))

    return blocks
