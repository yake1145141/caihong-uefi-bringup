# 上游资料与设备材料审计（source-audit）

| 项 | 值 |
|---|---|
| 审计对象 | 支撑「caihong 上运行 Windows on ARM」的全部外部来源 |
| 审计时间 | 2026-10-29（本次会话） |
| 审计方式 | 实际 `git clone` + 目录/文件读取 + 内容检索；未使用二手描述 |
| 工作目录 | `E:\caihong-windows` |
| 结论强度 | 见下方"抓取状态"定义；**未抓取的一律标"未验证"，不作依据** |

## 0. 摘要（先给结论）

1. **`WOA-Project/windows_silicon_qcom_lanai` 是空壳**：它是目前唯一自称"SM8650 Windows BSP"的公开仓库，但仓库内**只有 7 个文件、总计 49,477 字节**，没有驱动、没有源码。→ **SM8650 的 Windows BSP 在公开渠道不存在可用实现。**（§3，本文最重要结论）
2. **`musabcel/Mu-Qcom` 是当前最好的移植基线**：更新到 2025-08-19，含 SM8550（KailuaPkg）与 SM8750（PakalaPkg）SoC 包，submodule 全部到位，并自带 `iasl.exe`。但它**没有 SM8650**（§2.5）。
3. **`liliumbeta/Mu-Qcom` 已过时**：最后提交 2024-02-07，SoC 最高到 SM8450，且 `Silicium-ACPI` 目录为空（§2.4）。
4. **`Osilvfe/caihong-linux-rootfs` 不是内核源码**：它是 Linux/Arch 的构建脚本与发行物仓库，但**它证实了这块屏/触控/网络在 Linux 侧可用**，因而其 `dependencies.env` 指向了真正的内核 fork（§2.1、§5）。
5. **内核 fork 的 DTS 内容本次未取得**：克隆是 `blob:none` 部分克隆，本地无 blob；尝试从 GitHub 拉取时遭 HTTP 429，`work/sm8650-oneplus-caihong.dts` 实际是**错误页**（313 B），不是 DTS（§2.2）。

---

## 1. 审计方法与可重复性

### 1.1 抓取状态定义

| 状态 | 含义 |
|---|---|
| **已克隆** | `git clone` 成功，工作树在 `source/` 下，可读文件 |
| **已读取** | 具体文件内容被打开并引用 |
| **仅列表** | 只拿到了目录/文件名与大小（`ls-tree`、目录列举），内容未读 |
| **未验证** | 未抓取，只是会话中被提及 |

### 1.2 本次实际执行的命令（可复现）

```powershell
# 仓库
git -C source\<repo> log -1 --format='%H|%ad|%s' --date=short
git -C source\<repo> rev-parse --abbrev-ref HEAD
git -C source\linux-caihong config --get remote.origin.promisor   # -> true
git -C source\linux-caihong config --get remote.origin.partialclonefilter  # -> blob:none
git -C source\linux-caihong ls-tree -r --name-only HEAD | Select-String sm8650|caihong
# 固件
python scripts\extract_dtb.py --src E:\1+padpro\oxygenos --out work\dt
python scripts\extract_dtb.py --src <backup>\images --out work\dt_bak
# ACPI
python scripts\build_soc_acpi.py --kailua source\Mu-Qcom-musabcel\Silicium-ACPI\SoCs\Qualcomm\Kailua --out build\acpi
source\Mu-Qcom-musabcel\Silicium-ACPI\Compiler\iasl.exe acpi\caihong\DSDT.dsl
```

### 1.3 审计局限（诚实声明）

- 内核 fork 的 blob 不在本地，**DTS/defconfig 内容未核实**（只有路径存在性）。
- 未抓取 Renegade Project 网页、openwall 邮件列表（见 §9）。
- 未在真机上做过任何验证（无设备连接、未运行 fastboot/adb）。

---

## 2. 仓库逐项审计

### 2.1 `Osilvfe/caihong-linux-rootfs`

| 项 | 值 |
|---|---|
| URL | `https://github.com/Osilvfe/caihong-linux-rootfs` |
| 本地路径 | `source/caihong-linux-rootfs` |
| 分支 / commit | `main` / `4685dc8da324d1ca99c44177e8bc5922a1de9ca2` |
| 提交日期 / 标题 | 2026-10-27 / "rootfs: identify libcamera build artifacts" |
| 抓取状态 | **已克隆 + 已读取**（README、LICENSE、dependencies.env、目录树） |
| 许可证 | 仓库 `LICENSE` 实为内核 `COPYING` 文本（`GPL-2.0 WITH Linux-syscall-note`）。README §Licensing 明确：**项目自撰的构建脚本与工具为 `GPL-2.0-only`**；捆绑的设备固件仍受**厂商条款**约束；Armada 项目代码 `GPL-2.0-or-later`；Steam Client 为专有软件 |

**目录结构关键发现**

| 路径 | 内容 |
|---|---|
| `README.md` / `README.zh-CN.md` | **设备状态表**（见下）+ 完整安装步骤 |
| `config/dependencies.env` | 真正的内核/组件来源（§5） |
| `config/armada.env`、`caihong-direct-root-*.txt` | Armada 变体与 cmdline |
| `.github/workflows/` | `ci.yml`、`kernel-package.yml`、`release.yml`（ARM64 runner 构建） |
| `external/audioreach-topology/` | ALSA 拓扑，**含 `SM8650-Caihong.m4`（5,868 B）** |
| 无 `arch/`、无 `drivers/` | **确认：这不是内核源码仓库** |

**README 自称的 Linux 侧状态（上游声明，本会话未验证）**

- **Working**：触控与笔（10 点/悬停/压感/磁吸充电）、蓝牙、音频、USB + DP Alt Mode、CPU 调频与 s2idle/深睡、NPU（Hexagon v75/QNN）与 VPU 解码、UFS（**MCQ 开启，9 个硬件队列，最大深度 64**）。
- **Mostly working**：显示/GPU（3000×2120、Adreno、亮度；60/72/96/120 Hz 无缝，**144 Hz 需黑屏模式切换**，偶有轻微花屏）；Pogo 键盘（顶排映射 F1–F12，Search 作 Fn，按键会短暂打断触控板）；Wi-Fi（STA/AP 并发，但 **BDF 是兼容条目而非本机校准**）；摄像头（走 SM8650 ICP/BPS 硬件 ISP，前 3264×2448 / 后 4208×3120，约 24 fps）；电池与 PPS/VOOC 快充。
- 注意：**3.3024 GHz 加速默认关闭**。

**三栏结论**

| 可用于本项目 | 仅作参考 | 不可复用 |
|---|---|---|
| ① 设备能力的**存在性证明**（屏/触控/Wi-Fi/音频在该硬件上确实可驱动）；② 安装流程中的 fastboot 序列（`--disable-verity --disable-verification flash vbmeta`、`erase dtbo_<slot>`、`flash boot_<slot>`、`set-active`）对理解引导链与槽位模型有直接价值；③ `SM8650-Caihong.m4` 可作为音频硬件连接的旁证 | 面板/触控/传感器型号与拓扑；Linux 侧驱动命名（用于交叉核对 ACPI 该暴露什么）；构建/发布流程 | 全部代码：它是 **Linux/Arch rootfs 与内核打包**，与 EDK2/Windows 无共用路径；GPL-2.0-only 的脚本不能直接并入 BSD-2-Clause 的 UEFI 代码库 |

---

### 2.2 `Osilvfe/linux`（真正的内核 fork）

| 项 | 值 |
|---|---|
| URL | `https://github.com/Osilvfe/linux.git`（由 `dependencies.env` 指定） |
| 本地路径 | `source/linux-caihong` |
| 分支 / commit | `caihong-v7.3` / `4df9a88062ebcac3e1fd5052253f7500f7f70d30` |
| 提交日期 / 标题 | 2026-10-28 / "power: supply: sc8547: fix VOOC recovery and current negotiation" |
| 抓取状态 | **已克隆（部分克隆）**；`remote.origin.promisor=true`、`partialclonefilter=blob:none`、`.git/shallow` 存在 → **浅克隆 + 无 blob** |
| 许可证 | 内核 `COPYING`（GPL-2.0） |

**关键发现：克隆方式导致内容不可读**

- `core.sparseCheckout=true`，工作树只物化了顶层文件（`Makefile`、`COPYING` 等），**没有 `arch/`、`drivers/` 目录**。
- 但 `git ls-tree -r HEAD` 能列出完整树：**34 个 `sm8650` 路径**、**12 个 `caihong` 路径**。
- 对具体 blob 执行 `git cat-file` → `could not get object info`（本地无 blob）；触发懒加载时命令挂起超过 120 s 被中止。
- **旁证**：`work/sm8650-oneplus-caihong.dts`（313 B）内容是 GitHub **HTTP 429 限流页**：
  ```
  429: This request was rate-limited due to too many requests from your network...
  ```
  → **该 DTS 的正文在本会话中从未成功取得。**

**树内与 caihong 相关的文件（仅路径已证实）**

| 路径 |
|---|
| `arch/arm64/boot/dts/qcom/sm8650-oneplus-caihong.dts` |
| `arch/arm64/configs/caihong_defconfig` |
| `Documentation/devicetree/bindings/input/oneplus,caihong-pogo.yaml` |
| `Documentation/devicetree/bindings/power/supply/oneplus,caihong-battmgr.yaml` |
| `drivers/media/i2c/sc1320cs-caihong-regs.h`、`sc820cs-caihong-regs.h` |
| `drivers/power/supply/caihong_pen_power.c`、`qcom_battmgr_caihong*.{h,inc}` |
| `include/linux/power/qcom_battmgr_caihong.h` |

**树内 SM8650 支持（说明 fork = mainline + caihong 板级支持）**

`drivers/clk/qcom/{gcc,gpucc,camcc,tcsrcc}-sm8650.c`、`drivers/pinctrl/qcom/pinctrl-sm8650{,-lpass-lpi}.c`、`drivers/gpu/drm/msm/disp/dpu1/catalog/dpu_10_0_sm8650.h`、`drivers/media/platform/qcom/iris/iris_platform_sm8650.h`、`drivers/interconnect/qcom/sm8650.c`、`arch/arm64/boot/dts/qcom/sm8650.dtsi` + `sm8650-{mtp,qrd,hdk,ayaneo-pocket-s2}.dts`。

**三栏结论**

| 可用于本项目 | 仅作参考 | 不可复用 |
|---|---|---|
| ① **DT 事实的对照源**（我们已用 mainline `sm8650.dtsi` 做地址交叉验证）；② `caihong_defconfig` 与 DTS 的文件名/存在性，证明社区已有完整的 Linux 板级移植，可作为"硬件已被摸清"的证据；③ `qcom_battmgr_caihong*`、`caihong_pen_power` 等表明电池/笔的硬件接口已被逆向，对将来写 Windows 侧 ACPI 有参考价值 | Linux 驱动实现细节、电源域/时钟树命名、pogo 键盘的 GPIO 映射 | 内核代码整体（GPL-2.0），且**当前本地无 blob，连内容都取不到**；不能作为 Windows 侧的代码来源 |

---

### 2.3 ★ `WOA-Project/windows_silicon_qcom_lanai`（空壳，重点）

| 项 | 值 |
|---|---|
| URL | `https://github.com/WOA-Project/windows_silicon_qcom_lanai` |
| 本地路径 | `source/lanai` |
| 分支 / commit | `main` / `23a81f220c1df3076696344dce88fb4f4bceadcb` |
| 提交日期 / 标题 | 2024-11-10 / "Update README.md" |
| 抓取状态 | **已克隆 + 已完整读取**（全部 7 个文件） |
| 许可证 | `LICENSE.md`：Copyright (c) 2017-2024 The DuoWoA authors / 2011-2024 Qualcomm / 2019-2024 Microsoft；正文说明仓库包含来自 Snapdragon 8cx 笔记本/平板与 Surface Duo 固件的二进制，**受相应条款约束** |

**完整文件清单（这就是全部内容）**

| 文件 | 字节 | 实际内容 |
|---|---|---|
| `README.md` | 1,806 | 自称 "Windows on Snapdragon 8 Gen 3 Board Support Package"；支持 QRD |
| `LICENSE.md` | 3,088 | 二进制/固件条款 |
| `CODE_OF_CONDUCT.md` | 5,377 | 行为准则 |
| `docs/NTDBG.md` | 1,627 | **SM8650 上调试 Windows 的步骤**：`bcdedit /dbgsettings NET ...`、`bp ACPI!DriverEntry`、`!amli set verboseon spewon traceon` |
| `docs/RawPLATIDs.md` | 35,768 | SM8650 平台 ID 表 |
| `.gitattributes` | 1,555 | — |
| `.gitignore` | 256 | — |
| **合计** | **49,477** | **无 drivers/、无源码、无 BSP 代码** |

**README 原文（关键句）**

> "Currently non functional chipset features: List to be done, consider 'everything' for now."

即：作者自己说"所有功能都还没做，就当全部不可用"。

**唯一的可用资产：`docs/RawPLATIDs.md`**

| 指标 | 值 |
|---|---|
| 总行数 | 528 |
| `.dts` 条目行 | 507 |
| PlatformTypeID 非 0 的行 | 480（其余 27 行为 `0 (UNKNOWN)`） |
| 章节 | 两个 `## Snapdragon 8 Gen 3` + `### Overlays` |
| 是否含 caihong | **否**（只有 QRD/参考板条目） |
| 是否含 cliffs | **是**：`cliffs-ese-cdp.dts` 与 `pineapple-*.dts` 同表 |

示例：

```
| cliffs-ese-cdp.dts            | 1 (CDP) | 0 | 0 | 5.0 | 0 | 0 | 0 |
| pineapple-audio-wsa883x-cdp.dts | 1 (CDP) | 1 | 0 | 0.0 | 0 | 0 | 0 |
```

**三栏结论**

| 可用于本项目 | 仅作参考 | 不可复用 |
|---|---|---|
| ① `RawPLATIDs.md` 的 dtb→PlatformTypeID 映射（用于理解 ABL 的 DTB 选择逻辑）；② `NTDBG.md` 的 WinDbg/`!amli` 调试手法（将来验证 ACPI 时要用）；③ **"Cliffs 与 pineapple 同族"的独立旁证**（同一张表里两者并列） | README 的仓库定位（证明社区曾计划做 SM8650 BSP，但仅止于计划） | **全部代码——因为不存在**。不能声称"有 SM8650 Windows 支持"、不能从中找驱动 |

> **本次审计最重要的一条**：任何"SM8650 的 Windows 驱动可以在 WOA-Project 找到"的说法，都与实际文件清单矛盾。**该仓库是公告板，不是 BSP。**

---

### 2.4 `liliumbeta/Mu-Qcom`

| 项 | 值 |
|---|---|
| URL | `https://github.com/liliumbeta/Mu-Qcom` |
| 本地路径 | `source/Mu-Qcom-liliumbeta` |
| 分支 / commit | `main` / `7b51bdd13b694ca71df61782140683ac30362772` |
| 提交日期 / 标题 | 2024-02-07 / "Update Licences" |
| 抓取状态 | **已克隆 + 已读取**（目录列举、README 许可段） |
| 许可证 | README：除 `GPLDrivers`/`GPLApplications`/`GPLLibrary` 外为 **BSD 2-Clause**；GPL 驱动为 **GPLv2**。注意：**这三个 GPL 目录在本仓库中不存在** |

**`Silicon/Qualcomm/` 全部内容（12 个）**

`MSM8998Pkg`、`QcomPkg`、`SDM660Pkg`、`SM6115Pkg`、`SM6125Pkg`、`SM6225Pkg`、`SM7150Pkg`、`SM7325Pkg`、`SM8150Pkg`、`SM8250Pkg`、`SM8350Pkg`、`SM8450Pkg`

→ **最高只到 SM8450；无 SM8550，无 SM8650。**

**其他发现**

- `Platforms/`：Lenovo、Motorola、OnePlus、Samsung、Sony、Xiaomi。
- `Binaries`（30 项）、`Common/Mu`（31 项）已填充；**`Silicium-ACPI` 为 0 项**（未填充）→ 该 fork 里**没有 ACPI 表集合，也没有 `iasl.exe`**。
- 由此，本会话使用的 `iasl.exe` 只能来自 musabcel fork（已核实路径与版本）。

**三栏结论**

| 可用于本项目 | 仅作参考 | 不可复用 |
|---|---|---|
| 几乎无：仅可作为"Mu-Qcom 历史演进"的对照 | 早期平台包的写法 | SoC 包整体（太旧，无 SM8550 模板可用）；ACPI 目录缺失 |

---

### 2.5 `musabcel/Mu-Qcom`（本项目基线）

| 项 | 值 |
|---|---|
| URL | `https://github.com/musabcel/Mu-Qcom` |
| 本地路径 | `source/Mu-Qcom-musabcel` |
| 分支 / commit | `main` / `520b8826371bc19bdf81eee79e6640ee6cb0ef92` |
| 提交日期 / 标题 | 2025-08-19 / "Bump Features/DFCI from `220506e` to `174f45c` (#1744)" |
| 抓取状态 | **已克隆 + 已读取**（SoC 包、平台包、Silicium-ACPI、构建脚本、依赖清单） |
| 许可证 | README：除 GPL 目录外 **BSD-2-Clause**；GPL 驱动 **GPLv2+**。`KailuaPkg.dsc.inc` 等文件头为 `SPDX-License-Identifier: BSD-2-Clause-Patent`。GPL 目录在本仓库同样不存在 |

**`Silicon/Qualcomm/`（20 个）**

`BlackboltPkg`、`DivarPkg`、`HanaPkg`、`KailuaPkg`、`KamortaPkg`、`KodiakPkg`、`KonaPkg`、`LahainaPkg`、`MooreaPkg`、`NapaliPkg`、`NazgulPkg`、`NicobarPkg`、`PakalaPkg`、`PalawanPkg`、`PalimaPkg`、`QcomPkg`、`RennellPkg`、`StarlordPkg`、`StraitPkg`、`WaipioPkg`

→ **有 SM8550（KailuaPkg）、SM8750（PakalaPkg）；无 SM8650。**

**SoC 包的实际构成（关键：这不是"占位空壳"）**

| 包 | 文件数 | 内容 |
|---|---|---|
| `KailuaPkg`（SM8550） | 11 | `KailuaPkg.dsc.inc` + `Library/{PlatformPrePiLib, SoCPlatformLib, RFSProtectionLib, AcpiPlatformUpdateLib}` |
| `WaipioPkg`（SM8450，8 Gen 1） | 11 | 同上完整 |
| `PakalaPkg`（SM8750） | 6 | 只有 `PlatformPrePiLib` + `SoCPlatformLib`，**无** ACPI/RFS 库 → 更薄 |

**KailuaPkg.dsc.inc 关键常量（已读取）**

```
gArmPlatformTokenSpaceGuid.PcdCoreCount|8
gArmPlatformTokenSpaceGuid.PcdClusterCount|3
gArmTokenSpaceGuid.PcdGicDistributorBase|0x17100000
gArmTokenSpaceGuid.PcdGicRedistributorsBase|0x17180000
gArmTokenSpaceGuid.PcdGicInterruptInterfaceBase|0x17140000
gArmTokenSpaceGuid.PcdArmArchTimerFreqInHz|19200000
gArmTokenSpaceGuid.PcdArmArchTimerSecIntrNum|29
gArmTokenSpaceGuid.PcdArmArchTimerIntrNum|30
gArmTokenSpaceGuid.PcdFvDecompressAddr|0xA7043418
*_*_AARCH64_CC_FLAGS = -march=armv9-a+crypto+rcpc
PcdSmbiosProcessorModel = "Snapdragon (TM) 8 Gen 2" / SM8550-AB / SM8550-AC
```

**PakalaPkg.dsc.inc 关键常量（对比用）**

```
PcdCoreCount|8 (7 的变体行也存在)
PcdClusterCount|2
PcdGicDistributorBase|0x16000000
PcdGicRedistributorsBase|0x16080000
PcdArmArchTimerFreqInHz|19200000
PcdArmArchTimer{Sec,}IntrNum|29 / 30
PcdSmbiosProcessorModel = "Snapdragon (TM) 8 Elite" / SM8750-AB / SM8750-3-AB / SM8750-AC
*_*_AARCH64_CC_FLAGS = -march=armv8-a+crypto+rcpc
```

> 对照价值：**SM8650 的 GIC 基址与 SM8550 相同（0x17100000/0x17180000），与 SM8750 不同（0x16000000）**。这解释了为什么拿 SM8550 当模板而不是拿更新的 SM8750 当模板。

**`Silicium-ACPI`（已填充）**

| 子目录 | 内容 |
|---|---|
| `Compiler/` | **`iasl.exe`（1,006,592 B，version 20230628）** ← 本项目在 Windows 侧唯一可用的 AML 编译器 |
| `SoCs/Qualcomm/` | 17 个 SoC：Blackbolt、Divar、Hana、**Kailua**、Kamorta、Kodiak、Kona、Lahaina、Moorea、Napali、Nazgul、Nicobar、Palawan、Palima、Rennell、Starlord、Waipio（**无 Pakala、无 SM8650**） |
| `Platforms/` | 12 个厂商：Asus、Lenovo、LG、Motorola、Nintendo、Nothing、OnePlus、Realme、Samsung、Sony、Xiaomi、ZTE |

`SoCs/Qualcomm/Kailua/` 的表集合（字节数与本项目 `build/acpi` 的上游源一致）：

| 文件 | 字节 |
|---|---|
| `FACP.aml` | 276 |
| `APIC.aml` | 744 |
| `GTDT.aml` | 156 |
| `DBG2.aml` | 1,364 |
| `PPTT.aml` | 570 |
| `DSDT_minimal.asl` / `.aml` | 1,525 / 354 |

`Platforms/OnePlus/` 现有：`aston`、`guacamole`、`hotdog`、`kebab`、`lemonade`（**无 caihong**）。一个完整平台的 ACPI 由 `Sources/*.dsl` + 编译后的 `DSDT.aml` 组成，`aston` 的实例包含：`battery.dsl`、`cpu.dsl`、`gpio.dsl`、`i2c.dsl`、`i2c_hubs.dsl`、`mmu.dsl`、`pmic.dsl`、`spi.dsl`、`spmi.dsl`、`tree.dsl`、`ufs.dsl`、`usb.dsl` + `DSDT.dsl`。

**三栏结论**

| 可用于本项目 | 仅作参考 | 不可复用 |
|---|---|---|
| ① **SoC 包模板**（KailuaPkg 的 4 个库 + dsc.inc 结构）；② **ACPI 表集合**（5 张表可直接重定向，且已用硬断言验证常量一致）；③ `iasl.exe`（Windows 侧必需）；④ **板级 port 骨架**（`.dec`/`.dsc`/`.fdf` + `DeviceBuild.py` + 三个 `Device*Lib`）；⑤ `Platforms/OnePlus/aston` 作为 OnePlus 设备的 ACPI 写法参照 | 其他 SoC 的常量（不可套用到 SM8650）；`WaipioPkg`/`PakalaPkg` 的裁剪方式；构建脚本的组织 | **没有任何 SM8650 代码**；`KailuaPkg` 的 SMBIOS 字符串（8 Gen 2）、`PcdFvDecompressAddr=0xA7043418`、`-march` 之外的 SoC 特性均不可直接沿用 |

**⚠ 重要澄清：`source/Mu-Qcom-musabcel` 里有一部分内容是"我们写的"，不是上游的**

`git status` 结果：

```
 M Binaries / Common/Mu / Common/Mu_OEM_Sample / Common/Mu_Tiano_Plus
 M Features/DFCI / Mu_Basecore              (submodule 指针变化)
 M BootShim/BootShim.S / BootShim/Makefile
 M build_active_devices.sh / build_uefi.sh
?? Platforms/OnePlus/caihongPkg/
?? Resources/Configs/caihong.conf
?? Silicon/Qualcomm/CliffsPkg/
```

即：**`CliffsPkg`、`caihongPkg`、`caihong.conf` 是本会话新增的本地文件**，不来自上游。任何读者若看到这些目录，不应误认为"Mu-Qcom 已支持 caihong"。

---

## 3. 重点结论：空壳意味着什么

- **判定依据**：7 个文件 / 49,477 B；无 `drivers/`、`Platforms/`、`Silicon/`、`Binaries/`；README 自述"everything 不可用"；最后一次提交（2024-11-10）标题是 "Update README.md"。
- **影响**：期望从它得到的 SM8650 Windows 驱动、SM8650 ACPI 描述、BSP 构建方式——**全部不存在**。
- **结论**：**Windows-on-SM8650 的公开生态位是空的。** UEFI 层可自建（有 SM8550 模板），**驱动层没有任何可复用资产**，必须自研或等待 Qualcomm/其他团队。项目现实目标只能是"引导验证"，不是"可用系统"。

---

## 4. 从审计中学到的架构：一个 Mu-Qcom 板级 port 由什么组成

| 层 | 位置 | 必需要素 |
|---|---|---|
| SoC 包 | `Silicon/Qualcomm/<SoC>Pkg/` | `<SoC>Pkg.dsc.inc`（常量 + 编译标志）、`PlatformPrePiLib`、`SoCPlatformLib`（+ 可选 `RFSProtectionLib`、`AcpiPlatformUpdateLib`） |
| 平台包 | `Platforms/<Vendor>/<device>Pkg/` | `<device>.dec/.dsc/.fdf`、`DeviceBuild.py`、`Include/{ACPI,APRIORI,DXE,RAW}.inc`、`Library/{DeviceMemoryMapLib, DeviceConfigurationMapLib, DeviceGuidLib}` |
| 构建配置 | `Resources/Configs/<device>.conf` | vendor、model 数、BootShim 参数（`TARGET_FD_BASE/SIZE/BLOCKS`）、FDT 指针策略 |
| 镜像脚本 | `Resources/Scripts/<device>.sh` | 由 `build_uefi.sh` source，缺省只警告、不出镜像 |
| SoC ACPI | `Silicium-ACPI/SoCs/Qualcomm/<SoC>/` | `FACP.aml`、`APIC.aml`、`GTDT.aml`、`DBG2.aml`、`PPTT.aml`、`DSDT_minimal.asl` |
| 平台 ACPI | `Silicium-ACPI/Platforms/<Vendor>/<device>/` | `Sources/*.dsl` + `DSDT.aml` |
| 引导 | `BootShim/` | 当 `TARGET_REQUIRES_BOOTSHIM=1` 时由 BootShim 决定 FV 重定位地址 |

**Mu-Qcom 使用的 ACPI HID（本次在 `Silicium-ACPI` 源码中逐项检索确认存在）**：CPU `ACPI0007`（480 处）、容器 `ACPI0010`（104）、GPIO/TLMM `QCOM0C0C`+`QCOMFFEB`、I2C `QCOM0C10`+`QCOMFFEA`、SPI `QCOM0C0E`、SPMI `QCOM0C0B`+`PNP0CA2`（26）、PMIC `QCOM0C2B`/`QCOM0C2D`+`PNP0CA3`/`QCOMFFE3`、UFS `QCOM24A5`（44）、USB `QCOM0C8B`、SMMU `QCOM0C09`/`QCOM068F`、PCIe RC `QCOM04DE`+`QCOMFFEC`。

---

## 5. 依赖追踪：`dependencies.env` 全文

`source/caihong-linux-rootfs/config/dependencies.env`（599 B，逐字）：

```sh
# Stable source branches followed by the release workflow. Every build writes
# the resolved commit IDs into its release manifest.
LINUX_REPOSITORY=https://github.com/Osilvfe/linux.git
LINUX_REF=caihong-v7.3
LIBCAMERA_REPOSITORY=https://github.com/Osilvfe/libcamera.git
LIBCAMERA_REF=caihong-camera
PLASMA_CAMERA_REPOSITORY=https://github.com/Osilvfe/plasma-camera.git
PLASMA_CAMERA_REF=caihong-camera
QBOOTCTL_REPOSITORY=https://github.com/linux-msm/qbootctl.git
QBOOTCTL_REF=main
MKBOOTIMG_REPOSITORY=https://android.googlesource.com/platform/system/tools/mkbootimg
MKBOOTIMG_REF=main
```

| 依赖 | 指向 | 用途 | 本项目状态 |
|---|---|---|---|
| Linux 内核 | `Osilvfe/linux` @ `caihong-v7.3` | 设备的主要 OS 内核 | **已克隆**（部分克隆，commit `4df9a88`，与我们看到的分支名一致） |
| libcamera | `Osilvfe/libcamera` @ `caihong-camera` | 相机用户态 | 未克隆 |
| plasma-camera | `Osilvfe/plasma-camera` @ `caihong-camera` | 相机前端 | 未克隆 |
| qbootctl | `linux-msm/qbootctl` @ `main` | Android boot 槽位管理 | 未克隆 |
| mkbootimg | `android.googlesource.com` @ `main` | 生成 Android boot 镜像 | 未克隆（Windows 侧不需要） |

> 说明：这些依赖**全部服务于 Linux 侧**，与 Windows 端口无代码复用关系。列在这里的价值是：证明"设备已被完整摸清"以及"内核 fork 的确切坐标"。

---

## 6. 设备材料审计：`E:\1+padpro`

| 路径 | 性质 | 文件数 / 体积 | 本项目用途 |
|---|---|---|---|
| `oxygenos/` | **完整 stock 固件镜像集**（含 `xbl`、`abl`、`uefi`、`dtbo`、`boot`、`vendor_boot`、`payload.bin` 等） | 50 文件 / 13,765,921,681 B（≈12.8 GiB） | **DTB 提取的实际来源**（`extract-report.json` 的 `src`） |
| `linux/d90c9a3b…/` | 设备**状态备份 + 全量刷机包**（`1-backup-now.bat` … `5-flash-system-only.bat`、`payload.bin` 6.69 GB、`images/` 48 文件 8.5 GiB、`padpro/payload/{info,apks,appdata,settings,root}`） | ≈8.5 GiB（images） | **设备身份与运行状态的唯一来源**（`getprop.txt`、`kernel.txt`、`cmdline.txt`、`partitions.txt`） |
| `skroot/` | 已打补丁的 `boot.img`/`new-boot.img` + `kernel` + SukiSU APK | — | 未使用 |
| `xia/` | `GeekFlashTool.exe` + `Binaries/` + `configure.ini` | — | 未使用（厂商刷机工具） |
| `mio/` | 已解包的 Android 分区（`system/`、`my_product/`、`odm/`、`system_ext/` 等） | — | 未使用 |
| `twrp_caihong.img` | 104,857,600 B | — | 未使用 |

**重要发现（纠正一个容易搞错的点）**：`E:\1+padpro\linux\` **不是 Arch Linux 发行包**，而是"状态备份 + 刷机"工具包（README 为 GBK 编码：`一加平板 Pro (OPD2404) 状态备份数据`，`payload/manifest.txt` 记录 `backup_time=2026-10-05 12:01:34`、`build=OPD2404_15.0.0.1301(CN01)`）。真正的"Arch Linux"是 §2.1 那个 rootfs 仓库。

**两套固件不是同一个 build**（实测 sha256）：

| 镜像 | `oxygenos/` | `linux/…/images/` |
|---|---|---|
| `dtbo.img` | `eeccd9b772c0311f…` | `f8ad1372ca9c77da…` |
| `vendor_boot.img` | `a21ffe4c2d04e06c…` | `1c044469171abfe0…` |
| vendor DTB `dtb_size` | 3,171,955 | 4,014,793 |
| dtbo 第 7 项大小 | 777,871 | 768,444 |

两者**大小相同但内容不同**。已做的交叉验证：两套 vendor DTB 的 GIC/UFS3/USB3/TLMM/UART 地址与 `stdout-path` **完全一致**（差异集中在内存与 board 细节）。**残余风险**：`oxygenos/` 未必等于设备当前 build —— 需要在真机 dump 比对（记录于 `docs/feasibility.md` Q4）。

---

## 7. 未验证来源清单（不得作为依据）

| 来源 | 状态 | 影响 |
|---|---|---|
| Renegade Project（`renegade-project.tech`） | **未抓取** | 不能声称其支持 SM8650，也不能声称两个 Mu-Qcom fork 与该组织的关系 |
| openwall 邮件列表链接 | **未抓取** | 不引用其任何内容 |
| 两个 Mu-Qcom fork 与 Renegade 的关系 | **未验证** | 仅陈述仓库自身 README/文件事实 |
| `Osilvfe/linux` 的 DTS/defconfig 正文 | **未取得**（429 + blob:none） | 不能用它证明具体节点内容；我们用 mainline `sm8650.dtsi` 做地址核对 |
| Windows 是否有 UFS/`QCOM24A5` 的 inbox 驱动 | **未验证** | `docs/feasibility.md` 中相关判断标为"未知" |

---

## 8. 本次会话产出的本地代码（非上游）

| 路径 | 说明 |
|---|---|
| `scripts/fdtlib.py`（16,263 B） | 纯 Python 的 FDT / DTBO / vendor_boot / boot v4 解析器 |
| `scripts/extract_dtb.py`（6,695 B） | 提取 8 个 dtbo DTB + vendor DTB + kernel + bootconfig，输出含 sha256 的 JSON 报告 |
| `scripts/build_soc_acpi.py`（7,379 B） | 由 SM8550 表派生 SM8650 表；**对 GIC/timer 值做硬断言，不匹配即 `SystemExit`** |
| `build/acpi/*.aml` + `soc-tables.json` | 5 张表（276/744/156/1,364/570 B），OEM ID `ONEPLS`、Table ID `CAIHONG`、rev `0x8650`，checksum 全 OK |
| `acpi/caihong/DSDT.dsl` → `DSDT.aml`（8,510 → 743 B） | 13 Device / 32 Name / 18 Method / 1 Scope（= 64 命名空间节点）；iasl **0 Errors, 0 Warnings, 8 Remarks, 3 Optimizations** |
| `Silicon/Qualcomm/CliffsPkg/`（11 文件） | SM8650 SoC 包骨架，派生自 KailuaPkg，改动处逐条注明证据 |
| `Platforms/OnePlus/caihongPkg/`（14 文件） | 平台包骨架，派生自 astonPkg；含**故意关闭的构建闸门** |
| `Resources/Configs/caihong.conf`（1,201 B） | BootShim 参数（`TARGET_FD_BASE=0xBAB00000`，注明是"选择"而非"设备事实"） |
| `work/dt/`、`work/dt_bak/` | 每套 8 个 dtbo DTS + vendor DTS + kernel + bootconfig，可重跑复现 |

**已知缺陷（不掩饰）**

| 项 | 说明 |
|---|---|
| `work/sm8650-oneplus-caihong.dts` | **是 HTTP 429 错误页**（313 B），不是 DTS；应删除或改名以免误用 |
| `work/build-aston.log` | 证明构建从未成功：`./build_uefi.sh: cannot execute: required file not found` |
| `Resources/Scripts/caihong.sh` | 不存在 → 即便能编译也不会产出镜像 |
| `Silicium-ACPI/Platforms/OnePlus/caihong/` | 不存在 → 平台级 ACPI 尚未接入构建 |
| 代码注释引用的 `docs/hardware-sm8650.md`、`docs/bringup-log.md` | 仍不存在（`docs/` 下已有并行产出的 `hardware-matrix.md`、`recovery.md`、`hw-sm8650-caihong.json`，内容与本文件一致：均声明"未上机"） |

---

## 9. 总表：一句话版本

- **能拿代码的只有 `musabcel/Mu-Qcom`**（SoC 模板、ACPI 表、`iasl.exe`、板级骨架，BSD-2-Clause）；其余四个来源**没有任何一行能进 UEFI 代码库**。
- **能拿硬件事实的只有 `E:\1+padpro` 的固件镜像**（已复现为 `work/dt/`）。
- **`windows_silicon_qcom_lanai` 只能拿数据与调试手法**（`RawPLATIDs.md`、`NTDBG.md`），拿不到代码——因为它没有代码。
- **`Osilvfe/*` 两份材料只证明"这台设备的硬件在 Linux 下已被完整驱动"**，是可行性旁证，不是可复用资产。
- **Renegade Project / openwall 本会话未抓取，全部不作为依据。**
