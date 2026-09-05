Android AppOps Controller (ADB 权限限制管理器)

基于 Python Tkinter 构建的轻量级桌面端 Android 应用后台与权限管控工具。通过 ADB 底层 appops 指令，一键限制应用的后台运行、唤醒锁（WAKE_LOCK）、定时闹钟等行为，有效阻止流氓 App 后台保活、耗电与偷跑流量。

核心特性
真实中文应用名映射：内置覆盖国内主流生态（微信、QQ、B站、银行、电商等）、Google 官方套件及海外 Top 100 热门应用的中文名称识别字典，告别混乱的原始包名。

后台与唤醒权限双向管控：

一键限制：批量将 RUN_IN_BACKGROUND、RUN_ANY_IN_BACKGROUND、WAKE_LOCK、SCHEDULE_EXACT_ALARM、START_FOREGROUND、MONITOR_HIGH_POWER_LOCATION 设为 ignore。

一键恢复：误操作随时可还原为 allow 放行状态。

实时状态回查与分类筛选：

采用多线程并发检测手机各应用当前真实的受限状态（已限制 / 已放行）。

支持按「全部状态 / 已放行 / 已限制」进行动态下拉筛选，支持按状态权重排序与首字母排序。

多设备连接支持：自动扫描当前 PC 连接的多台 Android 手机/模拟器，支持下拉切换目标设备 Serial 独立操作。

双击查看应用详情：双击任意应用行，调出底层包信息（版本号、Target SDK、安装路径、系统/第三方属性），并支持一键跳转 Google Play 页面（电脑端浏览器或手机端商店联动）。

零依赖与跨版本兼容：纯 Python 标准库开发（Tkinter + Subprocess + Threading），已深度适配 Python 3.14 及 Windows 高 DPI 界面缩放，静默执行无控制台黑框闪烁。

🛠️ 环境要求
Python 3.10+（原生兼容 Python 3.14）

ADB 环境：电脑已配置 Android SDK Platform-Tools（命令行执行 adb devices 有效）。

手机端准备：

打开手机「开发者选项」。

开启「USB 调试」（部分国产 ROM 如 MIUI/HyperOS、ColorOS 需额外开启「USB 调试（安全设置）- 允许模拟点击/权限修改」）。

🚀 快速启动
源码运行
# 克隆仓库
git clone https://github.com/你的用户名/仓库名.git
cd 仓库名

# 运行主程序
python main.py

打包为独立 EXE
无需安装第三方依赖，仅需安装 pyinstaller：
pip install pyinstaller
pyinstaller -F -w main.py -n "AndroidAppOpsController"

生成的可执行文件位于 dist/AndroidAppOpsController.exe。

⚠️ 注意事项
即时通讯软件提醒：建议不要对微信、企业微信、钉钉等强依赖后台唤醒接收消息的应用执行限制操作，否则锁屏后可能会收不到即时通知。

系统应用防护：列表已将第三方常用应用自动置顶，系统底层无界面的服务组件默认沉底，请谨慎限制系统级核心包。

📄 开源协议
本项目采用 MIT License 开源。欢迎提交 Issue 与 PR 补充更多应用包名映射！
