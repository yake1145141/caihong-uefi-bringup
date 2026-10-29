# OnePlus Pad Pro (caihong) — Windows/UEFI 移植实录

> 一加平板 Pro（`caihong` / OPD2404 / SM8650 "Cliffs"）上尝试运行自建 UEFI 固件，
> 并朝着 Windows on ARM 推进的**完整工程记录**。
>
> 这份仓库的主体不是"成功的成果"，而是**一份带证据的失败地图**：哪些路走通了、
> 哪些被证伪、每个结论背后是哪一个实验。所有硬件结论都来自真机实测。

---

## 一句话现状

**UEFI 固件能在真机上运行，PrePi 全流程与 DxeCore 核心服务均已跑通，
但从未进入 BDS 启动菜单，屏幕上从未出现过任何图形化 UEFI 界面，更未涉及 Windows。**

当前阻塞点：参考固件在 DXE 派发过程中屏幕被清空 / 流程停住（见
[`docs/bringup-log.md`](docs/bringup-log.md) B25）。

---

## 目标设备（全部已核实）

| 项目 | 值 | 证据来源 |
| --- | --- | --- |
| 型号 | OnePlus OPD2404 / `OP5D77L1` | `ro.product.*` |
| 代号 | `caihong` | bootloader |
| SoC | SM8650（平台名 `pineapple`，QCOM 代号 LanaiLAA） | 设备固件 |
| Android | 15（SDK 35），kernel 6.1.118-android14-11 | `getprop` |
| 槽位 | `_b`，bootloader 已解锁 | `getprop ro.boot.slot_suffix` |
| GICv3 分发器 | `0x17100000`，GICR `0x17180000` | 设备 DTB |
| 架构定时器 | 19.2 MHz，PPI 13/14 → GSIV 29/30 | 设备 DTB |
| UFS | `0x1D84000`，GIC_SPI 265 → GSIV `0x129` | 设备 DTB |
| 显示 | 3000×2120，面板 CSOT NT35652（内核侧名 `nt36532`） | 面板 XML + qdcm JSON |
| 显示保留区 | `0xD5100000`，长 `0x02B00000` | XBL 区域表 |

更完整的数据见 [`docs/hardware-matrix.md`](docs/hardware-matrix.md)、
[`docs/hw-sm8650-caihong.json`](docs/hw-sm8650-caihong.json)、
[`docs/abl-memory-map.json`](docs/abl-memory-map.json)。

---

## 已验证成立的事实

以下每条都有真机证据，不是推测：

### 1. 两道加载门槛

| 门槛 | 现象 | 处理 |
| --- | --- | --- |
| **vbmeta 校验** | `Failed to load/authenticate boot image: Load Error` | 需要 `fastboot --disable-verity --disable-verification flash vbmeta` |
| **boot image 头部必须 v4** | v1 镜像 6 秒回 fastboot；v4 才会被接受 | `mkbootimg --header_version 4` |

### 2. 启动链

```text
ABL → BootShim（复制固件卷到目标地址并跳转）→ PrePi → DxeCore → DXE 派发 → …
```

`fastboot boot` 与 `fastboot flash boot_b` **两种方式都能启动自建固件**（已实测）。

### 3. PrePi 全流程通过（22 个里程碑）

用屏幕进度条逐步验证，全部通过：GICR 唤醒、内存区域定位、`ArchInitialize`、
Debug Agent、`HobConstructor`、**`MemoryPeim`（开 MMU + 建内存 HOB）**、
`BuildStackHob`/`BuildCpuHob`、`PlatformPeim`、`EnableMemoryProtection`、
库构造函数、固件卷处理等。

### 4. DxeCore 能加载并完成核心初始化

内存服务、GCD、事件服务、调度器初始化均成功；`ArmCpuDxe`、`ArmGicDxe`、
`MetronomeDxe`、`ArmTimerDxe` 等驱动能正常加载——**反过来证明 ACPI/MADT 里那套
GIC 与定时器地址是对的**。

### 5. 找到了一个真实崩溃并修复

异常转储：

```text
ESR 0x96000010 → EC=0x25、ISS=0x10 → EA=1（Synchronous external abort）
FAR 0x0C792008 → 落在 AOSS 区域（0x0B000000 + 0x04000000）
```

含义：访问了未上电的外设。根因是参考实现把 `VcsDxe`（电压域管理）入口**整体打桩**，
导致电压域从未初始化。换回本机原版 `VcsDxe`/`RscDxe` 后**崩溃消失**
（不再进入 900E 诊断模式）。

---

## 已被证伪的结论（不要重复踩坑）

| 曾经的判断 | 证伪方式 | 结论 |
| --- | --- | --- |
| `fastboot boot` 在这台 ABL 上不可用 | vbmeta 修复后重测 | **可用** |
| 内存映射应当沿用 SM5470/aston 布局 | 换成本机 XBL 区域表后 `MemoryPeim` 才通过 | 必须用本机区域表 |
| `EnvDxe` 失败是因为 `uefiplat.cfg` 缺区域 | 参考实现文档注明该报错是正常噪声 | 过度解读，非根因 |
| LZMA 失败是因为 scratch 缓冲只有 64 KB | 按字典大小动态推算后仍失败 | 该缺陷真实存在但**不是**根因 |
| UFS 失败是驱动版本不匹配 | 换成本机同版本驱动后错误相同 | 不是版本问题 |
| UFS 失败是 `fastboot boot` 不初始化存储 | 改用 flash + 正常启动，错误相同 | 不是启动方式问题 |
| 黑屏是 `VcsDxe` 关屏 | 打桩确认已生效后仍黑屏 | 另有原因（后定位为外部中止，已修） |

---

## 可观测性：没有串口怎么办

本机没有可接触的调试串口。本项目发展出三套行之有效的手段：

1. **帧缓冲纯色探针** —— 写一个 100 字节级的裸 AArch64 载荷，把
   `0xD5100000` 填成纯色后死循环。用于证明"ABL 真的跳转了"、"这块内存可写"。
2. **进度条里程碑** —— 在固件每个阶段把屏幕画成 N 条白条，**条数就是步号**。
   比颜色可靠得多（曾经因为"纯绿"和"春绿"肉眼看不出差别而误判过两轮）。
3. **DEBUG 文字日志** —— `SiliciumPkg.dsc.inc` 里 `SerialPortLib` 在 RELEASE 下是
   `Null`，**换成 `-r DEBUG` 才会把日志画到面板上**。这是本项目最重要的工具，
   配合 `PcdDebugPrintErrorLevel = 0x80000040` 只显示错误/警告，错误就不会被刷走。

相关脚本：`scripts/fbtest.S`、`scripts/make_fbtest.sh`、`scripts/shimprobe.S`、
`scripts/mark_reference_dxe.py`、`scripts/mark_reference_bds.py`。

---

## 参考实现（关键）

本项目后期转向以一处**同设备的已知可工作实现**为基线：

- [`Axiang-dev/uefi-caihong`](https://github.com/Axiang-dev/uefi-caihong) ——
  caihong 的完整 UEFI 工程（板级包 + 原厂驱动 + 二进制补丁 + 构建脚本），
  状态是"能进 BDS 启动菜单"
- [`Axiang-dev/UniXNU-caihong`](https://github.com/Axiang-dev/UniXNU-caihong) ——
  同设备的 XNU（macOS/iOS 内核）移植，含完整交接文档与踩坑记录

**重要教训**：该工程自带的 `scripts/build.sh` 开头会 `git checkout -f` 重置父树、
并用 `cp -r` 覆盖板级包，**会静默冲掉任何自定义改动**。本项目因此改用
`scripts/build_caihong_custom.sh`（跳过 checkout，直接驱动 `build_uefi.py`）。

---

## 目录结构

```text
docs/
  bringup-log.md        # 主记录，B0–B25，按时间顺序，含每一步的证据
  feasibility.md        # 可行性分析
  hardware-matrix.md    # 硬件清单与地址
  recovery.md           # 刷机与回滚流程（动手前必读）
  source-audit.md       # 上游源码/驱动的审计结论
  hw-sm8650-caihong.json
  abl-memory-map.json   # 从 xbl_config.img 提取的 41 项内存区域表
patches/
  0001-*.patch          # Mu-Qcom 的 caihong 板级包
  0002-*.patch          # Silicium ACPI 表
  0003-*.patch          # Mu_Basecore LZMA scratch 尺寸（真实缺陷，非本机根因）
scripts/                # 提取、构建、探针、诊断脚本（42 个）
```

---

## 如何构建

板级包基于 Mu-Silicium（上游 Project-Silicium）。参考实现的构建方式：

```bash
git clone https://github.com/Project-Silicium/Mu-Silicium.git uefi
cd uefi && git checkout <commit>
# 套用 patches/ 与板级包，放入 Binaries/caihong（原厂提取的 .efi）
python build_uefi.py -d caihong -r DEBUG
```

产物 `Mu-caihong-0.img`，用 `fastboot boot Mu-caihong-0.img` **内存启动，不写分区**。

> 在 Python 3.10 上需要 `scripts/fix_tomllib.sh` 提供 `tomllib` 兼容层。

---

## 安全与恢复

**动手前请先读 [`docs/recovery.md`](docs/recovery.md)。**

- 全流程优先使用 `fastboot boot`（纯内存，零写入）
- 必须写分区时只碰 `boot_b`，且事先完整备份
- 本项目的所有测试都在 `boot_b` 上进行，并已验证可完整回滚到原厂状态

---

## 诚实的边界

- 屏幕上**从未出现过** UEFI 界面、启动菜单或 Windows
- 没有任何 Windows 驱动被编写或验证
- GPU / Wi-Fi / 音频 / 触控在 UEFI 下均未工作
- 部分结论来自对**闭源厂商驱动的字符串分析与行为观察**，不是源码级确认

---

## 许可

MIT（见 `LICENSE`）。文档中的设备数据来自本机固件提取，不含任何专有二进制。
