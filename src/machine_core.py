"""Hand-encoded AMD64 Tetris. No compiler, assembler, linker or packager.

Each emit/rip/branch below supplies the actual CPU opcode bytes. Python only
writes those bytes, resolves relative displacements, and writes a PE32+ image.
Nothing from Python is included in the EXE. This module emits only engine bytes;
the GUI builder adds Windows system imports and the manually constructed PE image.
Build: python src/build_machine.py
"""
from pathlib import Path
import struct
import json
import hashlib

ROOT = Path(__file__).resolve().parent.parent
W, H = 62, 28
p16 = lambda n: struct.pack('<H', n & 0xffff)
p32 = lambda n: struct.pack('<I', n & 0xffffffff)
p64 = lambda n: struct.pack('<Q', n & 0xffffffffffffffff)
align = lambda n, a: (n + a - 1) & -a

class Bytes:
    def __init__(self):
        self.buf = bytearray()
        self.labels = {}
        self.fixups = []
        self.functions = []
    def mark(self, name):
        assert name not in self.labels, name
        self.labels[name] = len(self.buf)
    def emit(self, hex_bytes):
        self.buf.extend(bytes.fromhex(hex_bytes))
    def u32(self, n): self.buf.extend(p32(n))
    def raw(self, b): self.buf.extend(b)
    def ref(self, prefix, name):
        self.emit(prefix)
        self.fixups.append((len(self.buf), name))
        self.raw(bytes(4))
    def call(self, name): self.ref('E8', name)
    def api(self, name): self.ref('FF 15', 'iat_' + name)
    def start(self, name):
        self.mark(name)
        # PUSH RBX,RSI,RDI,R12,R13,R14,R15; SUB RSP,112
        # Entry RSP mod 16 = 8. Seven saves + 112-byte outgoing area -> 0.
        self.emit('53 56 57 41 54 41 55 41 56 41 57 48 83 EC 70')
    def end(self, name):
        self.emit('48 83 C4 70 41 5F 41 5E 41 5D 41 5C 5F 5E 5B C3')
        self.mark(name + '_end')
        self.functions.append(name)

c, d = Bytes(), Bytes()
def data(name, value, alignment=4):
    d.raw(bytes(align(len(d.buf), alignment) - len(d.buf)))
    d.mark(name)
    d.raw(value)
def word(name, value=0): data(name, p32(value))
def text(name, s): data(name, s.encode('ascii') + b'\0', 1)
def load(prefix, name): c.ref(prefix, name)
def imm_eax(value): c.emit('B8'); c.u32(value)
def setvar(name, value): imm_eax(value); load('89 05', name)
def j(prefix, name): c.ref(prefix, name)

shapes = [
    [0x00f0, 0x4444, 0x0f00, 0x2222], # I
    [0x0071, 0x0226, 0x0470, 0x0322], # J
    [0x0074, 0x0622, 0x0170, 0x0223], # L
    [0x0066, 0x0066, 0x0066, 0x0066], # O
    [0x0036, 0x0462, 0x0360, 0x0231], # S
    [0x0072, 0x0262, 0x0270, 0x0232], # T
    [0x0063, 0x0264, 0x0630, 0x0132], # Z
]
data('shapes', b''.join(p32(n) for row in shapes for n in row))

data('kicks', b''.join(p32(n) for n in [0,-1,1,-2,2]))
data('awards', b''.join(p32(n) for n in [0,100,300,500,800]))
for name in ['x','y','mask','kind','rotation','next_kind','score','lines','paused','game_over','quit','last_tick']:
    word(name)
word('rng',0x12345678)
data('board',bytes(200))
# --- RNG: EAX in 0..6. Leaf arithmetic, preserved nonvolatile registers. ---
c.start('random_piece')
load('8B 05', 'rng')                  # mov eax,[rip+rng]
c.emit('69 C0'); c.u32(1664525)       # imul eax,eax,1664525
c.emit('05'); c.u32(1013904223)       # add eax,1013904223
load('89 05', 'rng')
c.emit('C1 E8 08 31 D2 B9 07 00 00 00 F7 F1 89 D0') # shr eax,8; xor edx,edx; mov ecx,7; div ecx; mov eax,edx
c.end('random_piece')

# --- collides(ECX=x, EDX=y, R8D=mask) -> EAX=0 valid,1 invalid ---
c.start('collides')
c.emit('89 CB 89 D7 45 89 C4 45 31 ED') # ebx=x; edi=y; r12d=mask; r13d=0
load('48 8D 35', 'board')             # lea rsi,[rip+board]
c.mark('collision_loop')
c.emit('45 0F A3 EC')                 # bt r12d,r13d
j('0F 83', 'collision_next')          # jnc
c.emit('44 89 E8 83 E0 03 01 D8')    # eax=i&3; add eax,ebx
c.emit('83 F8 0A')                    # cmp eax,10 (unsigned rejects negatives)
j('0F 83', 'collision_yes')
c.emit('41 89 C2 44 89 E8 C1 E8 02 01 F8') # r10d=cellx; eax=(i>>2)+edi
c.emit('83 F8 14')
j('0F 83', 'collision_yes')
c.emit('6B C0 0A 44 01 D0')          # eax=celly*10+cellx
c.emit('80 3C 06 00')                # cmp byte [rsi+rax],0
j('0F 85', 'collision_yes')
c.mark('collision_next')
c.emit('41 FF C5 41 83 FD 10')       # inc r13d; cmp r13d,16
j('0F 82', 'collision_loop')
c.emit('31 C0')
j('E9', 'collision_return')
c.mark('collision_yes'); imm_eax(1)
c.mark('collision_return'); c.end('collides')

# --- Spawn from preview; top-out detection. ---
c.start('spawn')
load('8B 05','next_kind'); load('89 05','kind')
c.emit('C1 E0 04')                    # eax=kind*16 (4 rotations x 4 bytes)
load('48 8D 15','shapes')
c.emit('8B 04 02'); load('89 05','mask')
setvar('rotation',0); setvar('x',3); setvar('y',0)
c.call('random_piece'); load('89 05','next_kind')
load('8B 0D','x'); load('8B 15','y'); load('44 8B 05','mask')
c.call('collides'); load('89 05','game_over')
c.api('GetTickCount'); load('89 05','last_tick')
c.end('spawn')

# --- Restart: clear board and counters; RNG remains seeded. ---
c.start('reset')
load('48 8D 3D','board'); c.emit('31 C0 B9 32 00 00 00 F3 AB') # rep stosd 50 = 200 bytes
for name in ['score','lines','paused','game_over','quit']:
    load('89 05',name)                # eax remains zero after REP
c.call('random_piece'); load('89 05','next_kind')
c.call('spawn'); c.end('reset')

# --- try_move(ECX=dx, EDX=dy) -> EAX=1 moved,0 blocked ---
c.start('try_move')
load('8B 1D','x'); load('8B 35','y')
c.emit('01 CB 01 D6 89 D9 89 F2')    # ebx+=dx; esi+=dy; ecx=ebx; edx=esi
load('44 8B 05','mask'); c.call('collides')
c.emit('85 C0'); j('0F 85','move_blocked')
load('89 1D','x'); load('89 35','y'); imm_eax(1)
j('E9','move_return')
c.mark('move_blocked'); c.emit('31 C0')
c.mark('move_return'); c.end('try_move')

# --- Clockwise rotation with small horizontal wall kicks. ---
c.start('rotate')
load('8B 1D','rotation'); c.emit('FF C3 83 E3 03') # new rotation
load('8B 05','kind'); c.emit('C1 E0 02 01 D8 C1 E0 02')
load('48 8D 15','shapes'); c.emit('44 8B 24 02') # r12d=new mask
load('48 8D 3D','kicks'); c.emit('45 31 ED')
c.mark('rotate_loop')
load('8B 35','x'); c.emit('42 03 34 AF') # add esi,[rdi+r13*4]
c.emit('89 F1'); load('8B 15','y'); c.emit('45 89 E0')
c.call('collides'); c.emit('85 C0'); j('0F 84','rotate_ok')
c.emit('41 FF C5 41 83 FD 05'); j('0F 82','rotate_loop')
j('E9','rotate_return')
c.mark('rotate_ok')
load('89 35','x'); load('89 1D','rotation'); load('44 89 25','mask')
c.mark('rotate_return'); c.end('rotate')

# --- Commit a piece, compact full rows, award points, spawn. ---
c.start('lock_piece')
load('48 8D 35','board'); load('44 8B 25','mask'); c.emit('45 31 ED')
load('8B 1D','kind'); c.emit('FF C3') # board cell color = kind+1
c.mark('lock_loop')
c.emit('45 0F A3 EC'); j('0F 83','lock_next')
c.emit('44 89 E8 83 E0 03'); load('03 05','x'); c.emit('41 89 C2')
c.emit('44 89 E8 C1 E8 02'); load('03 05','y')
c.emit('6B C0 0A 44 01 D0 88 1C 06') # mov [rsi+rax],bl
c.mark('lock_next')
c.emit('41 FF C5 41 83 FD 10'); j('0F 82','lock_loop')
c.emit('BF 13 00 00 00 45 31 E4')   # edi=row19; r12d=clears
c.mark('clear_row')
c.emit('6B DF 0A 31 C9')             # ebx=row*10; ecx=col0
c.mark('scan_row')
c.emit('89 D8 01 C8 80 3C 06 00'); j('0F 84','row_not_full')
c.emit('FF C1 83 F9 0A'); j('0F 82','scan_row')
c.emit('41 FF C4 89 D9')            # cleared++; ecx=row*10
# Move preceding bytes backwards, safely handling overlapping rows.
c.mark('shift_loop')
c.emit('85 C9'); j('0F 84','clear_top')
c.emit('FF C9 0F B6 04 0E 88 44 0E 0A') # --ecx; al=[rsi+rcx]; [rsi+rcx+10]=al
j('E9','shift_loop')
c.mark('clear_top')
c.emit('31 C9 31 C0')
c.mark('zero_top')
c.emit('88 04 0E FF C1 83 F9 0A'); j('0F 82','zero_top')
j('E9','clear_row')                  # recheck same row after shift
c.mark('row_not_full')
c.emit('FF CF'); j('0F 89','clear_row') # dec edi; jns
load('8B 05','lines'); c.emit('44 01 E0'); load('89 05','lines')
load('48 8D 15','awards'); c.emit('42 8B 04 A2') # eax=awards[r12]
load('03 05','score'); load('89 05','score')
c.call('spawn'); c.end('lock_piece')

c.start('step_down')
c.emit('31 C9 BA 01 00 00 00'); c.call('try_move')
c.emit('85 C0'); j('0F 85','step_clock')
c.call('lock_piece')
c.mark('step_clock'); c.api('GetTickCount'); load('89 05','last_tick')
c.end('step_down')

c.start('hard_drop')
c.mark('drop_loop')
c.emit('31 C9 BA 01 00 00 00'); c.call('try_move')
c.emit('85 C0'); j('0F 85','drop_loop')
c.call('lock_piece'); c.end('hard_drop')

# --- Handle key-down virtual-key code in ECX. ---
c.start('handle_key')
c.emit('83 F9 1B'); j('0F 84','key_quit')
c.emit('83 F9 51'); j('0F 84','key_quit')
c.emit('83 F9 52'); j('0F 84','key_reset')
load('8B 05','game_over'); c.emit('85 C0'); j('0F 85','key_done')
c.emit('83 F9 50'); j('0F 84','key_pause')
load('8B 05','paused'); c.emit('85 C0'); j('0F 85','key_done')
for vk, dest in [(0x25,'key_left'),(0x27,'key_right'),(0x28,'key_down'),
                 (0x26,'key_rotate'),(0x58,'key_rotate'),(0x20,'key_drop')]:
    c.emit('83 F9'); c.raw(bytes([vk])); j('0F 84',dest)
j('E9','key_done')
c.mark('key_left'); c.emit('B9 FF FF FF FF 31 D2'); c.call('try_move'); j('E9','key_done')
c.mark('key_right'); c.emit('B9 01 00 00 00 31 D2'); c.call('try_move'); j('E9','key_done')
c.mark('key_down'); c.call('step_down'); j('E9','key_done')
c.mark('key_rotate'); c.call('rotate'); j('E9','key_done')
c.mark('key_drop'); c.call('hard_drop'); j('E9','key_done')
c.mark('key_reset'); c.call('reset'); j('E9','key_done')
c.mark('key_pause')
load('8B 05','paused'); c.emit('83 F0 01'); load('89 05','paused')
c.api('GetTickCount'); load('89 05','last_tick'); j('E9','key_done')
c.mark('key_quit'); setvar('quit',1)
c.mark('key_done'); c.end('handle_key')
