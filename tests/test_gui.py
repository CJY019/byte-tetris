"""Native GUI verification using ONLY Python standard library + Windows APIs.
No Pillow, pefile, automation framework, compiler, assembler, or third-party package.
The captured PNG comes from the real running EXE's double-buffer bitmap.
"""
import ctypes as C
from ctypes import wintypes as T
import json, struct, subprocess, time, zlib, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
ARTIFACTS=ROOT/'.artifacts'
ARTIFACTS.mkdir(exist_ok=True)
M=json.loads((ROOT/'docs'/'machine-map.json').read_text())
K=C.WinDLL('kernel32',use_last_error=True);U=C.WinDLL('user32',use_last_error=True);G=C.WinDLL('gdi32',use_last_error=True)
U.SetProcessDPIAware()
def api(lib,name,args,result):
    f=getattr(lib,name);f.argtypes=args;f.restype=result;return f
api(K,'ReadProcessMemory',[T.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],T.BOOL)
api(K,'WriteProcessMemory',[T.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],T.BOOL)
api(K,'CreateToolhelp32Snapshot',[T.DWORD,T.DWORD],T.HANDLE)
api(K,'CloseHandle',[T.HANDLE],T.BOOL)
api(U,'GetWindowThreadProcessId',[T.HWND,C.POINTER(T.DWORD)],T.DWORD)
api(U,'PostMessageW',[T.HWND,T.UINT,T.WPARAM,T.LPARAM],T.BOOL)
api(U,'SendMessageW',[T.HWND,T.UINT,T.WPARAM,T.LPARAM],T.LPARAM)
api(U,'GetClientRect',[T.HWND,C.POINTER(T.RECT)],T.BOOL)
api(U,'GetWindowRect',[T.HWND,C.POINTER(T.RECT)],T.BOOL)
api(U,'SetWindowPos',[T.HWND,T.HWND,C.c_int,C.c_int,C.c_int,C.c_int,T.UINT],T.BOOL)
api(U,'GetDC',[T.HWND],T.HDC);api(U,'ReleaseDC',[T.HWND,T.HDC],C.c_int)
api(U,'PrintWindow',[T.HWND,T.HDC,T.UINT],T.BOOL)
api(U,'GetGuiResources',[T.HANDLE,T.DWORD],T.DWORD)
api(G,'CreateCompatibleDC',[T.HDC],T.HDC)
api(G,'CreateCompatibleBitmap',[T.HDC,C.c_int,C.c_int],T.HBITMAP)
api(G,'SelectObject',[T.HDC,T.HANDLE],T.HANDLE)
api(G,'DeleteObject',[T.HANDLE],T.BOOL);api(G,'DeleteDC',[T.HDC],T.BOOL)
api(G,'GetDIBits',[T.HDC,T.HBITMAP,T.UINT,T.UINT,C.c_void_p,C.c_void_p,T.UINT],C.c_int)
class MODULEENTRY(C.Structure):
    _fields_=[('dwSize',T.DWORD),('th32ModuleID',T.DWORD),('th32ProcessID',T.DWORD),('GlblcntUsage',T.DWORD),('ProccntUsage',T.DWORD),('modBaseAddr',C.c_void_p),('modBaseSize',T.DWORD),('hModule',T.HMODULE),('szModule',T.WCHAR*256),('szExePath',T.WCHAR*260)]
api(K,'Module32FirstW',[T.HANDLE,C.POINTER(MODULEENTRY)],T.BOOL)
ENUM=C.WINFUNCTYPE(T.BOOL,T.HWND,T.LPARAM)
api(U,'EnumWindows',[ENUM,T.LPARAM],T.BOOL)
si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
exe=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'TetrisMachine.exe'
child=subprocess.Popen([str(exe)],cwd=exe.parent,startupinfo=si)
report=[]
def check(condition,msg):
    assert condition,msg
    report.append(msg);print('PASS: '+msg,flush=True)
def until(predicate,timeout=4):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if predicate():return True
        if child.poll() is not None:return False
        time.sleep(.025)
    return False
found=[]
@ENUM
def enum_cb(hwnd,lparam):
    pid=T.DWORD();U.GetWindowThreadProcessId(hwnd,C.byref(pid))
    if pid.value==child.pid:found.append(hwnd)
    return True
try:
    check(until(lambda: (U.EnumWindows(enum_cb,0),bool(found))[1]),'OS loads EXE and creates its native GUI window')
    hwnd=found[0]
    snap=K.CreateToolhelp32Snapshot(0x18,child.pid);me=MODULEENTRY();me.dwSize=C.sizeof(me)
    assert K.Module32FirstW(snap,C.byref(me));K.CloseHandle(snap);base=me.modBaseAddr
    def read(name,length):
        buf=(C.c_ubyte*length)();n=C.c_size_t()
        assert K.ReadProcessMemory(int(child._handle),base+M['labels'][name],buf,length,C.byref(n)),C.get_last_error()
        return bytes(buf)
    def state(name):return struct.unpack('<i',read(name,4))[0]
    def write(name,raw):
        buf=C.create_string_buffer(raw);n=C.c_size_t()
        assert K.WriteProcessMemory(int(child._handle),base+M['labels'][name],buf,len(raw),C.byref(n))
    def put(name,n):write(name,struct.pack('<I',n&0xffffffff))
    def key(vk,lparam=1):
        assert U.PostMessageW(hwnd,0x100,vk,lparam)
    check(until(lambda:struct.unpack('<Q',read('draw_dc',8))[0]!=0),'double-buffer drawing resources initialize')
    rect=T.RECT();outer=T.RECT()
    assert U.GetClientRect(hwnd,C.byref(rect)) and U.GetWindowRect(hwnd,C.byref(outer))
    # Hosted Windows desktops can clamp the initial window below our fixed canvas.
    # Size ONLY this hidden test window, not the user's desktop or display settings.
    # NOSENDCHANGING avoids the default track-size clamp; NOACTIVATE keeps it hidden.
    border_w=(outer.right-outer.left)-(rect.right-rect.left)
    border_h=(outer.bottom-outer.top)-(rect.bottom-rect.top)
    assert U.SetWindowPos(hwnd,None,0,0,800+border_w,800+border_h,0x0416),C.get_last_error()
    assert U.GetClientRect(hwnd,C.byref(rect))
    check((rect.right,rect.bottom)==(800,800),f'test viewport is exactly 800 x 800 (got {rect.right} x {rect.bottom})')
    key(0x52);check(until(lambda:state('paused')==0 and not any(read('board',200))),'R starts a fresh game')
    x=state('x');key(0x25);check(until(lambda:state('x')==x-1),'left key moves active piece')
    old=state('rotation');key(0x26);check(until(lambda:state('rotation')==(old+1)%4),'up key rotates active piece')
    key(0x20);check(until(lambda:sum(v!=0 for v in read('board',200))==4),'space hard drop locks four cells')
    key(0x50);check(until(lambda:state('paused')==1),'P pauses')
    y=state('y');key(0x50,0x40000001);time.sleep(.65)
    check(state('paused')==1 and state('y')==y,'held P does not toggle repeatedly and gravity stays paused')
    key(0x50);check(until(lambda:state('paused')==0),'P resumes')
    y=state('y');check(until(lambda:state('y')>y,2),'timer drives gravity in standalone GUI')
    U.PostMessageW(hwnd,0x1c,0,0);check(until(lambda:state('paused')==1),'losing activation auto-pauses')

    # Capture through Windows; write PNG ourselves with struct/zlib (stdlib only).
    ref=U.GetDC(None);dc=G.CreateCompatibleDC(ref);bm=G.CreateCompatibleBitmap(ref,800,800);old=G.SelectObject(dc,bm)
    def screenshot(name):
        # WM_PRINTCLIENT supports a hidden test window and never steals user focus.
        U.PrintWindow(hwnd,dc,3)
        pixel_address=struct.unpack('<Q',read('pixels_ptr',8))[0]
        assert pixel_address
        pixels=(C.c_ubyte*(800*800*4))();num=C.c_size_t()
        assert K.ReadProcessMemory(int(child._handle),pixel_address,pixels,len(pixels),C.byref(num))
        b=bytes(pixels)
        rgb=bytearray(800*800*3)
        rgb[0::3]=b[2::4];rgb[1::3]=b[1::4];rgb[2::3]=b[0::4]
        raw=b''.join(b'\0'+rgb[y*2400:(y+1)*2400] for y in range(800))
        def chunk(tag,b):return struct.pack('>I',len(b))+tag+b+struct.pack('>I',zlib.crc32(tag+b)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',800,800,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
        (ARTIFACTS/name).write_bytes(png)
        return b
    try:
        snap=screenshot('gui-paused.png')

        check(snap[:3]==bytes([0x1d,0x10,0x0b]) and len(set(snap))>40,'native renderer produces dark UI with colored graphics')
        check(state('paint_count')>0,'captured image invokes the EXE machine-code paint procedure')
        # Reproducible visual fixture, injected only in this test; game binary has no test mode.
        b=bytearray(200)
        layout=[
            (19,[2,2,2,6,6,6,3,3,3,3]),
            (18,[2,0,6,6,5,5,0,7,7,4]),
            (17,[0,0,0,5,5,0,7,7,4,4]),
            (16,[0,0,0,0,1,1,1,1,4,0]),
        ]
        # Keep rows incomplete so the fixture is a plausible in-progress board.
        for row,vals in layout:
            for i,v in enumerate(vals):b[row*10+i]=v
        b[19*10+9]=0
        write('board',bytes(b));put('score',2400);put('lines',18)
        put('kind',5);put('rotation',0);put('mask',0x72);put('x',3);put('y',7);put('next_kind',0);put('game_over',0);put('paused',0)
        # Capture before next gravity step.
        put('last_tick',K.GetTickCount())
        screenshot('gui-preview.png')
        check(state('ghost_y')>=state('y'),'render computes landing ghost without changing active piece')
        # Force a true four-line clear in the running process via its normal space handler.
        key(0x50);until(lambda:state('paused')==1)
        b=bytearray(200)
        for yy in range(16,20):
            for xx in range(10):b[yy*10+xx]=0 if xx==4 else 2
        write('board',bytes(b));put('kind',0);put('rotation',1);put('mask',0x4444);put('x',2);put('y',0);put('score',0);put('lines',0);put('paused',0)
        key(0x20);check(until(lambda:state('score')==800 and state('lines')==4),'running GUI clears four rows and scores 800')
        key(0x50);until(lambda:state('paused')==1)
        before=U.GetGuiResources(int(child._handle),0)
        for _ in range(200):U.PrintWindow(hwnd,dc,3)
        after=U.GetGuiResources(int(child._handle),0)
        check(before==after and after>0,f'no GDI handle leak over 200 frames ({before} -> {after})')
        put('game_over',1);screenshot('gui-gameover.png')
        key(0x52);check(until(lambda:state('game_over')==0 and state('paused')==0 and not any(read('board',200))),'R restarts after game over')
    finally:
        G.SelectObject(dc,old);G.DeleteObject(bm);G.DeleteDC(dc);U.ReleaseDC(None,ref)
    key(0x51);child.wait(timeout=4)
    check(child.returncode==0,'Q releases graphics and exits with code zero')
    (ARTIFACTS/'gui-test-results.txt').write_text('\n'.join(report)+f'\nImage base: {base:#x}\n',encoding='utf-8')
    print(f'ALL {len(report)} REAL-GUI CHECKS PASSED',flush=True)
finally:
    if child.poll() is None:
        child.terminate();child.wait(timeout=4)
