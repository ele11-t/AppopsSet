from concurrent.futures import ThreadPoolExecutor
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

OPS_LIST = [
    "RUN_IN_BACKGROUND",
    "RUN_ANY_IN_BACKGROUND",
    "WAKE_LOCK",
    "SCHEDULE_EXACT_ALARM",
    "START_FOREGROUND",
    "MONITOR_HIGH_POWER_LOCATION",
    # 阻断后台隐式唤醒与自启
    "BOOT_COMPLETED",         # 禁止开机自启广播唤醒
    "SYSTEM_ALERT_WINDOW",    # 禁止悬浮窗保活
    "READ_CLIPBOARD",         # 禁止后台窃听剪贴板
    "ACTIVITY_RECOGNITION",   # 禁止运动/计步唤醒
]


def run_cmd(cmd: str) -> tuple[int, str]:
    """执行命令行指令并返回状态码与输出，Windows 下静默执行不弹黑框"""
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    stdout, stderr = process.communicate()
    return process.returncode, (stdout + stderr).strip()


def check_single_pkg_restricted(pkg: str, serial: str = "") -> str:
    """检查指定应用的 appops 限制状态：已限制 / 已放行 / 未知"""
    target = f"-s {serial} " if serial else ""
    code, out = run_cmd(f'adb {target}shell "cmd appops get {pkg} RUN_IN_BACKGROUND"')
    if code != 0 or not out:
        return "默认"
    if "ignore" in out:
        return "已限制"
    if "allow" in out or "default" in out:
        return "已放行"
    return "未知"


class AppDetailDialog(tk.Toplevel):
    """应用详细信息展示及 Google Play 跳转弹窗"""

    def __init__(self, parent, app_label: str, package: str, serial: str = ""):
        super().__init__(parent)
        self.title(f"应用详情 - {app_label}")
        self.geometry("560x480")
        self.minsize(500, 500)
        self.transient(parent)
        self.grab_set()

        self.app_label = app_label
        self.package = package
        self.serial = serial

        self._build_ui()
        threading.Thread(target=self._fetch_app_details, daemon=True).start()

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 头部概览
        ttk.Label(
            main_frame,
            text=self.app_label,
            font=("Segoe UI", 14, "bold"),
            wraplength=520,
        ).pack(anchor=tk.W, pady=(0, 2))

        ttk.Label(
            main_frame,
            text=f"包名: {self.package}",
            font=("Consolas", 9),
            foreground="gray",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(0, 10))

        # 信息展示文本框
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        scrollbar = ttk.Scrollbar(text_frame)
        self.text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            font=("Consolas", 9),
            padx=8,
            pady=8,
        )
        scrollbar.config(command=self.text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_widget.insert(tk.END, "正在读取应用底层详细信息，请稍候...")
        self.text_widget.config(state=tk.DISABLED)

        # 底部操作栏
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X)

        ttk.Button(
            bottom_frame,
            text="在电脑浏览器打开 Google Play",
            command=self._open_web_play,
        ).pack(side=tk.LEFT, padx=(0, 6),ipady=5)

        ttk.Button(
            bottom_frame,
            text="在手机端打开 Play 商店",
            command=self._open_phone_play,
        ).pack(side=tk.LEFT,ipady=5)

        ttk.Button(
            bottom_frame,
            text="关闭",
            command=self.destroy,
        ).pack(side=tk.RIGHT)

    def _fetch_app_details(self):
        target = f"-s {self.serial} " if self.serial else ""
        code, out = run_cmd(f'adb {target}shell "dumpsys package {self.package}"')

        info_dict = {
            "应用名称": self.app_label,
            "应用包名": self.package,
            "版本名 (versionName)": "未知",
            "版本号 (versionCode)": "未知",
            "目标 SDK (targetSdk)": "未知",
            "最低 SDK (minSdk)": "未知",
            "首次安装时间": "未知",
            "最近更新时间": "未知",
            "APK 安装路径": "未知",
            "应用属性": "未知",
        }

        if code == 0 and out:
            # 提取版本信息
            m_vname = re.search(r"versionName=([^\s]+)", out)
            if m_vname:
                info_dict["版本名 (versionName)"] = m_vname.group(1)

            m_vcode = re.search(r"versionCode=(\d+)", out)
            if m_vcode:
                info_dict["版本号 (versionCode)"] = m_vcode.group(1)

            # 提取 SDK 版本
            m_tsdk = re.search(r"targetSdk=(\d+)", out)
            if m_tsdk:
                info_dict["目标 SDK (targetSdk)"] = m_tsdk.group(1)

            m_msdk = re.search(r"minSdk=(\d+)", out)
            if m_msdk:
                info_dict["最低 SDK (minSdk)"] = m_msdk.group(1)

            # 提取安装时间
            m_fit = re.search(r"firstInstallTime=([^\r\n]+)", out)
            if m_fit:
                info_dict["首次安装时间"] = m_fit.group(1).strip()

            m_lut = re.search(r"lastUpdateTime=([^\r\n]+)", out)
            if m_lut:
                info_dict["最近更新时间"] = m_lut.group(1).strip()

            # 提取路径与系统/第三方属性
            m_path = re.search(r"codePath=([^\r\n]+)", out)
            if m_path:
                path_str = m_path.group(1).strip()
                info_dict["APK 安装路径"] = path_str
                if "/system/" in path_str or "/product/" in path_str or "/vendor/" in path_str:
                    info_dict["应用属性"] = "系统内置应用 (System App)"
                else:
                    info_dict["应用属性"] = "用户第三方应用 (User App)"

        lines = [f"【{k}】: {v}" for k, v in info_dict.items()]
        result_text = "\n\n".join(lines)
        self.after(0, self._render_details, result_text)

    def _render_details(self, content: str):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert(tk.END, content)
        self.text_widget.config(state=tk.DISABLED)

    def _open_web_play(self):
        """调用电脑默认浏览器直接跳转 Google Play 详情页"""
        url = f"https://play.google.com/store/apps/details?id={self.package}"
        webbrowser.open(url)

    def _open_phone_play(self):
        """通过 ADB Intent 直接唤醒已连接手机上的 Play 商店展示该应用"""
        target = f"-s {self.serial} " if self.serial else ""
        cmd = (
            f'adb {target}shell "am start -a android.intent.action.VIEW '
            f'-d market://details?id={self.package}"'
        )
        code, _ = run_cmd(cmd)
        if code == 0:
            messagebox.showinfo("提示", "已向手机发送打开 Play 商店指令！", parent=self)
        else:
            messagebox.showwarning("提示", "手机端未安装 Google Play 商店或未响应。", parent=self)


class PackageDialog(tk.Toplevel):
    def __init__(self, parent, app_data: list[dict], serial: str = ""):
        super().__init__(parent)
        self.device_serial = serial
        title_suffix = f" [设备: {serial}]" if serial else ""
        self.title(f"Android 设备应用管理与权限状态监控{title_suffix}")
        self.geometry("900x640")
        self.minsize(750, 500)
        self.transient(parent)
        self.grab_set()

        # 数据结构: [{'label': 'QQ音乐', 'package': 'com...', 'status': '检测中...'}, ...]
        self.all_data = app_data
        self.filtered_data = list(app_data)
        self.sort_reverse_name = False
        self.sort_reverse_status = False

        self._build_ui()
        self._populate_list()
        # 异步加载所有包的当前权限状态，不卡界面
        threading.Thread(target=self._async_fetch_all_status, daemon=True).start()

    def _build_ui(self):
        # 顶部操作工具栏
        top_frame = ttk.Frame(self, padding="10 10 10 5")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="搜索过滤:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_filter)
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=16)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        # 状态分类筛选下拉框
        ttk.Label(top_frame, text="状态:").pack(side=tk.LEFT, padx=(0, 3))
        self.status_filter_var = tk.StringVar(value="全部状态")
        status_combobox = ttk.Combobox(
            top_frame,
            textvariable=self.status_filter_var,
            values=["全部状态", "已放行", "已限制", "检测中..."],
            state="readonly",
            width=9,
        )
        status_combobox.pack(side=tk.LEFT, padx=(0, 6))
        status_combobox.bind("<<ComboboxSelected>>", self._on_filter)

        ttk.Button(
            top_frame, text="按状态排序", command=self._toggle_sort_status
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            top_frame, text="按名称排序", command=self._toggle_sort_name
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            top_frame, text="刷新状态", command=self._refresh_status_manual
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="全选", command=self._select_all).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(top_frame, text="反选", command=self._select_invert).pack(
            side=tk.LEFT, padx=2
        )

        # 列表展示区：第一列 status, 第二列 label, 第三列 package
        list_frame = ttk.Frame(self, padding="10 5 10 5")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("status", "label", "package")
        self.tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", selectmode="extended"
        )

        self.tree.heading(
            "status", text="后台/唤醒状态 (点击排序)", command=self._toggle_sort_status
        )
        self.tree.heading(
            "label", text="应用名称 (点击排序)", command=self._toggle_sort_name
        )
        self.tree.heading("package", text="包名 (Package Name)")

        self.tree.column("status", width=140, anchor=tk.CENTER)
        self.tree.column("label", width=240, anchor=tk.W)
        self.tree.column("package", width=460, anchor=tk.W)

        # 绑定双击事件，弹出详细信息窗口
        self.tree.bind("<Double-1>", self._on_item_double_click)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 底部状态栏与双按钮栏（支持一键限制与一键恢复）
        bottom_frame = ttk.Frame(self, padding="10 5 10 10")
        bottom_frame.pack(fill=tk.X)

        self.status_label = ttk.Label(
            bottom_frame, text=f"共 {len(self.all_data)} 个应用 (双击查看应用详情/跳转Play)"
        )
        self.status_label.pack(side=tk.LEFT)

        # 右侧操作按钮群
        btn_box = ttk.Frame(bottom_frame)
        btn_box.pack(side=tk.RIGHT)

        self.restore_btn = ttk.Button(
            btn_box,
            text="恢复所选允许唤醒/后台",
            command=lambda: self._apply_action(mode="allow"),
        )
        self.restore_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.apply_btn = ttk.Button(
            btn_box,
            text="批量限制所选后台与唤醒",
            command=lambda: self._apply_action(mode="ignore"),
        )
        self.apply_btn.pack(side=tk.LEFT)

    def _on_item_double_click(self, event):
        """处理表格双击事件"""
        selected_id = self.tree.identify_row(event.y)
        if not selected_id:
            return
        vals = self.tree.item(selected_id, "values")
        if vals and len(vals) >= 3:
            # vals 结构: (status, label, package)
            app_label = vals[1]
            pkg = vals[2]
            AppDetailDialog(self, app_label, pkg, self.device_serial)

    def _populate_list(self):
        # 记录已选中的包名，重建列表时不丢失选中态
        selected_pkgs = set()
        for item_id in self.tree.selection():
            vals = self.tree.item(item_id, "values")
            if vals:
                selected_pkgs.add(vals[2])

        for item in self.tree.get_children():
            self.tree.delete(item)

        for item in self.filtered_data:
            item_id = self.tree.insert(
                "",
                tk.END,
                values=(item.get("status", "检测中..."), item["label"], item["package"]),
            )
            if item["package"] in selected_pkgs:
                self.tree.selection_add(item_id)

        self.status_label.config(
            text=f"当前显示: {len(self.filtered_data)} / 总数: {len(self.all_data)} (双击查看应用详情/跳转Play)"
        )

    def _async_fetch_all_status(self):
        """后台多线程并发探测所有包的状态"""

        def task(item):
            status = check_single_pkg_restricted(item["package"], self.device_serial)
            item["status"] = status
            return item["package"], status

        with ThreadPoolExecutor(max_workers=10) as executor:
            for pkg, st in executor.map(task, self.all_data):
                self.after(0, self._update_single_row_status, pkg, st)

    def _update_single_row_status(self, pkg: str, status: str):
        for item_id in self.tree.get_children():
            vals = self.tree.item(item_id, "values")
            if vals and vals[2] == pkg:
                self.tree.set(item_id, column="status", value=status)
                break
        if self.status_filter_var.get() != "全部状态":
            self._on_filter()

    def _refresh_status_manual(self):
        for item in self.all_data:
            item["status"] = "检测中..."
        self._populate_list()
        threading.Thread(target=self._async_fetch_all_status, daemon=True).start()

    def _on_filter(self, *args):
        query = self.search_var.get().strip().lower()
        filter_status = self.status_filter_var.get()

        res = []
        for item in self.all_data:
            item_status = item.get("status", "")
            if filter_status != "全部状态" and item_status != filter_status:
                continue
            if query and (
                    query not in item["label"].lower()
                    and query not in item["package"].lower()
                    and query not in item_status.lower()
            ):
                continue
            res.append(item)

        self.filtered_data = res
        self._populate_list()

    def _toggle_sort_name(self):
        """按应用名称排序"""
        self.sort_reverse_name = not self.sort_reverse_name
        self.filtered_data.sort(
            key=lambda x: (x["label"].lower(), x["package"].lower()),
            reverse=self.sort_reverse_name,
        )
        self.all_data.sort(
            key=lambda x: (x["label"].lower(), x["package"].lower()),
            reverse=self.sort_reverse_name,
        )
        self._populate_list()

    def _toggle_sort_status(self):
        """按状态排序"""
        self.sort_reverse_status = not self.sort_reverse_status
        weight = {"已放行": 0, "已限制": 1, "检测中...": 2, "默认": 3, "未知": 4}
        self.filtered_data.sort(
            key=lambda x: (weight.get(x.get("status", ""), 99), x["label"].lower()),
            reverse=self.sort_reverse_status,
        )
        self.all_data.sort(
            key=lambda x: (weight.get(x.get("status", ""), 99), x["label"].lower()),
            reverse=self.sort_reverse_status,
        )
        self._populate_list()

    def _select_all(self):
        self.tree.selection_set(self.tree.get_children())

    def _select_invert(self):
        all_items = set(self.tree.get_children())
        selected = set(self.tree.selection())
        to_select = all_items - selected
        self.tree.selection_set(list(to_select))

    def _apply_action(self, mode: str):
        """mode: 'ignore' (限制) 或 'allow' (恢复允许)"""
        selected_ids = self.tree.selection()
        if not selected_ids:
            messagebox.showwarning(
                "提示", "请先在列表中选中至少一个应用！", parent=self
            )
            return

        selected_items = [self.tree.item(item_id)["values"] for item_id in selected_ids]
        action_name = "限制" if mode == "ignore" else "恢复放行"

        if not messagebox.askyesno(
                "确认操作",
                f"确定对选中的 {len(selected_items)} 个应用执行【{action_name}】操作？",
                parent=self,
        ):
            return

        self.apply_btn.config(state=tk.DISABLED)
        self.restore_btn.config(state=tk.DISABLED)
        self.status_label.config(text=f"正在批量{action_name}中，请稍候...")

        pkgs = [item[2] for item in selected_items]
        threading.Thread(
            target=self._run_batch_worker, args=(pkgs, mode), daemon=True
        ).start()

    def _run_batch_worker(self, packages: list[str], mode: str):
        success_count = 0
        target_mode = "ignore" if mode == "ignore" else "allow"
        serial_prefix = f"-s {self.device_serial} " if self.device_serial else ""

        for pkg in packages:
            sub_cmds = [f"cmd appops set {pkg} {op} {target_mode}" for op in OPS_LIST]
            full_shell_cmd = f'adb {serial_prefix}shell "{";".join(sub_cmds)}"'
            ret, _ = run_cmd(full_shell_cmd)
            if ret == 0:
                success_count += 1
                new_st = "已限制" if mode == "ignore" else "已放行"
                for item in self.all_data:
                    if item["package"] == pkg:
                        item["status"] = new_st
                self.after(0, self._update_single_row_status, pkg, new_st)

        self.after(0, self._on_batch_complete, success_count, len(packages), mode)

    def _on_batch_complete(self, success: int, total: int, mode: str):
        self.apply_btn.config(state=tk.NORMAL)
        self.restore_btn.config(state=tk.NORMAL)
        action_name = "限制" if mode == "ignore" else "恢复放行"
        self.status_label.config(text=f"完成: {success}/{total} 成功{action_name}")
        messagebox.showinfo(
            "执行完毕",
            f"操作已完成！\n成功{action_name}: {success} 个\n失败: {total - success} 个\n列表状态已自动同步刷新。",
            parent=self,
        )


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ADB Android 应用权限控制器")
        self.geometry("450x260")
        self.resizable(False, False)

        self.device_map = {}

        self._build_ui()
        self._refresh_devices_async()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="选择已连接的 Android 设备并读取应用权限列表",
            font=("Segoe UI", 10),
            wraplength=400,
        ).pack(pady=(0, 12))

        # 设备选择区域
        dev_frame = ttk.Frame(frame)
        dev_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(dev_frame, text="目标设备:").pack(side=tk.LEFT, padx=(0, 6))
        self.device_var = tk.StringVar()
        self.device_combobox = ttk.Combobox(
            dev_frame, textvariable=self.device_var, state="readonly"
        )
        self.device_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        ttk.Button(
            dev_frame, text="刷新设备", command=self._refresh_devices_async
        ).pack(side=tk.LEFT)

        # 启动扫描按钮
        self.scan_btn = ttk.Button(
            frame, text="连接设备并列出所有应用", command=self._start_scan
        )
        self.scan_btn.pack(ipadx=10, ipady=6, pady=(5, 10))

        self.status_var = tk.StringVar(value="状态: 正在扫描已连接设备...")
        ttk.Label(frame, textvariable=self.status_var, foreground="gray").pack(
            side=tk.BOTTOM, pady=(5, 0)
        )

    def _refresh_devices_async(self):
        """异步刷新 ADB 已连接的可用设备列表"""
        self.status_var.set("状态: 正在检测 ADB 设备连接...")
        threading.Thread(target=self._refresh_devices_worker, daemon=True).start()

    def _refresh_devices_worker(self):
        code, out = run_cmd("adb devices -l")
        self.device_map.clear()
        device_display_names = []

        if code == 0 and out:
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    serial = parts[0]
                    model = ""
                    for p in parts[2:]:
                        if p.startswith("model:"):
                            model = p.split("model:", 1)[1]
                            break
                    display_text = f"{serial} ({model})" if model else serial
                    self.device_map[display_text] = serial
                    device_display_names.append(display_text)

        self.after(0, self._update_device_combobox, device_display_names)

    def _update_device_combobox(self, device_names: list[str]):
        if device_names:
            self.device_combobox["values"] = device_names
            if self.device_var.get() not in device_names:
                self.device_combobox.current(0)
            self.status_var.set(f"状态: 检测到 {len(device_names)} 台设备就绪")
            self.scan_btn.config(state=tk.NORMAL)
        else:
            self.device_combobox["values"] = []
            self.device_var.set("未检测到已连接的设备")
            self.status_var.set("状态: 未检测到可用设备，请检查 USB 调试")
            self.scan_btn.config(state=tk.DISABLED)

    def _start_scan(self):
        selected_display = self.device_var.get()
        serial = self.device_map.get(selected_display, "")
        if not serial:
            messagebox.showwarning("提示", "请选择有效的已连接设备！", parent=self)
            return

        self.scan_btn.config(state=tk.DISABLED)
        self.status_var.set(f"状态: 正在读取设备 [{serial}] 数据...")
        threading.Thread(
            target=self._fetch_packages_worker, args=(serial,), daemon=True
        ).start()

    def _fetch_packages_worker(self, serial: str):
        target = f"-s {serial} "
        # 1. 验证设备可达性
        code, out = run_cmd(f"adb {target}get-state")
        if code != 0 or "device" not in out:
            self.after(
                0,
                self._handle_error,
                f"设备 [{serial}] 离线或未完成调试授权，请重新连接手机授权后重试。",
            )
            return

        # 2. 读取全部已安装包名
        self.after(0, lambda: self.status_var.set("状态: 正在读取已安装包名..."))
        code, out = run_cmd(f'adb {target}shell pm list packages')
        if code != 0 or not out:
            self.after(0, self._handle_error, f"获取包名失败:\n{out}")
            return

        all_pkgs = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                all_pkgs.append(line.replace("package:", "").strip())

        # 3. 提取应用中文显示名称
        self.after(0, lambda: self.status_var.set("状态: 正在匹配应用中文名称..."))
        label_map = self._get_app_labels(serial)

        app_data = []
        for pkg in all_pkgs:
            label = label_map.get(pkg)
            if not label:
                label = pkg.split(".")[-1]
            app_data.append({"label": label, "package": pkg, "status": "检测中..."})

        # 排序：有中文名的优先置顶
        def sort_priority(item):
            lbl = item["label"]
            pkg = item["package"]
            has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in lbl)
            is_fallback = lbl == pkg.split(".")[-1]
            rank = 0 if has_chinese else (2 if is_fallback else 1)
            return (rank, lbl.lower(), pkg.lower())

        app_data.sort(key=sort_priority)
        self.after(0, self._open_package_dialog, app_data, serial)

    def _get_app_labels(self, serial: str = "") -> dict[str, str]:
        """内置高频应用字典 + Google 全家桶 + Google Play 海外热门 Top 100 + 系统解析"""
        known_map = {
            # ==========================================
            # 1. Google Play 海外热门榜单 Top 100
            # ==========================================
            "com.facebook.katana": "Facebook",
            "com.facebook.orca": "Messenger",
            "com.facebook.lite": "Facebook Lite",
            "com.facebook.mlite": "Messenger Lite",
            "com.instagram.android": "Instagram",
            "com.instagram.threadsapp": "Threads",
            "com.instagram.lite": "Instagram Lite",
            "com.whatsapp": "WhatsApp",
            "com.whatsapp.w4b": "WhatsApp Business",
            "org.telegram.messenger": "Telegram",
            "org.telegram.messenger.web": "Telegram Web",
            "com.snapchat.android": "Snapchat",
            "com.twitter.android": "X (Twitter)",
            "com.discord": "Discord",
            "jp.naver.line.android": "LINE",
            "org.thoughtcrime.securesms": "Signal",
            "com.viber.voip": "Viber",
            "com.reddit.frontpage": "Reddit",
            "com.pinterest": "Pinterest",
            "com.tumblr": "Tumblr",
            "com.linkedin.android": "LinkedIn",
            "com.tinder": "Tinder",
            "com.bumble.app": "Bumble",
            "com.match.android.matchapp": "Match",
            "com.openai.chatgpt": "ChatGPT",
            "com.anthropic.claude": "Claude",
            "com.microsoft.copilot": "Microsoft Copilot",
            "com.midjourney.app": "Midjourney",
            "com.perplexity.app": "Perplexity",
            "ai.character.app": "Character.ai",
            "com.zhiliaoapp.musically": "TikTok",
            "com.zhiliaoapp.musically.go": "TikTok Lite",
            "com.netflix.mediaclient": "Netflix",
            "com.disney.disneyplus": "Disney+",
            "com.amazon.avod.thirdpartyclient": "Amazon Prime Video",
            "com.wbd.stream": "Max (HBO Max)",
            "com.hulu.plus": "Hulu",
            "com.paramountplus": "Paramount+",
            "com.peacocktv.peacockandroid": "Peacock TV",
            "tv.twitch.android.app": "Twitch",
            "com.crunchyroll.crunchyroid": "Crunchyroll",
            "com.spotify.music": "Spotify",
            "com.spotify.lite": "Spotify Lite",
            "deezer.android.app": "Deezer",
            "com.soundcloud.android": "SoundCloud",
            "com.pandora.android": "Pandora",
            "com.shazam.android": "Shazam",
            "com.audible.application": "Audible",
            "com.lemon.lvoverseas": "CapCut",
            "com.canva.editor": "Canva",
            "com.adobe.psmobile": "Photoshop Express",
            "com.adobe.lrmobile": "Lightroom",
            "com.adobe.reader": "Adobe Acrobat Reader",
            "com.niksoftware.snapseed": "Snapseed",
            "com.vsco.cam": "VSCO",
            "com.picsart.studio": "Picsart",
            "com.camerasideas.instashot": "InShot",
            "com.meitu.airvid": "Wink",
            "com.remini.app": "Remini",
            "com.kwai.video": "Kwai",
            "com.amazon.mShop.android.shopping": "Amazon Shopping",
            "com.einnovation.temu": "Temu",
            "com.zzkko": "SHEIN",
            "com.alibaba.aliexpresshd": "AliExpress",
            "com.ebay.mobile": "eBay",
            "com.shopee.id": "Shopee",
            "com.lazada.android": "Lazada",
            "com.walmart.android": "Walmart",
            "com.target.ui": "Target",
            "com.etsy.android": "Etsy",
            "com.contextlogic.wish": "Wish",
            "com.ubercab": "Uber",
            "com.ubercab.eats": "Uber Eats",
            "me.lyft.android": "Lyft",
            "com.grabtaxi.passenger": "Grab",
            "com.dd.passenger": "DoorDash",
            "com.postmates.android": "Postmates",
            "com.deliveroo.orderapp": "Deliveroo",
            "com.justeat.app": "Just Eat",
            "com.airbnb.android": "Airbnb",
            "com.booking": "Booking.com",
            "com.expedia.bookings": "Expedia",
            "com.tripadvisor.tripadvisor": "Tripadvisor",
            "com.agoda.mobile.consumer": "Agoda",
            "com.microsoft.office.officehubrow": "Microsoft 365 (Office)",
            "com.microsoft.office.word": "Microsoft Word",
            "com.microsoft.office.excel": "Microsoft Excel",
            "com.microsoft.office.powerpoint": "Microsoft PowerPoint",
            "com.microsoft.office.onenote": "Microsoft OneNote",
            "com.microsoft.office.outlook": "Microsoft Outlook",
            "com.microsoft.teams": "Microsoft Teams",
            "us.zoom.videomeetings": "Zoom",
            "com.slack": "Slack",
            "com.dropbox.android": "Dropbox",
            "com.box.android": "Box",
            "com.evernote": "Evernote",
            "com.paypal.android.p2pmobile": "PayPal",
            "com.squareup.cash": "Cash App",
            "com.venmo": "Venmo",
            "com.revolut.revolut": "Revolut",
            "com.wise.android": "Wise",
            "com.binance.dev": "Binance",
            "com.coinbase.android": "Coinbase",
            "com.robinhood.android": "Robinhood",
            "io.metamask": "MetaMask",
            "com.wallet.crypto.trustapp": "Trust Wallet",
            "com.roblox.client": "Roblox",
            "com.epicgames.portal": "Epic Games",
            "com.activision.callofduty.shooter": "Call of Duty: Mobile",
            "com.tencent.ig": "PUBG MOBILE",
            "com.dts.freefireth": "Free Fire",
            "com.miHoYo.GenshinImpact": "原神 (国际版)",
            "com.supercell.clashofclans": "部落冲突",
            "com.supercell.brawlstars": "荒野乱斗",
            "com.supercell.clashroyale": "皇室战争",
            "com.ea.gp.fifamobile": "EA SPORTS FC Mobile",
            "com.nianticlabs.pokemongo": "Pokémon GO",
            "com.king.candycrushsaga": "Candy Crush Saga",
            "com.playrix.gardenscapes": "梦幻花园",
            "com.innersloth.spacemafia": "Among Us",

            # ==========================================
            # 2. Google 官方套件 (全家桶)
            # ==========================================
            "com.google.android.googlequicksearchbox": "Google 搜索",
            "com.android.vending": "Google Play 商店",
            "com.google.android.gms": "Google Play 服务",
            "com.google.android.gsf": "Google 服务框架",
            "com.google.android.chrome": "Chrome",
            "com.android.chrome": "Chrome",
            "com.google.android.gm": "Gmail",
            "com.google.android.apps.maps": "Google 地图",
            "com.google.android.youtube": "YouTube",
            "com.google.android.apps.youtube.music": "YouTube Music",
            "com.google.android.apps.photos": "Google 相册",
            "com.google.android.apps.docs": "Google 云端硬盘",
            "com.google.android.apps.docs.editors.docs": "Google 文档",
            "com.google.android.apps.docs.editors.sheets": "Google 表格",
            "com.google.android.apps.docs.editors.slides": "Google 幻灯片",
            "com.google.android.keep": "Google Keep 记事",
            "com.google.android.calendar": "Google 日历",
            "com.google.android.contacts": "Google 通讯录",
            "com.google.android.apps.messaging": "Google 信息",
            "com.google.android.dialer": "Google 电话",
            "com.google.android.calculator": "Google 计算器",
            "com.google.android.deskclock": "Google 时钟",
            "com.google.android.GoogleCamera": "Google 相机",
            "com.google.android.apps.cameralite": "Camera Go",
            "com.google.android.apps.nbu.files": "Files by Google",
            "com.google.android.apps.walletnfcrel": "Google 钱包",
            "com.google.android.apps.tachyon": "Google Meet",
            "com.google.android.talk": "Google Hangouts",
            "com.google.android.apps.translate": "Google 翻译",
            "com.google.android.apps.googleassistant": "Google 助理",
            "com.google.android.apps.chromecast.app": "Google Home",
            "com.google.android.apps.fitness": "Google Fit",
            "com.google.android.play.games": "Play 游戏",
            "com.google.android.apps.books": "Google Play 图书",
            "com.google.android.videos": "Google TV",
            "com.google.android.apps.authenticator2": "Google 身份验证器",
            "com.google.android.inputmethod.latin": "Gboard 键盘",
            "com.google.android.apps.bard": "Gemini",
            "com.google.android.apps.safetyhub": "个人安全",
            "com.google.android.apps.wellbeing": "数字健康",
            "com.google.android.soundpicker": "声音选择器",
            "com.google.android.apps.recorder": "录音机",
            "com.google.android.marvin.talkback": "Android 无障碍套件",

            # ==========================================
            # 3. 国内主流应用库
            # ==========================================
            "com.tencent.mm": "微信",
            "com.tencent.mobileqq": "QQ",
            "com.tencent.tim": "TIM",
            "com.sina.weibo": "微博",
            "com.sina.weibog3": "微博轻享版",
            "com.zhihu.android": "知乎",
            "com.xingin.xhs": "小红书",
            "com.coolapk.market": "酷安",
            "com.douban.frodo": "豆瓣",
            "com.baidu.tieba": "百度贴吧",
            "com.immomo.momo": "陌陌",
            "com.p1.mobile.putong": "探探",
            "com.soulapp.cn": "Soul",
            "tv.danmaku.bili": "哔哩哔哩",
            "com.bilibili.app.in": "哔哩哔哩国际版",
            "com.ss.android.ugc.aweme": "抖音",
            "com.ss.android.ugc.aweme.lite": "抖音极速版",
            "com.smile.gifmaker": "快手",
            "com.kuaishou.nebula": "快手极速版",
            "com.tencent.qqlive": "腾讯视频",
            "com.youku.phone": "优酷视频",
            "com.qiyi.video": "爱奇艺",
            "com.hunantv.imgo.activity": "芒果TV",
            "com.tencent.qqmusic": "QQ音乐",
            "com.netease.cloudmusic": "网易云音乐",
            "cn.kuwo.player": "酷我音乐",
            "com.kugou.android": "酷狗音乐",
            "cmccwm.mobilemusic": "咪咕音乐",
            "com.ximalaya.ting.android": "喜马拉雅",
            "fm.qingting.qtradio": "蜻蜓FM",
            "com.duowan.kiwi": "虎牙直播",
            "air.tv.douyu.android": "斗鱼",
            "com.taobao.taobao": "手机淘宝",
            "com.taobao.litetao": "淘特",
            "com.jingdong.app.mall": "京东",
            "com.jd.jdlite": "京东极速版",
            "com.xunmeng.pinduoduo": "拼多多",
            "com.taobao.idlefish": "闲鱼",
            "com.zhuanzhuan.zzfocus": "转转",
            "com.achievo.vipshop": "唯品会",
            "com.suning.mobile.ebuy": "苏宁易购",
            "com.sankuai.meituan": "美团",
            "com.sankuai.meituan.takeoutnew": "美团外卖",
            "me.ele": "饿了么",
            "com.dianping.v1": "大众点评",
            "com.autonavi.minimap": "高德地图",
            "com.baidu.BaiduMap": "百度地图",
            "com.tencent.map": "腾讯地图",
            "com.sdu.didi.psnger": "滴滴出行",
            "com.sdu.didi.gui": "滴滴出行",
            "com.t3go.passenger": "T3出行",
            "com.caocao.panel": "曹操出行",
            "com.gotokeep.keep": "Keep",
            "com.MobileTicket": "铁路12306",
            "ctrip.android.view": "携程旅行",
            "com.Qunar": "去哪儿旅行",
            "com.tongcheng.android": "同程旅行",
            "com.fliggy.android": "飞猪旅行",
            "com.ss.android.article.news": "今日头条",
            "com.ss.android.article.lite": "今日头条极速版",
            "com.tencent.news": "腾讯新闻",
            "com.netease.newsreader.activity": "网易新闻",
            "com.sohu.newsclient": "搜狐新闻",
            "com.dragon.read": "番茄免费小说",
            "com.kmxs.reader": "七猫免费小说",
            "com.chaozh.iReaderFree": "掌阅",
            "com.qq.reader": "QQ阅读",
            "com.tencent.weread": "微信读书",
            "com.duolingo": "多邻国",
            "com.fenbi.android.solar": "小猿搜题",
            "com.youdao.dict": "有道词典",
            "com.tencent.wework": "企业微信",
            "com.alibaba.android.rimet": "钉钉",
            "com.ss.android.lark": "飞书",
            "com.tencent.wemeet.app": "腾讯会议",
            "cn.wps.moffice_eng": "WPS Office",
            "com.baidu.netdisk": "百度网盘",
            "com.alicloud.databox": "阿里云盘",
            "com.quark.browser": "夸克",
            "com.xunlei.downloadprovider": "迅雷",
            "com.microsoft.todos": "微软待办",
            "com.notion.id": "Notion",
            "com.eg.android.AlipayGphone": "支付宝",
            "com.unionpay": "云闪付",
            "com.icbc": "中国工商银行",
            "com.chinamworld.main": "中国建设银行",
            "com.boc.bocsoft": "中国银行",
            "com.android.bankabc": "中国农业银行",
            "com.cmbchina.ccd.pltransitive": "掌上生活",
            "cmb.pb": "招商银行",
            "com.spdb.fms": "浦发银行",
            "com.cebbank.mobile.cemb": "光大银行",
            "com.pingan.paces.ccms": "平安口袋银行",
            "com.hexin.plat.android": "同花顺",
            "com.eastmoney.android.berlin": "东方财富",
            "org.mozilla.firefox": "Firefox",
            "com.microsoft.emmx": "Edge",
            "com.tencent.mtt": "QQ浏览器",
            "com.UCMobile": "UC浏览器",
            "bin.mt.plus": "MT管理器",
            "com.valvesoftware.android.steam.community": "Steam",
            "com.taptap": "TapTap",
            "com.android.settings": "系统设置",
            "com.android.camera": "相机",
            "com.android.deskclock": "时钟",
            "com.android.calculator2": "计算器",
            "com.android.calendar": "日历",
            "com.android.contacts": "通讯录",
            "com.android.mms": "短信",
            "com.android.dialer": "电话",
            "com.android.documentsui": "文件管理",
            "com.android.gallery3d": "图库",
        }

        target = f"-s {serial} " if serial else ""
        code, out = run_cmd(f'adb {target}shell "dumpsys package activities"')
        if code == 0 and out:
            cur_pkg = None
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Package ["):
                    parts = line.split("[")
                    if len(parts) > 1:
                        cur_pkg = parts[1].split("]")[0]
                elif "nonLocalizedLabel=" in line and cur_pkg:
                    name = line.split("nonLocalizedLabel=")[-1].strip()
                    if name and name != "null" and cur_pkg not in known_map:
                        known_map[cur_pkg] = name

        return known_map

    def _handle_error(self, message: str):
        self.scan_btn.config(state=tk.NORMAL)
        self.status_var.set("状态: 操作失败")
        messagebox.showerror("错误", message, parent=self)

    def _open_package_dialog(self, app_data: list[dict], serial: str):
        self.scan_btn.config(state=tk.NORMAL)
        self.status_var.set(f"状态: 读取成功，共 {len(app_data)} 个应用")
        PackageDialog(self, app_data, serial)


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()