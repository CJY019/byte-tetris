# astra制作的机器码俄罗斯方块：源码字节查看指南

所有命令均在仓库根目录执行；路径不依赖原作者电脑。

## 运行

双击 `.\TetrisMachine.exe`。

最终 EXE 为 **13,824 字节（13.5 KiB）**，其中 `.text` 指令代码为 **7,226 字节**。
它是原生 AMD64 / PE32+ GUI 程序。复制 EXE 一个文件到空目录即可运行，仓库中的源码和文档不是运行依赖。
本机 Windows 11 x64 已实测。目标为 64 位 Windows 桌面环境。

- ← / →：移动
- ↑ 或 X：顺时针旋转
- ↓：软降
- 空格：直接落底
- P：暂停 / 继续
- R：重新开始
- Esc 或 Q：退出
- 切出窗口时自动暂停，返回后按 P 继续。

## “手写机器码”具体是怎样实现的

指令操作码直接写成 `53`、`48 83 EC 70` 等十六进制字节。
没有使用 C/C++ 编译器、汇编器、链接器、PyInstaller、游戏引擎或第三方包。

构造脚本仅使用 Python **标准库**来：
1. 写入明确指定的 x64 指令字节；
2. 计算分支、函数调用和 RIP 相对寻址的位移；
3. 写 PE 文件头、数据、导入表、ASLR 重定位占位和 x64 栈展开信息。

这是“手写操作码 + 脚本写文件和填写地址”，不是声称完全不用辅助脚本逐字节敲入整个 EXE。
Python 不在 EXE 中，运行游戏不需要 Python。画面、游戏逻辑、窗口回调也都是这些机器指令。

依赖仅为 Windows 本身提供的：
- KERNEL32.dll：时钟、进程与模块功能
- USER32.dll：窗口、消息、键盘、文字布局
- GDI32.dll：字体、画刷、位图和绘图
- DWMAPI.dll：深色窗口标题栏

这些是系统 API，不是额外安装或随游戏分发的库。字体来自 Windows 自带的 Segoe UI / Consolas。
没有外部图片、音频、配置文件或资源包；不访问网络。

## 一：直接查看有标签的源机器码清单

打开：
`.\docs\machine-code.hex`

可用记事本，也可在 PowerShell 中：

```powershell
Get-Content -LiteralPath '.\docs\machine-code.hex' -TotalCount 50
```

例如当前版本的碰撞函数：

```text
collides:
00001044  53 56 57 41 54 41 55 41 56 41 57 48
00001050  83 EC 70 89 CB 89 D7 45 89 C4 45 31 ED 48 8D 35
```

左边是加载后的相对虚拟地址 RVA；右边每一对十六进制数字是一个实际字节。
例如 `53` 就是二进制 `01010011`。换行仅为排版，不一定是指令边界。

几个实际使用的指令：

| 字节 | 含义 |
|---|---|
| `53` | `push rbx`，保存 RBX |
| `48 83 EC 70` | `sub rsp,112`，预留调用参数区 |
| `45 0F A3 EC` | `bt r12d,r13d`，检查当前形状中的一个方格位 |
| `83 F8 0A` | `cmp eax,10`，与棋盘宽度 10 比较 |
| `E8 xx xx xx xx` | 调用相对地址函数，后四字节是有符号位移 |
| `FF 15 xx xx xx xx` | 通过 RIP 相对导入表调用系统 API |
| `C3` | `ret`，返回 |

## 二：读取 EXE 本身，确认字节确实在二进制内

不必安装十六进制编辑器。PowerShell 自带 `Format-Hex`。

看文件头：

```powershell
Format-Hex -LiteralPath '.\TetrisMachine.exe' | Select-Object -First 8
```

开头的 `4D 5A` 是 MZ/PE 容器头，不是俄罗斯方块逻辑。真正指令在 `.text` 节。
当前构建的 `.text` 文件偏移为 `0x400`，RVA 为 `0x1000`。
因此碰撞函数的 RVA `0x1044` 对应文件偏移：

```text
0x400 + (0x1044 - 0x1000) = 0x444
```

直接读取当前版本碰撞函数的前 64 字节：

```powershell
$b = [IO.File]::ReadAllBytes('.\TetrisMachine.exe')
Format-Hex -InputObject ([byte[]]$b[0x444..0x483])
```

与 `machine-code.hex` 中 `collides:` 后的字节可以逐项核对。
注意 Format-Hex 对这个截取数组显示的是从 0 开始的局部偏移。

还提供一个只读检查脚本，自动解析 PE 并定位函数：

```powershell
& '.\tools\Inspect-MachineCode.ps1' -Function collides -Count 96
& '.\tools\Inspect-MachineCode.ps1' -Function paint_frame -Count 96
```

它不执行 EXE、不修改文件、不引入模块。如果本机策略不允许运行 PS1，使用上面的直接读取命令即可，无需修改执行策略。
如果之后修改构建，优先使用脚本重新计算偏移，不要硬套当前的 `0x444`。

## 三：查看字节如何被手写和组合

- `.\src\machine_core.py`：碰撞、旋转、消行、计分、键盘操作等手写指令。
- `.\src\build_machine.py`：手写图形界面和窗口消息循环，以及 PE 文件的构造。
- `.\docs\machine-map.json`：函数 RVA、节布局和系统导入表。

源码中的 `c.emit('...')` 是原始指令字节；`c.call` / `c.api` 只是写 E8 / FF 15 并登记待填写的位移，不是编译 Python 为游戏。

如需重新生成（这一步才需要开发机上有 Python）：

```powershell
python '.\src\build_machine.py'
```

不需要 pip install，也没有 requirements 文件。相同脚本生成的 EXE 字节一致。

## 验证记录

- 39 项机器码 / PE 检查：直接加载实际 EXE 指令并调用，不是另写一版 Python 游戏来测试。
- 含 5,000 次随机碰撞对比、80 局随机操作、1,207 次落底。
- 19 项真实 GUI 检查：键盘、计时、暂停、消行计分、退出与独立运行。
- 200 次重绘前后 GDI 句柄数均为 46。
- 已将 EXE 单独复制到仅含这一个文件的目录，再次运行 GUI 测试。
- 测试工具也只用 Python 标准库及 Windows API，没有第三方包。

`assets/screenshot.png` 是从真实 EXE 的绘制缓冲区读取的画面；为检查排版和颜色，预览使用测试工具设置的固定棋盘状态，不是图片生成或网页模拟。

SHA256：
`b9298c23d51c633ab9e2a72742fabf499f82d268dac4397c9d46f6df1e793f40`
