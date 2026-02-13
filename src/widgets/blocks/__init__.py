# __init__.py

import re

from .latex import LatexRenderer
from .text import Text, GeneratingText, EditingText
from .table import Table
from .code import Code
from .separator import Separator
from .thinking import Thinking
from .inline_picture import InlinePicture

from .. import attachments
from ...sql_manager import generate_uuid, Instance as SQL

patterns = [
    r'(?P<online_picture>!\[(?P<label>[^\]]*)\]\((?P<url>.*?)\))',
    r'(?P<code>```(?P<language>[a-zA-Z0-9_+\-]*)\n(?P<code_content>.*?)\n\s*```)',
    r'(?P<latex>\\\[\s*(?P<latex_content1>.*?)\s*\\\]|\$\$\s*(?P<latex_content2>.*?)\s*\$\$)',
    r'(?P<table>(?:^|(?<=\n))\|[^\n]*\|[\s\xa0]*\n\|[\s\xa0\-|:]*\|[\s\xa0]*\n(?:\|[^\n]*\|(?:[\s\xa0]*\n|$))+)',
    r'(?P<line>^\s*-{3,}\s*$|\n-{3,}\n)'
]
master_regex = re.compile('|'.join(patterns), re.DOTALL | re.MULTILINE)


def text_to_block_list(raw_content:str):
    blocks = []
    last_idx = 0

    for match in master_regex.finditer(raw_content):
        if match.start() > last_idx:
            content = raw_content[last_idx:match.start()]
            if content:
                if len(blocks) > 0 and isinstance(blocks[-1], Text):
                    blocks[-1].append_content(content)
                else:
                    blocks.append(
                        Text(content=content)
                    )

        kind = match.lastgroup

        if kind == 'online_picture':
            url = match.group('url')
            # label = match.group('label')
            if url:
                blocks.append(
                    InlinePicture(url=url)
                )

        elif kind == 'code':
            content = match.group('code_content')
            language = match.group('language')
            if content:
                if language.lower() == 'latex':
                    blocks.append(
                        LatexRenderer(content=content)
                    )
                else:
                    blocks.append(
                        Code(content=content, language=language)
                    )

        elif kind == 'latex':
            content = match.group('latex_content1').strip() or match.group('latex_content2').strip()
            if content:
                if '\\' in content:
                    blocks.append(LatexRenderer(content=content))
                else:
                    if len(blocks) > 0 and isinstance(blocks[-1], Text):
                        blocks[-1].append_content(content)
                    else:
                        blocks.append(
                            Text(content=content)
                        )

        elif kind == 'table':
            content = match.group(0)
            if content:
                blocks.append(Table(content=content))
        elif kind == 'line':
            blocks.append(Separator())

        last_idx = match.end()

    if last_idx < len(raw_content):
        content = raw_content[last_idx:]
        if len(blocks) > 0 and isinstance(blocks[-1], Text):
            blocks[-1].append_content(content)
        else:
            blocks.append(
                Text(content=content)
            )

    return blocks


def text_to_block_listOLD(content: str):
    print(content)
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
        if pos < mb.start and content[pos:mb.start]:
            snippet = content[pos:mb.start]
            if snippet:
                if blocks and isinstance(blocks[-1], Text):
                    blocks[-1].append_content(snippet)
                else:
                    blocks.append(Text(content=snippet))

        match = mb.match
        if mb.name == "online_picture":
            url = match.group(1).strip()
            if url:
                blocks.append(
                    InlinePicture(
                        url=url
                    )
                )
        elif mb.name == "code":
            code_content = match.group(2)
            language = match.group(1)
            if code_content:
                if language.lower() == 'latex':
                    blocks.append(LatexRenderer(content=code_content))
                else:
                    blocks.append(Code(content=code_content, language=language))
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
            content = content[mb.start:mb.end]
            if content:
                blocks.append(Table(content=content))
        elif mb.name == "line":
            blocks.append(Separator())

        pos = mb.end

    # Remaining text after last match
    if pos < len(content):
        rest = content[pos:]
        if rest:
            if blocks and isinstance(blocks[-1], Text):
                blocks[-1].append_content(rest)
            else:
                blocks.append(Text(content=rest))

    return blocks
