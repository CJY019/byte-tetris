"""Exercise the generated AMD64 bytes, not a Python version of the game.
Loads the actual PE sections into memory, resolves system imports, marks code
RX, registers unwind metadata, then calls those bytes through the Windows ABI.
"""
import ctypes as C
from ctypes import wintypes as T
import json
from pathlib import Path
import random
import struct

ROOT=Path(__file__).resolve().parent.parent
M=json.loads((ROOT/'docs'/'machine-map.json').read_text())
IMAGE=(ROOT/'TetrisMachine.exe').read_bytes()
K=C.WinDLL('kernel32',use_last_error=True)
K.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,T.DWORD,T.DWORD]; K.VirtualAlloc.restype=C.c_void_p
K.VirtualProtect.argtypes=[C.c_void_p,C.c_size_t,T.DWORD,C.POINTER(T.DWORD)]; K.VirtualProtect.restype=T.BOOL
K.GetModuleHandleW.argtypes=[T.LPCWSTR]; K.GetModuleHandleW.restype=T.HMODULE
K.GetProcAddress.argtypes=[T.HMODULE,C.c_char_p]; K.GetProcAddress.restype=C.c_void_p
K.GetTickCount.restype=T.DWORD
K.FlushInstructionCache.argtypes=[T.HANDLE,C.c_void_p,C.c_size_t]
K.GetCurrentProcess.restype=T.HANDLE
base=K.VirtualAlloc(None,M['size_image'],0x3000,0x04)
assert base, C.get_last_error()
for s in M['sections']:
    C.memmove(base+s['rva'],IMAGE[s['file_offset']:s['file_offset']+s['raw_size']],s['raw_size'])
modules={dll:C.WinDLL(dll) for dll in set(M['api_dll'].values())}
for name in M['imports']:
    ptr=K.GetProcAddress(modules[M['api_dll'][name]]._handle,name.encode('ascii')); assert ptr,name
    C.c_void_p.from_address(base+M['labels']['iat_'+name]).value=ptr
for s in M['sections']:
    if s['name'] != '.data':
        old=T.DWORD()
        assert K.VirtualProtect(base+s['rva'],s['virtual_size'],0x20 if s['name']=='.text' else 2,C.byref(old))
K.FlushInstructionCache(K.GetCurrentProcess(),base,M['size_image'])
K.RtlAddFunctionTable.argtypes=[C.c_void_p,T.DWORD,C.c_uint64]; K.RtlAddFunctionTable.restype=T.BOOLEAN
pd=next(s for s in M['sections'] if s['name']=='.pdata')
assert K.RtlAddFunctionTable(base+pd['rva'],len(M['functions']),base)

def fn(name,*types): return C.WINFUNCTYPE(C.c_int,*types)(base+M['labels'][name])
def get(name): return C.c_int32.from_address(base+M['labels'][name]).value
def put(name,value): C.c_int32.from_address(base+M['labels'][name]).value=value
def board(): return (C.c_ubyte*200).from_address(base+M['labels']['board'])
reset=fn('reset'); collide=fn('collides',C.c_int,C.c_int,C.c_int)
move=fn('try_move',C.c_int,C.c_int); rotate=fn('rotate'); lock=fn('lock_piece')
key=fn('handle_key',C.c_int); drop=fn('hard_drop'); tick=fn('tick')
rand=fn('random_piece')
count=0

def check(condition, description):
    global count
    assert condition,description
    count+=1
    print(f'PASS {count:02d}: {description}',flush=True)

def piece(kind,x,y,rotation=0):
    put('kind',kind);put('x',x);put('y',y);put('rotation',rotation)
    put('mask',M['shapes'][kind][rotation])


reset()
check(not any(board()) and get('score')==0 and get('lines')==0,'reset clears board, score, lines')
check(get('x')==3 and get('y')==0 and not get('game_over'),'spawn starts in valid state')
check(all(mask.bit_count()==4 for row in M['shapes'] for mask in row),'all 28 piece masks have exactly four blocks')
values=[rand() for _ in range(500)]
check(set(values)==set(range(7)),'actual machine-code RNG produces all seven types')
check(collide(3,0,0x66)==0 and collide(-2,0,0x66)==1 and collide(8,0,0x66)==1,'left/right bounds reject occupied cells outside board')
check(collide(3,-1,0x66)==1 and collide(3,19,0x66)==1,'top and floor collision')
board()[4]=1
check(collide(3,0,0x66)==1,'collision detects settled block')
reset();piece(3,3,0)
check(move(-1,0)==1 and get('x')==2,'horizontal movement updates x')
piece(3,-1,0)
check(move(-1,0)==0 and get('x')==-1,'blocked movement does not mutate x')
reset();piece(5,3,0)
for _ in range(4):rotate()
check(get('mask')==0x72 and get('rotation')==0,'four clockwise rotations return to initial orientation')
piece(0,7,0,1);rotate()
check(get('rotation')==2 and get('x')==6 and not collide(get('x'),get('y'),get('mask')),'wall kick permits I-piece rotation at right wall')
reset();piece(5,3,18,0); old=get('mask');rotate()
check(get('mask')==old and get('rotation')==0,'invalid rotation at floor is rejected')
reset();piece(3,3,0);drop()
check(sum(bool(x) for x in board())==4 and all(board()[y*10+x]==4 for y in (18,19) for x in (4,5)), 'hard drop commits exactly four blocks at floor')
check(get('y')==0 and not get('game_over'),'hard drop spawns next piece')
reset();piece(0,2,16,1)
for y in range(16,20):
    for x in range(10): board()[y*10+x]=0 if x==4 else 2
board()[0]=3
lock()
check(get('lines')==4 and get('score')==800,'four simultaneous lines give 800 points')
check(sum(bool(x) for x in board())==1 and board()[40]==3,'line clear compacts all rows downward correctly')
reset();piece(0,3,18,0)
for x in range(10):board()[190+x]=0 if 3<=x<=6 else 7
lock()
check(get('lines')==1 and get('score')==100 and not any(board()),'single-line clear gives 100 points')
reset();piece(0,3,18,0)
for x in range(10):board()[x]=7
lock()
check(get('lines')==1 and not any(board()[:10]),'full top row is cleared without underflow')
reset();piece(3,3,18); put('next_kind',3)
board()[4]=2;lock()
check(get('game_over')==1,'blocked spawn triggers game over')
oldx=get('x');key(0x25)
check(get('x')==oldx,'movement disabled after game over')
key(0x52)
check(not get('game_over') and not any(board()),'R restarts from game over')
old=(get('x'),get('y'),get('mask')); key(0x50);key(0x25);key(0x20)
put('last_tick',0);tick()
check(get('paused')==1 and old==(get('x'),get('y'),get('mask')),'pause blocks movement, drop and gravity')
key(0x50)
check(get('paused')==0,'P resumes')
put('last_tick',(K.GetTickCount()-1000)&0xffffffff);tick()
check(get('y')==old[1]+1,'elapsed gravity tick moves piece one row')
y=get('y');tick()
check(get('y')==y,'gravity does not move again before delay')
key(0x51);check(get('quit')==1,'Q requests clean shutdown')
reset();key(0x1b);check(get('quit')==1,'ESC requests clean shutdown')
reset();piece(3,3,0)
ghost=fn('ghost_position');check(ghost()==18 and get('y')==0,'ghost finds landing row without moving active piece')
board()[184]=1
check(ghost()==16,'ghost stops at occupied board cells')
fmt=fn('format_number',C.c_uint32,C.c_uint32,C.c_void_p)
fmt(12345,6,base+M['labels']['score_buf'])
check(C.wstring_at(base+M['labels']['score_buf'])=='012345','machine-code UTF16 decimal formatting')

# Differential collision checks against a short independent mathematical oracle.
r=random.Random(20260926)
for _ in range(5000):
    for i in range(200):board()[i]=r.randrange(1,8) if r.random()<0.05 else 0
    mask=r.choice(r.choice(M['shapes']));x=r.randrange(-4,13);y=r.randrange(-4,23)
    expected=any(not(0<=x+(i%4)<10 and 0<=y+(i//4)<20) or
                 board()[(y+i//4)*10+x+i%4] for i in range(16) if mask>>i&1)
    assert bool(collide(x,y,mask))==expected,(x,y,mask)
check(True,'5,000 randomized collision comparisons passed')

# Randomized actions call only the machine-code game implementation.
locked=0
for game in range(80):
    reset()
    for step in range(300):
        if get('game_over'):break
        for _ in range(r.randrange(5)):rotate()
        for _ in range(r.randrange(9)):move(r.choice([-1,1]),0)
        if r.randrange(2):key(0x28)
        assert not collide(get('x'),get('y'),get('mask')) or get('game_over')
        if not get('game_over'):drop();locked+=1
        assert all(v<=7 for v in board())
        assert get('score')>=0 and get('lines')>=0
check(True,f'80 randomized games, {locked} hard drops, no invalid state or crash')

# Native PE metadata inspection with Python stdlib only.
pe_off=struct.unpack_from('<I',IMAGE,0x3c)[0]
coff=struct.unpack_from('<HHIIIHH',IMAGE,pe_off+4)
o=pe_off+24
check(IMAGE[:2]==b'MZ' and IMAGE[pe_off:pe_off+4]==b'PE\0\0' and coff[0]==0x8664,'valid AMD64 PE header')
check(struct.unpack_from('<H',IMAGE,o)[0]==0x20b and struct.unpack_from('<H',IMAGE,o+68)[0]==2,'PE32+ native Windows GUI subsystem')
check(set(M['api_dll'][a] for a in M['imports'])=={'KERNEL32.dll','USER32.dll','GDI32.dll','DWMAPI.dll'},'imports Windows system DLLs only')
check(struct.unpack_from('<II',IMAGE,o+112+14*8)==(0,0),'no CLR/.NET runtime directory')
section_base=o+coff[5]
flags=[struct.unpack_from('<I',IMAGE,section_base+40*i+36)[0] for i in range(coff[1])]
check(all(not(f&0x20000000 and f&0x80000000) for f in flags),'no writable executable sections')
end=max(s['file_offset']+s['raw_size'] for s in M['sections'])
check(end==len(IMAGE),'no appended interpreter or packaged archive')
check(struct.unpack_from('<II',IMAGE,o+112+3*8)[1]==len(M['functions'])*12,'all functions have x64 unwind metadata')
print(f'\nALL {count} CHECKS PASSED; mapped actual EXE code at {base:#x}.')
