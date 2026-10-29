# 恢复手册：一加平板 Pro（caihong / OPD2404 / SM8650）

本文只讲一件事：**把设备弄回出厂状态**需要什么、风险在哪、每级操作的确认点是什么。

> **边界声明（请先读完这一行）**
> 本项目**至今没有连接过设备，没有执行过任何 fastboot 命令**。本文所有命令都是**流程说明**，不是执行记录；所有"结果"都是**预期**，不是实测。仓库内也不存在任何调用 fastboot 的脚本（`scripts/` 只有 `extract_dtb.py`、`build_soc_acpi.py`、`fdtlib.py`，均为只读提取与 ACPI 生成）。
> 任何人在真机上执行下列操作，风险自负，且**必须逐级人工确认**（见 §7）。

---

## 1. 设备当前状态

| 项 | 值 | 含义 |
| --- | --- | --- |
| 型号 | OPD2404（`ro.product.device=OP5D77L1`） | 国行一加平板 Pro |
| codename | `caihong` | 所有镜像必须匹配这个名字 |
| SoC | SM8650（Cliffs / pineapple） | 与 SM8550、SM8750 的镜像**不通用** |
| build | `U.1f6e972_e4-2216a`（2025-08-25） | 恢复基线版本 |
| 启动状态 | `verifiedbootstate=orange` | Bootloader 已解锁，AVB 不再强制校验 |
| vbmeta 状态 | `vbmeta.device_state=unlocked` | 可刷非签名镜像 |
| 活动槽 | `_b` | **记录此值，它是所有恢复动作的锚点** |
| 序列号 | `67ab95c8` | 多设备环境下用于确认操作对象 |
| 内核 | `6.1.118-android14-11` | 与 `boot.img` 对应用 |
| 系统 | Android 15 / SDK 35 | — |

### 1.1 解锁意味着什么

**能确认的：**

- AVB（Android Verified Boot）已不处于强制模式。`verifiedbootstate=orange` 是"bootloader 已解锁且运行非原厂签名镜像"的状态标识。
- 因此**可以**用 `fastboot flash` 写入非原厂签名的 `boot` / `dtbo` / `vbmeta`，这是本项目一切实验的前提。
- 刷坏 `boot` 不会立刻变成硬砖：只要 bootloader 还能进 fastboot，就能回刷。**前提是 `xbl`/`abl`/`uefi` 这些引导链分区完好。**

**不能确认的（未验证）：**

- 哪些具体功能因解锁而失效（依赖硬件 attestation 的应用、部分流媒体 DRM、OEM OTA 等）。这些是解锁的**通用后果**，但**本机未验证**，本文不把它们当作事实陈述。
- 是否会触发熔断式（eFuse）不可逆标志。**未知。** 一加/OPPO 平台的解锁策略随版本变化，本文不做任何断言。

### 1.2 一句话结论

当前状态是**"可实验"**：刷坏了能靠 fastboot + 出厂镜像回去。真正不可逆的只有 L5 那一档（见 §7），本项目不碰。

---

## 2. 原始工厂镜像清单

全部位于 `E:\1+padpro\oxygenos`，共 50 个文件（下表逐一列出）。字节数为目录实测值。

### 2.1 引导链与安全固件 —— **绝不刷写**

| 文件 | 大小（字节） | 用途 |
| --- | --- | --- |
| `xbl.img` / `xbl_config.img` / `xbl_ramdump.img` | 1,114,112 / 233,472 / 884,736 | 高通引导链第一级（PBL 之后）、其配置、崩溃转储 |
| `abl.img` | 278,528 | Android Bootloader（fastboot 的实现体） |
| `uefi.img` / `uefisecapp.img` | 3,158,016 / 200,704 | UEFI 固件（已确认其中**无可用 ACPI 字符串**）、UEFI 安全应用 |
| `tz.img` / `hyp.img` | 4,141,056 / 1,642,496 | TrustZone / TEE 固件、Hypervisor |
| `aop.img` / `aop_config.img` | 335,872 / 28,672 | Always-On Processor 固件与其配置 |
| `devcfg.img` | 61,440 | 设备配置（含熔丝/密钥相关） |
| `cpucp.img` / `cpucp_dtb.img` | 253,952 / 16,384 | CPU 控制处理器固件与其设备树 |
| `qupfw.img` / `shrm.img` | 61,440 / 139,264 | QUP 固件、资源共享管理固件 |
| `keymaster.img` | 425,984 | 密钥库 TA |
| `featenabler.img` / `imagefv.img` | 106,496 / 106,496 | 特性开关、镜像校验 |
| `engineering_cdt.img` | 1,048,576 | 工程 CDT（分区表配置） |
| `oplus_sec.img` | 872,448 | 厂商安全分区 |
| `modem.img` / `dsp.img` / `bluetooth.img` | 95,776,768 / 67,108,864 / 1,454,080 | 基带固件、音频/传感器 DSP 固件、蓝牙固件（含每机校准数据） |
| `splash.img` / `recovery.img` | 15,298,560 / 104,857,600 | 开机 logo、Recovery（不建议动，但不属"绝不碰"） |

### 2.2 可恢复分区 —— 本项目**只**动这三个

| 文件 | 大小（字节） | 用途 | 为什么可恢复 |
| --- | --- | --- | --- |
| `vbmeta.img` | 8,192 | AVB 元数据（整机校验入口） | 原厂文件在手，回刷即恢复 AVB 状态 |
| `boot.img` | 201,326,592 | 内核 + ramdisk（GKI 布局） | 原厂文件在手，回刷即恢复 |
| `dtbo.img` | 25,165,824 | 设备树 overlay 分区（含 8 个索引，索引 7 为活动项） | 原厂文件在手，整分区回刷 |

> `dtbo.img` 是**整分区镜像**（含全部索引），不是单个 overlay。所以"擦掉 `dtbo_<slot>` 再回刷"是可行的，但**必须回刷这个完整的 24 MiB 文件**，不能只回刷某一个索引。

### 2.3 系统与动态分区 —— 用于整体恢复，不用于日常实验

| 文件 | 大小（字节） | 用途 |
| --- | --- | --- |
| `payload.bin` | 5,762,227,089 | **完整 OTA 载荷**，动态分区的权威来源 |
| `super.img` | **不存在** | 目录中**没有**独立的 super 镜像；动态分区已以拆开形式提供（见下） |
| `system.img` / `system_ext.img` | 663,449,600 / 941,678,592 | system / system_ext 逻辑分区 |
| `product.img` / `vendor.img` | 7,000,064 / 1,047,605,248 | product / vendor |
| `odm.img` | 1,617,698,816 | odm |
| `vendor_boot.img` | 201,326,592 | vendor_boot（**内含本项目事实来源的 vendor DTB**） |
| `init_boot.img` | 8,388,608 | init_boot（GKI 的 generic ramdisk） |
| `system_dlkm.img` / `vendor_dlkm.img` | 14,479,360 / 37,445,632 | 可加载内核模块（系统 / 厂商） |
| `my_bigball.img` / `my_heytap.img` | 782,254,080 / 895,021,056 | 厂商 my_* 逻辑分区 |
| `my_stock.img` / `my_product.img` | 750,866,432 / 400,125,952 | 厂商 my_* 逻辑分区 |
| `my_preload.img` / `my_region.img` / `my_manifest.img` | 108,068,864 / 737,280 / 421,888 | 厂商预装、区域定制、清单 |
| `my_carrier.img` / `my_company.img` / `my_engineering.img` | 335,872 各 | 运营商 / 公司 / 工程定制 |
| `vbmeta_system.img` / `vbmeta_vendor.img` | 8,192 / 4,096 | system / vendor 的 AVB 元数据 |

### 2.4 用 `payload.bin` 重建完整出厂状态

`payload.bin` 是 OTA 载荷，包含动态分区的数据。用 `payload-dumper` 一类社区工具解包（常见实现的入口脚本名为 `payload_dumper.py`），可得到每个动态分区的镜像以及 `payload_properties.txt`。

要点：

- **`payload.bin` 是唯一能保证分区内容与出厂一致的来源**，因为它是签名载荷；而目录中拆开的 `.img` 是它的展开结果（是否与 `payload.bin` 逐字节一致 **未验证**）。
- 解包后可用 `fastboot flash <逻辑分区名>` 逐个回刷，或先合成为 `super.img` 再整刷（合成需要 `lpmake` 一类工具，且需正确的分区组与大小参数——**本项目未做过，未验证**）。
- 解包出的分区数量应为 §2.3 中的动态分区集合。**不要**把 `payload.bin` 直接 `fastboot flash` 到任何分区，它不是分区镜像。

### 2.5 一个重要缺口

镜像目录中**未见 firehose programmer**（`prog_firehose_ddr.elf` 一类的 `.elf`/`.mbn` 文件）。这意味着：**一旦失去 fastboot（引导链损坏），本项目没有已确认的 EDL/9008 救砖手段。** 该能力是否存在：**未知**；定论方法是检查 OEM 完整服务包或 Qualcomm 授权工具链。

---

## 3. 已有的恢复路径证据

### 3.1 来源

`caihong-linux-rootfs` README（以下简称"那份 README"）给出了安装 Linux 的完整流程。本项目引用它**只作为"恢复路径存在"的证据**，不代表本项目执行过。

### 3.2 那份 README 的刷写序列

```sh
fastboot devices
fastboot getvar current-slot

fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img

LINUX_SLOT=b
fastboot erase "dtbo_${LINUX_SLOT}"
fastboot flash "boot_${LINUX_SLOT}" "<caihong-boot-*.img>"
fastboot flash linux "<rootfs 镜像>"
fastboot --set-active="$LINUX_SLOT"
fastboot reboot
```

### 3.3 为什么这条路径是可逆的

| 被改动的对象 | 改动内容 | 恢复动作 | 恢复材料是否在手 |
| --- | --- | --- | --- |
| `vbmeta` | 以 `--disable-verity --disable-verification` 刷入，关闭 AVB 校验 | 回刷原厂 `vbmeta.img`，**不带**这两个 flag，恢复原始校验状态 | ✅ `vbmeta.img`（8,192 字节） |
| `boot_<slot>` | 换成 Linux 内核 | 回刷原厂 `boot.img` 到同一槽 | ✅ `boot.img`（192 MiB） |
| `dtbo_<slot>` | 被 `erase` 清空 | 回刷原厂 `dtbo.img` 到同一槽（整分区 24 MiB） | ✅ `dtbo.img` |
| active slot | `--set-active` 切到 Linux 槽 | `fastboot --set-active=<原槽>` 切回（当前原槽 = `b`） | ✅ 已记录 |

**关键点**：据那份 README 的命令形式（`flash vbmeta` 不带 `_<slot>` 后缀，而 `boot`/`dtbo` 带）推断，这台设备的 `vbmeta` 是**单实例分区**（不是 `vbmeta_a`/`vbmeta_b`）——**此为推断，未在设备分区表上核实**（见 §10）。若成立，则关闭 AVB 影响的是整机校验入口；回刷原厂 `vbmeta.img` 就能整体恢复。这也是为什么 §2.2 把它列为"可恢复"——**前提是原厂文件一定在手，且 SHA-256 已核对**。

### 3.4 关于槽位的建议

设备当前活动槽是 `_b`，Android 在 `b`。那份 README 的例子用 `LINUX_SLOT=b`，但那会**覆盖 Android 的 `boot_b`**。

**建议：把实验系统放到非活动槽（当前即 `a`）**，让 Android 槽保持完整。这样失败时 `fastboot --set-active=b` 一条命令就能回 Android，`boot_a`/`dtbo_a` 与 `boot_b`/`dtbo_b` 互不影响；但 `vbmeta` 是共享的，仍需按 §3.3 恢复。（以上为**基于分区布局的推理**，未在真机验证。）

### 3.5 恢复命令（**示例，勿直接粘贴**）

```sh
# 前提：已确认序列号 67ab95c8、已确认原活动槽
fastboot devices
fastboot getvar current-slot          # 预期 b

fastboot flash vbmeta vbmeta.img      # 不带 --disable-verity/--disable-verification
fastboot flash boot_a boot.img
fastboot flash dtbo_a dtbo.img
fastboot --set-active=b
fastboot reboot
```

`fastboot flash dtbo_a dtbo.img` 是否会因分区大小/稀疏格式报错：**未验证**。若报错，先 `fastboot erase dtbo_a` 再刷。

---

## 4. 分区保护原则

一句话：**只动 `boot` / `dtbo` / `vbmeta`，其余一律不碰。**

### 4.1 绝对不碰（写了就可能不可逆）

| 分区 | 原因 |
| --- | --- |
| `xbl`、`xbl_config`、`abl`、`uefi`、`uefisecapp` | 引导链本体。写坏 = 失去 fastboot，而本项目**没有已确认的 EDL 手段**（§2.5） |
| `tz`、`hyp`、`aop`、`aop_config`、`devcfg`、`cpucp`、`qupfw`、`shrm` | 安全/协处理器固件。与熔丝、密钥、电源时序耦合，写错可能永久不可启动 |
| `keymaster`、`oplus_sec`、`featenabler` | 安全与授权相关 |
| `modem`、`dsp`、`bluetooth` | 基带与 DSP 固件，含每台设备独有的校准数据 |
| **`persist`** | 含 Wi-Fi/BT MAC、传感器校准、指纹等**每机唯一**数据。**丢了不可重建** |
| **`sensor`** / **`calibration`** | 传感器与屏幕校准数据 |
| **`modemst1` / `modemst2` / `fsg`** | 基带持久化数据（IMEI 相关）。**写坏可能永久失去蜂窝能力**；本机是否存在：未知 |
| `engineering_cdt`、`xbl_ramdump`、`imagefv` | 分区表配置、崩溃转储、镜像校验 |

> 平板没有蜂窝模组时，`modemst1`/`modemst2`/`fsg` 仍可能存在（高通平台的通用布局），**是否存在于本机：未知**。不确定时，**不要**对它们执行任何 `erase` 或 `flash`。

### 4.2 可动（有原厂镜像兜底）

| 分区 | 恢复材料 |
| --- | --- |
| `boot_<slot>` | `boot.img` |
| `dtbo_<slot>` | `dtbo.img` |
| `vbmeta` | `vbmeta.img` |
| `linux` / `userdata`（仅重装系统时） | 见 §2.3；`userdata` 会丢用户数据 |

### 4.3 灰区（需单独评估，不在本项目范围）

`splash`（开机 logo）、`recovery`、`init_boot`、`vendor_boot`、`system_dlkm` / `vendor_dlkm`。写坏了通常还能靠 fastboot 恢复，但会改变系统行为，不属于"最小实验面"。

---

## 5. 前置检查清单

**每一条都必须是 ✅，否则不要开始。** 这份清单的目的不是流程感，而是让"可恢复"这个前提真的成立。

### 5.1 备份

- [ ] 设备内重要数据已备份（照片/文档/微信等），且**已验证备份可读**
- [ ] `E:\1+padpro\oxygenos` 全目录已另存一份（至少 `vbmeta.img`、`boot.img`、`dtbo.img`）
- [ ] 三个关键镜像的 SHA-256 已计算并记录（`Get-FileHash -Algorithm SHA256`）
- [ ] 已把"原活动槽 = `b`"写进操作记录
- [ ] 已保存 `fastboot getvar all` 的完整输出（当前状态快照，出问题时可对照）

### 5.2 镜像正确性

- [ ] 镜像来自本机的 SM8650 / `caihong` 出厂包，不是 SM8550 或其他机型
- [ ] 可用 `scripts/extract_dtb.py` 从 `dtbo.img` 或 `vendor_boot.img` 解出 DTB，确认面板串包含 `qcom,mdss_dsi_panel_csot_nt36532_2120_3000_dual_dsc_144hz_vid`
- [ ] 确认 `boot.img` 内内核版本与设备当前内核（`6.1.118-android14-11`）属同一构建线
- [ ] **未验证项**：这批镜像与 build `U.1f6e972_e4-2216a` 是否逐分区一致（未比对过 hash）

### 5.3 工具与环境

- [ ] `fastboot` 可用（`fastboot --version` 有输出）
- [ ] Windows 侧 USB 驱动正常（`fastboot devices` 能看到 `67ab95c8`；**未验证**实际是否显示该串号）
- [ ] 使用**数据线**而非充电线；直连主板后置 USB 口，不经 hub
- [ ] 设备电量 > 50%（刷写中途断电是最常见的变砖原因之一）
- [ ] 已阅读 §4 的分区保护原则，并确认本次操作只涉及 §4.2 的分区

### 5.4 心理与流程

- [ ] 已接受"可能丢失 Android 数据 / 可能需要重装系统"
- [ ] 一次只做一步，每步后确认结果，**不串联执行**
- [ ] 手上有一台能上网的备用设备用于查错

---

## 6. 常用只读诊断命令（零风险）

```sh
fastboot devices                 # 确认连通
fastboot getvar current-slot     # 当前槽
fastboot getvar all              # 全部变量，建议存档
fastboot getvar unlocked         # 解锁状态（变量名随 bootloader 版本可能不同，未知）
```

只读命令**不会写任何分区**。但注意：`getvar all` 的输出可能包含设备唯一标识，分享日志前请自行脱敏。

---

## 7. 风险分级与人工确认点

分级原则：**只看"能否用手中的原厂镜像恢复到操作前状态"**。本项目对每一级都**未执行过**任何操作。

| 级别 | 操作 | 可逆性 | 人工确认点 | 失败模式 | 在本项目范围 |
| --- | --- | --- | --- | --- | --- |
| L0 只读 | `fastboot devices`、`getvar`、`getvar all` | 完全可逆（不改状态） | 确认连的是目标设备（`67ab95c8`） | 无 | 是 |
| L1 单分区写入 | `flash boot_<slot>`、`flash dtbo_<slot>`、`flash vbmeta` | 可逆：回刷原厂镜像即恢复 | ① 原活动槽已记录 ② 目标槽**不是** Android 活动槽（或已明确接受 Android 暂时无法启动）③ 原厂镜像 SHA-256 已核对 ④ 分区名逐字念一遍（`boot_a` ≠ `boot_ab` ≠ `boot`）⑤ 确认没有带多余 flag | 刷错槽 → 该槽无法启动，另一槽仍可启动；回刷即恢复 | 是 |
| L2 擦除分区 | `erase dtbo_<slot>`（那份 README 的流程要求） | 可逆，但**必须回刷** `dtbo.img` 才能恢复该槽 | 同 L1，且额外确认：擦的是**实验槽**的 dtbo，Android 槽的 dtbo 必须保留 | 擦错槽 → 该槽丢失 DTBO，两个系统都无法启动该槽；回刷 `dtbo.img` 可恢复 | 是 |
| L3 切换活动槽 | `fastboot --set-active=<slot>` | 可逆：再切回去即可（前提：目标槽有可启动镜像） | ① 记录切换**前**的槽 ② 确认目标槽内有可启动镜像 ③ 切换后立刻 `getvar current-slot` 复核 | 切到空槽 → 启动失败但停在 bootloader，可用 fastboot 切回。**这是可恢复的，不要慌** | 是 |
| L4 大分区 / 分区表 | `flash linux <rootfs>`、`flash userdata <rootfs>`、在 recovery 里用 `parted` 重新分区 | **部分可逆**：内容可用 §2.3 镜像重建，但**用户数据丢失**；分区表改动需手工还原 | ① `parted print` 输出已存档 ② 原 `userdata` 起点**未改变** ③ 分区名严格为 `linux` / `userdata` ④ 容量大于镜像逻辑大小 ⑤ 已接受数据全失 ⑥ **由人逐字确认将要删除的分区编号** | 分区表写坏 → 可能无法挂载 userdata 甚至无法启动；需重刷动态分区并重建分区表 | 仅限明确需要时 |
| L5 不可逆 / 高危 | 任何针对 §4.1 分区的 `flash` / `erase`，尤其 `xbl`、`abl`、`uefi`、`tz`、`devcfg`、`persist`、`modemst1`、`modemst2`、`fsg` | **可能不可逆**：失去引导链 = 失去 fastboot；失去 `persist`/`modemst*` = 每机唯一数据永久丢失；本项目**无已确认的 EDL 手段**（§2.5） | **本项目不提供。不执行。** 若确有必要，必须先证明存在可用的 firehose programmer，并准备好完整救砖流程 | 硬砖 / 不可重建数据丢失 | **否** |

---

## 8. 出问题时的判断路径

| 现象 | 判断 | 动作 |
| --- | --- | --- |
| 能进 Android | 无需恢复 | 无 |
| 能进 fastboot（`fastboot devices` 有响应） | 引导链完好，只是某个槽的镜像坏了 | 按 §3.5 回刷 `vbmeta` / `boot_<slot>` / `dtbo_<slot>`，再 `--set-active` 回原槽 |
| 卡在开机 logo，但能进 fastboot | 同上（多为 boot 或 dtbo 不匹配） | 同上 |
| 循环重启，fastboot 时有时无 | 可能 `boot` 反复崩溃 | 立即回刷原厂 `boot_<slot>`，不要反复尝试启动 |
| **完全无法进 fastboot**，仅 9008/EDL 可能可用 | 引导链或 XBL 层损坏 | **本项目无手段。** 需 firehose programmer（目录中未见，§2.5）或送修 |
| 完全无响应、无 9008 | 硬件级问题 | 送修 |

> 第一条永远是：**先停下，别再刷。** 每多刷一次，可恢复状态就少一分。冷静下来对照 §5 的清单，确认到底改了什么。

---

## 9. 本项目与刷写的边界

- 本仓库的 `scripts/` 里**没有**任何 `fastboot` 调用（已核查：`extract_dtb.py` 只从镜像里提取 DTB；`build_soc_acpi.py` 只生成 ACPI 表；`fdtlib.py` 是纯解析库）。
- 本项目产出的是 `build/acpi/*.aml`（DSDT/FACP/APIC/GTDT/DBG2/PPTT）——**这些表目前只经过 iasl 编译验证，从未被放进任何 UEFI 固件，也从未在设备上加载过**。
- 本项目**不提供**刷机脚本、不自动化任何 flash 步骤。本文的命令必须由人**逐条**复制、**逐条**确认。
- 截至本文写作时：**未连接设备、未执行任何 fastboot 命令、未刷写任何分区、未启动任何自建镜像。**

---

## 10. 待确认事项清单

| 事项 | 现状 | 定论方法 |
| --- | --- | --- |
| 镜像与 build `U.1f6e972_e4-2216a` 是否逐分区一致 | 未验证 | 逐分区 SHA-256 比对 |
| `fastboot devices` 是否显示 `67ab95c8` | 未验证 | 首次连接时观察 |
| 是否存在 EDL / firehose programmer | **未知** | 检查 OEM 完整服务包；联系售后 |
| `modemst1`/`modemst2`/`fsg` 是否存在于本机 | **未知** | `fastboot getvar all` 或分区表输出 |
| `vbmeta` 是否为单实例分区（无 `_a`/`_b`） | **未验证**（据 README 命令形式推断） | `fastboot getvar all` 或分区表输出中查 `vbmeta` 是否有槽后缀 |
| 解锁导致的功能损失范围 | 未验证 | 实机观察（非本项目优先级） |
| `fastboot erase dtbo_a` 后回刷整分区是否一次成功 | 未验证 | 真机操作时记录 |
| `boot.img` 与设备内 `boot_b` 是否同版本 | 未验证 | 比对内核版本与 hash |
