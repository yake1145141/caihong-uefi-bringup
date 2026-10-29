# 硬件矩阵：一加平板 Pro（caihong / OPD2404 / SM8650）

本文是 `caihong-windows` 项目的硬件事实与可行性基线。它回答两个问题：**这块板子上到底有什么**（可追溯到设备自身固件），以及**Windows on ARM 这条路对每一块硬件走到了哪一步**。

## 0. 阅读前必须知道的三件事

1. **本机没有连接任何设备。** 没有启动过、没有刷写过、没有进过 fastboot / EDL、没有跑过 Windows。本表所有"Windows 侧状态"都是**纸面评估**，不是测试结果。
2. **因此本表没有任何一行是 `已验证正常`。** 该值只出现在下面的枚举定义里，行数为 0。同样，`已有可复用的 Windows ARM64 驱动` 的行数也是 0——不是"没用上"，而是"确认不存在"。
3. 凡是推断、未核实、未知的地方，本文一律写 `未验证` / `未知`，并给出**什么证据能把它变成确定结论**。宁可空着，不编。

## 1. 状态枚举

`Windows 侧状态` 列只能取以下六个值之一：

| 值 | 含义 | 判定门槛 |
| --- | --- | --- |
| 已验证正常 | 在本机上实机验证通过 | 需要一次真实启动并观察到功能。**当前 0 行** |
| 已有可复用的 Windows ARM64 驱动 | 公开可获取、可合法分发的现成驱动 | 需要驱动二进制或源码在手。**当前 0 行** |
| 需要板级适配 | 有生态先例（HID/资源格式可沿用），主要工作是把 ACPI/资源/引脚按本机重做 | 不等于"有可用驱动"，只是"接口形状已知" |
| 需要新驱动 | 没有可用驱动，但接口是标准的，理论上可由第三方实现 | 例如 HID-over-I²C 这类通用栈 |
| 暂时没有可行实现 | 缺公开驱动/固件/文档路径，或强依赖闭源 BSP | 当前最大的几块都落在这一档 |
| 尚未测试 | 路径已就位、只差上机 | 需要上机才能翻案 |

## 2. 证据来源

| 编号 | 来源 | 提供什么 | 可靠性 |
| --- | --- | --- | --- |
| E1 | `dtbo.img` 索引 7（活动 overlay，据 getprop） | 板级覆盖层：PMIC 子设备、面板、时钟 | 设备自身签名固件，高 |
| E2 | `vendor_boot.img` 内的 vendor DTB | SoC 级地址/中断/定时器/CPU 拓扑 | 设备自身签名固件，高 |
| E3 | `boot.img` | 内核版本 `6.1.118-android14-11` | 高 |
| E4 | `getprop` | 型号、device、slot、`ro.boot.*`、`device_info.ddr_info` | 高（设备运行时） |
| E5 | `uefi.img`（3,158,016 字节） | 无可用 ACPI 字符串（已确认读不出） | 高（否定性结论） |
| E6 | 上游 SM8550（"Kailua"）ACPI 表集 | FACP/APIC/GTDT/DBG2/PPTT 的起点模板 | 中（需逐项断言，见 §6） |
| E7 | Mu-Qcom（musabcel / liliumbeta 两个 fork） | Windows 驱动先例，最高 SM8450/SM8550 | 中（无 SM8650） |
| E8 | WOA-Project/windows_silicon_qcom_lanai | 仅 README + 2 个 md，无代码；面向 QRD | 低（README 自称"一切非功能"） |
| E9 | `caihong-linux-rootfs` README | Linux 侧状态的**唯一**来源 | 中（他项目自述，未在本机复现） |
| E10 | 本仓库 `build/acpi/*.aml` | 已生成、iasl 编译通过的表 | 高（编译层面）／低（运行层面） |

## 3. 设备身份（已核实）

| 项 | 值 | 来源 |
| --- | --- | --- |
| 产品 | OnePlus Pad Pro（国行） | E4 |
| 型号 | OPD2404 | E4 |
| `ro.product.device` | `OP5D77L1` | E4 |
| codename | `caihong` | E4 |
| SoC | SM8650，Qualcomm codename **Cliffs**，Android platform **pineapple** | E2（`qcom,cliffs-pinctrl`）+ E4 |
| Android | 15 / SDK 35 | E4 |
| build | `U.1f6e972_e4-2216a`（2025-08-25） | E4 |
| 内核 | `6.1.118-android14-11` | E3 |
| bootloader | 已解锁：`verifiedbootstate=orange`、`vbmeta.device_state=unlocked` | E4 |
| 活动槽 | `_b` | E4 |
| 序列号 | `67ab95c8` | E4 |
| 内屏 | 3000×2120 | E1/E2 |
| 面板驱动串 | `qcom,mdss_dsi_panel_csot_nt36532_2120_3000_dual_dsc_144hz_vid` | E1 |
| 触摸 IC | `novatek,nf_nt36532` | E1/E2 |
| 存储 | UFS，控制器 `ufshc@1d84000`；`sda` = 245,223,424 块 ≈ 234 GB | E2/E4 |
| 内存容量 | **未知**（见 §8） | — |

## 4. 主表

> "Linux 侧状态"一律引自 `caihong-linux-rootfs` README（E9），是**他项目的自述**，本项目未复现、也不为其背书。

| 硬件模块 | 已核实的硬件事实（来源） | Linux 侧状态（来自 caihong-linux-rootfs README） | Windows 侧状态（六选一） | 依据与缺口 | 下一步验证方法 |
| --- | --- | --- | --- | --- | --- |
| CPU / 多核 | 8 核 3 cluster，DTB `cpuidle-domain` 的 cpu-map 为 **3 / 4 / 1**；所有 CPU 的 compatible 均为 `qcom,kryo`，**无 part number 字符串**，故 X4/A720/A520 的精确分布未验证（E2） | CPU 调频正常，默认关闭 3.3024 GHz boost；s2idle 与深度休眠恢复可用 | 需要板级适配 | DSDT 已声明 `CPU0..CPU7`（ACPI0007，`_UID` 0..7），PPTT 已生成。Windows 侧 CPU 由内核/HAL 驱动，不需要厂商驱动，属于纯"板级描述"工作。风险点是拓扑按 SM8550 推导 | 8 核全部 online；比对 ACPI PPTT 与 DTB `cpu-map`；读各核 MPIDR |
| GIC（GICv3） | `interrupt-controller@17100000`：GICD 0x17100000+0x10000，GICR 0x200000 @ 0x17180000，`#interrupt-cells=3`（E2） | README 未单列；系统能启动即隐含 GICv3 工作（推断，未在本机验证） | 需要板级适配 | FACP/APIC 已重定目标并断言 GICD/GICR 基址存在，iasl 编译通过。**MADT 里三个 redistributor 基址继承自 SM8550，是本项目唯一未验证字段**（见 §5.1） | 读每个 redistributor 的 `GICR_TYPER.Affinity_Value`；或 8 核全部 online |
| 架构定时器 / 平台定时器 | `arm,armv8-timer` 19.2 MHz；PPI 13/14 → GSIV 29/30；hypervisor PPI 11/12；平台定时器 `frame timer@17420000`（`arm,armv7-timer-mem`）、`gh-qtimer@17425000`（E2） | README 未单列（推断同 GIC） | 需要板级适配 | GTDT 已生成，且对 0x17420000、GSIV 29、GSIV 30 的断言全部 PASS。定时器由 HAL 使用，无厂商驱动 | 启动后系统时间不漂移；观察是否卡在 timer 校准阶段 |
| UFS | `ufshc@1d84000`：reg 0x1d84000+0x3000 / 0x1d88000+0x8000 / 0x1d90000+0x9000 / 0x1da5000+0x2000 / 0x1da4000+0x10；IRQ `<0 265 4>` → **GSIV 0x129**（E2/E4） | UFS 可用，MCQ 已启用（实测日志：9 个硬件队列、最大深度 64）；设备专属完整频率表待补 | 需要板级适配 | DSDT 已声明 `UFS0` = `QCOM24A5`，子设备 `DEV0` `_ADR` 0x08，`_CRS` 覆盖 0x1D84000+0x23000、IRQ 0x129，HID/资源格式沿用 Mu-Qcom 先例。**缺口：是否存在 SM8650 的 Windows UFS 驱动——未验证**。Mu-Qcom 最高 SM8550，其驱动是 Qualcomm BSP 二进制（不可再分发，且无 SM8650 版本）。若无该驱动，本行应升级为"需要新驱动" | Windows PE 下看设备管理器是否出现 `QCOM24A5` 节点；若无法枚举，改用 USB 存储做安装介质（依赖下一行） |
| USB3 / Type-C | `ssusb@a600000` reg 0xa600000+0x100000；`dwc3@a600000` reg 0xa600000+0xd93c；IRQ `<0 133 4>` → **GSIV 0xA5**；`ro.boot.usbcontroller=a600000.dwc3`（E2/E4） | USB host/device 控制器与 DP Alt Mode 可用 | 需要板级适配 | DSDT 已声明 `USB0` = `QCOM0C8B`。但 Type-C role switch、redriver、DP alt-mode 均未描述（DSDT 明确标记 TODO）。即使控制器驱动可用，没有连接器/GPIO 描述也触发不了角色切换与 DP 输出 | PE 下热插拔 U 盘（device 模式）与 OTG（host 模式）；`usbview` 看 xHCI 是否枚举出根端口 |
| 内屏面板 | 3000×2120；`qcom,mdss_dsi_panel_csot_nt36532_2120_3000_dual_dsc_144hz_vid`（CSOT 面板 + Novatek NT36532 + 双 DSC + 144 Hz video mode）；`mdss_mdp@ae00000`（reg 0xae00000+0x84000 / 0xaeb0000+0x2008 / 0xaf80000+0x7000 / 0x400000+0x2000，IRQ `<0 83 4>`）、`mdss_dsi_ctrl0@ae94000`、`mdss_dsi_phy0@ae95500`（E1/E2） | 3000×2120 内屏与亮度调节正常；60/72/96/120 Hz 可无感切换，144 Hz 仍需黑屏模式切换；偶发小面积花屏 | 暂时没有可行实现 | **单点最大阻塞。** DSDT 未声明显示控制器；Windows 需要 WDDM 显示 miniport（DPU/DSI）+ 面板时序与初始化序列 + 背光控制。公开生态中不存在 SM8650 的 WDDM 驱动；DSI 面板在 Windows 上要么由驱动内置参数、要么由 ACPI `_DSD` 提供，两者都没有。没有显示，连安装器界面都看不见 | 无独立可执行验证。前置条件是出现 SM8650 WDDM miniport，或存在可用的 UEFI GOP（只能点亮简单 framebuffer，未验证） |
| GPU | SoC 集成 Adreno GPU（SM8650 平台命名对应 Adreno 750；README 仅称 "Adreno GPU"）；DSDT 未声明任何 GPU 节点（E1/E2/E10） | GPU 与显示同列："基本正常" | 暂时没有可行实现 | **没有公开的 Windows ARM64 Adreno 750 驱动。** WDDM 渲染驱动与显示 miniport 通常成对交付，两者皆缺。Linux 侧是 MSM/KGSL（DRM 架构），**不能**当 Windows 驱动复用 | 只能等 OEM 授权或 BSP 出现；否则无路径 |
| 触摸屏 | 触摸控制器 `novatek,nf_nt36532`，与显示驱动 IC 同一颗 NT36532；**I²C 总线实例与从地址尚未从 overlay 解析（未知）**（E1/E2） | 10 点触控、悬停、压感、绘画、休眠恢复、磁吸充电与首次自动配对已验证 | 需要新驱动 | DSDT 未声明触摸设备。理论唯一现实路径是 HID-over-I²C（Windows 内置 HIDI2C），但需要三样都不存在的东西：正确的 GENI QUP I²C 控制器 ACPI 描述（其 _HID 未核实）、触摸设备的 `_HID`/`_DSD`（HID 描述符寄存器地址）、NT36532 的 report descriptor | 先从 overlay 解出 i2c 总线号与从地址；再取 NT36532 的 HID 描述符；确认 Novatek 是否提供 Windows HID 驱动（未知） |
| 手写笔 | 依赖触摸 digitizer + 蓝牙 + 磁吸线圈；README 提到用 CPS8601 磁吸事件校验地址后配对、压感、磁吸充电（E9） | 压感、绘画、休眠恢复、磁吸充电与首次自动配对已验证 | 暂时没有可行实现 | 需要"digitizer 可用 + 蓝牙栈可用 + 厂商 AES/BLE 配对协议"三者同时成立，任一缺失即不可用；而这三条在本表分别落在"需要新驱动"和"暂时没有可行实现"。没有公开的第三方实现 | 无。必须先解决触摸屏与蓝牙两行 |
| 磁吸键盘 / 触控板 | Pogo 磁吸（README 描述顶部按键在 Linux 下重映射为 F1–F12，搜索键作 Fn）；DSDT 未声明；**接口总线与控制器未从 DTB 提取（未知）**（E9/E10） | 键盘与触控板可用；按键时触控板可能短暂停顿 | 需要新驱动 | 若是 I²C/USB HID 复合设备，Windows 可走通用 HID 栈；但连接器、供电、中断 GPIO 与 ACPI 描述全缺。属于"标准接口、零驱动零描述" | 先在 Linux 侧用 `lsusb` / `i2cdetect` 确定总线（未在本机执行）；再决定走 HID-over-I²C 还是 HID-over-USB |
| Wi-Fi | DSDT 未声明；**未从 DTB 提取到 WLAN 节点，芯片型号未知**；README 提到 BDF 使用兼容的厂商条目而非 caihong 专属校准（E9/E10） | 联网、硬件 MAC、STA/AP 并发可用；休眠恢复偶尔偏慢 | 暂时没有可行实现 | Windows 需要 WLAN miniport（厂商驱动）+ ACPI 描述（SDIO/PCIe 资源、`_DSD` 里的 MAC/BDF）。Qualcomm WLAN 的 Windows 驱动是 BSP 二进制，不可再分发且无 SM8650 版本 | 先定型号（DTB 中 wifi 节点 / Linux `lspci` / `lsmod`），再查该型号有无公开 Windows ARM64 驱动 |
| 蓝牙 | DSDT 未声明；**芯片型号未知**；README 提到 `caihong-hardware-mac` 从冗余 NVRAM 读回原厂 WLAN/BT 地址（E9/E10） | 扫描、配对、BLE、HID 与手写笔电量可用 | 暂时没有可行实现 | 同 Wi-Fi：需厂商 BT 驱动（通常挂 UART 或 USB）+ ACPI 描述 + 固件 nvm。无 BSP，且 BT 与 Wi-Fi 常为同一颗 combo 芯片 | 同 Wi-Fi；注意 combo 芯片意味着两行同时解或同时不解 |
| 音频 | DSDT 未声明；**ADSP 与 codec 拓扑未提取，型号未知**；README 称未包含 Dolby 与完整原厂调音（E9/E10） | 麦克风与立体声扬声器可用；音量低于原厂 Android | 暂时没有可行实现 | Windows 音频需要音频驱动（ADSP + WSA codec 的 WDM/ACX）+ ACPI 描述（SoundWire/I²S、GPIO、电源域）。全部属 BSP。**音频是继显示之后的第二类硬骨头** | 只能靠 BSP。系统其余部分可用 USB 声卡旁证（未验证） |
| 电池 / 充电 | DSDT 未声明；PMIC 侧仅知 SPMI arbiter 与 PM8550/PM8550B/PM8010 存在（见 PMIC 行）（E1/E10） | 电量显示与已测试的 PPS/VOOC 快充可用；VOOC 按温度限流，进入快充时可能记录瞬时重试/故障消息，仍需持续监控；其他充电协议未适配 | 暂时没有可行实现 | Windows 需要电池类驱动（ACPI `_BIF`/`_BST` 或厂商 miniport）+ 燃料计与充电器（PM8550 的 SPMI 子设备枚举）+ 热管理联动。SPMI 子设备在 DSDT 中全缺，**电源/充电是第三类硬骨头** | 先完成 SPMI 子设备枚举，再谈 `_BIF`/`_BST` |
| 温度 | dtbo overlay 中 PM8550/PM8550B 带 temp alarm 与 bcl 引用；**TSENS（片上温度）未从 DTB 提取，未知**（E1） | README 未单列温度；电池章节"VOOC 按温度限流"说明温度读取路径存在（推断，未在本机验证） | 暂时没有可行实现 | 两条路径都缺：TSENS 需 Qualcomm BSP 驱动；PMIC ADC 需 SPMI 子设备。ACPI 热区（TZ）可以写，但读不到真实温度就没有意义 | 从 overlay 解出 PMIC ADC 通道与 TSENS 节点；确认 Windows 侧是否有对应驱动（未知） |
| 睡眠 / 唤醒 | DSDT 中**没有任何 `_PRW`/`_DSW`/电源资源对象**；DTB 的 `cpuidle-domain` 存在但未转成 ACPI（E1/E10） | s2idle 与深度休眠恢复可用；唤醒后网络重连可能较慢 | 暂时没有可行实现 | Modern Standby 需要固件（UEFI）与平台驱动（低功耗进入/退出、唤醒源、GPIO 唤醒）配合，Qualcomm 平台相关驱动属 BSP。既缺 ACPI 电源对象，也缺驱动 | 无独立验证路径，依赖整体 BSP |
| 传感器 / 旋转 / 亮度 | DSDT 未声明；README 列出加速度计、陀螺仪、环境光、自动亮度、霍尔开关（说明硬件存在），**具体型号未提取，未知**（E9/E10） | 加速度计、陀螺仪、环境光、自动亮度、保护套霍尔开关可用（SSC 服务） | 暂时没有可行实现 | Windows 传感器栈需要 Qualcomm SSC/SNS 驱动 + 传感器注册表（JSON）+ ACPI 描述；自动亮度还要显示驱动配合，而显示行已无解 | 无 |
| 调试串口 | `qcom,qup_uart@a94000`（`qcom,geni-debug-uart`），reg 0xa94000+0x4000，IRQ `<0 358 4>` → **GSIV 0x186**；它是内核 chosen/stdout-path 控制台，也是 DBG2 的目标（E1/E2） | README 未单列（Linux 侧调试串口属内核 earlycon 常规能力，未在 README 声明） | 尚未测试 | DBG2 已生成（1364 字节，iasl 反汇编通过）并指向该 UART；Windows 内核调试（KD over serial）走 DBG2，**不需要**普通串口驱动。DSDT 故意未声明该 UART：其 ACPI `_HID` 无第一方来源可核实（`uefi.img` 无可用 ACPI 字符串，Mu-Qcom 也无 QUP UART 先例），**编造 HID 比省略更糟** | 上机后接串口抓 DBG2 输出（前提：先有可启动镜像）；或从 OEM UEFI 二进制中搜 AML 字符串（未验证可行性） |
| PMIC（SPMI） | `pmic-arb` @0xc42d000 与 @0xc432000；dtbo 引用 **PM8010**（`qcom,pm8010@c`、`qcom,pm8010@d`）与 **PM8550 家族**（`qcom,pm8550@1`、`qcom,pm8550b@7`），带 temp alarm/bcl。**PMIC 完整清单尚未枚举完（未知）**（E1/E2） | README 未单列；电池/快充与温度限流正常工作即隐含 SPMI 通路可用（推断） | 需要板级适配 | DSDT 已声明 `SPMI` = `QCOM0C0B` + CID `PNP0CA2`，覆盖 0xC42D000+0x4000。但 **PMIC 子设备（GPIO、RTC、ADC、regulator、charger、fuel gauge）一个都没声明**——控制器声明再多，没有子设备就不产生任何功能 | 从 overlay 的 spmi 节点逐个解析 USID 与 compatible 生成子设备表；再逐个匹配 Windows 驱动（GPIO/RTC/ADC 有先例，charger/fuel gauge 无） |
| 摄像头 | DSDT 未声明；README 给出前摄 3264×2448、后摄 4208×3120、SM8650 Camera ICP/BPS 硬件 ISP；**传感器型号未提取，未知**（E9） | 前后摄全分辨率 NV12 采集、libcamera/GStreamer 接入、AE/AWB 闭环、约 24 fps 连续 80 帧验证 | 暂时没有可行实现 | Windows 摄像头需要 AVStream/MediaFoundation 驱动 + ISP 固件 + ACPI 描述（CCI/I²C、GPIO、clock）。Qualcomm Camera 的 Windows 驱动属 BSP | 无 |

## 5. 已核实的寄存器 / 中断地图

以下数值全部从设备自身固件（E1/E2）提取，`scripts/extract_dtb.py` 可复现。GSIV = 32 + DTB 中的 SPI 号。

| 模块 | 基址 / 长度 | 中断 | 备注 |
| --- | --- | --- | --- |
| GICv3 分发器 | 0x17100000 + 0x10000 | — | `#interrupt-cells = 3` |
| GICv3 重分发器 | 0x17180000 + 0x200000 | — | cluster 内偏移见 §5.1 |
| 架构定时器 | — | PPI 13/14 → GSIV 29/30 | 19.2 MHz；hypervisor PPI 11/12 |
| 平台定时器 | `frame timer@17420000`，`gh-qtimer@17425000` | — | `arm,armv7-timer-mem` |
| UFS | 0x1d84000+0x3000、0x1d88000+0x8000、0x1d90000+0x9000、0x1da5000+0x2000、0x1da4000+0x10 | `<0 265 4>` → GSIV 0x129 | ACPI 侧合并为 0x1D84000+0x23000 |
| USB3 | `ssusb@a600000` 0xa600000+0x100000；`dwc3@a600000` 0xa600000+0xd93c | `<0 133 4>` → GSIV 0xA5 | `ro.boot.usbcontroller=a600000.dwc3` |
| TLMM / pinctrl | 0xf000000 + 0x1000000 | `<0 208 4>` → GSIV 0xF0 | `qcom,cliffs-pinctrl` |
| 调试 UART | `qup_uart@a94000` 0xa94000+0x4000 | `<0 358 4>` → GSIV 0x186 | `qcom,geni-debug-uart` |
| 显示控制器 | `mdss_mdp@ae00000` 0xae00000+0x84000、0xaeb0000+0x2008、0xaf80000+0x7000、0x400000+0x2000 | `<0 83 4>` | DSI ctrl0 @0xae94000，PHY0 @0xae95500 |
| SPMI | `pmic-arb` 0xc42d000+0x4000；0xc400000 / 0xc500000 / 0xc440000 / 0xc4c0000 区域；第二 arbiter 0xc432000 | — | 子设备未枚举 |

### 5.1 MADT 内的三个重分发器基址（唯一未验证字段）

| 基址 | 来源 | 状态 |
| --- | --- | --- |
| 0x17180000 | E2 直接给出（DTB 的 GICR 起点） | 已核实 |
| 0x171C0000 | 继承自 SM8550 模板（E6） | **未验证** |
| 0x17200000 | 继承自 SM8550 模板（E6） | **未验证** |

三个基址各自对应哪个 cluster，**未验证**——SM8650 的 cluster 是 3/4/1，SM8550 的划分不同，不能按 SM8550 的顺序套。

## 6. 已生成的 ACPI 表（编译通过，未上机）

| 表 | 大小 | 内容 | 校验状态 |
| --- | --- | --- | --- |
| DSDT | 743 字节 | 64 个命名对象：CPU0..CPU7、UFS0、USB0、GIO0、SPMI | iasl 20230628：0 error / 0 warning |
| FACP | 276 字节 | OEM ID `ONEPLS`，Table ID `CAIHONG`，OEM rev 0x8650 | 校验和已重算 |
| APIC(MADT) | 744 字节 | GICD/GICR 断言通过 | 同上 |
| GTDT | 156 字节 | 0x17420000、GSIV 29/30 断言通过 | 同上 |
| DBG2 | 1364 字节 | 指向 0xa94000 UART | 同上 |
| PPTT | 570 字节 | CPU 拓扑 | 同上 |

**关键结论（这是实证，不是推测）**：SM8550 的 GIC 分发器 0x17100000、重分发器 0x17180000、平台定时器 0x17420000 与 GSIV 29/30，在本机 SM8650 固件的 DTB 中**逐项断言全部 PASS**。也就是说两块 SoC 在这些位置上的布局一致，表可以平移，只需重定目标与重算校验和。

**唯一未验证字段**：MADT 内的 per-cluster 重分发器基址（见 §5.1）。

- 会怎么坏：某个 cluster 的 PPI（含架构定时器中断）投递不到，表现为只有部分核能收到中断，或多余核永远起不来。
- 怎么定论：读每个重分发器的 `GICR_TYPER.Affinity_Value` 核对；或者上机后确认 8 个 CPU 全部 online。二者任一即可。

## 7. Windows 驱动模型对照

这一列用来解释"为什么不能直接把 Linux 驱动搬过来"——每一行的 Windows 侧是完全不同的驱动框架。

| 模块 | Windows 侧需要的驱动模型 | 是否必须厂商 BSP | 公开可获取性 |
| --- | --- | --- | --- |
| 内屏 / GPU | WDDM 显示 miniport + 渲染驱动 | 是 | **无 SM8650 版本** |
| UFS | StorPort miniport | 是 | 无 SM8650 版本 |
| USB3 | xHCI（系统内置）+ 平台 glue / Type-C 连接器描述 | 部分 | 控制器描述已写，Type-C 缺 |
| SPMI / PMIC | 平台驱动（GPIO、RTC、ADC、regulator） | 是 | 无 |
| 触摸屏 / 键盘 | HID-over-I²C（HIDI2C，系统内置） | 否（但需设备描述符） | 栈内置，设备侧描述全缺 |
| Wi-Fi | WLAN miniport（NetAdapter 框架） | 是 | 无 |
| 蓝牙 | 传输驱动 + profile 驱动 | 是 | 无 |
| 音频 | ACX / WDM 音频驱动 + APO | 是 | 无 |
| 摄像头 | AVStream / MediaFoundation | 是 | 无 |
| 电池 / 充电 | ACPI 电池类（可写）+ 燃料计 miniport（需 BSP） | 部分 | 缺燃料计 |
| 传感器 | SSC/SNS 驱动 + 传感器注册表 | 是 | 无 |
| CPU / GIC / 定时器 | 内核 HAL（内置） | **否** | 只需正确的 ACPI 表 |
| 调试串口 | DBG2 + KD（内置） | **否** | 只需 DBG2 表 |

**从这个表能读出一件事**：真正"只差一张 ACPI 表"的只有 CPU、GIC、定时器、调试串口四项；其余全部卡在厂商驱动上。这也解释了为什么本项目的 ACPI 工作虽然扎实，却无法单独把设备推到可用状态。

## 8. 尚未确定的事实

| 事实 | 现状 | 定论方法 |
| --- | --- | --- |
| 内存容量 | **未知。** `getprop` 只有 `device_info.ddr_info=6\|8`，这是 DDR 类型/工艺编码，**不是容量** | `fastboot getvar`（内存相关变量）、bootloader 启动日志、或 SMEM 中的 DDR 信息 |
| CPU 具体核心型号 | **未知。** 厂商 DTB 里所有 CPU 都是 `qcom,kryo`，无 part number 字符串 | 读 MIDR_EL1；或对照 Qualcomm 公开的 SM8650 配置（未验证） |
| PMIC 完整清单 | **未枚举完。** 只有 PM8010 + PM8550/PM8550B 确认 | 解析 overlay 全部 spmi 子节点 USID |
| 触摸 I²C 总线与地址 | **未知** | 解析 overlay 的 i2c 节点 |
| Wi-Fi / BT 芯片型号 | **未知** | DTB 节点 / Linux 侧 `lspci`、`lsmod` |
| 传感器型号 | **未知** | SSC 配置 / DTB |
| 工厂镜像是否与当前 build 同版本 | **未验证**（未逐分区比对 hash） | 比对 `boot.img`/`dtbo.img` 与设备内分区的 SHA-256 |
| 是否存在 firehose programmer | **未知**（镜像目录中未见 `.elf`/`.mbn`） | 检查 OEM 完整包；否则 EDL 恢复能力无法确认 |

## 9. 汇总

| 状态 | 行数 | 哪些 |
| --- | --- | --- |
| 已验证正常 | **0** | —（没有任何硬件在本机跑过） |
| 已有可复用的 Windows ARM64 驱动 | **0** | — |
| 需要板级适配 | **6** | CPU/多核、GIC、定时器、UFS、USB3/Type-C、PMIC |
| 需要新驱动 | **2** | 触摸屏、磁吸键盘/触控板 |
| 暂时没有可行实现 | **11** | 内屏面板、GPU、手写笔、Wi-Fi、蓝牙、音频、电池/充电、温度、睡眠唤醒、传感器/旋转/亮度、摄像头 |
| 尚未测试 | **1** | 调试串口 |
| 合计 | **20** | |

### 三个最大阻塞

1. **显示（面板 + GPU/WDDM）。** 没有 WDDM miniport 就没有任何画面，连 Windows 安装器都看不见。这不是"驱动不完美"，是"从零创建"。而且 DSI 面板参数既不在 ACPI 里也不在任何公开驱动里，属于必须靠 OEM 资料才能补的空白。**这是单一最大阻塞。**
2. **存储（UFS 的 Windows 驱动）。** 没有 UFS 驱动就装不上系统；退路是 USB 存储，但那要 USB3 先能工作，而 USB3 又只到"控制器描述已写、Type-C 未描述"。两条路都不通时，安装介质无处落地。
3. **没有任何 SM8650 的 Windows 驱动来源（结构性问题）。** 公开生态最高只到 SM8550：Mu-Qcom 两个 fork 都止步 SM8450/SM8550；WOA-Project 的 `windows_silicon_qcom_lanai` 只有 README 和两个 md，且其 README 自己说"一切非功能"，目标还是 Qualcomm 参考设计（QRD）而非任何一加产品。Mu-Qcom 的 Windows 驱动来自 Qualcomm BSP 二进制、受 Qualcomm 自身许可约束、不可再分发，且**没有 SM8650 版本**。这一条同时决定了音频、电源、无线、传感器、摄像头全部无解——它们不是"分别难"，而是"共同缺同一个前提"。

### 必须说清的两条界线

- **Linux 驱动不能当 Windows 驱动用。** MSM/KGSL、ASoC、mac80211 这些是 Linux 内核框架里的东西，Windows 的 WDDM/WDM/ACX/NetAdapter 是完全不同的驱动模型。Linux 侧"正常"只能证明硬件存在且能工作，不能缩短 Windows 侧的工作量。
- **Linux DTS 不能替代 ACPI。** Windows 不读设备树。DTS 里的地址是**证据**（本文的事实来源），不是**交付物**；交付物必须是 ACPI 表加驱动。

### 诚实的底线

即使一切顺利，SM8650 的 Windows bring-up 也是一个**研究/bring-up 原型**，不是能用的平板。要走到"能进 Windows 安装器"，至少需要 UFS 或 USB 存储可用，**并且**显示可用——而显示恰恰是最难的那一项。在出现 SM8650 的 Windows BSP（无论是 OEM 授权还是其他来源）之前，本表中有 11 行不会移动。

## 10. 本表的维护规则

- 状态只能取六个值之一，不允许写"部分可用""基本正常"这类模糊词。
- **升级到 `已验证正常` 必须有实机启动记录**（哪次启动、观察到什么、日志在哪个文件）。仅编译通过、仅推理成立，都不算。
- 新增"硬件事实"必须带证据编号（E1–E10）；无来源的数字一律写 `未知`。
- 状态迁移需在提交信息里说明依据（例如"UFS 从需要板级适配改为需要新驱动，因为确认无 SM8650 StorPort miniport"）。
