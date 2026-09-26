"""Hand-encoded x64 graphical Tetris, no compiler / assembler / linker.
Python writes the specified instruction bytes and PE metadata; never packaged.
The core and every drawing/window procedure are native machine instructions.
"""
from machine_core import *

CW,CH=800,800
CELL,BX,BY=30,40,128

def wide(name,s): data(name,s.encode('utf-16le')+b'\0\0',2)
def qword(name): data(name,bytes(8),8)
def color(s):
    n=int(s.strip('#'),16)
    return ((n&255)<<16)|(n&0xff00)|(n>>16)
def stack32(off,val): c.emit('C7 44 24');c.raw(bytes([off]));c.u32(val)
def arg_rax(off): c.emit('48 89 44 24');c.raw(bytes([off]))

wide('class_name','ByteTetrisHandEncoded64')
wide('window_title','BYTE TETRIS - Machine Code Edition')
wide('font_segoe','Segoe UI');wide('font_mono','Consolas')
labels_text={
 'brand':'BYTE', 'brand_suffix':'/ TETRIS',
 'subtitle':'A small game. Nothing but native bytes.',
 'badge':'NATIVE  /  X64', 'playfield':'PLAYFIELD', 'dimensions':'10 x 20',
 'score_label':'SCORE', 'lines_label':'LINES', 'level_label':'LEVEL',
 'next_label':'NEXT PIECE', 'next_caption':'A new shape. A fresh chance.',
 'controls_label':'HOW TO PLAY', 'key_move':'\u2190  \u2192', 'key_rotate':'\u2191 / X',
 'key_drop':'SPACE', 'key_pause':'P / R', 'move_help':'Move sideways',
 'rotate_help':'Rotate', 'drop_help':'Hard drop', 'pause_help':'Pause / restart',
 'soft_help':'\u2193  Soft drop          Esc  Quit',
 'footer':'HAND-ENCODED X64', 'footer_right':'One file. No language runtime.',
 'pause_title':'Paused', 'pause_subtitle':'P  TO CONTINUE',
 'over_title':'Game over', 'over_subtitle':'R  TO PLAY AGAIN',
 'running':'PLAY YOUR WAY',
}
for name,value in labels_text.items():wide('txt_'+name,value)
for name in ['score_buf','lines_buf','level_buf']:data(name,bytes(32),2)
for name in ['hwnd','instance','draw_dc','bitmap','old_bitmap','screen_dc','pixels_ptr']:
    qword(name)
word('ghost_y');word('paint_count');word('outer_w');word('outer_h');word('window_x');word('window_y')
word('dark_enabled',1);word('caption_color',color('#0b101d'))
data('wndclass',bytes(80),8);data('message',bytes(48),8);data('paint_struct',bytes(72),8)
data('client_rect',p32(0)+p32(0)+p32(CW)+p32(CH))
data('bitmap_info',struct.pack('<IiiHHIIiiII',40,CW,-CH,1,32,0,CW*CH*4,0,0,0,0))
data('text_rect',bytes(16));data('backdrop_rect',bytes(16))

# COLORREF constants and live GDI brush handles. These are pure data, no assets.
UI_COLORS=['#0b101d','#25324a','#111b2d','#0e1626','#152036','#5be7c4','#202d44','#172338','#070c16','#1b2940']
brush_names=['bg','border','panel','board','grid','accent','key','overlay','shadow','divider']
piece_colors=['#5be7e9','#6294ff','#ffb862','#f7d96d','#63deb4','#bb96fa','#ff788f']
def shade(s,mix,target=0):
    rgb=[int(s[i:i+2],16) for i in (1,3,5)]
    return '#'+''.join(f'{round(v*(1-mix)+target*mix):02x}' for v in rgb)
ALL_COLORS=UI_COLORS[:]
for i,s in enumerate(piece_colors):
    for suffix,value in [('edge',shade(s,.50)),('face',s),('shine',shade(s,.42,255)),('ghost',shade(s,.70))]:
        brush_names.append(f'p{i}_{suffix}');ALL_COLORS.append(value)
data('brush_colors',b''.join(p32(color(s)) for s in ALL_COLORS))
data('brushes',bytes(8*len(ALL_COLORS)),8)
for i,name in enumerate(brush_names):d.labels['brush_'+name]=d.labels['brushes']+i*8
FONT_SPECS=[(14,600),(16,400),(34,700),(46,600),(28,600),(14,600)]
# Preview origins center each mask's occupied cells, rather than its 4x4 box.
preview_origins=[]
for rotation_set in shapes:
    occupied=[(i%4,i//4) for i in range(16) if rotation_set[0]>>i&1]
    xs=[p[0] for p in occupied];ys=[p[1] for p in occupied]
    preview_origins.extend([576-(min(xs)+max(xs)+1)*15,382-(min(ys)+max(ys)+1)*15])
data('preview_origins',b''.join(p32(v) for v in preview_origins))
data('fonts',bytes(8*len(FONT_SPECS)),8)
for i in range(len(FONT_SPECS)):d.labels['font_'+str(i)]=d.labels['fonts']+8*i

# Generic primitives, called by hand-encoded drawing code below.
# rounded(ECX=x, EDX=y, R8D=w, R9D=h, RAX=brush, R10D=corner diameter)
c.start('rounded')
c.emit('89 CB 89 D6 44 89 C7 45 89 CC 49 89 C5 45 89 D6')
load('48 8B 0D','draw_dc');c.emit('4C 89 EA');c.api('SelectObject')
load('48 8B 0D','draw_dc');c.emit('89 DA 41 89 F0 41 89 D9 41 01 F9')
c.emit('44 89 E0 01 F0 89 44 24 20 44 89 74 24 28 44 89 74 24 30')
c.api('RoundRect');c.end('rounded')

# gui_text(ECX=x, EDX=y, R8=text, R9D=font index, R10D=COLORREF)
c.start('gui_text')
c.emit('89 CB 89 D6 4D 89 C4 45 89 CD 45 89 D6')
load('48 8B 0D','draw_dc');load('48 8D 05','fonts');c.emit('4A 8B 14 E8');c.api('SelectObject')
load('48 8B 0D','draw_dc');c.emit('44 89 F2');c.api('SetTextColor')
load('4C 8D 0D','text_rect')
c.emit('41 89 19 41 89 71 04 8D 83 20 03 00 00 41 89 41 08 8D 46 64 41 89 41 0C')
load('48 8B 0D','draw_dc');c.emit('4C 89 E2 41 B8 FF FF FF FF');stack32(32,0x920)
c.api('DrawTextW');c.end('gui_text')

# format_number(ECX=value, EDX=digits, R8=UTF16 output buffer)
c.start('format_number')
c.emit('4C 89 C7 89 C8 89 D1 BB 0A 00 00 00')
c.emit('48 8D 3C 57 66 C7 07 00 00 48 83 EF 02')
c.mark('format_loop')
c.emit('31 D2 F7 F3 83 C2 30 66 89 17 48 83 EF 02 FF C9');j('0F 85','format_loop')
c.end('format_number')

# tile_xy(ECX=pixel x,EDX=pixel y,R8D=color 1..7), 3-layer beveled tile.
c.start('tile_xy')
c.emit('89 CB 89 D6 45 89 C4 41 FF CC 41 C1 E4 05') # r12=brush offset (kind-1)*32
load('4C 8D 2D','brush_p0_edge')
c.emit('4D 01 E5 49 8B 45 00')
c.emit('8D 4B 01 8D 56 01 41 B8 1C 00 00 00 41 B9 1C 00 00 00 41 BA 08 00 00 00');c.call('rounded')
c.emit('49 8B 45 08 8D 4B 01 8D 56 01 41 B8 1C 00 00 00 41 B9 18 00 00 00 41 BA 08 00 00 00');c.call('rounded')
c.emit('49 8B 45 10 8D 4B 05 8D 56 04 41 B8 14 00 00 00 41 B9 02 00 00 00 41 BA 02 00 00 00');c.call('rounded')
c.end('tile_xy')

# board tile with active coordinates translated to pixels.
c.start('gui_tile')
c.emit('6B C9 1E 83 C1 28 6B D2 1E 81 C2 80 00 00 00');c.call('tile_xy');c.end('gui_tile')

# Ghost uses a dim outline on the existing board cell.
c.start('ghost_tile')
c.emit('6B D9 1E 83 C3 28 6B F2 1E 81 C6 80 00 00 00')
c.emit('45 89 C4 41 FF CC 41 C1 E4 05')
load('48 8D 05','brush_p0_ghost');c.emit('4A 8B 04 20')
c.emit('8D 4B 02 8D 56 02 41 B8 1A 00 00 00 41 B9 1A 00 00 00 41 BA 08 00 00 00');c.call('rounded')
load('48 8B 05','brush_grid')
c.emit('8D 4B 04 8D 56 04 41 B8 16 00 00 00 41 B9 16 00 00 00 41 BA 06 00 00 00');c.call('rounded')
c.end('ghost_tile')

# Static call-site helpers only concatenate chosen opcode bytes and constants.
def box(x,y,w,h,brush,radius=16):
    c.emit('B9');c.u32(x);c.emit('BA');c.u32(y);c.emit('41 B8');c.u32(w);c.emit('41 B9');c.u32(h)
    load('48 8B 05','brush_'+brush);c.emit('41 BA');c.u32(radius);c.call('rounded')
def say(name,x,y,font=0,tint='#eef3fb',raw=False):
    c.emit('B9');c.u32(x);c.emit('BA');c.u32(y)
    load('4C 8D 05',name if raw else 'txt_'+name)
    c.emit('41 B9');c.u32(font);c.emit('41 BA');c.u32(color(tint));c.call('gui_text')
def card(x,y,w,h):
    box(x,y+4,w,h,'shadow',20);box(x,y,w,h,'border',20);box(x+1,y+1,w-2,h-2,'panel',18)

c.start('ghost_position')
load('8B 1D','y')
c.mark('ghost_seek')
load('8B 0D','x');c.emit('8D 53 01');load('44 8B 05','mask');c.call('collides')
c.emit('85 C0');j('0F 85','ghost_found');c.emit('FF C3');j('E9','ghost_seek')
c.mark('ghost_found');load('89 1D','ghost_y');c.emit('89 D8');c.end('ghost_position')

# The full scene is drawn to a compatible memory bitmap, then one BitBlt.
c.start('paint_frame')
box(0,0,CW,CH,'bg',0)
# Brand, lightweight top badge.
say('brand',28,24,2);say('brand_suffix',127,24,2,'#91a3bd')
say('subtitle',29,72,1,'#7587a5')
box(598,32,174,32,'panel',16);box(610,43,8,8,'accent',8)
say('badge',630,39,0,'#5be7c4')
say('playfield',40,97,0,'#7587a5');say('dimensions',286,97,0,'#7587a5')
card(28,116,324,624)
box(BX-2,BY-2,304,604,'board',8)
# Board grid: rounded inset cells with two-pixel gutters.
c.emit('45 31 E4') # r12d=index
c.mark('grid_loop')
c.emit('44 89 E0 31 D2 B9 0A 00 00 00 F7 F1')
c.emit('6B CA 1E 83 C1 29 6B D0 1E 81 C2 81 00 00 00')
c.emit('41 B8 1C 00 00 00 41 B9 1C 00 00 00 41 BA 06 00 00 00')
load('48 8B 05','brush_grid');c.call('rounded')
c.emit('41 FF C4 41 81 FC C8 00 00 00');j('0F 82','grid_loop')
# Locked blocks.
load('48 8D 35','board');c.emit('31 DB')
c.mark('settled_loop')
c.emit('44 0F B6 04 1E 45 85 C0');j('0F 84','settled_next')
c.emit('89 D8 31 D2 B9 0A 00 00 00 F7 F1 89 D1 89 C2');c.call('gui_tile')
c.mark('settled_next');c.emit('FF C3 81 FB C8 00 00 00');j('0F 82','settled_loop')
load('8B 05','game_over');c.emit('85 C0');j('0F 85','gui_hud')
c.call('ghost_position');load('44 8B 25','mask');c.emit('45 31 ED')
c.mark('ghost_draw_loop')
c.emit('45 0F A3 EC');j('0F 83','ghost_draw_next')
c.emit('44 89 E9 83 E1 03');load('03 0D','x')
c.emit('44 89 EA C1 EA 02');load('03 15','ghost_y')
load('44 8B 05','kind');c.emit('41 FF C0');c.call('ghost_tile')
c.mark('ghost_draw_next');c.emit('41 FF C5 41 83 FD 10');j('0F 82','ghost_draw_loop')
c.emit('45 31 ED')
c.mark('active_draw_loop')
c.emit('45 0F A3 EC');j('0F 83','active_draw_next')
c.emit('44 89 E9 83 E1 03');load('03 0D','x')
c.emit('44 89 EA C1 EA 02');load('03 15','y')
load('44 8B 05','kind');c.emit('41 FF C0');c.call('gui_tile')
c.mark('active_draw_next');c.emit('41 FF C5 41 83 FD 10');j('0F 82','active_draw_loop')
c.mark('gui_hud')
card(380,116,392,160)
say('score_label',404,136,0,'#91a3bd')
load('8B 0D','score');c.emit('BA 06 00 00 00');load('4C 8D 05','score_buf');c.call('format_number')
say('score_buf',399,157,3,raw=True)
box(568,140,1,112,'divider',0)
say('lines_label',592,136,0,'#91a3bd')
load('8B 0D','lines');c.emit('BA 03 00 00 00');load('4C 8D 05','lines_buf');c.call('format_number')
say('lines_buf',590,155,4,raw=True)
say('level_label',592,218,0,'#91a3bd')
load('8B 05','lines');c.emit('31 D2 B9 0A 00 00 00 F7 F1 FF C0 89 C1 BA 02 00 00 00')
load('4C 8D 05','level_buf');c.call('format_number')
say('level_buf',697,212,4,'#5be7c4',True)
box(405,236,7,7,'accent',7);say('running',420,231,0,'#7587a5')
card(380,292,392,176);say('next_label',404,312,0,'#91a3bd')
# Preview occupies a stable 4x4 frame with piece-specific centering.
load('8B 05','next_kind');load('48 8D 15','preview_origins');c.emit('44 8B 34 C2 44 8B 7C C2 04 C1 E0 04');load('48 8D 15','shapes');c.emit('44 8B 24 02 45 31 ED')
c.mark('next_draw_loop')
c.emit('45 0F A3 EC');j('0F 83','next_draw_skip')
c.emit('44 89 E9 83 E1 03 6B C9 1E 44 01 F1') # centered x
c.emit('44 89 EA C1 EA 02 6B D2 1E 44 01 FA') # centered y
load('44 8B 05','next_kind');c.emit('41 FF C0');c.call('tile_xy')
c.mark('next_draw_skip');c.emit('41 FF C5 41 83 FD 10');j('0F 82','next_draw_loop')
say('next_caption',404,437,0,'#7587a5')
card(380,484,392,256);say('controls_label',404,504,0,'#91a3bd')
for y,keytext,helptext in [(536,'key_move','move_help'),(576,'key_rotate','rotate_help'),(616,'key_drop','drop_help'),(656,'key_pause','pause_help')]:
    box(404,y,70,29,'key',8);say(keytext,415,y+5,5,'#c8d6ec');say(helptext,492,y+4,1,'#a9b9d0')
say('soft_help',404,706,0,'#7587a5')
say('footer',28,765,5,'#5be7c4');say('footer_right',518,765,0,'#7587a5')
# Pause and game-over overlays remain inside the board card.
load('8B 05','game_over');c.emit('85 C0');j('0F 85','overlay_over')
load('8B 05','paused');c.emit('85 C0');j('0F 84','paint_done')
box(57,363,266,148,'shadow',16);box(54,358,272,148,'border',16);box(55,359,270,146,'overlay',14)
box(78,378,224,2,'accent',0);say('pause_title',139,394,4);say('pause_subtitle',133,452,0,'#5be7c4');j('E9','paint_done')
c.mark('overlay_over')
box(57,363,266,148,'shadow',16);box(54,358,272,148,'border',16);box(55,359,270,146,'overlay',14)
box(78,378,224,2,'accent',0);say('over_title',119,394,4);say('over_subtitle',122,452,0,'#5be7c4')
c.mark('paint_done');load('8B 05','paint_count');c.emit('FF C0');load('89 05','paint_count');c.api('GdiFlush')
c.end('paint_frame')

# Gravity uses the same real instruction bytes as the console edition.
c.start('tick')
load('8B 05','paused');c.emit('85 C0');j('0F 85','tick_done')
load('8B 05','game_over');c.emit('85 C0');j('0F 85','tick_done')
c.api('GetTickCount');load('2B 05','last_tick');c.emit('89 C3')
load('8B 05','lines');c.emit('6B C0 0C 3D 7C 01 00 00');j('0F 86','tick_rate');imm_eax(380)
c.mark('tick_rate');c.emit('B9 F4 01 00 00 29 C1 39 CB');j('0F 82','tick_done');c.call('step_down')
c.mark('tick_done');c.end('tick')

c.start('init_graphics')
load('48 8B 0D','hwnd');c.api('GetDC');c.emit('48 89 C3 48 89 C1');c.api('CreateCompatibleDC')
load('48 89 05','draw_dc');c.emit('48 89 D9');load('48 8D 15','bitmap_info');c.emit('45 31 C0');load('4C 8D 0D','pixels_ptr')
c.emit('31 C0');arg_rax(32);arg_rax(40);c.api('CreateDIBSection')
load('48 89 05','bitmap');c.emit('48 89 C2');load('48 8B 0D','draw_dc');c.api('SelectObject');load('48 89 05','old_bitmap')
load('48 8B 0D','hwnd');c.emit('48 89 DA');c.api('ReleaseDC')
c.emit('B9 08 00 00 00');c.api('GetStockObject');c.emit('48 89 C2');load('48 8B 0D','draw_dc');c.api('SelectObject')
load('48 8B 0D','draw_dc');c.emit('BA 01 00 00 00');c.api('SetBkMode')
# Allocate brushes once, never in a frame.
load('48 8D 35','brush_colors');load('48 8D 3D','brushes');c.emit('31 DB')
c.mark('create_brush_loop');c.emit('8B 0C 9E');c.api('CreateSolidBrush');c.emit('48 89 04 DF FF C3 83 FB');c.raw(bytes([len(ALL_COLORS)]));j('0F 82','create_brush_loop')
for idx,(height,weight) in enumerate(FONT_SPECS):
    c.emit('B9');c.u32(-height);c.emit('31 D2 45 31 C0 45 31 C9')
    for offset,val in [(32,weight),(40,0),(48,0),(56,0),(64,1),(72,0),(80,0),(88,5),(96,0)]:stack32(offset,val)
    load('48 8D 05','font_mono' if idx==5 else 'font_segoe');arg_rax(104)
    c.api('CreateFontW');load('48 89 05','font_'+str(idx))
c.end('init_graphics')

c.start('free_graphics')
load('48 8B 0D','draw_dc');load('48 8B 15','old_bitmap');c.api('SelectObject')
load('48 8B 0D','draw_dc');c.api('DeleteDC')
load('48 8B 0D','bitmap');c.api('DeleteObject')
load('48 8D 35','brushes');c.emit('31 DB')
c.mark('free_brush_loop');c.emit('48 8B 0C DE');c.api('DeleteObject');c.emit('FF C3 83 FB');c.raw(bytes([len(ALL_COLORS)]));j('0F 82','free_brush_loop')
load('48 8D 35','fonts');c.emit('31 DB')
c.mark('free_font_loop');c.emit('48 8B 0C DE');c.api('DeleteObject');c.emit('FF C3 83 FB');c.raw(bytes([len(FONT_SPECS)]));j('0F 82','free_font_loop')
c.end('free_graphics')

# Standard WNDPROC(HWND,UINT,WPARAM,LPARAM), all arguments and return are Win64 ABI.
c.start('window_proc')
c.emit('48 89 CB 89 D6 4D 89 C4 4D 89 CD')
for msg,label in [(0x0f,'wm_paint'),(0x318,'wm_print'),(0x317,'wm_print'),(0x14,'wm_erase'),(0x100,'wm_key'),(0x113,'wm_timer'),(0x10,'wm_close'),(2,'wm_destroy'),(0x1c,'wm_activate')]:
    c.emit('81 FE');c.u32(msg);j('0F 84',label)
c.emit('48 89 D9 89 F2 4D 89 E0 4D 89 E9');c.api('DefWindowProcW');j('E9','wnd_return')
c.mark('wm_erase');imm_eax(1);j('E9','wnd_return')
# WM_PRINTCLIENT supports native window previews and non-invasive visual tests.
c.mark('wm_print')
load('4C 89 25','screen_dc');c.call('paint_frame')
load('48 8B 0D','screen_dc');c.emit('31 D2 45 31 C0 41 B9');c.u32(CW)
stack32(32,CH);load('48 8B 05','draw_dc');arg_rax(40)
stack32(48,0);stack32(56,0);stack32(64,0xcc0020);c.api('BitBlt');j('E9','wnd_zero')
c.mark('wm_paint')
c.emit('4D 85 E4');j('0F 85','wm_print')
c.emit('48 89 D9');load('48 8D 15','paint_struct');c.api('BeginPaint');load('48 89 05','screen_dc')
load('48 8B 05','draw_dc');c.emit('48 85 C0');j('0F 84','wm_endpaint')
c.call('paint_frame')
load('48 8B 0D','screen_dc');c.emit('31 D2 45 31 C0 41 B9');c.u32(CW)
stack32(32,CH);load('48 8B 05','draw_dc');arg_rax(40)
stack32(48,0);stack32(56,0);stack32(64,0xcc0020);c.api('BitBlt')
c.mark('wm_endpaint');c.emit('48 89 D9');load('48 8D 15','paint_struct');c.api('EndPaint');j('E9','wnd_zero')
c.mark('wm_timer');c.call('tick');j('E9','wnd_invalidate')
c.mark('wm_key')
c.emit('41 83 FC 50');j('0F 84','key_check_repeat');c.emit('41 83 FC 52');j('0F 85','gui_dispatch_key')
c.mark('key_check_repeat');c.emit('41 F7 C5 00 00 00 40');j('0F 85','wnd_zero')
c.mark('gui_dispatch_key');c.emit('44 89 E1');c.call('handle_key')
load('8B 05','quit');c.emit('85 C0');j('0F 85','wm_close');j('E9','wnd_invalidate')
c.mark('wm_activate');c.emit('4D 85 E4');j('0F 85','wnd_zero')
setvar('paused',1);j('E9','wnd_invalidate')
c.mark('wm_close');c.emit('48 89 D9');c.api('DestroyWindow');j('E9','wnd_zero')
c.mark('wm_destroy');c.emit('48 89 D9 BA 01 00 00 00');c.api('KillTimer');c.call('free_graphics')
c.emit('31 C9');c.api('PostQuitMessage');j('E9','wnd_zero')
c.mark('wnd_invalidate');c.emit('48 89 D9 31 D2 45 31 C0');c.api('InvalidateRect')
c.mark('wnd_zero');c.emit('31 C0')
c.mark('wnd_return');c.end('window_proc')

# GUI entry point. There is no CRT startup, interpreter or application framework.
c.start('entry')
c.emit('FC');c.api('SetProcessDPIAware');c.emit('31 C9');c.api('GetModuleHandleW');load('48 89 05','instance')
load('48 8D 3D','wndclass')
c.emit('C7 07 50 00 00 00 C7 47 04 03 00 00 00')
load('48 8D 05','window_proc');c.emit('48 89 47 08')
load('48 8B 05','instance');c.emit('48 89 47 18')
c.emit('31 C9 BA 00 7F 00 00');c.api('LoadCursorW');c.emit('48 89 47 28')
c.emit('31 C9 BA 00 7F 00 00');c.api('LoadIconW');c.emit('48 89 47 20 48 89 47 48')
load('48 8D 05','class_name');c.emit('48 89 47 40 48 89 F9');c.api('RegisterClassExW')
c.emit('85 C0');j('0F 84','entry_fail')
load('48 8D 0D','client_rect');c.emit('BA 00 00 CA 00 45 31 C0 45 31 C9');c.api('AdjustWindowRectEx')
load('48 8D 35','client_rect');c.emit('8B 46 08 2B 06');load('89 05','outer_w')
c.emit('8B 46 0C 2B 46 04');load('89 05','outer_h')
c.emit('31 C9');c.api('GetSystemMetrics');load('2B 05','outer_w');c.emit('D1 F8');load('89 05','window_x')
c.emit('B9 01 00 00 00');c.api('GetSystemMetrics');load('2B 05','outer_h');c.emit('D1 F8');load('89 05','window_y')
c.emit('31 C9');load('48 8D 15','class_name');load('4C 8D 05','window_title');c.emit('41 B9 00 00 CA 00')
for off,var in [(32,'window_x'),(40,'window_y'),(48,'outer_w'),(56,'outer_h')]:load('8B 05',var);c.emit('89 44 24');c.raw(bytes([off]))
stack32(64,0);stack32(68,0);stack32(72,0);stack32(76,0)
load('48 8B 05','instance');arg_rax(80);c.emit('31 C0');arg_rax(88)
c.api('CreateWindowExW');load('48 89 05','hwnd');c.emit('48 85 C0');j('0F 84','entry_fail')
# Ask supported Windows versions for a dark title bar; unsupported attributes are benign.
load('48 8B 0D','hwnd');c.emit('BA 14 00 00 00');load('4C 8D 05','dark_enabled');c.emit('41 B9 04 00 00 00');c.api('DwmSetWindowAttribute')
load('48 8B 0D','hwnd');c.emit('BA 23 00 00 00');load('4C 8D 05','caption_color');c.emit('41 B9 04 00 00 00');c.api('DwmSetWindowAttribute')
c.call('init_graphics');c.api('GetTickCount');load('89 05','rng');c.call('reset')
load('48 8B 0D','hwnd');c.emit('BA 01 00 00 00 41 B8 1E 00 00 00 45 31 C9');c.api('SetTimer')
load('48 8B 0D','hwnd');c.emit('BA 05 00 00 00');c.api('ShowWindow')
load('48 8B 0D','hwnd');c.api('UpdateWindow')
c.mark('message_loop')
load('48 8D 0D','message');c.emit('31 D2 45 31 C0 45 31 C9');c.api('GetMessageW')
c.emit('85 C0');j('0F 8E','message_exit')
load('48 8D 0D','message');c.api('TranslateMessage')
load('48 8D 0D','message');c.api('DispatchMessageW');j('E9','message_loop')
c.mark('message_exit');c.emit('31 C9');c.api('ExitProcess')
c.mark('entry_fail');c.emit('B9 01 00 00 00');c.api('ExitProcess');c.end('entry')

# Explicit import ownership: the image uses Windows system DLLs only.
API_DLL={}
for dll,names in {
 'KERNEL32.dll':'GetTickCount GetModuleHandleW ExitProcess',
 'USER32.dll':'SetProcessDPIAware GetDC ReleaseDC DrawTextW DefWindowProcW BeginPaint EndPaint InvalidateRect DestroyWindow PostQuitMessage KillTimer LoadCursorW LoadIconW RegisterClassExW AdjustWindowRectEx GetSystemMetrics CreateWindowExW SetTimer ShowWindow UpdateWindow GetMessageW TranslateMessage DispatchMessageW',
 'GDI32.dll':'SelectObject SetTextColor RoundRect CreateCompatibleDC CreateDIBSection GdiFlush GetStockObject SetBkMode CreateSolidBrush CreateFontW DeleteDC DeleteObject BitBlt',
 'DWMAPI.dll':'DwmSetWindowAttribute',
}.items():
    for name in names.split():API_DLL[name]=dll
apis=sorted({label[4:] for _,label in c.fixups if label.startswith('iat_')})
assert all(name in API_DLL for name in apis)
DLLS=list(dict.fromkeys(API_DLL[name] for name in apis))
for name in apis:data('hint_'+name,p16(0)+name.encode('ascii')+b'\0',2)
for dll in DLLS:
    data('dll_'+dll,dll.encode('ascii')+b'\0',1)
    names=[a for a in apis if API_DLL[a]==dll]
    data('ilt_'+dll,bytes(8*(len(names)+1)),8)
    data('iat_'+dll,bytes(8*(len(names)+1)),8)
    for i,name in enumerate(names):d.labels['iat_'+name]=d.labels['iat_'+dll]+8*i
# IAT directory may encompass intervening ILTs and names; actual import descriptors govern patching.
data('imports',bytes(20*(len(DLLS)+1)),4)
text_rva=0x1000;data_rva=align(text_rva+len(c.buf),4096);pdata_rva=align(data_rva+len(d.buf),4096)
labels={name:text_rva+off for name,off in c.labels.items()}
labels.update({name:data_rva+off for name,off in d.labels.items()})
for off,name in c.fixups:struct.pack_into('<i',c.buf,off,labels[name]-(text_rva+off+4))
for dll in DLLS:
    names=[a for a in apis if API_DLL[a]==dll]
    for i,name in enumerate(names):
        struct.pack_into('<Q',d.buf,d.labels['ilt_'+dll]+i*8,labels['hint_'+name])
        struct.pack_into('<Q',d.buf,d.labels['iat_'+dll]+i*8,labels['hint_'+name])
    struct.pack_into('<IIIII',d.buf,d.labels['imports']+DLLS.index(dll)*20,labels['ilt_'+dll],0,0,labels['dll_'+dll],labels['iat_'+dll])
unwind_rva=pdata_rva+12*len(c.functions)
pdata=bytearray()
for name in c.functions:pdata+=struct.pack('<III',labels[name],labels[name+'_end'],unwind_rva)
# PUSH seven nonvolatiles and SUB RSP,112 -> UWOP_ALLOC_SMALL opinfo13.
pdata+=bytes([1,15,8,0,15,0xd2,11,0xf0,9,0xe0,7,0xd0,5,0xc0,3,0x70,2,0x60,1,0x30])
reloc_rva=align(pdata_rva+len(pdata),4096);reloc=struct.pack('<IIHH',text_rva,12,0,0)
sections=[(b'.text',text_rva,bytes(c.buf),0x60000020),(b'.data',data_rva,bytes(d.buf),0xc0000040),
          (b'.pdata',pdata_rva,bytes(pdata),0x40000040),(b'.reloc',reloc_rva,reloc,0x42000040)]
pe_offset,optional_size=0x80,240
headers_size=align(pe_offset+24+optional_size+40*len(sections),512)
headers=bytearray(headers_size);headers[:2]=b'MZ';struct.pack_into('<I',headers,0x3c,pe_offset)
headers[pe_offset:pe_offset+4]=b'PE\0\0'
struct.pack_into('<HHIIIHH',headers,pe_offset+4,0x8664,len(sections),0,0,0,240,0x22)
o=pe_offset+24
struct.pack_into('<HBBIII',headers,o,0x20b,0,0,align(len(c.buf),512),sum(align(len(s[2]),512) for s in sections[1:]),0)
struct.pack_into('<IIQII',headers,o+16,labels['entry'],text_rva,0x140000000,4096,512)
struct.pack_into('<HHHHHH',headers,o+40,6,0,0,0,6,0)
size_image=align(reloc_rva+len(reloc),4096)
struct.pack_into('<IIII',headers,o+52,0,size_image,headers_size,0)
struct.pack_into('<HH',headers,o+68,2,0x160) # Windows GUI, ASLR + NX
struct.pack_into('<QQQQII',headers,o+72,0x100000,0x1000,0x100000,0x1000,0,16)
def directory(index,rva,size):struct.pack_into('<II',headers,o+112+index*8,rva,size)
directory(1,labels['imports'],20*(len(DLLS)+1));directory(3,pdata_rva,12*len(c.functions));directory(5,reloc_rva,len(reloc))
# Leave the optional IAT directory empty; the loader follows the import descriptors.
image=bytearray(headers);manifest_sections=[]
for i,(name,rva,buf,flags) in enumerate(sections):
    file_offset=len(image);raw_size=align(len(buf),512);sh=pe_offset+24+optional_size+40*i
    struct.pack_into('<8sIIIIIIHHI',image,sh,name,len(buf),rva,raw_size,file_offset,0,0,0,0,flags)
    image+=buf+bytes(raw_size-len(buf))
    manifest_sections.append(dict(name=name.decode(),rva=rva,virtual_size=len(buf),file_offset=file_offset,raw_size=raw_size))
exe=ROOT/'TetrisMachine.exe';exe.write_bytes(image)
manifest=dict(size=len(image),sha256=hashlib.sha256(image).hexdigest(),size_image=size_image,entry=labels['entry'],labels=labels,
              imports=apis,api_dll=API_DLL,sections=manifest_sections,functions=c.functions,code_bytes=len(c.buf),
              client_width=CW,client_height=CH,shapes=shapes,brush_count=len(ALL_COLORS))
(ROOT/'docs'/'machine-map.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
# Exact byte listing, respecting label boundaries.
by_offset={}
for name,off in c.labels.items():by_offset.setdefault(off,[]).append(name)
boundaries=sorted(set([0,len(c.buf)]+list(by_offset)+list(range(0,len(c.buf),16))))
listing=[]
for a,b in zip(boundaries,boundaries[1:]):
    for name in by_offset.get(a,[]):listing.append('\n'+name+':')
    listing.append(f'{text_rva+a:08X}  '+c.buf[a:b].hex(' ').upper())
(ROOT/'docs'/'machine-code.hex').write_text('\n'.join(listing)+'\n',encoding='ascii',newline='\n')
print(f'Wrote {exe}\n{len(image):,} bytes; {len(c.buf):,} instruction bytes; {len(c.functions)} functions')
print('System DLL imports: '+', '.join(DLLS));print('SHA256: '+manifest['sha256'])
