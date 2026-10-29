# 可行性评估：OnePlus Pad Pro（caihong / OPD2404）运行 Windows on ARM

| 项 | 值 |
|---|---|
| 文档状态 | 阶段性评估，非结论文档 |
| 编写时间 | 2026-10-29（本次会话） |
| 目标设备 | OnePlus OPD2404 / `ro.product.device=OP5D77L1` / 代号 `caihong` |
| 目标 SoC | Qualcomm SM8650（内部代号 "Cliffs"） |
| 当前是否已引导 | **否。本会话没有任何 UEFI 或 Windows 在真机上运行过。** |

## 0. 阅读须知：本文的证据纪律

本文只使用本次会话中**实际读取到的数据**（固件镜像解析、上游仓库内容、本机工具输出）。三档标注：

- **【已核实】**：来自真实数据/文件，可复现。
- **【推断】**：由已核实数据推出，但无直接观测。
- **【未知/开放】**：明确写"未知"，并说明需要什么才能确定。

**未经验证的来源不作为依据**：Renegade Project 站点页面在本会话中未被抓取，openwall 邮件列表链接未被抓取，故本文不对其作任何支持性陈述（见 §8）。

---

## 1. 目标与范围

### 1.1 目标

在这台平板上让 Windows on ARM 走到"可用"，按顺序是三个递进目标：

1. **G1**：自建的 Mu-Qcom（EDK2/Silicium）UEFI 固件能在真机上执行到 Shell/控制台输出。
2. **G2**：Windows 安装介质能被该固件引导，Windows 能接受我们提供的 ACPI 表（不 0x7B/0xA5 蓝屏）。
3. **G3**：Windows 安装到 UFS，且显示、触控、键盘（pogo）可用。

### 1.2 范围

**在范围内**：设备树/固件事实提取、ACPI 表（FACP/APIC/GTDT/DBG2/PPTT/DSDT）生成、Mu-Qcom 平台移植骨架、引导链（xbl/abl → BootShim → UEFI）的可验证性分析。

**不在范围内（本会话未触及）**：Windows 驱动开发（WDDM/触控/网络等）、Linux 侧工作、分区实际写入、任何 fastboot/adb 操作。

### 1.3 判据

每条路线/阶段必须有**可验证的出口条件**（能观测的产物或现象），而不是"看起来可行"。第 6 节按此原则编排。

---

## 2. 已核实的硬件与设备事实

### 2.1 主机与工具环境 【已核实】

| 项 | 值 | 证据来源 |
|---|---|---|
| 主机 OS | Windows 11 Pro build 26300 | 会话环境 |
| CPU | AMD Ryzen 7 7800X3D | 会话环境 |
| 内存 | 31.12 GB | 会话环境 |
| 工作目录 | `E:\caihong-windows`（起始为空） | 目录列举 |
| WSL2 发行版 | Alpine Linux 3.22.7，名为 `FnosPort`，root，网络可用 | `wsl -d FnosPort` 执行成功 |
| WSL 工具链 | clang 20.1.8（Alpine）、lld/ld.lld、iasl 20230628、dtc 1.7.2、python 3.12.15、make、gcc | `work/toolcheck.sh` 输出 |
| WSL **缺失** | `aarch64-linux-gnu-gcc`、`nasm`、`mono` | 同上（逐项 `MISSING`） |
| Windows 侧 | 无 Visual Studio / MSVC / clang；无 iasl | 会话环境 |
| 可用 iasl | `source/Mu-Qcom-musabcel/Silicium-ACPI/Compiler/iasl.exe`（1,006,592 B，version 20230628） | `iasl.exe -v` |

> 影响：EDK2/Mu-Qcom 的官方构建说明（`Building.md`）要求 Ubuntu 22.04 + `gcc-aarch64-linux-gnu` + `nasm`（`setup_env.sh` 只支持 apt/dnf/pacman/yay）。**Alpine 不在其支持列表内，且缺少交叉 gcc 与 nasm** —— 这是"构建环境"层面的真实缺口，不是理论问题。

### 2.2 设备身份 【已核实】

来源：`E:\1+padpro\linux\d90c9a3b40c34d35b619993947063e25\padpro\payload\info\getprop.txt`（设备自身 dump）。

| 属性 | 值 |
|---|---|
| `ro.product.model` / `ro.product.name` | `OPD2404` |
| `ro.product.device` | `OP5D77L1` |
| `ro.build.fingerprint` | `OnePlus/OPD2404/OP5D77L1:15/UKQ1.231108.001/U.1f6e972_e4-2216a:user/release-keys` |
| Android / SDK | 15 / 35 |
| `ro.board.platform` | `pineapple` |
| Bootloader | `ro.boot.vbmeta.device_state=unlocked`，`verifiedbootstate=orange` |
| 活动槽位 | `_b` |
| 序列号 | `67ab95c8` |
| `ro.boot.boot_devices` | `soc/1d84000.ufshc` |
| `ro.boot.usbcontroller` | `a600000.dwc3` |
| `ro.boot.dtbo_idx` | `7` |
| 内核 | `6.1.118-android14-11-o-g2b8edc801b38`，clang 17.0.2，构建于 2025-08-25 13:49:08 UTC |
| 系统构建号 | `OPD2404_15.0.0.1301(CN01)`（`payload/manifest.txt`） |
| Dump 时间 | 2026-10-05 11:54:32 CST（`info/date.txt`） |

### 2.3 SoC 识别：Cliffs = SM8650 【已核实 + 一处推断】

| 观测 | 值 | 来源 |
|---|---|---|
| vendor DTB `model` | `Qualcomm Technologies, Inc. Cliffs SoC` | `work/dt/vendor_boot/vendor.dts` |
| vendor DTB `compatible` | `qcom,cliffs`（另有 `qcom,cliffs-rpmh-clk`、`qcom,cliffs-pdc`、`qcom,cliffs-llcc`、`qcom,cliffs-pinctrl`） | 同上 |
| 同节点 mainline 命名 | `qcom,sm8650-tlmm` | mainline `sm8650.dtsi` |
| mainline `qcom/` dts 目录 | **无任何 `cliffs` 条目**，只有 `sm8650-*` 板级文件 | `work/qcom-Makefile.txt`（grep `cliffs` = 0 命中） |
| 独立旁证 | Mu-Qcom 的 SM8650 平台 ID 表中存在 `cliffs-ese-cdp.dts` 行，与 `pineapple-*` 同表并列 | `source/lanai/docs/RawPLATIDs.md` |

**结论【推断，证据较强】**：Qualcomm 用 "Cliffs" 指代 SM8650，`pineapple` 是同族平台/板级代号。支撑证据：① vendor DTB 自身把 `qcom,cliffs-pinctrl` 挂在 mainline 的 `sm8650` TLMM 地址上；② mainline 的 `qcom/` dts 目录里没有任何 `cliffs` 条目（排除"另一个独立 SoC"的解释）；③ SM8650 的 Windows 平台 ID 表把 `cliffs-*.dts` 与 `pineapple-*.dts` 并列。**仍未获得 Qualcomm 官方文档级确认**——若需 100% 确定，需要 Qualcomm 公开的 SoC 命名表或 SM8650 TRM。

### 2.4 固件镜像结构 【已核实】

`dtbo.img`（`E:\1+padpro\oxygenos\dtbo.img`，25,165,824 B，sha256 `eeccd9b7…`）：

| 项 | 值 |
|---|---|
| DTBO blob 数 | 1 |
| entry 数 | 8 |
| 全部 entry 的 `dt_id` / `dt_rev` | 均为 `0` / `0`（OPPO 未填），因此选择只能按表索引 |
| 活动 entry | `ro.boot.dtbo_idx=7` → 索引 7，777,871 B |

`vendor_boot.img`（201,326,592 B，sha256 `a21ffe4c…`）：`VNDRBOOT` header **v4**，`dtb_size=3171955`，`dtb_addr=0x1F00000`，vendor ramdisk 表 108 B / 1 条。

板级 overlay（entry 7）身份：`model = "Qualcomm Technologies, Inc. Pineapple MTP,caihong"`，`compatible = qcom,pineapple-mtp / qcom,pineapple / qcom,pineapplep-mtp / qcom,pineapplep / qcom,mtp`，`qcom,msm-id = <0x22d 0x10000 0x241 0x10000>`，`qcom,board-id = <8 0>`。

### 2.5 关键控制器地址（全部来自设备自身 DTB）【已核实】

GSIV 换算规则：`GSIV = 32 + SPI`（SPI 编号从 DTB 的 `interrupts` 第 2 个 cell 取）。

| 模块 | 物理地址 | 中断 | GSIV | 备注 |
|---|---|---|---|---|
| GICv3 distributor | `0x17100000` + 0x10000 | — | — | `#interrupt-cells = 3` |
| GICv3 redistributor | `0x17180000` + 0x200000 | — | — | mainline 同址（含 `redistributor-stride = 0x40000`，8 核） |
| Arch timer | `19200000` Hz | PPI 13/14 | 29 / 30 | hyp 11/12 |
| 平台定时器 | `0x17420000` | — | — | `arm,armv7-timer-mem` |
| UFS 主机控制器 | `0x1d84000`+0x3000 / `0x1d88000`+0x8000 / `0x1d90000`+0x9000 / `0x1da5000`+0x2000 / `0x1da4000`+0x10 | SPI 265 | `0x129` | `ro.boot.boot_devices` 亦指向 `1d84000.ufshc` |
| USB3 DRD（dwc3） | `0xa600000` + 0xd93c | SPI 133 | `0xA5` | `ro.boot.usbcontroller=a600000.dwc3` |
| TLMM / pinctrl | `0xf000000` + 0x1000000 | SPI 208 | `0xF0` | `qcom,cliffs-pinctrl` |
| SPMI PMIC arbiter | `0xc42d000`（主）/ `0xc432000`（次） | — | — | 子设备（PM8550 族）未解析 |
| GENI 调试 UART | `0xa94000` + 0x4000 | SPI 358 | `0x186` | `chosen stdout-path` 指向此处，115200n8 |
| MDSS / MDP | `0xae00000` | SPI 83 | `0x73` | `dsi_ctrl0@ae94000`，`dsi_phy0@ae95500` |

**与 mainline `sm8650.dtsi` 的地址交叉验证【已核实】**：

| 节点 | mainline 位置 | 结果 |
|---|---|---|
| `ufshc@1d84000` | 第 4041 行 | 命中 |
| `timer@17420000` | 第 7314 行 | 命中 |
| `geniqup@ac0000` | 第 2934 行 | 命中 |
| `geniqup@8c0000` | 第 2067 行 | 命中 |
| `interrupt-controller@17100000` | 第 7274 行（GICR 在 `reg` 内，第 7277 行） | 命中 |
| MDSS | mainline 为 `display-subsystem@ae00000`（`reg` 仅 0x1000），设备侧为 `mdss_mdp@ae00000` | **基地址一致，节点粒度不同** |
| `#interrupt-cells` | mainline = **4**，设备 DTB = **3** | 不一致，见 §2.8 |

### 2.6 CPU 与中断拓扑 【已核实】

- 8 个 `cpu@0` … `cpu@700`，`compatible = "qcom,kryo"`。
- `qcom,cpuidle-domain` 的 cpu-map 声明簇大小为 **3 / 4 / 1**。
- 因此 EDK2 侧 `PcdCoreCount=8`、`PcdClusterCount=3` 有直接依据。

### 2.7 面板与触控 【已核实】

设备内核 cmdline：

```
msm_drm.dsi_display0=qcom,mdss_dsi_panel_csot_nt36532_2120_3000_dual_dsc_144hz_vid
  :PanelID-0x00488000:PanelSN-0x0000000000000000:
oplus_bsp_tp_custom.dsi_display0=mdss_dsi_panel_csot_nt36532_2120_3000_dual_dsc_144hz_vid:novatek,nf_nt36532
```

- 面板：CSOT + Novatek NT36532 驱动 IC，3000×2120，dual DSC，144 Hz，video mode。
- 触控：Novatek NT36532（与面板同 IC 方案）。
- **未知**：触控挂在哪个 I2C 实例、I2C 从地址是多少 —— dtbo overlay 中未在本次提取结果里定位到明确绑定，需要在设备端 `dmesg`/`i2cdetect` 或完整解析 overlay 才能确定。

### 2.8 开放问题（必须诚实列出）

| # | 问题 | 现状 | 需要什么才能确定 |
|---|---|---|---|
| Q1 | **msm-id 不一致**：base vendor DTB 为 `0x266`，板级 overlay 为 `0x22d`/`0x241` | 两组值都在真实数据中，互相不一致 | Qualcomm 的 msm-id 分配表，或 ABL 选择 DTB 的日志 |
| Q2 | `#interrupt-cells` 3（设备）vs 4（mainline） | 已确认差异 | mainline 绑定文档 + 设备侧实际使用方式（ACPI 侧直接用 GSIV，暂不受影响） |
| Q3 | 活动 DTBO 到底是哪一个 | `dtbo_idx=7` 来自设备 dump；两套固件的 entry 7 内容不同（777,871 B vs 768,444 B） | 设备端读 `ro.boot.dtbo_idx` 与当前槽位一致性，或用 `fastboot getvar` 交叉确认 |
| Q4 | 已提取地址对应的固件版本 | 提取用的是 `oxygenos/`（dtbo sha `eeccd9b7…`），而设备当前 build 的备份镜像 dtbo sha 为 `f8ad1372…` | 在真机上 dump 一次 dtbo/vendor_boot 并比对 sha256 |
| Q5 | 调试 UART 的 ACPI `_HID` | 无任何一方来源给出 | Qualcomm 公开 ACPI 绑定，或在 Mu-Qcom 其他平台找到实例（本次未找到） |
| Q6 | SPMI 上的 PMIC 子设备（USID、型号） | 未解析 | 完整解析 dtbo overlay 的 spmi 子节点 |
| Q7 | 内存实际速率/类型 | 无来源 | 不需要（仅 SMBIOS 装饰性字段） |
| Q8 | **MADT 内三个按簇的 GICR 基址**（0x17180000 / 0x171C0000 / 0x17200000） | 设备 DTB 只证明重分发器**区域**基址与大小（0x17180000 + 0x200000），按簇切分是从 SM8550 继承的；而 SM8650 的簇构成是 3/4/1，不等于 SM8550 | 上机后读各重分发器的 `GICR_TYPER.Affinity_Value`，或确认 8 个 CPU 全部 online |

> 说明：Q1–Q4 中，Q4 是**方法学上最需要严肃对待的一条**——硬件地址表来自 `oxygenos/` 镜像集，而设备当前运行的 build 是另一套镜像。已做的交叉检查是：两套 vendor DTB 的 GIC / UFS / USB3 / TLMM / UART 地址与 `stdout-path` **完全相同**（差异集中在内存与 board 细节，约 2,900 行），所以 §2.5 的地址对当前 build **仍然成立**；但这是"两套都验过"，不是"设备上实测过"。

---

## 3. 路线选择：A / B / C

### 3.1 三条候选路线（本节归纳本会话讨论的三类策略）

| 路线 | 内容 | 依赖 |
|---|---|---|
| **A. 等待上游** | 等 Mu-Qcom / Renegade / WOA-Project 出现可用的 SM8650 支持后直接复用 | 上游有 SM8650 SoC 包 + Windows 驱动 BSP |
| **B. 自建移植** | 以 Mu-Qcom（musabcel fork）为基线，自建 `CliffsPkg`（SoC）+ `caihongPkg`（平台）+ 自行生成 ACPI，再用 BootShim 接 ABL | 自己解决 SoC 常量、ACPI、ABL 地址、驱动 |
| **C. 绕开 UEFI** | 放弃 Windows-on-bare-metal，改走 Linux 优先（`caihong-linux-rootfs` 路线）或虚拟化 | Linux 主线对 SM8650 的支持（该项目自称基本可用） |

### 3.2 对比

| 维度 | A 等待上游 | B 自建移植 | C 绕开 |
|---|---|---|---|
| 上游现状（已核实） | **SM8650 Windows BSP 是空壳**（§5.1）；Mu-Qcom 最高到 SM8550/SM8750 | 有 SM8550（KailuaPkg）可作模板，架构清晰 | Linux 侧该项目自称显示/触控/网络等多数组件可用 |
| 能否现在动手 | 不能，阻塞在别人 | 能，且已有骨架产物 | 能，但目标不是 Windows |
| 主要成本 | 不可控的等待 | 工作量最大（SoC + ACPI + 驱动） | 最低，但拿到的是 Linux |
| 关键未知 | 是否有团队在做 | ABL 交接地址、驱动缺口 | 无关 |
| 结论 | 排除 | **选中** | 保留为并行/兜底 |

### 3.3 为什么选 B

1. **A 被实证否定**：`WOA-Project/windows_silicon_qcom_lanai` 明确是 SM8650 的 Windows BSP 仓库，但**只有 7 个文件、约 48 KiB，没有任何驱动/源码/BSP 代码**（详见 `docs/source-audit.md` §3）。等待等于无限期等待。
2. **B 有真实模板**：`musabcel/Mu-Qcom` 的 `KailuaPkg`（SM8550）是完整可编译的 SoC 包（含 `PlatformPrePiLib`/`SoCPlatformLib`/`RFSProtectionLib`/`AcpiPlatformUpdateLib`），其 GIC（`0x17100000`/`0x17180000`）、timer（19200000，GSIV 29/30）、CoreCount 8 与 SM8650 设备实测值**逐项相同**。
3. **B 已被本会话部分执行且有产物**：`CliffsPkg` + `caihongPkg` + `caihong.conf` 已创建；5 张 SoC 级 ACPI 表已生成并通过 iasl 校验；DSDT 已通过编译（§6 表）。
4. **B 的风险是可控的**：`caihong.dsc` 里有一道**故意关掉的构建闸门**（`CAIHONG_ABL_ADDRESSES_VERIFIED=0` → `!error`），保证不会在地址未知时产出会毁内存的固件。这是"慢但不会瞎猜"的路线。

### 3.4 选 B 的代价（必须承认）

- 需要自己当 SoC 包作者：SM8650 常量、ACPI、board 描述都要自证。
- 需要自己解决 Windows 驱动缺口（§5），这部分**没有任何公开可复用资产**。
- 需要自己搞清 ABL 交接（§4 致命项）。

---

## 4. 真实阻塞项分级

分级定义：**致命** = 不解决就无法推进下一阶段；**严重** = 会让阶段反复/成本大增，但有明确攻克路径；**可绕过** = 有已知替代或影响有限。

### 4.1 致命（P0）

| # | 阻塞项 | 证据 | 为什么致命 |
|---|---|---|---|
| **F1** | **ABL 交接地址未知**：`PcdFvDecompressAddr`、`PcdCpuVectorBaseAddress`、`PcdPrePiStackBase` | `CliffsPkg.dsc.inc` 显式标注 "NOT YET KNOWN FOR CAIHONG"；`caihong.dsc` 用 `!error` 硬阻断 | 这些值来自 xbl/abl 引导链，**无法从设备树推出**；猜错会在真机上静默破坏内存。当前固件根本编译不出来 |
| **F2** | **SM8650 的 Windows 驱动/BSP 不存在公开实现** | `windows_silicon_qcom_lanai` 为空壳；Mu-Qcom 树内无 sm8650 相关内容 | 即使 UEFI 跑起来，没有显示/触控/网络等驱动，Windows 装完也无法使用 |

> 这两条是**真阻塞**，不是"难"。F1 有明确攻克路径（读 ABL/日志/对比同族设备），F2 没有（要么自己写驱动，要么等 Qualcomm/社区）。

### 4.2 严重（P1）

| # | 阻塞项 | 证据 | 攻克路径 |
|---|---|---|---|
| S1 | 无 SM8650 SoC 包（需自建） | `Silicon/Qualcomm/` 无 SM8650；最高 SM8550/SM8750 | 已建 `CliffsPkg` 骨架；常量有据可依，`-march` 故意保守用 `armv9-a+crypto+rcpc` |
| S2 | 平台级 ACPI 未接入构建 | `Silicium-ACPI/Platforms/OnePlus/` 只有 aston/guacamole/hotdog/kebab/lemonade，**无 caihong**；`DeviceBuild.py` 会去该目录找 | 把 `acpi/caihong/DSDT.dsl` 扩展为 `Sources/*.dsl` + `DSDT.aml` 放到该路径 |
| S3 | 构建工具链不匹配 | WSL Alpine 缺 `aarch64-linux-gnu-gcc`、`nasm`；`setup_env.sh` 不支持 Alpine | 换 Ubuntu/Debian WSL 发行版，或手工装交叉工具链 |
| S4 | 构建从未成功 | `work/build-aston.log`：`./build_uefi.sh: cannot execute: required file not found`（连脚本都没跑起来） | 修执行环境（解释器/权限/CRLF），再跑一次 |
| S5 | 无镜像生成脚本 | `Resources/Scripts/caihong.sh` 不存在 → 构建脚本会警告 "No Output Image Was Generated" | 参照 `aston.sh` 写一个 |
| S6 | board 级 ACPI 设备缺失 | DSDT 只有 CPU×8 + UFS0 + USB0 + GIO0 + SPMI；触控/PMIC 子设备/电源/热区均无 | 解析 dtbo overlay 补全 |

### 4.3 可绕过（P2）

| # | 项 | 绕过方式 |
|---|---|---|
| B1 | Windows 无 iasl | 用 `Silicium-ACPI/Compiler/iasl.exe`（20230628，已实测可用） |
| B2 | Windows 无 clang/MSVC | 全部编译在 WSL 内做；ACPI 用 iasl.exe 在 Windows 侧验证 |
| B3 | msm-id 不一致（Q1） | ACPI 侧不消费 msm-id；仅在判断"哪个 overlay 生效"时需澄清 |
| B4 | 两套固件 build 不同（Q4） | 核心控制器地址已交叉验证一致；如需严格，真机 dump 比对 |
| B5 | `#interrupt-cells` 3 vs 4 | ACPI 用 GSIV，不经过 DT cells 语义 |
| B6 | fork 的 DTS 内容未取到（GitHub 429） | 不影响：DTS 属于 Linux 侧，Windows 侧用 ACPI |
| B7 | 无设备连接 | 现阶段不需要；真机验证时再解决 |

---

## 5. Windows on SM8650 的驱动缺口有多严重

### 5.1 事实：唯一的"SM8650 Windows BSP"仓库是空壳

`WOA-Project/windows_silicon_qcom_lanai`（README 自称 "Windows on Snapdragon 8 Gen 3 Board Support Package"）：

| 文件 | 大小 | 内容 |
|---|---|---|
| `README.md` | 1,806 B | 声明支持 SM8650/QRD；**"Currently non functional chipset features: List to be done, consider 'everything' for now."** |
| `LICENSE.md` | 3,088 B | DuoWoA 二进制许可条款 |
| `CODE_OF_CONDUCT.md` | 5,377 B | — |
| `docs/NTDBG.md` | 1,627 B | **SM8650 上调试 Windows 的 WinDbg 步骤**（讽刺的是：有调试指南，没有 BSP） |
| `docs/RawPLATIDs.md` | 35,768 B | SM8650 平台 ID 表（507 行 dts 条目）——**唯一有复用价值的部分** |
| `.gitattributes` / `.gitignore` | 1,555 / 256 B | — |

**没有 drivers/、没有源码、没有 BSP 代码。** 这不是"不完整"，是"只有文档"。

### 5.2 Mu-Qcom 能提供什么、不能提供什么

| 能提供 | 不能提供 |
|---|---|
| EDK2 应用层：DXE 驱动、ACPI 生成框架、BootShim | Windows 内核驱动（WDDM/触控/网络/音频/电源） |
| SoC 级常量的**模板**（SM8550/SM8750） | SM8650 的已验证常量（需自证） |
| Silicium-ACPI 的 SoC 表集合（17 个 SoC，含 Kailua） | Windows 侧 ACPI 消费方的兼容性保证 |
| 板级 port 的标准骨架（`.dec/.dsc/.fdf` + 三个 `Device*Lib`） | 任何 GPU 驱动 |

### 5.3 逐子系统缺口

| 子系统 | Windows 侧需要 | 公开可用性 | 严重程度 |
|---|---|---|---|
| 中断/定时器/CPU | ARM GICv3 + arch timer（Windows 自带通用栈） | 有，且常量已核实 | 低 |
| UFS | `QCOM24A5` 绑定的存储驱动 | **未知**——Windows inbox 是否有对应实现，本会话**未验证** | 高（若 inbox 不覆盖则致命） |
| USB3 | `QCOM0C8B` | 同上，未验证 | 中 |
| GPIO/I2C/SPI/SPMI | `QCOM0C0C`/`QCOM0C10`/`QCOM0C0E`/`QCOM0C0B` | Mu-Qcom 的 ACPI HID 体系对此有约定，但驱动本体不在树内 | 高 |
| 显示/GPU（Adreno + MDSS） | WDDM 迷你端口（KGSL/DPU 后继） | **无公开实现** | **致命（G3）** |
| 触控（Novatek NT36532） | HID-over-I2C 或厂商驱动 | 无 | 高 |
| Wi-Fi/BT（具体芯片型号未在本会话确认） | 厂商驱动 + BDF | 无 | 高 |
| 音频 / 摄像头 / 电池充电 / 传感器 | 各自驱动 | 无 | 高（G3 之外） |

### 5.4 结论：严重程度

> **G1（UEFI 能跑）在工程上可达**——只需要 EDK2 层的常量与 ACPI，Mu-Qcom 的架构已经证明这条路可行（同族 SM8550 在 Mu-Qcom 中有完整 port，是否已在真机跑通 Windows 本会话未验证）。
>
> **G2（Windows 能接受 ACPI 并启动）大概率可达**——ACPI 是描述性工作，我们已有可编译的 DSDT 与 5 张表。
>
> **G3（可用）目前不可达**——显示驱动没有任何公开实现，触控/Wi-Fi 同理。这不是"缺一块"，是"缺一整层"。因此本项目的现实目标是 **G1 + G2 的验证**，G3 属于研究性工作。

---

## 6. 阶段化路线与出口条件

| 阶段 | 目标 | 产出 | 出口条件（可验证） | 当前状态 |
|---|---|---|---|---|
| **P0 事实基座** | 从设备固件提取可复现的硬件事实 | `scripts/fdtlib.py`、`extract_dtb.py`、`build_soc_acpi.py`、`work/dt/*.dts` | 重新运行脚本得到逐字节相同的报告（sha256 一致） | **已完成** |
| **P1 ACPI 骨架** | SoC 表 + 最小 DSDT | `build/acpi/{FACP,APIC,GTDT,DBG2,PPTT}.aml`、`acpi/caihong/DSDT.dsl` | iasl 编译 0 error / 0 warning；反汇编回读一致 | **已完成**（DSDT 743 B，0 err/0 warn/8 remark/3 opt） |
| **P2 构建打通** | 让 `build_uefi.sh -d caihong` 产出 FV | `Build/caihongPkg/**/*.fd` | 构建日志出现 FV 产物，`Mu-caihong.fd` 存在且大小符合 `caihong.conf` 的 `TARGET_FD_SIZE` | **未完成**（闸门关闭 + 工具链缺失 + 上次执行即失败） |
| **P3 ABL 交接** | 确定 3 个交接地址并开门 | `CAIHONG_ABL_ADDRESSES_VERIFIED=1` | 地址来自可复现来源（ABL 反汇编/日志/同族对照），并记录在 `docs/bringup-log.md` | **未开始** |
| **P4 真机 UEFI** | 固件在设备上执行 | 屏幕或 UART 输出 | 看到 EDK2 启动日志/Shell 提示符；设备不重启循环 | **未开始（无设备连接）** |
| **P5 Windows PE** | 引导安装介质 | bootmgr → winload.efi | 通过 ACPI 表初始化（无 0x7B/0xA5），进入 PE 界面 | **未开始** |
| **P6 安装与驱动** | 装到 UFS 并可用 | 可用系统 | 桌面出现且输入可用 | **未开始；依赖 G3 驱动，目前不可达** |

> 出口条件刻意写成"现象/产物"，避免"进度百分比"式的自我安慰。

---

## 7. 一页式结论

### 7.1 当前进度

口径说明：百分比是**估算**，按"端到端 Windows 在 caihong 上可用"为 100% 拆分各里程碑，权重按是否卡住后续阶段分配。

| 里程碑 | 权重 | 完成度 | 依据 |
|---|---|---|---|
| M0 事实基座 | 10% | ~90% | 地址表、SoC 识别、镜像解析全部有产物；余下是 Q1/Q3/Q4 澄清 |
| M1 ACPI 骨架 | 10% | ~75% | 5 张表 + DSDT 已过 iasl；平台级 `Sources/*.dsl` 未接入 |
| M2 可编译固件 | 15% | ~50% | `CliffsPkg`/`caihongPkg`/`caihong.conf` 齐备，闸门关闭、从未构建成功 |
| M3 真机 UEFI | 25% | ~2% | 无设备连接、无 ABL 地址 |
| M4 Windows 引导 | 20% | ~0% | 未开始 |
| M5 可用性（驱动） | 20% | ~0% | 无公开驱动 |
| **合计** | 100% | **≈ 25%** | 主要来自 M0–M2 的设计与描述性工作 |

**另一口径**：若只问"能不能马上在设备上看到 Windows"，答案是 **0%**——从未编译出固件、从未刷写、从未引导。

### 7.2 现在能做什么

1. 复现设备事实：解析 dtbo/vendor_boot，得到全部控制器地址与中断号（脚本可重跑）。
2. 生成并通过 iasl 校验 SM8650 的 FACP/APIC/GTDT/DBG2/PPTT，以及最小 DSDT。
3. 继续写 Mu-Qcom 平台移植代码（SoC 包、平台包、board ACPI），不需要设备。
4. 把构建环境搬到 Ubuntu WSL 并尝试真正编译（受 F1 闸门限制，只能到"编译到链接前"）。

### 7.3 现在不能做什么（明确否定）

- ❌ 不能声称 Windows 或 UEFI 已在设备上运行过——**从未发生过**。
- ❌ 不能声称"已支持 caihong"——上游 Mu-Qcom **没有** SM8650，我们的包是本地新增、未编译的骨架。
- ❌ 不能刷机/引导——ABL 地址未知，固件不存在。
- ❌ 不能承诺可用性——GPU/触控/网络驱动无公开实现。
- ❌ 不能声称 Renegade Project 支持 SM8650——本会话未验证。

### 7.4 下一步最小可行动作

1. 换 Ubuntu 22.04 WSL，跑 `setup_env.sh`，把 P2 推到"能产出 FV"。
2. 从 `abl.img` / UEFI 日志 / 同族设备对照，确定 F1 的三个地址。
3. 把 `acpi/caihong/DSDT.dsl` 拆成 `Silicium-ACPI/Platforms/OnePlus/caihong/Sources/*.dsl` 并接入 `DeviceBuild.py`。
4. 补 `Resources/Scripts/caihong.sh`。

---

## 8. 证据来源索引

| 结论 | 证据 |
|---|---|
| 设备身份/构建号 | `E:\1+padpro\linux\d90c9a3b…\padpro\payload\info\getprop.txt`、`manifest.txt`、`date.txt` |
| 内核/面板/触控 | 同上 `kernel.txt`、`cmdline.txt` |
| SoC = Cliffs | `work/dt/vendor_boot/vendor.dts`（由 `scripts/extract_dtb.py` 生成） |
| 无 mainline cliffs | `work/qcom-Makefile.txt` |
| dtbo/vendor_boot 结构 | `work/dt/extract-report.json`（含每个镜像的 sha256 与 header） |
| 控制器地址/GSIV | `work/dt/dtbo/dtbo_idx07_id0_rev0.dts`、`work/dt/vendor_boot/vendor.dts` |
| 与 mainline 地址一致 | `work/sm8650.dtsi`（行号见 §2.5） |
| SM8550 模板常量 | `source/Mu-Qcom-musabcel/Silicon/Qualcomm/KailuaPkg/KailuaPkg.dsc.inc` |
| 构建闸门 | `source/Mu-Qcom-musabcel/Platforms/OnePlus/caihongPkg/caihong.dsc` 第 56–60 行 |
| 构建失败 | `work/build-aston.log` |
| 工具链缺口 | `work/toolcheck.sh` 输出 |
| iasl 校验 | `build/acpi/soc-tables.json`、本会话 iasl 重编译输出 |

**未验证、不作依据**：Renegade Project 站点、openwall 邮件列表、两个 Mu-Qcom fork 与 Renegade 的关系。
