#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from time import time
from drawBot import transform, FormattedString, textSize, pages, newPage, savedState, font, fontSize, cmykFill, tracking, text, saveImage, translate, oval, openTypeFeatures
import copy


MM2PT = 2.8346438836889
HAS_PAGE_FLAG = False

from typing import List, Dict, Optional
@dataclass
class Style:
    font: Optional[str] = None
    fallbackFont: Optional[str] = 'LucidaGrande'
    fontSize: float = None
    fill: Optional[tuple] = None
    cmykFill: tuple = (0.0, 0.0, 0.0, 1.0, 1.0)
    stroke: Optional[tuple] = None
    cmykStroke: Optional[tuple] = None
    strokeWidth: float = 1.0
    lineHeight: float = 20.8
    tracking: float = 0.0
    baselineShift: Optional[float] = None
    openTypeFeatures: Optional[Dict[str, bool]] = field(default_factory=dict)
    fontVariations: Optional[Dict[str, bool]] = field(default_factory=dict)
    tabs: Optional[tuple] = None
    language: Optional[str] = None

@dataclass
class Token:
    characters: str = ''
    token_type: str = 'char'

@dataclass
class Page:
    w: float = 210.0
    h: float = 297.0
    margins: tuple = (0, 0, 0, 0)

    def __post_init__(self):
        self.lm = self.margins[0] * MM2PT
        self.tm = self.margins[1] * MM2PT
        self.rm = self.margins[2] * MM2PT
        self.bm = self.margins[3] * MM2PT
        self.w *= MM2PT
        self.h *= MM2PT

@dataclass
class Rules:
    lock: str = r''
    flip: str = r''
    highlight: str = r''
    flip_hlgt: str = r''
    char: str = r''

    def __post_init__(self):
        self.all = self._all()

    def _all(self):
        return '|'.join(filter(lambda x: x != '', self.__dict__.values()))

@dataclass
class PrinterTask:
    chrs: str = ''
    pos: tuple = (0, 0)
    w:  float = 0.0
    flip: bool = False
    style: Style = Style()

def tokenize(raw_input: str, rules: Rules, styles: Dict[str, Style]) -> List[Token]:
    query = re.compile(rules.all)
    parsed_input = query.finditer(raw_input)
    tokens = []
    for raw_token in parsed_input:
        tokens.append(Token(characters=raw_token.group(),
                            token_type=raw_token.lastgroup))
    return tokens

def container(chrs: str, style: Style) -> FormattedString:
    fs = FormattedString()
    attributes = fs._validateAttributes(style.__dict__)
    for key, value in attributes.items():
        fs._setAttribute(key, value)
    fs._setColorAttributes(attributes)
    fs.append(chrs)
    return fs

def formattedWidth(chrs: str='', style: Style=Style(), cont: FormattedString=None) -> float:
    if not cont:
        cont = container(chrs, style)
    return textSize(cont)[0]

def makeLines(page: Page, tokens: List[Token], styles: Dict[str, Style], init_offset: tuple) -> List[List[Token]]:
    
    text_area_width = page.w - page.lm - page.rm
    cur_pos = init_offset
    lines = []
    while tokens:
        line = []
        first_char = True
        while cur_pos < text_area_width and tokens:
            token = tokens.pop(0)
            if first_char and isWhite(token.characters):
                first_char = False
            elif first_char:
                first_char = False
                line.append(token)
                cur_pos += formattedWidth(token.characters, styles[token.token_type])
            else:
                line.append(token)
                cur_pos += formattedWidth(token.characters, styles[token.token_type])
        
        if isWhite(line[-1].characters):
            line.pop()
        lines.append(line)
        cur_pos = 0
    return lines

def isWhite(s: str) -> bool:
    if re.match(r'\s', s):
        return True
    else:
        return False

def calcLineHeight(line: List[Token], styles: List[Style]) -> float:
    return max(styles[token.token_type].lineHeight for token in line)

def printer(task: PrinterTask, page: Page):

    with savedState():

        if task.style.font:
            font(task.style.font)
        if task.style.fontSize:
            fontSize(task.style.fontSize)   
        if task.style.cmykFill:
            cmykFill(*task.style.cmykFill) 
        if task.style.tracking:
            tracking(task.style.tracking)

        if task.flip:
            
            x_correction = task.w - textSize(FormattedString(task.chrs, font=task.style.font, fontSize=task.style.fontSize, tracking=0))[0]
            transform(( -1.0, 0.0,
                        0.0, 1.0,
                        task.pos[0]*2+task.w, 0))
            translate(x_correction, 0)
        openTypeFeatures(**task.style.openTypeFeatures)
        text(task.chrs, task.pos)
   
def mark(xy, m='', kind=1, s=2):
    x = xy[0] - s/2
    y = xy[1] - s/2
    if kind == 1:        
        oval(x, y, s, s)
    elif kind == 2:
        text(m, (x, y))

def trackingToJustify(line, styles, lenght):
    em = formattedWidth(' ', style=styles[list(styles.keys())[0]])
    stick = container('', styles[line[0].token_type])
    for token in line:
        style = copy.copy(styles[token.token_type])
        stick.append(token.characters, **style.__dict__)
    start_lenght = formattedWidth(cont=stick)
    if lenght < start_lenght or lenght - start_lenght < em:
        tracking_correction = (lenght - start_lenght) / len(line)
    else:
        tracking_correction = 0
    return tracking_correction

def drawLines(page: Page, lines: List[List[Token]], styles: Dict[str, Style], init_offset: tuple):
    cur_xy = [page.lm + init_offset, page.h - page.tm - calcLineHeight(lines[0], styles)]
    if not pages():
        newPage(page.w, page.h)
    direction = 1
    cnt = 0
    for line in lines:

        if cnt == 0:
            lenght = page.w - page.rm - cur_xy[0]
        else:
            lenght = page.w - page.lm - page.rm
        
        tracking_correction = trackingToJustify(line, styles, lenght)

        print(f'{round((cnt+1)/len(lines)*100):4}% | line {cnt+1:^2} tracking correction is {round(tracking_correction, 3):6} pt')

        lineHeight = calcLineHeight(line, styles)

        if direction == -1:
            cur_xy[0] -= formattedWidth(line[0].characters, styles[line[0].token_type])
        i = 0
        
        for i, token in enumerate(line):
            flip = True if direction == -1 and token.token_type[:4] == 'flip' else False
            style = copy.copy(styles[token.token_type])
            style.tracking += tracking_correction
            task = PrinterTask( chrs=token.characters,
                                pos=(cur_xy[0], cur_xy[1]),
                                flip=flip,
                                w=formattedWidth(token.characters, style),
                                style=style)

            if direction == 1:
                cur_xy[0] += formattedWidth(token.characters, style)
            else:
                if len(line) > i+1:
                    cur_xy[0] -= formattedWidth(line[i+1].characters, style)
            printer(task, page)
        
        if direction == 1:
            cur_xy[0] = page.w - page.rm
        if direction == -1:
            cur_xy[0] = page.lm

        cur_xy[1] -= lineHeight
        direction *= -1
        cnt += 1        

def directPrint(page: Page, txt: str, pos: tuple, style: Style):
    if not pages():
        newPage(page.w, page.h)
    
    if pos[0] == 'center' or 'right':
        w = formattedWidth(txt, style)
        pos = ((page.w - page.lm - page.rm) / 2 + page.lm - w/2, pos[1])
        
    task = PrinterTask( chrs=txt,
                        pos=pos,
                        style=style)
    printer(task, page)

if __name__ == "__main__":
    
    variables = {}
    with open("editor.txt") as f:
        for line in f:
            name, value = line.split("::")
            variables[name] = value.strip()
    
    start = time()

    m_x = 2.763 # width of module
    m_y = 2.154 # height of modul
    ml, mt, mr, mb = tuple(variables['margins'].split(' '))

    page = Page(    w=float(tuple(variables['page'].split(' '))[0]), 
                    h=float(tuple(variables['page'].split(' '))[1]),
                    margins=(float(ml)*m_x, float(mt)*m_y, float(mr)*m_x, float(mb)*m_y))
    
    rules = Rules(  lock=r'(?P<lock>\d+)(?=\W→)',
                    flip=r'(?P<flip>[»«\(\)' + variables['flip'] +'])',
                    highlight=r'(?P<highlight>МНОГО БУКВ)',
                    flip_hlgt=r'(?P<flip_hlgt>→)',
                    char=r'(?P<char>.|\s)',
                    )
    fontname = variables['fontname']
    fsize = float(variables['fsize'])
    lineheight = float(variables['lineheight'])
    logosize = float(variables['logosize'])
    if 'tracking' in variables:
        base_tracking = float(variables['tracking'])
    else:
        print('tracking not found in editor.txt and was set to default (0.0)')
        base_tracking = 0.0

    if 'features' in variables:
        features = {feature: True for feature in tuple(variables['features'].split(' '))}

    styles = {  'char': Style(      font=fontname,
                                    fontSize=fsize,
                                    tracking=base_tracking,
                                    lineHeight=lineheight,
                                    openTypeFeatures=features),
    
                'flip': Style(      font=fontname,
                                    fontSize=fsize,
                                    tracking=base_tracking,
                                    lineHeight=lineheight,
                                    openTypeFeatures=features),
    
                'lock': Style(      font=fontname,
                                    fontSize=fsize,
                                    tracking=base_tracking,
                                    cmykFill=(0.0, .74, .85, 0.0, 1.0),
                                    lineHeight=lineheight,
                                    openTypeFeatures=features),

                'highlight': Style( font=fontname,
                                    fontSize=fsize,
                                    tracking=base_tracking,
                                    cmykFill=(0.0, .74, .85, 0.0, 1.0),
                                    lineHeight=lineheight,
                                    openTypeFeatures=features),

                'flip_hlgt': Style( font=fontname,
                                    fontSize=fsize,
                                    tracking=base_tracking,
                                    cmykFill=(0.0, .74, .85, 0.0, 1.0),
                                    lineHeight=lineheight,
                                    openTypeFeatures=features),

                'logo': Style(      font=fontname,
                                    fontSize=logosize,
                                    tracking=base_tracking,
                                    openTypeFeatures=features,
                                    ),
                }
    
    txt = variables['txt']
    logo = variables['logo']

    init_offset = float(variables['init_offset'])

    end = time()
    print(f'It took {round(end-start, 1)} seconds to init')
    
    start = time()
    tokens = tokenize(txt, rules, styles)
    
    end = time()
    print(f'It took {round(end-start, 1)} seconds to tokenize text')
    
    start = time()
    lines = makeLines(page, tokens, styles, init_offset)
    
    end = time()
    print(f'It took {round(end-start, 1)} seconds to make lines')
    
    start = time()
    drawLines(page, lines, styles, init_offset)

    directPrint(page, logo, ('center', page.bm), styles['logo'])
    end = time()
    print(f'It took {round(end-start, 1)} seconds to draw them')
    
    start = time()
    date = datetime.now().strftime('%d-%B-%Y-%Hh.%Mm.%Ss').replace('-', '—')
    saveImage(f'output/cover_by_code—{date}.pdf')
    saveImage('output/cover_by_code—temp.pdf')
    end = time()
    print(f'It took {round(end-start, 1)} seconds to save the file')