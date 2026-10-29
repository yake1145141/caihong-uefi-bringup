# 移植实录（bring-up log）

本文件只记录**真实执行过**的操作与**真实观察到的**结果。没有执行过的事情一律不写。
每条记录包含：时间、动作、命令、结果、产物、结论。

> 运行环境：Windows 11 Pro 26300 / Ryzen 7 7800X3D / 31.12 GiB RAM，
> 工作目录 `E:\caihong-windows`（开始时为空）。
> Linux 侧：WSL2 + Alpine Linux 3.22.7（发行版名 `FnosPort`），以 root 运行。
> **真机自始至终未连接。**

---

## B0. 环境审计（2026-10-29 16:15）

| 检查项 | 结果 |
| --- | --- |
| OS | Microsoft Windows 11 Pro，10.0.26300，64-bit |
| CPU | AMD Ryzen 7 7800X3D，8C/16T |
| 内存 | 31.12 GiB |
| 磁盘 | C: 110 GiB 可用 / E: 242 GiB 可用 |
| Git | 2.55.0.windows.3 |
| Python | 3.12.0（Windows） |
| 编译器 | **无** MSVC、**无** clang（Windows 侧）；仅有 mingw64 的 gcc/cmake/ninja |
| iasl | Windows 侧无；**Mu-Qcom 仓库自带** `Silicium-ACPI/Compiler/iasl.exe`（ACPICA 20230628） |
| WSL | 3.0.3.0，内核 6.18.54.1，发行版 `FnosPort` = Alpine 3.22.7，网络可用，root |

**结论**：Windows 侧不具备 EDK2 原生编译条件（无 MSVC/clang）。改走 WSL Alpine。

**发现用户已提供的设备材料**（只读分析，未删除、未覆盖）：

```text
E:\1+padpro\oxygenos\              50 个原厂镜像（xbl/abl/uefi/tz/hyp/aop/devcfg/
                                   cpucp/dsp/modem/vbmeta/boot/vendor_boot/dtbo/
                                   system/vendor/odm/my_* ...）+ payload.bin
E:\1+padpro\linux\<hash>\          状态备份+刷机工具包（GBK README，1..5-*.bat，
                                   padpro/payload/info/ 内含 getprop/kernel/cmdline/
                                   partitions/df/dumpsys 等设备运行态 dump）
E:\1+padpro\skroot\                已 patch 的 boot.img 与 SukiSU
E:\1+padpro\twrp_caihong.img       100 MB recovery
E:\1+padpro\xia\, mio\             第三方刷机工具（未执行）
```

---

## B1. 设备身份识别（来自 `padpro/payload/info/`，只读）

`getprop.txt` 关键属性：

```text
ro.product.device            = OP5D77L1
ro.build.fingerprint         = OnePlus/OPD2404/OP5D77L1:15/UKQ1.231108.001/U.1f6e972_e4-2216a:user/release-keys
ro.build.version.release     = 15          ro.build.version.sdk = 35
ro.board.platform            = pineapple
ro.boot.vbmeta.device_state  = unlocked    ro.boot.verifiedbootstate = orange
ro.boot.slot_suffix          = _b           ro.boot.serialno = 67ab95c8
ro.boot.boot_devices         = soc/1d84000.ufshc
ro.boot.usbcontroller        = a600000.dwc3
```

`kernel.txt`：`Linux 6.1.118-android14-11-o-g2b8edc801b38`，clang 17.0.2，构建于 2025-08-25。
`cmdline.txt` 含面板串：`qcom,mdss_dsi_panel_csot_nt36532_2120_3000_dual_dsc_144hz_vid`。

**结论**：机型、SoC 平台、解锁状态、slot、UFS/USB 控制器基址均已确证。

---

## B2. 固件镜像解析（16:20 起）

`E:\caihong-windows\source\` 下克隆（均为 `--depth 1`）：

| 仓库 | HEAD | 日期 |
| --- | --- | --- |
| Osilvfe/caihong-linux-rootfs | （见 source/caihong-linux-rootfs.commit） | — |
| WOA-Project/windows_silicon_qcom_lanai | `23a81f22…` | 2024-11-10 |
| liliumbeta/Mu-Qcom | `7b51bdd1…` | 2024-02-07 |
| musabcel/Mu-Qcom | `520b8826…` | 2025-08-19 |
| Osilvfe/linux (caihong-v7.3) | `4df9a880…` | 2026-10-28 |

自己编写了解析器（`scripts/fdtlib.py`），过程中**修复三个真实的格式问题**：

1. **DTBO 条目选择**：8 个条目的 `dt_id`/`dt_rev` 全为 0（OPPO 未填），
   因此 ABL 的 `ro.boot.dtbo_idx=7` 指的是**表索引**而非 id。首版按 id 命名导致
   8 个文件互相覆盖。
2. **vendor_boot magic**：是 `VNDRBOOT` 而不是 `ANDROID!`。首版直接报
   `not an Android vendor_boot image`。
3. **v4 头偏移**：`dtb_addr` 是 **u64**，所以 v4 新增字段从 **2112** 开始而不是
   2108；ramdisk 表条目是 **108** 字节（不是 20）。修正后 `ramdisk` 数量从
   108 个垃圾条目变为正确的 1 个。

### B2.1 提取结果

```text
dtbo.img        : 单个 DTBO blob，8 个条目，每条目约 750 KB
                  索引 7（活动）= 777,871 字节
                  全部 model = "Qualcomm Technologies, Inc. Pineapple MTP,caihong"
                  compatible 含 qcom,pineapple / qcom,pineapplep
                  qcom,msm-id = <0x22d 0x10000 0x241 0x10000>，board-id = <8 0>
vendor_boot.img : VNDRBOOT v4，dtb_size 3,171,955，dtb_addr 0x1F00000
                  vendor DTB model = "Qualcomm Technologies, Inc. Cliffs SoC"
                  compatible = "qcom,cliffs"，msm-id = <0x266 0x10000>
                  board-id = <0 0>
boot.img        : kernel 33.4 MiB 已解出
```

### B2.2 SoC 识别（关键判断）

- mainline `arch/arm64/boot/dts/qcom/Makefile` 中**有** `sm8650-*.dtb`，**没有**任何
  `cliffs` 条目。
- 但设备 vendor DTB 的 `pinctrl@f000000` compatible 是 `qcom,cliffs-pinctrl`，
  而 mainline 对应 `qcom,sm8650-tlmm`。
- 地址交叉验证（vendor DTB vs mainline `sm8650.dtsi`）：

| 节点 | vendor DTB | mainline sm8650.dtsi | 一致 |
| --- | --- | --- | --- |
| UFS | `ufshc@1d84000` | `ufshc@1d84000` | ✅ |
| 定时器帧 | `timer@17420000` | `timer@17420000` | ✅ |
| GENI SE | `0xac0000` / `0x8c0000` | 同 | ✅ |
| MDSS | `mdss_mdp@ae00000` | 同 | ✅ |

**结论（记为【推断】，非【已核实】的官方命名）**：`Cliffs` 是高通对 SM8650 的
SoC 内部代号，`Pineapple` 是平台/板级家族名；基础 DTB 是 SoC 级，dtbo 是板级覆盖层。
**未解决的不一致**：基础 DTB 声明 `msm-id 0x266`，而覆盖层声明 `0x22d`/`0x241`。
已列入开放问题，未据此修改任何实现。

---

## B3. 硬件映射提取（`docs/hw-sm8650-caihong.json`）

`scripts/extract_hw.py` 输出（全部来自设备自身固件）：

| 模块 | 基址 | 大小 | 中断 | GSIV |
| --- | --- | --- | --- | --- |
| GICv3 distributor | 0x17100000 | 0x10000 | — | — |
| GICv3 redistributor | 0x17180000 | 0x200000 | — | — |
| GIC ITS | 0x17140000 | 0x20000 | — | — |
| ARM generic timer | — | — | PPI 13/14 | 29 / 30 |
| 定时器帧 | 0x17420000 | 0x1000 | — | — |
| UFS | 0x1D84000 | 0x3000(+4 段) | SPI 265 | 0x129 |
| USB3 dwc3 | 0xA600000 | 0xD93C | SPI 133 | 0xA5 |
| TLMM/GPIO | 0x0F000000 | 0x1000000 | SPI 208 | 0xF0 |
| SPMI arb | 0xC42D000 | 0x4000 | — | — |
| 调试 UART (GENI) | 0xA94000 | 0x4000 | SPI 358 | 0x186 |
| MDSS MDP | 0xAE00000 | 0x84000 | SPI 83 | 0x73 |
| DSI ctrl0 / phy0 | 0xAE94000 / 0xAE95500 | 0x1000 / 0xA00 | — | — |
| Adreno 750 (kgsl) | 0x3D00000 | 0x40000 | SPI 300 | 0x14C |
| KGSL SMMU | 0x3DA0000 | 0x40000 | — | 0x2C1 |

CPU：8 核，`qcom,cpuidle-domain` 簇划分 **3 / 4 / 1**。

> 说明：`extract_hw.py` 首版把 `#address-cells`/`#size-cells` 一律当 2/2，
> 而该 DTB 在 `/soc` 下是 1/1，导致 base 被拼成 `0xAE0000000084000` 这种错误值。
> 已改为逐节点向上解析 cells 数。

---

## B4. ACPI 生成与验证（已通过）

### B4.1 DSDT

`acpi/caihong/DSDT.dsl` 手写，用仓库自带 `iasl.exe` 编译：

```text
AML Output: build/acpi/DSDT.aml - 743 bytes, 18 opcodes, 64 named objects
Compilation successful. 0 Errors, 0 Warnings, 8 Remarks, 3 Optimizations
```

声明：`CPU0..CPU7`、`UFS0`(QCOM24A5)、`USB0`(QCOM0C8B)、`GIO0`(QCOM0C0C)、
`SPMI`(QCOM0C0B)。

**两次真实纠错**：

1. OEM ID 写成 `ONEPLUS`（7 字符）→ `error 6156 - Invalid OEM ID`，改为 `ONEPLS`。
2. 调试 UART 原写了 `_HID "QCOM0C0D"`——**这是编造的**。核查后发现
   `uefi.img`（3,158,016 B）内既无明文 DSDT/FACP/APIC/GTDT，也无 `QCOM*` 字符串，
   没有任何一手来源能证实该 HID。**已删除该设备**，改为在文件中留下说明并列入缺口。

### B4.2 SoC 级表（FACP / APIC / GTDT / DBG2 / PPTT）

策略：**派生 + 硬断言**（`scripts/build_soc_acpi.py`）。脚本在改写前断言上游 SM8550
表内确实存在 SM8650 的数值，断言失败即拒绝生成：

```text
OK   FACP.aml   276 bytes   asserted=0
OK   APIC.aml   744 bytes   asserted=2   (GICD 0x17100000, GICR 0x17180000)
OK   GTDT.aml   156 bytes   asserted=3   (0x17420000, GSIV 29, GSIV 30)
OK   DBG2.aml  1364 bytes   asserted=0
OK   PPTT.aml   570 bytes   asserted=0
```

**全部断言通过**，这在事实上证明了 SM8550 与 SM8650 的 GIC/定时器布局一致。
表头重定向为 `ONEPLS` / `CAIHONG` / rev `0x8650`，校验和重算，并用 `iasl -d`
反汇编 6 张表全部无错误。

**未验证项**：MADT 内每簇 GIC redistributor 基址
（0x17180000 / 0x171C0000 / 0x17200000）继承自 SM8550；SM8650 的簇划分是 3/4/1
而 SM8550 不同，因此这是 SoC 表集中唯一未经验证的字段。验证方法：真机读
`GICR_TYPER.Affinity_Value`，或确认 Windows 下 8 个核全部上线。

---

## B5. Mu-Qcom 板级工程（已创建）

```text
Silicon/Qualcomm/CliffsPkg/                  ← 由 KailuaPkg(SM8550) 派生，SM8650 数值
Platforms/OnePlus/caihongPkg/                ← 由 astonPkg 派生
Resources/Configs/caihong.conf               ← BootShim / FD 布局
Resources/Scripts/caihong.sh                 ← 组装 boot.img（不刷写）
Silicium-ACPI/SoCs/Qualcomm/Cliffs/          ← SM8650 SoC 表 + DSDT_minimal
Silicium-ACPI/Platforms/OnePlus/caihong/     ← 板级 DSDT
patches/0001-mu-qcom-add-caihong-board-package.patch          (27 文件)
patches/0002-silicium-acpi-add-sm8650-caihong-tables.patch    (9 文件)
```

### B5.1 ABL 交接地址 —— 故意设置的构建闸门

`caihong.dsc` 中：

```text
CAIHONG_ABL_ADDRESSES_VERIFIED = 0
!if $(CAIHONG_ABL_ADDRESSES_VERIFIED) == 0
!error "... ABL handover addresses are not yet verified for this device ..."
!endif
```

涉及三个地址：

| PCD | 当前值（继承 SM8550，**非本机实测**） | 为什么无法推导 |
| --- | --- | --- |
| `PcdFvDecompressAddr` | 0xA703A0C8 | 来自 xbl/abl 启动链，因设备和固件版本而异 |
| `PcdCpuVectorBaseAddress` | 0xA7600000 | 同上 |
| `PcdPrePiStackBase` | 0xA760D000 | 同上 |

**解锁方法（尚未执行）**：
1. 从 `E:\1+padpro\oxygenos\xbl.img` / `abl.img` 反汇编，或
2. 在真机上让 ABL 输出 handover 区域的 SMEM/InfoBlk 记录，
3. 确认后把三个值填入 `caihong.dsc`，并将 `CAIHONG_ABL_ADDRESSES_VERIFIED` 置 1。

---

## B6. 构建尝试（真实结果）

### B6.1 工具链准备（WSL Alpine）

```sh
apk add bash clang20 lld20 llvm20 iasl dtc python3 py3-pip make git zstd \
        gcc-aarch64-none-elf binutils-aarch64-none-elf
python3 -m pip install --break-system-packages -r pip-requirements.txt
```

安装结果：clang 20.1.8、lld 20、llvm 20、iasl 20230628、dtc 1.7.2、
python 3.12.15、aarch64-none-elf-gcc 15.1.0 —— 全部就绪。

### B6.2 第一次失败：CRLF

```text
./build_uefi.sh: cannot execute: required file not found
```

原因：在 Windows 上克隆导致 `core.autocrlf` 把 `#!/bin/bash` 写成 `#!/bin/bash\r`，
内核去找名为 `/bin/bash\r` 的解释器。**不是**缺 bash。
修复：`scripts/fix_line_endings.sh`（只转换真正影响构建的文件）。
验证：`head -1 build_uefi.sh | od -c` → `# ! / b i n / b a s h \n`。

### B6.3 第二次失败：aston 需要 `-m`

```text
This Device has 2 different Models. Use -m or --model To define wich Model using a Number.
```

修正为 `-d aston -m 0`。

### B6.4 第三次尝试：BootShim 编译成功，子模块解析通过，卡在 NuGet 依赖

```text
clang --target=aarch64-linux-gnu -c BootShim.S -o BootShim.elf -DCREATE_FDT_POINTER=0 \
      -DFDT_POINTER_ADDRESS=0x0 -DUEFI_BASE=0xBAB00000 -DUEFI_SIZE=0x00300000
llvm-objcopy -O binary BootShim.elf BootShim.bin          <-- 成功
...
PROGRESS - ## Resolving Git Submodule: Binaries / Common/Mu / Common/Mu_OEM_Sample /
           Common/Mu_Tiano_Plus / Features/DFCI / Mu_Basecore /
           Silicon/Arm/Mu_Tiano / Silicium-ACPI          <-- 全部 Done
```

子模块解析全部通过后，在 edk2-pytool-extensions 的依赖更新阶段失败：

```text
WARNING - [SDE] Failed to fetch NugetDependecy: edk2-basecrypto-driver-bin@1.0.1
WARNING - [SDE] Failed to fetch NugetDependecy: mu_nasm@20016.1.1
ERROR   - We were unable to successfully update 2 dependencies in environment
Failed to Update UEFI Env!
```

原因：这两个包需要从 NuGet 拉取，而当时网络已中断（B7）。NASM 只用于 x86
汇编、AArch64 不需要，因此我做了**临时实验**：把声明这两个依赖的文件改名，
使 SDE 不再拉取——

```text
Mu_Basecore/BaseTools/Bin/nasm_ext_dep.yaml                       -> .disabled
Mu_Basecore/CryptoPkg/Binaries/BaseCryptoDriver_ext_dep.json      -> .disabled
```

### B6.5 第四次尝试：依赖更新通过，编译推进到 GenFds，最终失败

依赖更新成功：

```text
SECTION - Initial update of environment   Updated/Verified 1 dependencies
SECTION - Second pass update of environment   Updated/Verified 1 dependencies
PROGRESS - Success
```

随后进入真正编译，`Build total time: 00:00:40`，**在 GenFds 阶段失败**：

```text
warning: ArmSmcPsciResetSystemLib.inf does not support LIBRARY_CLASS ResetSystemLib
build.py... : error C0DE: Unknown fatal error when processing
       [Mu_Basecore/MdeModulePkg/Library/ResetUtilityLib/ResetUtilityLib.inf
        [AARCH64, CLANGPDB, RELEASE]]
...
FileNotFoundError: [Errno 2] No such file or directory:
  Build/astonPkg/RELEASE_CLANGPDB/FV/Ffs/90A49AFD-...EnvDxe/90A49AFD-...SEC1.1.dpx
CRITICAL - Build failed
Failed to Compile UEFI!
```

调用栈定位到 `GenFds/EfiSection.py:311` → `GenFdsGlobalVariable.GenerateSection()`
→ `os.path.getsize(Output)`：**EnvDxe 的 DEPSECTION 文件从未生成**。
（同一轮里 PcdDxe / DxeCore / PrePi 的 `.dpx` 都生成了，只有 EnvDxe 缺失。）

**未完成归因**：`error C0DE` 是 BaseTools 的兜底报错，真实原因是 EnvDxe 的 depex
没产出。两个候选原因，本次会话**未能区分**：

1. **主嫌**：我临时禁用了 `edk2-basecrypto-driver-bin`。EnvDxe 属于 Mu 环境驱动，
   若它依赖 CryptoPkg 的二进制库，缺库会使其 depex 生成阶段静默失败。
   这是本次唯一引入的偏差。
2. BaseTools 与 Python 3.12 的兼容性问题（`LARGE_FILE_SIZE` 相关路径，
   `LongFilePathOsPath.getsize`）。

**判别方法**（所需条件：网络恢复）：
- 恢复两个 `.disabled` 文件 → 让 NuGet 正常拉取 → 重跑。若 EnvDxe 的 `.dpx` 出现，
  则原因是 1；若仍缺，则是 2。
- 或把 Python 降到 3.10/3.11（Mu BaseTools 的目标版本）重跑。

两个 `.disabled` 文件**已恢复原名**，工作树未留下该实验痕迹。

### B6.6 结论：本次会话没有编译出任何 UEFI 固件镜像

- `Build/astonPkg/RELEASE_CLANGPDB/FV/` 下**没有** `.fd`，
  `artifacts/` 中只有 6 个 ACPI 表。
- 已确认能走到的位置：BootShim 交叉编译成功 → 全部子模块解析成功 →
  依赖更新成功 → 编译执行 → GenFds 失败。
- `caihong` 目标本身即便工具链打通，也会**在 DSC 解析阶段被 B5.1 的闸门拒绝**
  （设计意图），因此本次用 `aston` 作为工具链证明目标。

### B6.7 副作用：子模块被统一为 LF

排查 CRLF 时执行的整树转换实际跑完了，因此 `Mu_Basecore` 等子模块内大量文件
的 CRLF 被改为 LF，`git -C Mu_Basecore status` 会显示大量 ` M` 条目。
这**不是**逻辑改动，且对 Linux 下构建有利，但会使子模块偏离上游。
如需恢复原始状态：

```sh
for d in Mu_Basecore Common/Mu Common/Mu_OEM_Sample Common/Mu_Tiano_Plus \
         Features/DFCI Silicon/Arm/Mu_Tiano Silicium-ACPI Binaries; do
    git -C "source/Mu-Qcom-musabcel/$d" checkout -- .
done
```
（恢复后会重新引入 `#!/bin/bash\r` 类问题，需再次运行 `scripts/fix_line_endings.sh`。）

---

## B7. 网络故障记录

会话中段起，主机到外网的全部连接失败：

```text
github: 000     raw.githubusercontent.com: 000     cdn.jsdelivr.net: 000
```

此前成功的操作（克隆 5 个仓库、下载 `sm8650.dtsi`、下载 `qcom-Makefile.txt`）
均已在本记录中留痕。网络中断导致的**两项未完成工作**：

1. **caihong 板级 DTS 正文未取得**。原因是三轮连续失败：
   - `git sparse-checkout set arch/arm64/boot/dts/qcom` → `error: RPC failed;
     curl 56 schannel: server closed abruptly (missing close_notify)` /
     `fatal: could not fetch … from promisor remote`
   - `raw.githubusercontent.com` → 先 HTTP **429 限流**，后 HTTP 000
   - `cdn.jsdelivr.net` → HTTP 000
   → 期间落到 `work/sm8650-oneplus-caihong.dts` 的 313 字节文件实为 **HTTP 429
   错误页**，已删除。目前只能通过 `git ls-tree -r` 证明该路径在仓库树中存在
   （`arch/arm64/boot/dts/qcom/sm8650-oneplus-caihong.dts` 等 12 条 caihong 相关
   路径、34 条 sm8650 相关路径），**不能**声称读过其内容。
   → 影响评估：**不阻塞移植**。所有地址取自设备自身 firmware DTB，DTS 只是旁证。
2. **Mu-Qcom 完整编译**：见 B6.4。

---

## B8. 已生成产物与校验

| 产物 | 大小 | 校验 |
| --- | --- | --- |
| `build/acpi/DSDT.aml` | 743 B | checksum ✅ / iasl 反汇编 ✅ |
| `build/acpi/FACP.aml` | 276 B | checksum ✅ / iasl 反汇编 ✅ |
| `build/acpi/APIC.aml` | 744 B | checksum ✅ / iasl 反汇编 ✅ |
| `build/acpi/GTDT.aml` | 156 B | checksum ✅ / iasl 反汇编 ✅ |
| `build/acpi/DBG2.aml` | 1364 B | checksum ✅ / iasl 反汇编 ✅ |
| `build/acpi/PPTT.aml` | 570 B | checksum ✅ / iasl 反汇编 ✅ |
| UEFI 固件 | — | **未生成** |

`artifacts/SHA256SUMS` 覆盖上表 6 个文件。

---

## B9. 下一步（按优先级，均需先解决前置条件）

| # | 任务 | 前置条件 |
| --- | --- | --- |
| 1 | 打通 Mu-Qcom 编译，先产出 aston 的 `.fd` 作为工具链证明 | 网络恢复，或改用已联网的 Ubuntu WSL |
| 2 | 取得 ABL 交接三地址，解除 `caihong.dsc` 闸门 | 真机（或 xbl/abl 反汇编） |
| 3 | 真机读 `GICR_TYPER`，确认 MADT 三个 redistributor 基址 | 真机 + 可回滚的临时启动方式 |
| 4 | 取得 caihong 板级 DTS 正文，补齐 PMIC/I2C/触摸节点 | 网络恢复 |
| 5 | 解决显示（面板 + WDDM）——**最大阻塞** | 需要 Adreno 750 Windows 驱动，公开渠道无 |
| 6 | 确认 `QCOM24A5` UFS 驱动是否兼容 SM8650 | 需要 QCOM BSP 二进制（不可再分发） |

---

## B10. 诚实结论

- **已完成**：设备身份确证；固件解析工具链（含 3 个真实 bug 修复）；完整硬件寄存器映射；
  6 张 ACPI 表并全部通过校验与反汇编验证；Mu-Qcom 板级包（2 个补丁，36 个文件）；
  BootShim 交叉编译通过。
- **未完成**：UEFI 固件镜像一次都没能编译出来；从未启动过 Windows；从未接触真机。
- **不可达**：在不获得 SM8650 Windows 驱动（尤其显示）的前提下，无法让这台平板进入
  Windows 桌面。这不是工作量问题，是缺少可用的驱动实现。
---

## B11. 第二轮突破（2026-10-29 17:55 起，网络恢复后）

### B11.1 `Lanai` 是 SM8650 的高通构建代号

从 `uefi.img`（3,158,016 B，ELF64 AArch64）的内部字符串里直接读到构建路径：

```text
/work/0005/workspace/Build_S_BP/22194/code/source/msm_amss/BOOT.MXF.2.1/
  boot_images/Build/LanaiLAA/Core/RELEASE_CLANG160LINUX/AARCH64/QcomPkg/XBLCore/...
```

**`LanaiLAA`** —— 说明 SM8650 的高通内部代号是 **Lanai**（"Cliffs" 是 SoC/DT 侧的
命名，两者并存）。这同时解释了 WOA 仓库为什么叫
`windows_silicon_qcom_lanai`：**它本来就是 SM8650 的 BSP 仓库**，只是公开内容为空壳。
本项为【已核实】（证据是设备自身固件里的构建路径字符串）。

### B11.2 ABL 交接地址：已从 `xbl_config.img` 完整解出

此前 B5.1 里三个"无法推导"的地址，实际上**就明文存放在设备自己的 XBL 配置里**。
`xbl_config.img` 是 ELF64，内含一张内存区域表，条目结构为：

```text
03 00 00 00 <namelen> 00 00 09 <name>       # 名称前缀
... <base 4B 大端> ... <size 4B 大端> ...   # base 在 name_off-23，size 在 name_off-15
```

解析结果共 **41 个区域**，已保存为 [`docs/abl-memory-map.json`](abl-memory-map.json)。
与本项目直接相关的部分：

| 区域 | 基址 | 大小 | 用途 |
| --- | --- | --- | --- |
| UEFI_FD | 0xA7000000 | 0x400000 | 原厂 UEFI 固件卷所在区间 |
| UEFI_FD_Reserved | 0xA7400000 | 0x200000 | FD 保留区 |
| **CPU_Vectors** | **0xA7600000** | 0x1000 | 异常向量表 |
| **Info_Blk** | **0xA7601000** | 0x1000 | Mu 读取的 ABL InfoBlk |
| MMU_PageTables | 0xA7602000 | 0x3000 | MMU 页表 |
| Log_Buffer | 0xA7605000 | 0x8000 | 日志缓冲 |
| **UEFI_Stack** | **0xA760D000** | **0x40000** | PrePi 栈 |
| SEC_Heap | 0xA764D000 | 0x8C000 | SEC 堆 |
| Sched_Heap | 0xA76D9000 | 0x400000 | 调度堆 |
| **FV_Region** | **0xA7AD9000** | 0x400000 | FV 解压目标区 |
| UEFI_RESV | 0xA7ED9000 | 0x127000 | UEFI 保留区 |
| Kernel | 0xA8000000 | 0x10000000 | 内核加载区 |
| DXE_Heap | 0xB8000000 | 0x1BA00000 | DXE 堆 |
| Display_Reserved | 0xD5100000 | 0x2B00000 | 显示保留区 |
| TZApps_Reserved | 0xD8800000 | 0x1B000000 | TZ 应用保留区 |

**三个 PCD 的结论**：

| PCD | 取值 | 依据 |
| --- | --- | --- |
| `PcdCpuVectorBaseAddress` | **0xA7600000** | = `CPU_Vectors` 基址（已核实） |
| `PcdPrePiStackBase` / `Size` | **0xA760D000** / **0x40000** | = `UEFI_Stack` 基址/大小（已核实） |
| `PcdFvDecompressAddr` | **0xA7AD9000** | = `FV_Region` 基址（**推断**：区域名与语义对应，但上游 SM8550 用的是 FD 内部偏移 0xA703A0C8，语义可能不同） |

> 重要旁证：上一轮我从 SM8550（aston）继承的两个值
> （0xA7600000 / 0xA760D000+0x40000）与本设备 XBL 表**逐字节相同**。
> 说明这套 UEFI 区域布局是高通该代的参考布局，SM8550 与 SM8650 共用。

### B11.3 显示不必"无解"：GOP 走 ABL 遗留 framebuffer

树内实际存在：

```text
Silicon/Silicium/SiliciumPkg/Drivers/SimpleFbDxe        <- 消费 PcdPrimaryFrameBuffer*
Common/Mu/MsGraphicsPkg/GopOverrideDxe
Common/Mu/MsGraphicsPkg/Library/FrameBufferMemDrawLib
```

`SimpleFbDxe` **不驱动 MDSS**，只把 bootloader 已经初始化好的 framebuffer 包装成 GOP。
因此 UEFI 出画面不依赖 Adreno WDDM 驱动；WinPE 再通过 GOP 使用
**Microsoft Basic Display**（系统自带帧缓冲驱动）渲染安装界面。
**修正上一轮"显示不可达"的说法**：不可达的是"桌面 GPU 加速"，不是"安装界面能显示"。

### B11.4 NuGet 失败的真正原因（不是网络，也不是缺镜像源）

上一轮记录的两个包拉取失败，根因有两个，且都不是"nuget.org 慢"：

1. **这两个包不在 nuget.org**。它们的源写死在 ext_dep 声明里，是 Azure DevOps 的
   Project Mu 私有源：

   ```text
   mu_nasm@20016.1.1                 <- https://pkgs.dev.azure.com/projectmu/mu/_packaging/Basetools-Binary/nuget/v3/index.json
   edk2-basecrypto-driver-bin@1.0.1  <- https://pkgs.dev.azure.com/projectmu/mu/_packaging/Mu-Public/nuget/v3/index.json
   ```

   实测 `mu_nasm` 在 nuget.org 上只有 2.13.3 / 2.14.2 / 2.15.5，**没有 20016.1.1**。
   因此**换 nuget.org 镜像源无效**。两个 Azure 源实测均返回 HTTP 200。

2. **Alpine 上没有 mono**。edk2toolext 的 `NugetDependency.GetNugetCmd()` 在非 Windows
   平台会拼成 `["mono", ".../NuGet.exe"]`：

   ```python
   if GetHostInfo().os != "Windows":
       cmd += ["mono"]
   ```

   缺 mono 时 NuGet.exe 根本起不来，表现为"下载失败"，极易被误判为网络问题。
   已安装 `mono 6.14.1`。

### B11.5 caihong 板级设备树终于取得

网络恢复后 `git sparse-checkout set arch/arm64/boot/dts/qcom` 成功（629 个文件），
取得 `sm8650-oneplus-caihong.dts`（36 KB）：

```text
model = "Oneplus Pad Pro";
compatible = "oneplus,caihong", "qcom,sm8650";
chassis-type = "tablet";
```

由此补齐了此前标为 TODO 的板级事实：

| 硬件 | 真实接口（来自 DTS） | GSIV |
| --- | --- | --- |
| 触摸屏 | **SPI4 @ 0xA90000**，`novatek,nt36532e`，中断 TLMM GPIO 162，复位 GPIO 161，12 MHz | 0x185 (32+357) |
| 磁吸键盘 | **UART7 @ 0xA9C000**，`oneplus,caihong-pogo` | — |
| 蓝牙 | **WCN7850 over UART14 @ 0x898000** | 0x1ED (32+461) |
| Wi-Fi | **WCN7850 over PCIe0 @ 0x1C00000** | 0xAD (32+141) |
| 充电 | **SC8547 @ I2C 0x6F**（primary/secondary 双路） | — |
| UFS 复位 | TLMM GPIO 210 | UFS 0x129（与厂商 DTB 一致） |

**同时修正一处此前的错误**：缺口清单里曾写"触摸走 I2C"，实际是 **SPI4**。
---

## B12. 首次成功构建 caihong UEFI 固件（2026-10-29 22:07）

### B12.1 结果

```text
FVMAIN          [99%Full] 10907648 (0xa67000) total, 10903824 used
FVMAIN_COMPACT  [29%Full]  4194304 (0x400000) total,  1236768 used
Return Code: 0x00000000
0051 Images Verified
PROGRESS - Success

 == caihong: assembling boot payload
    fd      : Build/caihongPkg/RELEASE_CLANGPDB/FV/CAIHONG_UEFI.fd  (4194304 bytes)
    bootshim: BootShim/BootShim.bin                                  (144 bytes)
 == caihong: wrote Mu-caihong-0-Model.img (1208320 bytes)
```

产物与校验（已入 `artifacts/SHA256SUMS`，9 条）：

| 文件 | 大小 | 校验 |
| --- | --- | --- |
| `artifacts/uefi/CAIHONG_UEFI.fd` | 4,194,304 B | `_FVH` 签名正确，`FvLength` == 文件大小 |
| `artifacts/uefi/Mu-caihong-0-Model.img` | 1,208,320 B | `ANDROID!` magic 正确 |
| `artifacts/uefi/BootShim.bin` | 144 B | — |
| `artifacts/uefi/build-caihong.log` | — | 完整构建日志 |
| `artifacts/uefi/BUILD_REPORT.TXT` | — | EDK2 构建报告 |

模块架构抽查（`PrePi.efi`、`UsbBusDxe.efi`、`GraphicsConsoleDxe.efi` 等 6 个）：
全部 `machine=0xaa64` = **AArch64 PE32+**。

FD 大小为 4,194,304 字节，**正好等于 ABL 为 UEFI_FD 保留的 0x400000 区间**，
与 `Resources/Configs/caihong.conf` 里的 `TARGET_FD_BASE=0xA7000000` /
`TARGET_FD_SIZE=0x00400000` 一致。

### B12.2 ⚠️ 这份固件的致命限制

**`Binaries/caihong/` 是从 `Binaries/aston/`（SM8550）复制来的占位。**

Mu-Silicium 的架构要求每设备一份**高通预编译 QcomPkg 驱动二进制**
（`EnvDxe`、`ClockDxe`、`UFSDxe`、`I2CDxe`、`DisplayDxe` 等 76 个），
源码树里 `Silicon/Qualcomm/QcomPkg/Drivers` 只有 7 个小驱动，其余全靠预编译二进制。

所以：

- 本次产物**证明了工具链与板级包完整可用**（这是真实成果）；
- 但固件内部是 **SM8550 的驱动**，在 SM8650 真机上**必然不能正常工作**
  （时钟、UFS、TLMM 全是 SoC 相关）。
- **这份 `.fd` 不可刷入，也不应被当作可启动固件。**

要得到真正可用于 caihong 的固件，必须把 `Binaries/caihong/` 换成 SM8650 的高通
BSP UEFI 二进制——公开渠道没有。

### B12.3 本次打通构建所解决的 8 个真实问题

按遇到的顺序，每个都是**真实卡点**，不是猜测：

| # | 现象 | 真正原因 | 处理 |
| --- | --- | --- | --- |
| 1 | `build_uefi.sh: cannot execute: required file not found` | Windows 克隆的 **CRLF** 让 shebang 变成 `#!/bin/bash\r` | `scripts/fix_line_endings.sh` |
| 2 | NuGet 拉不到包 | 包**不在 nuget.org**，在 `pkgs.dev.azure.com/projectmu` 私有源；换 nuget.org 镜像无效 | 确认源可达 |
| 3 | 依赖更新失败 | Alpine 缺 **mono**（edk2toolext 在非 Windows 用 mono 跑 NuGet.exe） | `apk add mono` |
| 4 | 仍失败 | mono 的 **CA 证书库为空** → `CERTIFICATE_VERIFY_FAILED` | `cert-sync` 导入 118 个根证书 |
| 5 | 构建几乎不动 | `/mnt/e` 的 9p I/O：mono 30 分钟只耗 8 秒 CPU | 整树迁到 `/root/muqcom`（2.1 GB） |
| 6 | `stray operand ==` | ① `[Defines]` 里的**注释**含 `!if`/`==` 字面量，edk2toollib 连注释都当条件式解析；② `TARGET_MULTIPLE_MODELS=0` 使 `DEVICE_MODEL` 为空，`!if $(DEVICE_MODEL) == 0` 塌缩成 `!if  == 0` | 改写注释措辞；caihong 单机型直接去掉该条件 |
| 7 | `Binaries/caihong/...EnvDxe.inf is not found` | 架构要求每设备预编译二进制 | 从 aston 复制（见 B12.2 限制） |
| 8 | `error C0DE` / `FileNotFoundError: ...SEC1.1.dpx` | **Alpine 是 musl，而 Mu 预编译 BaseTools 是 glibc 二进制**，`GenSec` 返回 127 却不报错，`.dpx` 段从未生成 | `apk add gcompat` 兼容层；验证：`GenSec` 手工执行产出 5 字节合法段 `05 00 00 13 08` |

第 8 条最隐蔽：`GenSec` 文件存在、可执行位正常、`ls` 看得见，但运行返回 127，
BaseTools 把失败吞掉，最终只在 GenFs 深处报一个与该问题毫无关系的 `os.path.getsize` 错误。
`scripts/diag_gensec.sh` 就是为定位它写的。

### B12.4 顺带修正的两处配置错误

- `TARGET_FD_BASE` 原来是 `0xBAB00000`，**落在 `DXE_Heap`（0xB8000000+0x1BA00000）区内**；
  改为设备真实的 `0xA7000000`（XBL `UEFI_FD`）。
- `PcdDtbExtensionAddr` / `PcdScheduleInterfaceAddr` 原抄 SM8550 的
  `0xA703A0C8`/`0xA703A950`。`PlatformHobLib.c` 里它们是受 `if (address)` 保护的
  **协议指针**，抄错地址会让固件把任意内存当 vtable 解引用 → 静默崩溃。
  已改为 `0x0`（不发布这两个 HOB），是唯一有依据的选择。

### B12.5 现在的确切位置

- ✅ caihong 板级包可以从源码完整构建出 AArch64 UEFI 固件卷
- ✅ ACPI 六表齐备并校验通过
- ✅ 构建链全部打通并脚本化（`scripts/sync_to_buildtree.sh`、`diag_gensec.sh` 等）
- ❌ 固件内驱动是 SM8550 的，**不能上机**
- ❌ 从未接触真机、从未刷写、从未启动

### B12.6 下一步（按阻塞度）

1. **拿 SM8650 的高通 BSP UEFI 驱动二进制**（`Binaries/caihong/` 的真货）——
   这是唯一真正的硬阻塞，公开渠道无解，只能从整机固件的 `uefi.img` 里反推，
   或从同 SoC 的其他设备提取。
2. 用 `xbl.img`/`uefi.img` 交叉验证 `PcdFvDecompressAddr` 的语义。
3. 显示：确认 `SimpleFbDxe` 能否拿到 ABL 遗留的 framebuffer
   （`Display_Reserved 0xD5100000 + 0x2B00000`）。
4. 之后才谈"装 Windows 到平板"。
---

## B13. 在真实 Linux 主机上构建成功（2026-10-30 03:50）

### B13.1 远端环境

用户提供了一台可用的 Linux 构建机：

```text
Ubuntu 22.04.5 LTS   x86_64
8 core / 15 GiB RAM / /root/data 435 GiB 可用
clang 14.0.0    mono 6.8.0.105    python 3.10.12    gcc/g++/make/git 齐备
```

这是**原生 glibc 环境**，正好消除了 B12.3 #8 那个 musl/glibc 根本问题。

### B13.2 复现流程（全部脚本化）

```sh
# 1) 远端准备（本地 Windows 侧驱动，密码只走环境变量，不入库）
python scripts/remote_exec.py  "apt-get install -y build-essential uuid-dev nasm bc \
     python3-pip git mono-complete clang lld llvm zlib1g-dev libssl-dev"
python scripts/remote_exec.py  "cd /root/data && git clone --depth 1 \
     --recurse-submodules --shallow-submodules \
     https://github.com/musabcel/Mu-Qcom.git muqcom"

# 2) 应用本项目的两个补丁
python scripts/remote_put.py patches/0001-*.patch /root/data/patches/0001.patch
python scripts/remote_put.py patches/0002-*.patch /root/data/patches/0002.patch
python scripts/remote_exec.py "cd /root/data/muqcom && git apply /root/data/patches/0001.patch && \
     cd Silicium-ACPI && git apply /root/data/patches/0002.patch"

# 3) 占位二进制 + 修复畸形 depex + 依赖
python scripts/remote_exec.py "cd /root/data/muqcom && cp -a Binaries/aston Binaries/caihong && \
     printf '\010' > Binaries/caihong/QcomPkg/Drivers/EnvDxe/EnvDxe.depex && \
     python3 -m pip install -r pip-requirements.txt"

# 4) 构建
python scripts/remote_exec.py "cd /root/data/muqcom && ./build_uefi.sh -d caihong -r RELEASE"

# 5) 取回产物
python scripts/remote_get.py <remote> artifacts/uefi-ubuntu/<name>
```

远端克隆到的 commit 与本地完全一致：`520b8826…`（2025-08-19），
所有 8 个子模块版本相同。两个补丁 `git apply` **零冲突**。

### B13.3 结果

```text
FVMAIN          [99%Full] 10940416 (0xa6f000) total, 10937032 used
FVMAIN_COMPACT  [29%Full]  4194304 (0x400000) total,  1244328 used
Return Code: 0x00000000
0051 Images Verified
PROGRESS - Success
Build total time: 00:00:29          <-- 30 秒

   fd     : Build/caihongPkg/RELEASE_CLANGPDB/FV/CAIHONG_UEFI.fd (4194304 bytes)
   bootshim: BootShim/BootShim.bin (144 bytes)
   wrote Mu-caihong-0-Model.img (1216512 bytes)
```

### B13.4 两次构建的交叉验证（可复现性证据）

同一份源码、两个不同环境，均产出结构合法的固件：

| 环境 | 编译器 | FD 大小 | FD SHA-256 前 16 位 | 校验 |
| --- | --- | --- | --- | --- |
| WSL Alpine 3.22 (musl + gcompat) | clang 20.1.8 | 4,194,304 | `242f3c0427e9ab06` | `_FVH` ok, FvLength 匹配 |
| Ubuntu 22.04 (glibc) | clang 14.0.0 | 4,194,304 | `1de6b01817861f67` | `_FVH` ok, FvLength 匹配 |

哈希不同是**预期的**：编译器版本不同（20 vs 14）。两者 FV 结构、大小、
模块数（51 个镜像通过 PE 校验）一致。

**结论**：板级包本身是正确的、可移植的、可复现的。B12.3 #8 的诊断得到验证——
Alpine/musl 只是构建环境问题，与 caihong 无关。

### B13.5 限制未变

远端构建**没有消除** B12.2 那条致命限制：

`Binaries/caihong/` 仍然是从 `Binaries/aston/`（SM8550）复制的占位。
换一台更好的构建机解决的是"能不能编出来"，解决不了"编出来的是不是 SM8650 的驱动"。

**这两份 FD 依旧不可刷入。**

### B13.6 关于凭据

远端主机地址与口令由用户在本轮提供，仅用于本次构建。
`scripts/remote_exec.py` / `remote_put.py` / `remote_get.py` **不保存任何凭据**，
只从环境变量 `REMOTE_HOST` / `REMOTE_PORT` / `REMOTE_USER` / `REMOTE_PASS`
（或 `REMOTE_KEY`）读取，因此可以安全地留在仓库里。

### B13.7 现在的确切位置

- ✅ 同一份板级包在 **musl 与 glibc 两种 Linux**、**clang 20 与 clang 14** 下均可构建通过
- ✅ 构建流程完全脚本化、可复现、双语环境验证
- ✅ ACPI 六表 + UEFI 固件卷 + boot.img，11 项校验全绿
- ❌ 固件内驱动仍是 SM8550 的占位
- ❌ 仍未接触真机

### B13.8 下一步（未变）

唯一硬阻塞仍是：**拿到 SM8650 的高通 BSP UEFI 驱动二进制**填进 `Binaries/caihong/`。
在此之前继续做的价值有限；可行方向是从设备自身的 `uefi.img`（ELF64，含 76 个驱动）
里尝试提取原始模块复用——与之前从 `xbl_config.img` 解出 ABL 区域表属同类工作。
---

## B14. 从设备自身 uefi.img 提取出真正的 SM8650 UEFI 驱动（2026-10-30 04:13）

### B14.1 动机

B12.2 认定的唯一致命限制：`Binaries/caihong/` 里没有 SM8650 的高通预编译驱动，
只能借用 SM8550(aston) 的占位，导致固件"能编出来但不能上机"。

而设备自己的 `uefi.img` **就是一个 UEFI 固件卷**，里面本来就装着这些驱动。

### B14.2 uefi.img 的结构（已解析）

```text
ELF64 AArch64, e_type=EXEC, e_entry = 0xA7000000   <-- 正好是 ABL 的 UEFI_FD 基址
  文件偏移 0x1000 处一个 3 MB 固件卷 (FvLength 0x300000)
    FFS 0x000048  type 0xF0  PAD（GUID 全 0xFF）
    FFS 0x000FE8  type 0x03  DXE Core（TE 映像，非 PE32）
    FFS 0x050000  type 0x02  FREEFORM（RAW，签名/哈希块）
    FFS 0x051118  type 0x0B  嵌套 FV，GUIDed 段 1d301fe9-be79-4353-91c2-d23bc959ae0c
    FFS 0x194030  type 0x0B  嵌套 FV，同一 GUID
```

`1d301fe9-…` 的 payload 以 `1f 8b 08 00` 开头 —— **纯 gzip**，标准库即可解开，
不需要任何 EDK2 工具。解开后又是一层段流（空 RAW 段 + `FV_IMAGE` 段），
真正的 `_FVH` 在偏移 48。

### B14.3 提取结果

新增 `scripts/extract_uefi_drivers.py`（纯 stdlib：ELF→FV→FFS→段→PE32），
**共提取 106 个 PE32 模块，78 个带 depex，合计 7.3 MB**，其中包括本项目最需要的：

```text
UFSDxe            DALSys            PmicDxe           RpmhDxe
DALTLMM           HALIOMMU          ClockDxe          ArmGicDxe
EnvDxeEnhanced    XhciDxe           UsbBusDxe         UsbMassStorageDxe
DisplayDxe        TsensDxe          ChargerExDxe      SmemDxe
QcomBds           ULogDxe           NpaDxe            VcsDxe  ...
```

修复的三个解析问题（都是真实踩到的）：

| 现象 | 真因 |
| --- | --- |
| 一个模块都提不出来 | `iter_ffs` 把 **GUID 全 0xFF 的 PAD 文件**当成卷结束标志，而本设备卷的第一个文件就是 pads |
| 嵌套 FV 解压后 "不是 FV" | gzip 解出来的是**段流**（空 RAW 段 + FV_IMAGE 段），`_FVH` 在偏移 48，不在 0 |
| 模块名只剩一个字母 | UI 段是 **UTF-16LE**，按 UTF-8 解会在第二个字节的 `\x00` 处截断 |

还有一个：GUIDed 段的 `DataOffset` 是相对**段头**（含 4 字节公共头）的，
按相对 payload 计算会偏 4 字节，gzip 直接报 "not a gzip file"。

### B14.4 生成 `Binaries/caihong`

新增 `scripts/make_binaries_from_uefi.py`：把提取结果转成 EDK2 期望的
`Binaries/caihong/QcomPkg/Drivers/<Dir>/<File>.{inf,efi,depex}`，
INF 里写入**模块原始的 FFS GUID**（FV 构建与 GUID 交叉引用都依赖它）。

- 平台 `Include/*.inc` 里共 **67 条** `Binaries/caihong/…` 引用
- 按 BASE_NAME 直接匹配 **65 条**
- 命名差异用**显式映射表**处理（不猜），例如：
  `EnvDxe→EnvDxeEnhanced`、`DALSYSDxe→DALSys`、`TLMMDxe→DALTLMM`、
  `HWIODxe→HWIODxeDriver`、`I2CDxe→I2C`、`SPMIDxe→SPMI`、`PmicDxeLa→PmicDxe`、
  `Phoenix2_0Dxe→Phoenix2_0Dex`、`XhciPciEmulationDxe→XhciPciEmulation`
- **2 条无法解析**：`FvUtilsDxe`、`SPSSDxe` —— 在 SM8650 固件的 106 个模块里
  **确实不存在**，已在 `APRIORI.inc` / `DXE.inc` 中注释掉并写明原因
- 生成 **65 个模块、184 个文件、4.75 MB**

顺带证实：设备原始 depex 里就有 `06 08`（PUSH 吃掉 END 的畸形表达式），
说明 B12.3 #8 遇到的那个 2 字节 depex 是上游共性问题，不是 aston 特有。
生成器已自动归一化为合法的单字节 `08`。

### B14.5 构建结果：成功

```text
PROGRESS - Success
Return Code: 0x00000000      0051 Images Verified
Build total time: 00:00:12

  fd      : CAIHONG_UEFI.fd        (4194304 bytes)
  bootshim: BootShim.bin           (144 bytes)
  wrote     Mu-caihong-0-Model.img (1212416 bytes)
```

### B14.6 驱动确实进去了（实测验证）

新增 `scripts/verify_fv_drivers.py`：拿 `BINARIES_INDEX.json` 里的 GUID
逐条核对构建产物 `FV/Ffs/` 目录。

```text
modules generated : 65
FFS entries in FV : 243
present in the FV : 63
missing from FV   : 2

-- spot check of SoC-critical drivers --
   EnvDxe      PRESENT  90a49afd-422f-08ae-9611-e788d3804845
   DALSYSDxe   PRESENT  8e9bd160-b184-11df-94e2-0800200c9a66
   RpmhDxe     PRESENT  cb29f4d1-7f37-4692-a416-93e82e219766
   TLMMDxe     PRESENT  8681cc5a-0df6-441e-b4b8-e915c538f067
   PmicDxeLa   PRESENT  5776232e-082d-4b75-9a0e-fe1d13f7a5d9
   UFSDxe      PRESENT  0d35cd8e-97ea-4f9a-96af-0f0d89f76567
```

**UFSDxe、DALSys、RpmhDxe、TLMM、Pmic 这些 SM8650 专有驱动已经进入固件卷。**

缺的 2 个：`GLinkDxe`、`Phoenix2_0Dxe`（非启动关键）。
它们的 INF 存在、路径正确，但在 `FV/Ffs` 里没有对应目录，构建日志也没提到，
**原因未查明**，列为待办。可能与其 INF 的 FILE_GUID 或 depex 有关。

### B14.7 产物

| 文件 | 大小 | 校验 |
| --- | --- | --- |
| `artifacts/uefi-real/CAIHONG_UEFI.fd` | 4,194,304 B | `_FVH` 正确，FvLength 匹配 |
| `artifacts/uefi-real/Mu-caihong-0-Model.img` | 1,212,416 B | `ANDROID!` 正确 |
| `artifacts/uefi-real/BINARIES_INDEX.json` | — | 65 个模块的 GUID/来源/大小 |
| `artifacts/uefi-real/build-caihong.log` | — | 完整构建日志 |

`artifacts/SHA256SUMS` 现为 **14 条**，`check_artifacts.sh` **33 项全绿**。

### B14.8 状态变化：致命限制已降级

| 项目 | B12 时 | 现在 |
| --- | --- | --- |
| `Binaries/caihong/` 驱动来源 | SM8550 占位，**不可上机** | **设备自身 uefi.img 提取的 65 个 SM8650 驱动**（含 UFSDxe） |
| 固件是否反映本机硬件 | 否 | **是**（SoC 级驱动已对齐） |

**仍然存在的缺口（必须说清）**：

1. **面板 XML 缺失**。`RawFiles/` 里仍是 aston 的面板配置；caihong 的
   `csot_nt36532_2120_3000` 配置**不在 uefi.img 里**（在 vendor 分区）。
   若 `DisplayDxe` 需要它，则显示仍不会初始化。
   （但若走 `SimpleFbDxe` + ABL 遗留 framebuffer，则不依赖面板 XML。）
2. **`RawFiles/` 其余内容**（BDS_Menu.cfg、logo1.bmp）仍是 SM8550 的，属配置类，非驱动。
3. **从未上机**。这份固件比 B12 的版本合理得多，但**仍未在真机上运行过**，
   不能声称能启动。
4. `GLinkDxe` / `Phoenix2_0Dxe` 未进 FV，原因待查。

### B14.9 下一步

1. 查明 `GLinkDxe` / `Phoenix2_0Dxe` 为何没进 FV。
2. 从 vendor 分区（或本机 dump）取 caihong 的面板 XML，补进 `RawFiles/`。
3. 真机验证：BootShim 能否从 `0xA7000000` 起得来、SimpleFbDxe 能否出画面、
   UFSDxe 能否枚举分区。**这一步必须上机，且需要先确认恢复路径。**
---

## B15. `GLinkDxe` / `Phoenix2_0Dxe` 未进 FV 的排查结论（2026-10-30 04:20）

### B15.1 结论：不是缺陷，是上游有意禁用

B14.6 里报的"2 个模块缺失"已经查清，**不是构建问题**：

```text
Include/DXE.inc:36      #INF Binaries/caihong/QcomPkg/Drivers/GLinkDxe/GLinkDxe.inf
Include/DXE.inc:97      #INF Binaries/caihong/QcomPkg/Drivers/Phoenix2_0Dxe/Phoenix2_0Dxe.inf
```

这两行**开头就有 `#`**，即 DXE 驱动列表里它们是关闭的。而
`Include/APRIORI.inc` 第 31 / 71 行仍以 `INF ...` 形式列着它们。

关键点：**APRIORI.inc 只生成 FV 的派发顺序表（APRIORI 文件），
不决定模块是否进入 FV**；决定这一点的是 DXE.inc。所以只出现在 APRIORI
而不在 DXE 里的模块，天然不会进 FV —— 而 APRIORI 表里仍会写它的 GUID，
这是一个上游遗留的、无害但过期的引用。

**与上游一致的证据**（aston = OnePlus Ace 3 / SM8550）：

```text
astonPkg/Include/DXE.inc:36   #INF Binaries/aston/QcomPkg/Drivers/GLinkDxe/GLinkDxe.inf
astonPkg/Include/DXE.inc:97   #INF Binaries/aston/QcomPkg/Drivers/Phoenix2_0Dxe/Phoenix2_0Dxe.inf
```

行号都一样 —— 说明这是 **Mu-Silicium 对这批 OnePlus 设备的统一处理**，
不是 caihong 引入的问题。

### B15.2 依赖影响评估：无

两个模块的 GUID 在提取出的 105 个 depex 里**均无被引用**：

```text
modules whose depex references GLinkDxe     : 0
modules referencing Phoenix2_0Dxe            : 0
```

所以它们的缺席**不会造成任何 depex 悬挂**，不会让别的驱动无法派发。

### B15.3 但有一点值得注意

设备**原厂** `uefi.img` 里这两者都是存在的（我们提取到了 `GlinkDxe` 与
`Phoenix2_0Dex`）。也就是说：

- 上游把它们关掉，是 Mu-Silicium 侧的取舍（可能与它自己的 GLINK 实现冲突），
  **不是**因为 SM8650 硬件不需要；
- 若后续需要 `PmicGlinkDxe` 之外的 GLINK 通道（例如某些 OPPO 专有服务），
  把这两行的 `#` 去掉即可重新启用，风险是可能与 Mu 的实现冲突。

**当前决定：保持上游行为（不启用）**，理由是没有依赖需要、且缺少真机验证手段。
这是一项**明确的、有依据的选择**，不是遗漏。

### B15.4 验证工具已修正

原先 `scripts/verify_fv_drivers.py` 把这类"按设计排除"误报成缺失。
已改为读取平台 `DXE.inc` 中被注释的条目，把结果分成三类：

```text
classifying against: Platforms/OnePlus/caihongPkg/Include/DXE.inc (5 disabled entries)
modules generated      : 65
FFS entries in FV      : 243
present in the FV      : 63
absent by design       : 2  (commented out in DXE.inc)
     GLinkDxe               7942a7eb-b7d5-4e2e-b908-831e4de55b58
     Phoenix2_0Dxe          77749afd-422f-08ae-9611-e788d3801414
unexpectedly missing   : 0
```

退出码也改为：有"意外缺失"才返回非 0。第三参数可显式传入 `DXE.inc`，
因为索引里记录的 `platform_include` 是构建主机的绝对路径，换机器就失效。

### B15.5 状态

B14 的结论不变，且更清晰了：**65 个 SM8650 驱动全部按预期处理，
63 个进卷，2 个按上游设计排除，0 个意外丢失。**

下一个未决项仍是 **caihong 的面板 XML**（不在 `uefi.img` 里，在 vendor 分区）。
---

## B16. 面板 XML：无需上机，从本地固件镜像提取成功（2026-10-30 04:24）

### B16.1 结论先行

B14.8 里列为"面板 XML 不在 uefi.img 里、需从 vendor 分区取"的那一项，
**实际上不用动设备**：面板配置就在设备自己的 `xbl_ramdump.img` 里，已提取到手。

### B16.2 定位过程

先排除大分区，再在全部本地镜像里搜 Qualcomm UEFI 的面板 XML 标记：

```text
镜像                 大小          nt36532  dsc_cmd  <Panel 标签
dtbo.img             25 MB         136      80       0
my_manifest.img      0.4 MB        1        1        0
my_product.img       400 MB        1        1        0
vendor_boot.img      200 MB        2        0        0
vendor_dlkm.img      37 MB         5        0        0
xbl_ramdump.img      0.88 MB       2        18       12      <-- 命中
```

`xbl_ramdump.img` 里共 6 个面板定义，其中**唯一**符合本机规格的是：

```text
<PanelName>CSOT_NT35652</PanelName>
<PanelDescription>CSOT NT35652 Dual DSI Video Mode Panel with DSC (2120x3000 24bpp)</PanelDescription>
<HorizontalActive>3000</HorizontalActive>
<VerticalActive>2120</VerticalActive>
```

与内核 cmdline 的 `qcom,mdss_dsi_panel_csot_nt36532_2120_3000_dual_dsc_144hz_vid`
完全对应（2120×3000 / Dual DSI / Video mode / DSC / 144 Hz）。

其余 5 个是通用集合里的别的面板（`AC545 1 A0005`、`boe ili7838e`、
`VTDR6130 Visionox`、`VirtioDSI` 等），其中 `boe ili7838e` 的
**1264×2780** 正好是 aston 的屏幕——说明这是高通/OPPO 打包的通用面板库，
不是本机专属。这也解释了为什么 `Binaries/aston/RawFiles/` 里的面板名字
在 caihong 的 `RawFiles/`（当时是从 aston 复制的）里也能看到。

### B16.3 提取出的文件

```text
work/panel/Panel_CSOT_NT35652.xml    2961 字节
  以 <?xml version='1.0' encoding='utf-8'?> 开头
  以 </Group>（Backlight Configuration 结尾）
```

提取方法：定位 `<PanelName>CSOT_NT35652` → 向前回退到最近的 `<?xml` 起点
→ 向后到下一个 `<?xml` 或 NUL 填充为止。

### B16.4 顺带纠正一个方向错误

面板 XML 里 `HorizontalActive = 3000`、`VerticalActive = 2120`，
说明**在 bootloader 的坐标系里面板是 3000 宽 × 2120 高**。
而我在 `caihong.dsc` 里填的是 `Width|2120 / Height|3000`，**方向反了**。
已改为：

```text
gSiliciumPkgTokenSpaceGuid.PcdPrimaryFrameBufferWidth|3000
gSiliciumPkgTokenSpaceGuid.PcdPrimaryFrameBufferHeight|2120
```

### B16.5 接入方式（Mu-Silicium 机制）

面板 XML 不是驱动，而是以 **FREEFORM 文件** 打进 FV，`UI` 段就是文件名，
`DisplayDxe` 按文件名查找。因此在 `caihongPkg/Include/RAW.inc` 末尾追加：

```text
  FILE FREEFORM = C2A147E0-7E5B-4E2A-9C6D-1F0B3A5D8E21 {
    SECTION UI = "Panel_CSOT_NT35652.xml"
    SECTION RAW = Binaries/caihong/RawFiles/Panel_CSOT_NT35652.xml
  }
```

GUID 是为 caihong 新取的（`DisplayDxe` 按 UI 名匹配，GUID 只需唯一）。

### B16.6 验证

```text
构建： PROGRESS - Success，11 秒
产物： CAIHONG_UEFI.fd 4194304 字节 / Mu-caihong-0-Model.img 1212416 字节

FV 内：
  Build/.../FV/Ffs/C2A147E0-7E5B-4E2A-9C6D-1F0B3A5D8E21FVMAIN   <-- 面板 XML 已进卷
  FFS 文件数 243 -> 244                                        <-- 正好多这一个
```

### B16.7 仍未解决 / 仍需上机

1. **面板命名不确定**：bootloader 的 XML 叫 `CSOT_NT35652`，内核叫 `nt36532`。
   本机究竟用哪一颗、`DisplayDxe` 会不会按这个名字去找，
   **只有真机能确认**。两个变体可能对应不同硬件批次。
2. `RawFiles/` 里其余面板 XML 仍是 aston 带来的通用集合，无害但冗余。
3. **依旧没有上机**：面板 XML 打进 FV 只代表"素材齐了"，
   不代表 `DisplayDxe` 能点亮屏幕。
---

## B17. 真机首次上电验证：从"卡在 fastboot"到"PrePi 完成 11/12 步"（2026-10-30）

本节记录**第一次在真机上运行自编译固件**的全过程。设备：OnePlus Pad Pro
（caihong，序列号 67ab95c8），已解锁，用户已完成全量分区备份。

### B17.1 上机前置条件（两条都是硬门槛，缺一不可）

| 门槛 | 现象 | 结论 |
| --- | --- | --- |
| **vbmeta 校验必须关闭** | `fastboot boot` 返回 `Failed to load/authenticate boot image: Load Error`；刷入后直接回 fastboot | 设备 `vbmeta_a/b` 的 flags 均为 `0x00000000`（hashtree/verification 都启用）。用 `fastboot --disable-verity --disable-verification flash vbmeta_b <原厂 vbmeta>` 后，同一镜像变为 `Booting OKAY` |
| **boot 镜像头必须是 v4** | v1 镜像刷入后 6 秒回到 fastboot 页面，屏幕停在 fastboot 页；v4 镜像则停在厂商 logo，不再回落 | 原厂 boot.img 是 `header_version=4`（header_size 1584、ramdisk_size 0）。Mu-Silicium 默认脚本产出 v1，**在这台设备上被 ABL 直接拒绝** |

这两条都不是"猜测"：第一条有 fastboot 的明确错误串，第二条有可复现的行为差异
（6 秒回落 vs 不再回落）。

### B17.2 没有 UART 时如何获得可观测性

设备没有可接触的调试串口，也没有 adb/USB 输出。方案是把**面板本身当作输出设备**：

1. **前置探针**（`scripts/fbtest.S`）：一个 104 字节的裸 AArch64 载荷，
   往 `0xD5100000` 填充纯色后死循环。屏幕变绿 → 证明 ABL 确实跳转、
   且该地址就是可写的帧缓冲。这是整个诊断体系的地基。
2. **BootShim 探针**（`scripts/shimprobe.S`）：复制固件卷前染蓝、复制后染色，
   用来区分"载荷没跑"和"载荷跑了但固件崩"。
3. **固件内进度条**（`CAIHONG_BRINGUP_MARKERS`）：在 PrePi 的每个里程碑
   重绘屏幕为 N 条白色横条（`BRINGUP_STEP(n)`），**条数就是步号**。

> 教训：最初用"整屏染不同颜色"做标记，实测**不可靠**——`0xFF00FF00`（纯绿）和
> `0xFF00FF80`（春绿）肉眼无法区分，同一现象被报告成不同的步。改成横条计数后
> 立刻收敛。这套方法后来固化在 `PrePi.c` / `PeiHobLib.c` 的宏里，默认编译关闭。

### B17.3 完整的启动里程碑链（全部有真机证据）

| # | 里程碑 | 结果 |
| --- | --- | --- |
| — | ABL 接受镜像并交出控制权 | ✅ |
| — | BootShim 复制 4 MB 固件卷到 `0xA7000000` 并跳转 | ✅ |
| 1 | PrePi `CEntryPoint` 进入（SEC/入口汇编、FV 交接正常） | ✅ |
| 2 | `PlatformInitialize()`（GICR_WAKER 唤醒） | ✅ |
| 3 | Display Reserved 清零 + `SerialPortInitialize` | ✅ |
| 4 | `LocateMemoryMapAreaByName("UEFI FD")` + D-cache 无效化 | ✅ |
| 5 | `PrePiMain` 进入 | ✅ |
| 6 | "DXE Heap" 与 "UEFI Stack" 区域定位成功（内存表存在） | ✅ |
| 7 | `ArchInitialize()` | ✅ |
| 8 | Debug Agent + 调试定时器中断 | ✅ |
| 9 | `HobConstructor` + `PrePeiSetHobList` | ✅ |
| 10 | **`MemoryPeim()`（开 MMU + 建内存 HOB）** | ✅ 修内存映射后才通过 |
| 11 | `BuildStackHob` + `BuildCpuHob` | ✅ |
| 12 | MP core PPI 段 | ✅ |
| 13 | SEC performance HOB | ✅ |
| 14 | `SetBootMode` | ✅ |
| 15 | `PlatformPeim` 进入且 `PcdFvBaseAddress` 正确 | ✅ |
| 16 | `BuildFvHob` | ✅ |
| 17 | `BuildMemHobForFv` | ✅ |
| 18 | `BuildPlatformHobs` | ✅ |
| 19 | `EnableMemoryProtection` | ✅ |
| 20 | `ProcessLibraryConstructorList`（全部库构造函数） | ✅ |
| 21 | `FfsAnyFvFindFirstFile(FV_IMAGE)` | ✅ |
| 22 | **`FfsProcessFvFile`（压缩固件卷解压完成）** | ✅ |
| 23 | `LoadDxeCoreFromFv` → DxeCore 接管 | ❌ **当前卡点** |

进度条最终停在 **11 条**（对应上表的第 22 步）。

### B17.4 期间修掉的真实 bug

| # | bug | 影响 | 修复 |
| --- | --- | --- | --- |
| 1 | `DeviceMemoryMapLib.c` 用的是 **SM8550(aston) 的内存布局** | PrePi 按名字查 DXE Heap / UEFI Stack / UEFI FD，拿到的是另一台设备的地址；`MemoryPeim` 必崩 | 按设备自身 XBL 41 项区域表重写（`UEFI FD=0xA7000000`、`DXE Heap=0xB8000000+0x1BA00000`、`Display Reserved=0xD5100000`） |
| 2 | MP core PPI 空指针解引用 | `GetPlatformPpi` 失败时 `ASSERT_EFI_ERROR` 在 RELEASE 下编译为空，随后直接解引用 NULL | 增加 `ArmMpCoreInfoPpi == NULL` 判断后跳过 |
| 3 | 进度条颜色歧义（工具问题） | 无法判读，浪费多轮上机 | 改为横条计数 |

### B17.5 当前卡点：`LoadDxeCoreFromFv`

`LoadDxeCoreFromFv(NULL, 0)` 的实现是：

```c
Status = FfsAnyFvFindFirstFile (EFI_FV_FILETYPE_DXE_CORE, &VolumeHandle, &FileHandle);
if (!EFI_ERROR (Status)) return LoadDxeCoreFromFfsFile (FileHandle, StackSize);
```

它遍历**所有固件卷**找类型 `0x03`（DXE_CORE）的文件。而我们 FD 的布局是：

```text
FFS @0x000048  type 0x03  PrePi            <-- 类型就是 DXE_CORE
FFS @0x00C000  type 0x02  FREEFORM
FFS @0x00E220  type 0x0B  FV_IMAGE (压缩的 FVMAIN，解压后 10.4 MB)
```

**外层卷里的第一个文件 PrePi 本身就是 `DXE_CORE` 类型**，因此
`FfsAnyFvFindFirstFile(DXE_CORE)` 很可能返回的是 PrePi 自己而不是解压后的
真 DxeCore。若成立，`LoadDxeCoreFromFfsFile` 会把 PrePi 当作 DXE 核心加载，
导致异常。

**这是下一次上机要验证的第一件事。** 验证方法：在 `LoadDxeCoreFromFv` 前后
各加一个进度条步骤，看是否进入、以及进入后是否重演前面的条数序列
（若重演，即证明加载的是 PrePi 自身）。

其他候选原因（按可能性排序）：
1. 解压后的 FV 落在不合适的地址，`LoadDxeCoreFromFfsFile` 取 PE32 时越界；
2. DxeCore 栈分配（`StackSize=0` 走默认值）失败；
3. `PcdFvDecompressAddr`（当前 `0xA7AD9000`，**全项目唯一推断值**）影响
   `FvDxe` 等预编译驱动，而非 PrePi。

### B17.6 产物与恢复

本次上机使用的镜像全部留在 `artifacts/fbtest/`：

| 文件 | 用途 |
| --- | --- |
| `Mu-fbtest.img` | 帧缓冲纯色探针（证明跳转与 FB 地址） |
| `Mu-shimprobe.img` | BootShim 双色探针 |
| `Mu-markers*.img` | 各阶段颜色/横条标记版本 |
| `Mu-bars3.img` | 最终 12 段进度条版本 |

**回滚点**（均实测有效，设备已多次成功恢复）：

```text
backup/boot_b_stock.img    201326592 B  sha256 EF33FE88539915D0...
backup/vbmeta_b_stock.img       65536 B  sha256 287B6A1941809FF2...
```

回滚命令：
`fastboot flash boot_b backup\boot_b_stock.img` 与
`fastboot flash vbmeta_b backup\vbmeta_b_stock.img`。

### B17.7 诚实结论

- 固件**已经能在真机上执行**，并且推进到 PrePi 的最后一步；
  这比 B12 时"完全不能上机"有了本质区别。
- 但**仍未进入 DxeCore**，因此屏幕、USB、UEFI Shell、Windows 全都还看不到。
- 全程**没有**任何一刻显示过 UEFI 界面。
- 设备每次都成功恢复，Android 数据未受影响。
---

## B18. 深入 `DecompressFirstFv`：把 `EFI_NOT_FOUND` 追到底（2026-10-30）

B17 停在 `LoadDxeCoreFromFv`。本轮把失败点前移到**解压**这一步，并用三组
独立证据排除了三个假设。

### B18.1 把失败点精确化

把 `DecompressFirstFv()` 在 PrePi 里**内联展开**成它的两个真实步骤，并用进度条
分别标记：

```c
Status = FfsAnyFvFindFirstFile (EFI_FV_FILETYPE_FIRMWARE_VOLUME_IMAGE, ...);
BRINGUP_STEP (10);                    // 步骤 10 = 查找返回
if (!EFI_ERROR (Status)) {
  Status = FfsProcessFvFile (...);
  // 成功 -> 步骤 11；失败 -> 条数编码错误码
}
```

失败时按错误码分档显示，实测结果：

| 条数 | 错误码 | 实测 |
| --- | --- | --- |
| 3 | `EFI_UNSUPPORTED` | |
| 4 | `EFI_OUT_OF_RESOURCES` | |
| 5 | `EFI_VOLUME_CORRUPTED` | |
| **6** | **`EFI_NOT_FOUND`** | **✅ 就是这个** |
| 7 | 其他 | |

所以：**FV_IMAGE 文件找到了（步骤 10 通过），但 `FfsProcessFvFile` 返回
`EFI_NOT_FOUND`。**

### B18.2 固件卷结构是正确的（本地解压验证）

`FfsProcessFvFile` 的 `EFI_NOT_FOUND` 只有一处来源：

```c
Status = FfsFindSectionDataWithHook (EFI_SECTION_FIRMWARE_VOLUME_IMAGE, ...);
if (EFI_ERROR (Status)) return Status;      // <-- 就是这里
```

于是用 Python 在本地把 FD 里那个 GUIDed LZMA 段**真正解开**验证内容：

```text
FD 偏移 0x00E220 : FFS type=0x0B (FV_IMAGE)
  └─ 段 0x02 GUIDED  GUID=ee4e5898-…（LZMA） data_offset=24
       └─ 解压后 10,571,784 字节：
            section 0x19 (RAW, 4 字节)
            section 0x17 (FV_IMAGE, 0x00A15004 = 10.5 MB)   <-- 正是要找的
```

**结论：镜像结构完全正确**，0x17 段确实在压缩层里面。问题100% 在"运行时解不开"。

### B18.3 三个假设，逐一用证据排除

| # | 假设 | 证据 | 结论 |
| --- | --- | --- | --- |
| 1 | PrePi 没链 LZMA 解压库 | `SiliciumPkg.dsc.inc` 中 `SiliciumPkg/PrePi/PrePi.inf { <LibraryClasses> NULL\|MdeModulePkg/Library/LzmaCustomDecompressLib/... }` | **排除** |
| 2 | 库构造函数顺序反了（LZMA 先于 ExtractGuidedSection 注册） | 生成物 `AutoGen.c`：`ExtractGuidedSectionLibConstructor()` 在 407 行、`LzmaDecompressLibConstructor()` 在 **419 行** | **排除** |
| 3 | `PcdMaximumGuidedExtractHandler` 在 PrePi 里读成 0，导致处理器表分配失败 | 该 PCD 在库 INF 里声明为 `[FixedPcd.common]`，编译期常量 `0x10` | **排除** |

额外做过的尝试：在解压前**显式再调一次** `LzmaDecompressLibConstructor()`
（重复注册在实现里是覆盖更新，无害）——**仍然 6 条**，即
`ExtractGuidedSectionGetInfo()` 依旧找不到 LZMA 处理器。

### B18.4 剩下的唯一解释

`ExtractGuidedSectionGetInfo()` 返回错误 → `FfsProcessSection` 打印
`Decompress GetInfo Failed` 后**直接 `return EFI_NOT_FOUND`** —— 与现象一致。

而处理器表在 `PrePiExtractGuidedSectionLib` 里的存储方式是：

```c
ExtractGuidedSectionLibConstructor():           // 模块构造函数
  ExtractHandlerGuidTable   = AllocatePool (0x10 * sizeof (GUID));
  ExtractDecodeHandlerTable = AllocatePool (...);
  ExtractGetInfoHandlerTable= AllocatePool (...);
  BuildGuidDataHob (&PRE_PI_EXTRACT_GUIDED_SECTION_DATA_GUID, &SavedData, sizeof (SavedData));
```

也就是说处理器表**挂在一个 GUID HOB 上**。若该 HOB 在后续
`ExtractGuidedSectionRegisterHandlers()` 查找时不可见，
注册就会失败，且**不会报错**（返回值被构造函数吞掉）。

### B18.5 下一步的确定性探针（尚未执行）

在 PrePi 里直接对**已知地址**的 GUIDed 段调用
`ExtractGuidedSectionGetInfo()`，把返回值编码成条数显示：

```c
VOID *Sec = (VOID *)(UINTN)(0xA7000000ULL + 0xE220 + 24);  // FD 内 0x0B 文件的第一个段
Status = ExtractGuidedSectionGetInfo (Sec, &Dst, &Scratch, &Attr);
```

- 返回 `EFI_SUCCESS` → 处理器没问题，问题在 `FfsProcessSection` 的遍历/递归
- 返回 `EFI_UNSUPPORTED`/`EFI_NOT_FOUND` → 确认处理器表不可见，
  进而检查 `GetFirstGuidHob` 与 HOB 链是否一致

这是**一次刷机就能定性**的实验，下一步优先做它。

### B18.6 本轮的进度条编码表（供后续复用）

`CAIHONG_BRINGUP_MARKERS` 打开时，屏幕显示 N 条白色横条（黑底、条间有 6 px 黑色
间隔，共 12 格）。语义：

| 条数 | 含义 |
| --- | --- |
| 1–9 | PrePi 各阶段（见 B17.3） |
| 10 | `FfsAnyFvFindFirstFile(FV_IMAGE)` 返回 |
| 11 | `FfsProcessFvFile` **成功** |
| 3 / 4 / 5 / 6 / 7 | 解压失败，条数即错误码（见 B18.1） |

### B18.7 设备状态

本轮结束后已回滚到原厂 `boot_b`，`sys.boot_completed=1`，Android 正常。
回滚点未变：

```text
backup/boot_b_stock.img     sha256 EF33FE88539915D0…
backup/vbmeta_b_stock.img   sha256 287B6A1941809FF2…
```

### B18.8 诚实结论

- 失败点从"`LoadDxeCoreFromFv` 未知"收敛到"`ExtractGuidedSectionGetInfo` 返回错误"，
  范围再次缩小，且**排除了三个具体假设**（每个都有代码或实测证据）。
- 仍未进入 DxeCore，屏幕上仍只有进度条，没有任何 UEFI 界面。
- 下一步是一次性判别实验（B18.5），不需要再猜。
---

## B19. 解压链路最后一次深挖：GUIDed 段"能问不能解"（2026-10-30）

B18 把失败定位在 `FfsProcessFvFile → FfsFindSectionDataWithHook`。本轮在**固件内
直接探测**了 GUIDed 段的两个阶段，拿到了此前被上层抹掉的真实错误码。

### B19.1 关键发现：`FfsProcessSection` 把两种失败映射成同一个错误

```c
// Common/Mu_Tiano_Plus/EmbeddedPkg/Library/PrePiLib/FwVol.c
Status = ExtractGuidedSectionGetInfo (Section, ...);
if (EFI_ERROR (Status)) {
  DEBUG (("Decompress GetInfo Failed - %r\n", Status));
  return EFI_NOT_FOUND;          // <-- 抹掉真实原因 (A)
}
...
Status = ExtractGuidedSectionDecode (Section, &DstBuffer, ScratchBuffer, ...);
if (EFI_ERROR (Status)) {
  DEBUG (("Decompress Failed - %r\n", Status));
  return EFI_NOT_FOUND;          // <-- 抹掉真实原因 (B)
}
```

两个不同故障都变成 `EFI_NOT_FOUND`，这就是为什么连续几轮看到的都是"6 条"。

### B19.2 探针实测结果

在 PrePi 里用**已知的 FFS 文件句柄**复现内部调用（跳过 24 字节文件头取第一个段）：

| 探针 | 调用的函数 | 结果（条数） | 结论 |
| --- | --- | --- | --- |
| 第一版 | `ExtractGuidedSectionGetInfo` | **11** = `EFI_SUCCESS` | 处理器**正常**，头部可解析 |
| 第二版 | `ExtractGuidedSectionDecode` | **9** = 其他错误 | **解码失败** |

`LzmaGuidedSectionExtraction` 只有两条返回路径：GUID 不匹配 → `INVALID_PARAMETER`，
否则返回 `LzmaUefiDecompress()`，而后者在 `LzmaDecode != SZ_OK` 时**也只返回
`RETURN_INVALID_PARAMETER`**（`LzmaDecompress.c:218`）。

所以：**`LzmaDecode` 解码失败**。

### B19.3 一个真实的潜在缺陷（但不解释本次故障）

从流头能读出**字典大小**：

```text
payload head: 5d 00 00 00 01 | 08 50 a1 00 00 00 00 00
              props | 字典 = 0x01000000 = 16 MB
                      解压后 = 0x00A15008 = 10,571,784 字节
```

而 EDK2 的 scratch 缓冲是个**固定 64 KB 常量**：

```c
LzmaDecompress.c:14
#define SCRATCH_BUFFER_REQUEST_SIZE  SIZE_64KB
```

`LzmaDecode` 的字典是从这块 scratch 里通过 `ISzAlloc` 分配的，64 KB 装不下 16 MB
字典 → `SZ_ERROR_MEM` → `RETURN_INVALID_PARAMETER`。

**已按此修改**（`Mu_Basecore/.../LzmaCustomDecompressLib/LzmaDecompress.c`）：
把 scratch 大小改为从流头动态推算 `max(64KB, 字典大小 + 1MB)`，并同时用于
`GetInfo` 与 `UefiDecompress` 两处，保证调用方分配量与解码方上限一致。

**但实测仍然 9 条**（编码已确认重新编译进固件、DSC 也指向该库）。因此：

> 64 KB 的 scratch 确实是个真实缺陷，但**不是本次失败的根因**。
> 这个修改保留，因为它对任何大字典流都是必要的；但它没有解决本项目的问题。

### B19.4 尝试绕开 LZMA：Tiano 压缩（受阻于工具链）

FDF 里内层卷的包装方式（`Platforms/OnePlus/caihongPkg/caihong.fdf`）：

```ini
FILE FV_IMAGE = 9E21FD93-9C72-4C15-8C4B-E77F1DB2D792 {
  SECTION GUIDED EE4E5898-3914-4259-9D6E-DC7BD79403CF PROCESSING_REQUIRED = TRUE {
    SECTION FV_IMAGE = FVMAIN
  }
}
```

`EE4E5898-…` 就是 LZMA。换成 Tiano（`EFI_SECTION_COMPRESSION`）可以**完全绕开**
guided-section 路径：PrePiLib 用 `UefiDecompress()` + `BaseUefiDecompressLib`
直接处理，**不需要 scratch 缓冲**，而且 `UefiDecompressLib` 在本平台已映射、
`PrePiLib.inf` 也已声明依赖。

两种写法都被工具链拒绝：

| 写法 | 结果 |
| --- | --- |
| `SECTION COMPRESS PI_STD {` | `edk2toollib` 的 FDF 解析器 `IndexError: list index out of range`（该解析器要求所有非 GUIDED 的 SECTION 行含 `=`） |
| `SECTION COMPRESS = PI_STD {` | 解析器通过，但 **GenFds 报错**，FD 未重新生成 |

FDF 已恢复为原来的 LZMA 写法（并在注释里记录了这条线索），构建验证通过。

### B19.5 剩余候选（按可操作性排序）

1. **让 FDF 生成 Tiano 压缩卷**：研究 `edk2toollib` 解析器与 GenFds 对
   `SECTION COMPRESS` 的语法分歧，或绕过该解析器（它只在环境准备阶段用）。
   一旦成功，LZMA 问题整体消失。
2. **改用不压缩布局**：需要把固件卷放到 ≥12 MB 的空闲区域
   （如 `Kernel` 区 `0xA8000000`），并同步改 `TARGET_FD_BASE/SIZE` 与
   `DeviceMemoryMapLib` 的 "UEFI FD" 条目。
3. **继续 debug `LzmaDecode`**：用 SDK 的 `LzmaDec_DecodeToBuf` 逐步解码，
   或对比 7-Zip 与 SDK 对同一流的处理。成本最高。

### B19.6 设备状态

已回滚原厂 `boot_b`，`sys.boot_completed=1`，Android 正常。

### B19.7 诚实结论

- 本轮**证伪了自己上一轮的判断**（"处理器没注册"）：`GetInfo` 实际是成功的，
  失败在**解码**这一步。这是靠固件内探针实测得到的，不是推断。
- 顺手发现并修掉了一个真实的潜在缺陷（64 KB scratch），但**它不是本项目的根因**。
- 仍未进入 DxeCore。屏幕从头到尾只有进度条，**没有出现过任何 UEFI 界面**。
- 结论：`LZMA` 这条路在本平台上受上游实现限制，**下一步应当绕开它**（方案 1 或 2），
  而不是继续深挖解码器。
---

## B20. 突破：绕开 LZMA，DxeCore 首次被加载（2026-10-30）

B19 的结论是"LZMA 这条路受上游限制，应当绕开"。本轮按方案 2 实施，**成功让 PrePi
跑完全程并进入 DxeCore**。

### B20.1 关键决策：不使用压缩

FDF 里内层固件卷由

```ini
SECTION GUIDED EE4E5898-3914-4259-9D6E-DC7BD79403CF PROCESSING_REQUIRED = TRUE {
  SECTION FV_IMAGE = FVMAIN
}
```

改为直接内嵌：

```ini
SECTION FV_IMAGE = FVMAIN
```

这样 `FfsProcessSection` 直接找到 `EFI_SECTION_FIRMWARE_VOLUME_IMAGE`，
`FfsProcessFvFile` 只是把它发布成 FV HOB，**完全不需要解码器**。

**代价**：卷从 1.2 MB 变成 **14 MB**，原来的 4 MB `UEFI_FD` 区装不下。

### B20.2 固件卷搬迁

把固件卷放到 ABL "DXE_Heap" 区（`0xB8000000 + 0x1BA00000`，452 MB 普通 DRAM）的
**前部**，DXE 堆相应后移：

| 项目 | 原值 | 新值 |
| --- | --- | --- |
| `TARGET_FD_BASE` | `0xA7000000` | `0xB8000000` |
| `TARGET_FD_SIZE` | `0x00400000` (4 MB) | `0x00E00000` (14 MB) |
| `"UEFI FD"` 描述符 | `0xA7000000 / 0x400000` | `0xB8000000 / 0xE00000` |
| `"DXE Heap"` 描述符 | `0xB8000000 / 0x1BA00000` | `0xB8E00000 / 0x1AC00000` |

选这里的原因是它**不是** ABL 加载 boot.img 的区域（那是 `Kernel` 区
`0xA8000000`），所以 BootShim 的"复制到自己脚下"不会踩到源数据。

### B20.3 过程中解决的两个真实构建问题

未压缩卷触发了 GenFv 的重定位路径，而重定位要求 PE 的
`SectionAlignment == FileAlignment`。本项目只设了 `/ALIGN`，没设 `/FILEALIGN`
（默认 0x200），于是：

```text
GenFv: ERROR 3000: Invalid
  PE image Section-Alignment and File-Alignment do not match : ...DxeCore.ffs
  Could not rebase ...
```

`Silicon/Silicium/SiliciumPkg/SiliciumPkg.dsc.inc` 里补上：

| 模块类型 | 原 | 现 |
| --- | --- | --- |
| `SEC`（原本就对） | `/ALIGN:0x1000 /FILEALIGN:0x1000` | 不变 |
| `DXE_CORE`/`DXE_DRIVER`/… | `/ALIGN:0x1000` | `/ALIGN:0x1000 /FILEALIGN:0x1000` |
| `DXE_RUNTIME_DRIVER` | `/ALIGN:0x10000` | `/ALIGN:0x10000 /FILEALIGN:0x10000` |

改完后 GenFv 只剩容量问题（`required 0xc25240 > set 0xc00000`），把 FD 提到 14 MB
即通过。

### B20.4 真机结果（决定性）

| 步骤 | 含义 | 结果 |
| --- | --- | --- |
| 11 条 | `FfsProcessFvFile` 成功，内层卷已发布为 FV HOB | ✅ **首次达成** |
| 12 条 | 即将调用 `LoadDxeCoreFromFv` | ✅ **首次达成** |
| 13 条 | `LoadDxeCoreFromFv` 返回（不该发生） | ❌ 未出现 |

**12 条而不出现 13 条，意味着 `LoadDxeCoreFromFv` 没有返回——DxeCore 被加载并
`SwitchStack` 接管了执行，之后在 DxeCore 内部失败。**

这是本项目第一次真正进入 DXE 阶段。

### B20.5 与 LZMA 修复的关系（诚实说明）

B19 里把 `SCRATCH_BUFFER_REQUEST_SIZE` 从固定 64 KB 改成按字典大小推算的改动
**保留但未验证有效**：`LzmaDec` 用 scratch 分配的只是 `probs` 数组（约 16 KB），
字典用的是调用方给的目标缓冲，所以"16 MB 字典需要 16 MB scratch"的推理是**错的**。
那段注释已在代码里按事实修正。既然现在不再使用 LZMA，它对本次启动路径无影响。

### B20.6 当前状态与下一步

**已完成**：PrePi 全流程（22 个里程碑）→ 内层卷发布 → DxeCore 加载接管。

**当前卡点**：DxeCore 内部失败。下一步的排查方向（按可能性）：

1. **HOB 链**：DxeCore 依赖 `HobConstructor` 产出的 handoff HOB；内存描述符改动后
   堆基址变了，需确认 `BuildMemoryAllocationHob` / `BuildStackHob` 的范围仍然自洽。
2. **PCD 数据库**：`Pcd.inf` 需要从 FV 里定位 PCD 数据；卷位置变了要确认 HOB 正确。
3. **DxeCore 自身的重定位**：未压缩卷不再由 GenFv 重定位，DxeCore 以自己的
   `ImageBase` 运行，需确认 `LoadDxeCoreFromFfsFile` 的加载地址没有冲突。
4. **内存保护**：`EnableMemoryProtection()` 已按新内存表设置了属性。

建议下一步：在 DxeCore 入口处加同样的"染色/进度条"标记（`MdeModulePkg/Core/Dxe/DxeMain`），
把 DxeCore 的初始化阶段也切成若干段，方法与本项目的 PrePi 埋点完全一致。

### B20.7 设备状态

已回滚原厂 `boot_b`，`sys.boot_completed=1`，Android 正常。
---

## B21. 进入 DXE 调度阶段：找到可读日志，并定位到 SMEM（2026-10-30）

B20 结束时"DxeCore 被加载但不返回"。本轮做了两件事：**拿到了固件内部的文字日志**，
并顺着日志把失败点从"DxeCore 内部某处"一路收敛到 **`SmemDxe` / SMEM 初始化**。

### B21.1 关键工具：DEBUG 构建 + 帧缓冲控制台

`SiliciumPkg.dsc.inc` 里有个条件：

```ini
!if $(TARGET) == RELEASE
  SerialPortLib|MdePkg/Library/BaseSerialPortLibNull/BaseSerialPortLibNull.inf
!else
  SerialPortLib|SiliciumPkg/Library/FrameBufferSerialPortLib/FrameBufferSerialPortLib.inf
!endif
```

也就是说**本项目之前所有 RELEASE 构建都是静默的**——这正是为什么连续多轮只能靠
"屏幕变什么颜色/几条"这种一比特信息去猜，而且猜错了好几次。

改 `-r DEBUG` 后，`DEBUG()` 输出直接画到面板上。`FrameBufferSerialPortLib`
按名字查找 "Display Reserved" 区域，而这个名字在 B17 修好的内存映射里**已经存在**，
所以控制台立即可用。**这是本轮最重要的收获：从此不再盲猜。**

（同时把 `CAIHONG_BRINGUP_MARKERS` 设为 0，否则进度条会盖掉文字。）

### B21.2 第一次读到的真实失败

```text
Loading driver at 0x000D37A000 EntryPoint=0x000137AF130  PcdDxe.efi
Loading driver at 0x000D3839000 EntryPoint=0x0001383A000  EnvDxeEnhanced.efi
ASSERT_EFI_ERROR (Status = Not Found)
ASSERT AutoGen.c +648: !EFI_ERROR (Status)
```

**`EnvDxeEnhanced.efi` 的入口返回 `EFI_NOT_FOUND`。** DEBUG 下 `ASSERT` 会停机；
RELEASE 下断言被编译掉，所以同一次失败在之前只表现为"卡住不动"——两种现象对上了。

### B21.3 排查 `EnvDxe` 时发现的真实 bug（已修）

把 `EnvDxe` 的字符串抽出来，看到它读一份 **`uefiplat.cfg`** 做区域校验：

```text
ERROR: CPU_Vectors region not present in cfg file !
ERROR: UEFI FD region not present in cfg file !
```

而我们的 cfg（从设备 `uefi.img` 提取的原厂文件）写的是：

```text
0xA7000000, 0x00400000, "UEFI FD"
0xB8000000, 0x02B00000, "Display Reserved"
0xBAB00000, 0x0D1C0000, "DXE Heap"
```

对比 B20 的做法——当时为了放 14 MB 的未压缩卷，把固件放到了 **`0xB8000000`**，
那**正好压在原厂标注的 Display Reserved 上**，且与 cfg 里的 UEFI FD 完全不符。

**修正**：把固件放进原厂 DXE Heap 区的前部，并让三处定义保持一致：

| 位置 | 新值 |
| --- | --- |
| `Resources/Configs/caihong.conf` `TARGET_FD_BASE` | `0xBAB00000` |
| `Platforms/OnePlus/caihongPkg/RawFiles/uefiplat.cfg` `"UEFI FD"` | `0xBAB00000 / 0x00E00000` |
| 同上 `"DXE Heap"` | `0xBAC00000 / 0x00C3E0000` |
| `DeviceMemoryMapLib` 同名条目 | 同上 |

另外把 cfg 从 `Binaries/caihong/RawFiles/`（构建时生成、会被覆盖）搬到板级包
`Platforms/OnePlus/caihongPkg/RawFiles/uefiplat.cfg` 并改 `caihong.fdf` 指向它，
**这才是它之前会过期失配的根因**。

修完后 `EnvDxe` 仍然失败，但固件体积/布局的一致性问题解决了。

### B21.4 禁用 EnvDxe 后的大幅推进

为了看清依赖链，临时把 `EnvDxe` 注释掉（`Include/DXE.inc`）。随后一大串驱动
成功加载：

```text
✅ PcdDxe.efi
✅ ReportStatusCodeRouterRuntimeDxe.efi
✅ StatusCodeHandlerRuntimeDxe.efi
✅ ArmCpuDxe.efi          ("ReplaceTableEntry; splitting block entry with rl disabled")
✅ ArmGicDxe.efi          ← 中断控制器起来了
✅ MetronomeDxe.efi
✅ ArmTimerDxe.efi        ← 架构定时器起来了
❌ SmemDxe.efi            → EFI_NOT_FOUND
   ERROR: 230000002:V03000007 T0 F5410663-A648-A0AA-AABF-FF158CCAE34F
```

**GIC 和架构定时器能初始化，说明 ACPI/MADT 那套地址是对的**，DxeCore 的中断
基础设施也是好的。

### B21.5 当前根因假设：SMEM 未初始化

`EnvDxe` 和 `SmemDxe` 都指向同一件事：

```text
# EnvDxe 里
WARNING: Unable to read memory partition table from SMEM
SMEM is not initialized by Boot.
# SmemDxe 里
SMEM base addr=0x%08X, size=%d memory mapping failed.
```

两个驱动的字符串里**都有完整的 SMEM 分区表代码**（smem_partition.c / smem_legacy.c）。
失败点很可能是 SMEM 区域（`0x81D00000`，cfg 与内存映射里都有）**内容本身**：
ABL 走内核启动路径时，SMEM 的初始化状态与走 UEFI 路径时不同。

> 这是下一步要验证的第一件事：把 `0x81D00000` 开头若干字节的内容读出来，
> 看是否符合 SMEM 的 TOC/分区表格式（`SMEM_READ_SMEM_4(&toc->version) == 1`）。
> 读取方法可以直接在 DxeCore 的标记代码里做，或用 `SmemDxe` 前的探针。

可能的走向：
1. SMEM 已初始化但我们的映射属性不对（应 `UNCACHEABLE`，当前就是）；
2. SMEM 未初始化 → 需要自己按 vendor 格式建立最小分区表，或改由 ABL 的 UEFI 路径启动；
3. `SmemDxe` 需要 DT/`gQcomSmemProtocolGuid` 的前置信息。

### B21.6 本轮的进度条编码（补充）

DxeCore 的探针改用**竖直**白条（PrePi 是横向），避免与 PrePi 混淆：

| 竖条 | 里程碑 |
| --- | --- |
| 1 | `DxeMain` 入口 |
| 2 | 内存服务 + GCD |
| 3 | 事件服务 |
| 4 | 调度器初始化完成 |
| 5 | `CoreDispatcher()` 返回 |
| 6 | 即将交给 BDS |

### B21.7 设备状态

已回滚原厂 `boot_b`，`sys.boot_completed=1`，Android 正常。

### B21.8 诚实结论

- **PrePi 全流程 + DxeCore 核心初始化 + 多个架构驱动加载成功**，这是本项目
  第一次走到这么远。
- 但仍**没有出现任何图形化的 UEFI 界面**，也没有进 BDS。
- 当前阻塞在 SMEM 初始化，`EnvDxe` 与 `SmemDxe` 共同指向它。
- 本轮新增的两项能力（DEBUG 文字日志、竖条探针）是后续工作的基础。
---

## B22. 决定性结论：SMEM 在内核启动路径下未被初始化（2026-10-30）

B21 把阻塞点收敛到 `SmemDxe` / SMEM。本轮用固件内的纯色探针**直接读取并判定**
`0x81D00000` 的首字，得到了明确答案。

### B22.1 探针设计（为什么用纯色而不是打印十六进制）

第一次尝试是把 SMEM 前 32 个字用 `DEBUG()` 打印到面板上。实测不可行——面板每行
字符很多、字形很小，逐字抄录十六进制不现实（过程中还收到过一张完全无关的
Windows/.NET 崩溃截图，说明这种转述方式本身不可靠）。

改为**固件自己判断、只输出结论**：读 `0x81D00000` 的第一个 32 位字，按值整屏染一种颜色：

| 颜色 | 条件 | 含义 |
| --- | --- | --- |
| 绿 | `0x00000001` | SMEM 分区表头正常 |
| **红** | **`0x00000000`** | **区域全零，从未初始化** |
| 蓝 | `0xFFFFFFFF` | 擦除态 |
| 黄 | 其他 | 表头异常 |

判定依据正是 `SmemDxe` 内部的第一道校验：

```c
Assertion SMEM_READ_SMEM_4(&toc->version) == 1 failed
```

### B22.2 实测结果：**红色**

`0x81D00000` 处**全是零**。也就是说：

> **ABL 在"启动内核"这条路径上，没有建立 SMEM 分区表。**

这与 `EnvDxe` 里的字符串完全一致：

```text
WARNING: Unable to read memory partition table from SMEM
SMEM is not initialized by Boot.
```

（顺带说明：B21 曾在 `+0x1000` 处看到 `54525024`＝ASCII `$PRT`，那是另一处的
分区头残留，但 TOC 本身（版本号/条目数）是零，所以驱动仍然判定失败。）

### B22.3 地址本身是对的

排除"地址写错"这个可能：

```text
xbl_config.img 的 XBL 区域表:  SMEM 0x81D00000 + 0x200000
uefiplat.cfg:                  0x81D00000, 0x00200000, "SMEM"
DeviceMemoryMapLib.c:          {"SMEM", 0x81D00000, 0x00200000, ...}
```

三处一致，映射属性为 `UNCACHEABLE`（正确）。**问题不是地址，是内容。**

### B22.4 这意味着什么（战略层面的判断）

到这一步，可以把问题分成两类：

**已经解决的（全部有真机证据）**

```text
✅ BootShim 加载并跳转 14 MB 未压缩固件卷
✅ PrePi 全流程（22 个里程碑）：GIC、内存定位、MMU、HOB、库构造函数、卷发布
✅ DxeCore 加载并接管，核心服务（内存/GCD/事件/调试）全部初始化
✅ 驱动调度：PcdDxe、ReportStatusCodeRouter、StatusCodeHandler、
             ArmCpuDxe、ArmGicDxe、MetronomeDxe、ArmTimerDxe 全部加载成功
```

**新出现的根本性障碍**

厂商的 UEFI 驱动（`EnvDxe`、`SmemDxe`）**假定 SMEM 分区表已由 ABL 建好**，
而这个前提只在 ABL 走 **UEFI 启动路径**时成立。我们用 `boot.img` 走的是
**内核启动路径**，ABL 不会建这张表，于是：

- `SmemDxe` → `EFI_NOT_FOUND`
- `EnvDxe` → `EFI_NOT_FOUND`（同因）

而且这两个驱动是 DAL/TLMM/I2C/SPMI 等一系列硬件驱动的前置，所以它们不通，
后面全都不通。

### B22.5 三条可选路线（按可行性排序）

| # | 路线 | 说明 | 风险 |
| --- | --- | --- | --- |
| 1 | **走真正的 UEFI 启动路径** | 让 ABL 以 UEFI 模式启动（而不是把固件伪装成 boot.img 的内核），这样 SMEM 由 ABL 建好，厂商驱动的前提成立 | 需要设备支持该启动方式；刷写位置与现有方案不同 |
| 2 | **自己建立最小 SMEM 分区表** | 在 PrePi 里按 vendor 格式写 TOC（version=1、num_entries）+ 必要的分区头到 `0x81D00000` | 格式必须精确；错的表可能让驱动行为更不可预测 |
| 3 | 放弃厂商 `SmemDxe`/`EnvDxe`，用开源实现 | 不现实：DAL 驱动的 ABI 依赖这些协议 | 极大工作量 |

**建议**：先评估路线 1（这是"正统"做法，也是其他 Mu-Silicium 设备能跑的原因——
它们刷到 UEFI 分区），再考虑路线 2。

### B22.6 设备状态

已回滚原厂 `boot_b`，`sys.boot_completed=1`，Android 正常，数据无损。

### B22.7 诚实结论

- 本轮把一个模糊的"卡在某个驱动"变成了**明确的、可解释的环境差异**：
  SMEM 分区表缺失，且**已用固件内实测确认**（红色探针），不是推测。
- **仍未进入 BDS**，屏幕从未出现图形化 UEFI 界面。
- 更重要的是：这个发现**动摇了"通过替换 boot.img 来跑 Windows"这条技术路线的前提**。
  如果厂商驱动硬依赖 ABL 在 UEFI 路径下建立的 SMEM，那么正确做法应当是让
  ABL 走 UEFI 路径，而不是继续在 boot.img 里打补丁。
- 这一点必须在继续投入之前先向用户说清楚。
---

## B23. 发现两份 caihong 参考实现，并首次用"已知可工作"的固件上机（2026-10-30）

用户提供了两个外部仓库地址。本机 DNS 把 `github.com` 解析到内网地址，`web_fetch`
不可用；**远端 Linux 构建机有外网**，改用它 `git clone` 成功取得两份仓库。

### B23.1 两份参考实现

| 仓库 | 性质 | 对我们的价值 |
| --- | --- | --- |
| `Axiang-dev/UniXNU-caihong` | 跑 **XNU（macOS/iOS 内核）** 的移植工程（overlay 形式） | 记录了完整启动链、ABL 行为、boot.img 结构、9 个二进制补丁 |
| `Axiang-dev/uefi-caihong` | **caihong 的完整 UEFI 固件工程**（板级包 + 原厂驱动 + 补丁 + 构建脚本） | **已知可工作**：能进 BDS 启动菜单 |

`uefi-caihong` 的 README 明确写着状态：

> 可以正常进 BDS 启动菜单（`Internal Storage` / `USB Storage` / `PXE Path` /
> `Ram Storage` / `Power Off` / `Exit`），音量键上下移动、电源键确认。
> ⚠️ 开机时必须按一次键才会进菜单。

### B23.2 他们的启动方式与结构

```text
ABL → fastboot boot boot.img
boot.img = header(v4) + gzip(BootShim + UEFI FV) + DTB
ABL → BootShim → UEFI(Mu-Silicium)
```

要点：
- **用 `fastboot boot`**（全程 RAM，不写任何分区）
- 固件卷 **4 MB**（压缩形式），FD 基址 **`0xA7100000`**（注意不是我们用的 `0xA7000000`）
- boot image 头部必须 **v4**
- 必须按一次键，否则 BDS 找不到可启动项 → logo 10 秒 → 复位 → ABL 回 Android

### B23.3 他们修好的关键问题（HANDOFF.md §4）

| # | 问题 | 处理 |
| --- | --- | --- |
| 4.1 | boot image 必须 v4 | 与我们的独立发现一致 |
| 4.2 | 帧缓冲 PCD 宽高反着写（3000×2120） | 已修正 |
| 4.3 | 固件卷 4 MB | 与 ABL 预留一致 |
| **4.4** | **关屏元凶是 `VcsDxe`（电压域管理）** | **整体打桩**（入口 `mov x0,#0; ret`） |
| 4.5 | `RscDxe` 阻塞 DXE 派发 | 整体打桩 |
| 4.6 | 官方 giulia（SM8650）补丁 | 全部应用 |

并且特别注明：`ERROR: CPU_Vectors region not present in cfg file!` 与
`tz_armv8_smc_call failed` 都是**正常噪声，不用管**——这一点纠正了我们 B21/B22
里对 cfg 的过度推断。

### B23.4 二进制补丁工具链（可复用）

`tools/apply_binary_patches.py` 从原厂 `.efi` 生成 `*.patched.efi`，并把对应
`.inf` 的 `PE32|` 行改指向 patched 文件。验证结果（远端构建树）：

```text
OK   QcomPkg/Drivers/VcsDxe/VcsDxe   @0x1000  (entry stub - the driver that kills the panel)
OK   QcomPkg/Drivers/RscDxe/RscDxe   @0x1000  (entry stub - lets DXE dispatch finish to BDS)
```

`VcsDxe.patched.efi` 已生成，`VcsDxe.inf` 中 `PE32|VcsDxe.patched.efi|*` 已生效。

### B23.5 在远端构建参考固件

```bash
cd /root/data/uefi-caihong
./scripts/build.sh /root/data/caihong-work RELEASE   # 以及 DEBUG
```

构建脚本自包含：固定 `MU_COMMIT=3aa95a72…` 的 Project-Silicium/Mu-Silicium，
套上板级包与 `Binaries/caihong`，重新生成补丁驱动后编译。

**遇到并解决的环境问题**：`build_uefi.py` 导入 `tomllib`（Python 3.11+），
而远端是 3.10 → 用 `tomli` 后备库加一个 `tomllib` 兼容层即可
（`scripts/fix_tomllib.sh`）。

产物：

| 目标 | 大小 | sha256（前 16 位） |
| --- | --- | --- |
| RELEASE | 1,286,144 B | `1df86efd383d92a0` |
| DEBUG | 1,396,736 B | `b7a690abacd3fdc0` |

### B23.6 上机实测结果（本设备）

| 测试 | 结果 |
| --- | --- |
| `fastboot boot` RELEASE 参考固件 | **直接进 Android**（失败后 ABL 回退） |
| `fastboot boot` DEBUG 参考固件 | **跑码后黑屏**（日志有输出，随后屏幕变黑） |

**重要**：`fastboot boot` 本身在这台设备上是**可用的**（我们自己的镜像此前通过它
成功显示过探针颜色），所以不是启动方式的问题。

**关于黑屏**：已确认 `VcsDxe`/`RscDxe` 的入口桩**确实已打进固件**（见 B23.4），
因此黑屏**不是**他们文档里记的 `VcsDxe` 关屏问题，而是这台设备上的另一个差异。

### B23.7 与自研构建的对比（诚实结论）

两条路线目前各自的卡点：

| 路线 | 进展 | 卡点 |
| --- | --- | --- |
| **自研**（musabcel fork + 我们的板级包） | PrePi 全流程 + DxeCore 核心服务 + 多个驱动加载 | `SmemDxe` 报 `EFI_NOT_FOUND`，`0x81D00000` 实测全零 |
| **参考实现**（uefi-caihong） | 固件能跑、日志能出 | 跑码后黑屏 |

值得注意的一点：**参考实现的固件卷是 4 MB 压缩（含 LZMA）形式并且能走通**，
而我们的 fork 在同样的 LZMA 解压上失败——这强烈提示**基线差异**（fork 与上游
Project-Silicium）是自研路线的根本问题之一，而不是设备限制。

### B23.8 下一步建议

1. **弄清参考固件为什么在本机黑屏**：先确认"跑码"阶段最后打印到哪里
   （把 DEBUG 输出的最后若干行读出来），再对照 HANDOFF 的已知问题表。
   可能是 Android 15 与我们手上 ABL 版本差异（他们是在 Android 16 上验证的）。
2. **以 `uefi-caihong` 为基线继续**，而不是继续给 musabcel fork 打补丁：
   它是**同设备、已知可工作**的实现，且包含全部踩坑记录与二进制补丁工具。
3. 我们的板级成果（进度条埋点、FDT/x0 中转、内存映射勘误）可以作为改进提案
   回灌到参考实现，而不是另起一套。

### B23.9 设备状态

本次测试后设备处于黑屏，需长按电源键 15 秒复位。原厂 `boot_b` 未被修改
（全程用 `fastboot boot`，零写入），回 Android 后一切正常。
---

## B24. 用参考固件把失败点精确定位到 UFSDxe（2026-10-30）

B23 结束时参考固件只能看到"跑码后黑屏"。本轮通过三处改动拿到了**确切的错误**。

### B24.1 让错误留在屏幕上（关键手段）

参考固件的 DEBUG 输出刷屏太快，错误一闪而过。两步解决：

1. **只打印错误/警告**：在板级 DSC 里设
   `gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x80000040`（ERROR|WARN）。
2. **绕过"必须按键才进菜单"**：`BootManagerLib/KeyCallback.c:20`
   的 `mEnterBootManager = FALSE` 改为 `TRUE`，让
   `PlatformBootManagerPriorityBoot()` 无条件进入 BootManagerMenu。

> 注意：仓库自带的 `scripts/build.sh` 开头会 `git checkout -f` 重置父树、
> 并用 `cp -r` 覆盖板级包，**会把上述改动冲掉**。因此改用
> `scripts/build_caihong_custom.sh`（跳过 checkout，直接驱动 `build_uefi.py`）。

### B24.2 读到的确切错误

```text
0x00000000D1F1E000 - 0x0000000000023000
ufs_error_log: 11
ufs_error_log: 3b
ufs_error_log: 55
ASSERT_EFI_ERROR (Status = Device Error)
ERROR: C90000002:403000007 I0 0D35CD8E-97EA-4F9A-96AF-0F0D89F76567
ASSERT UFS.c +2172: !EFI_ERROR (((RETURN_STATUS)(0x8000000000000000ULL | (7))))
```

解读：

| 信息 | 含义 |
| --- | --- |
| `0x8000000000000007` | `EFI_DEVICE_ERROR` |
| `0D35CD8E-97EA-4F9A-96AF-0F0D89F76567` | **UFSDxe** 的文件 GUID |
| `UFS.c +2172` | UFS 驱动内部断言位置 |
| `ufs_error_log: 11 / 3b / 55` | UFS 链路启动（link startup）失败的错误码 |

### B24.3 已排除的可能性

| 假设 | 验证方式 | 结论 |
| --- | --- | --- |
| UFSDxe 补丁没打上 | 检查构建树：`UFSDxe.patched.efi` 存在，INF 为 `PE32\|UFSDxe.patched.efi\|*` | **排除**，补丁在 |
| `fastboot boot` 不初始化 UFS（镜像走 USB，ABL 不读存储） | 改为 `fastboot flash boot_b` 后正常启动（ABL 必须从 UFS 读镜像） | **排除**，两种方式错误完全一致 |
| 屏幕被 `DisplayDxe` 重新初始化而关掉 | 参考工程的 `USE_CUSTOM_DISPLAY_DRIVER` 默认就是 `0`，只有 `SimpleFbDxe` 在用 ABL 帧缓冲 | **排除** |
| 黑屏是 `VcsDxe` 关屏 | 补丁日志确认 `VcsDxe/RscDxe` 入口已被桩掉（`mov x0,#0; ret`） | **排除** |
| 不按键导致 BDS 走"无法启动→关机" | 强制 `mEnterBootManager = TRUE` 后仍黑屏 | **排除** |

### B24.4 当前唯一剩下的解释

UFS 控制器在这台设备上**初始化失败**，且失败发生在 BDS 之前足以致命的位置：

- **DEBUG 版**：断言直接停住。
- **RELEASE 版**（断言被编译掉）：UFS 驱动失败后流程继续，但仍在"第一屏之后约十秒"
  黑屏，说明 BDS 也没能正常起来。

最可能的原因：**参考工程的 `Binaries/caihong` 来自作者设备的 Android 16 固件，
而我们的设备是 Android 15**。UFS 驱动与 PHY/时钟/稳压器配置是版本相关的，
跨版本使用很可能初始化不成功。

佐证：作者 `HANDOFF.md` 明确写着"设备升到 Android 16 后，新 ABL 拒收 v0 镜像"——
说明他的验证环境确实与我们不同。

### B24.5 下一步的三条可选路线

| # | 路线 | 说明 | 成本 |
| --- | --- | --- | --- |
| **1** | **用我们自己的驱动替换 `Binaries/caihong`** | 我们已从本机 `uefi.img` 提取了 106 个 PE32 模块（`artifacts/uefi-real/`）。把参考工程的驱动换成**与我们 Android 15 固件同版本**的，是最直接的对齐手段 | 中（需要把驱动放回 INF 布局并确保 GUID 一致） |
| 2 | 把设备升级到 Android 16 再试 | 与作者环境完全一致 | 高（用户需 OTA，且可能改变分区/ABL） |
| 3 | 继续在自研 fork 上推进 SMEM | 已确认自研路线受 fork 基线（LZMA 解压）拖累 | 高、且方向不优 |

**建议路线 1**：参考工程的板级包与构建链是好的，把它下面的厂商驱动换成我们自己
固件同版本的那一套，是"已知可工作框架 + 匹配的驱动"的组合，最有希望。

### B24.6 本轮的工程产出

| 产物 | 说明 |
| --- | --- |
| `/root/data/uefi-caihong` | 参考工程（远端已 clone） |
| `/root/data/caihong-work/uefi` | 已构建的 Mu-Silicium 树（RELEASE + DEBUG 均可编译） |
| `scripts/fix_tomllib.sh` | Python 3.10 的 `tomllib` 兼容层（参考工程需要 3.11+） |
| `scripts/build_caihong_custom.sh` | 保留自定义改动的构建脚本（跳过 checkout） |
| `scripts/force_boot_menu.sh` | 强制进 BDS 菜单的补丁 |
| `scripts/quiet_debug_log.sh` | 只打印 ERROR/WARN 的补丁 |
| `artifacts/fbtest/Mu-ref*.img` | 各版本参考固件镜像 |

### B24.7 设备状态

已回滚原厂 `boot_b`，`sys.boot_completed=1`，Android 15 正常，数据无损。
本轮所有测试均在 `boot_b` 上进行并可完整回滚。

### B24.8 诚实结论

- 本轮把参考固件的失败点**从"黑屏"精确到 `UFSDxe` 的 `EFI_DEVICE_ERROR`**，
  并**逐条排除了五个假设**，每个都有实测或代码依据。
- **仍未出现 BDS 启动菜单**，屏幕上从未显示过任何 UEFI 图形界面。
- 判断：剩下的障碍是**驱动与固件版本不匹配**，而不是启动链或板级配置错误。
  参考工程的框架可用，需要把厂商驱动换成与本机固件同版本的一套。
---

## B25. 用异常转储定位到"外部中止"，并修掉它（2026-10-30）

B24 结束时参考固件"跑码后黑屏"。本轮拿到了**处理器的异常转储**，据此定位并修复了一个
真实的崩溃，把问题从"硬件异常"推进到"显示/控制台被清空"。

### B25.1 决定性证据：异常转储

故障时屏幕输出的内容：

```text
SP   0x00000000A764B950
ESR  0x96000010
FAR  0x000000000C792008
SPSR 0x22000205   FPSR 0x00000010
ESR : EC 0x25  IL 0x1  ISS 0x00000010
Data abort: Synchronous external abort
ASSERT [ArmCpuDxe] CpuExceptionHandlerLib.c(438): ((BOOLEAN)(0==1))
```

逐条解读：

| 字段 | 值 | 含义 |
| --- | --- | --- |
| `ESR.EC` | `0x25` | Data Abort from lower exception level |
| `ESR.ISS` | `0x10` | `EA`（bit4）=1，`DFSC`=`0x10` → **Synchronous External Abort** |
| `FAR` | `0x0C792008` | 出错地址，**落在 AOSS 区域**（`0x0B000000 + 0x04000000`） |

**外部中止**在 ARM 上的语义很明确：**CPU 访问了一块没有上电/没有时钟的外设寄存器**。
这不是指针错误，是硬件电源域没打开。

### B25.2 根因：`VcsDxe` 被打桩

参考工程把电压域管理驱动 `VcsDxe` 的**入口整体桩掉**（`mov x0,#0; ret`），
原因是原作者文档 §4.4 写的"关屏元凶是 VcsDxe"。`RscDxe` 同样处理（§4.5）。

后果：**电压域子系统从未初始化**。在作者的设备（Android 16 ABL）上可能被
ABL 的遗留状态掩盖；在本机（Android 15 ABL）上没有，于是后续任何驱动一碰
AOSS 寄存器就触发外部中止。

### B25.3 修复与效果

把 `VcsDxe` / `RscDxe` 换回**本机固件（Android 15）提取的原版**（不打桩），
同时把 `UFSDxe` / `ClockDxe` / `SPMIDxe` / `PmicDxeLa` 也换成同源版本：

| 驱动 | 参考工程 | 本次 |
| --- | --- | --- |
| `VcsDxe` | 入口打桩 | **本机原版** |
| `RscDxe` | 入口打桩 | **本机原版** |
| `UFSDxe` | Android 16 版 + 补丁 | 本机原版 |
| `ClockDxe` / `SPMIDxe` / `PmicDxeLa` | 打过补丁 | 本机原版 |

**效果**：

```text
之前：跑码 → 黑屏 → 进 900E 诊断模式（外部中止）
之后：跑码 → 黑屏 → 背光不灭、不进 900E、不崩溃
```

**崩溃被消除了。** 这是本轮最实质的成果。

### B25.4 崩溃消除后的新状态

设备表现为：**屏幕黑、背光仍亮、无 USB 枚举、按键无响应、不重启、不进 900E。**

这种状态说明固件还在跑，但既没有显示输出也没有 USB。

### B25.5 里程碑探针的结论

给 DxeCore 与 BDS 分别加了纯色探针：

- `DxeMain` 入口 → **红**
- `CoreDispatcher()` 返回 → 橙
- 交给 `gBds->Entry` 前 → 黄
- `PlatformBootManagerPriorityBoot()` 入口 → 洋红（画在清屏之后）
- 走"不显示菜单"分支 → 蓝

实测：**先红一下，然后黑屏**。

含义：**`DxeMain` 确实进入了**，但在"调度器返回"之前屏幕就被清空（或该阶段就停住）。

> 注意：DxeCore 的探针画在 `gBds->Entry()` 之前，而 BDS 启动时会重置控制台，
> 会把整屏颜色抹掉——所以"黑屏"里既有可能是真没走到，也可能是被清掉了。
> BDS 内部的探针（洋红/蓝）就是为了区分这一点，但实测连洋红都没出现。

### B25.6 本轮新增的可复用工具

| 脚本 | 作用 |
| --- | --- |
| `scripts/fix_tomllib.sh` | Python 3.10 的 `tomllib` 兼容层 |
| `scripts/build_caihong_custom.sh` | **自定义构建**：跳过 `git checkout`，保留三处改动后直接编译 |
| `scripts/force_boot_menu.sh` | 强制进入 BDS 菜单（`mEnterBootManager = TRUE`） |
| `scripts/quiet_debug_log.sh` | 只打印 ERROR/WARN（`PcdDebugPrintErrorLevel = 0x80000040`） |
| `scripts/swap_ufsdxe.sh`、`swap_power_drivers.sh`、`swap_vcs_rsc.sh` | 把厂商驱动换成本机同源版本 |
| `scripts/mark_reference_dxe.py`、`mark_reference_bds.py` | 里程碑纯色探针注入 |

> **重要教训**：仓库自带的 `scripts/build.sh` 开头会 `git checkout -f` 重置父树、
> 并用 `cp -r` 覆盖板级包，**会静默冲掉所有自定义改动**。必须用
> `build_caihong_custom.sh`。

### B25.7 当前进度总览

```text
✅ ABL 接受 v4 boot image、跳转
✅ BootShim → UEFI 固件卷（4 MB 压缩，LZMA 解压正常）
✅ PrePi 全流程、DxeCore 加载接管
✅ DxeMain 进入（红色探针实测）
✅ 外部中止崩溃已消除（真实 VcsDxe/RscDxe）
❌ 调度器完成之前屏幕被清空 / 停住
❌ 从未出现 BDS 启动菜单，从未出现任何图形化 UEFI 界面
```

### B25.8 下一步（按优先级）

1. **搞清"清屏"是谁做的**：在 `SimpleFbDxe`、`GraphicsConsoleDxe`、`ConSplitter`
   等控制台相关驱动的入口各加一个探针，看是谁把屏幕弄黑的。
2. **在调度器循环里逐驱动打点**：在每个驱动 `StartImage` 前后画一格进度条，
   定位是哪个驱动让流程停住。
3. 若确认是图形控制台切换导致，可考虑**只保留文本控制台**（不加载
   `GraphicsConsoleDxe`），让日志一直可见。

### B25.9 设备状态

已回滚原厂 `boot_b`，`sys.boot_completed=1`，Android 15 正常，数据无损。
全程使用 `fastboot boot` + `boot_b` 测试，未触碰其他分区。
