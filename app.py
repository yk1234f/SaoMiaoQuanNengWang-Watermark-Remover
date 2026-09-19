import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
from cleaner import clean_pdf


class App:
    def __init__(self, initial_files=None):
        self.root = TkinterDnD.Tk()
        self.root.title('PDF 固定水印清理')
        self.root.geometry('820x540')
        self.root.minsize(680, 440)
        self.pending = queue.Queue()
        self.events = queue.Queue()
        self.output = ''
        self.last_folder = None
        panel = ttk.Frame(self.root, padding=24)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='把 PDF 拖到这里，自动批量处理', font=('Microsoft YaHei UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='适配示例中的“扫描全能王”独立图片水印 · 保留原文件 · 不压缩扫描正文', wraplength=740).pack(anchor='w', pady=(10, 20))
        drop = tk.Label(panel, text='拖入一个或多个 PDF\n也可以拖入文件夹（仅处理该文件夹内的 PDF）', bg='#eaf2fa', fg='#215787', font=('Microsoft YaHei UI', 13), height=5)
        drop.pack(fill='x')
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', lambda e: self.add(self.root.tk.splitlist(e.data)))
        bar = ttk.Frame(panel)
        bar.pack(fill='x', pady=14)
        ttk.Button(bar, text='选择 PDF', command=self.choose).pack(side='left')
        ttk.Button(bar, text='设置输出文件夹', command=self.set_output).pack(side='left', padx=10)
        ttk.Button(bar, text='打开最近输出', command=self.open_output).pack(side='left')
        self.location = ttk.Label(panel, text='默认输出到：原 PDF 所在文件夹 / 去水印输出', wraplength=740)
        self.location.pack(anchor='w')
        self.log = tk.Text(panel, height=10, wrap='word', font=('Microsoft YaHei UI', 10), state='disabled')
        self.log.pack(fill='both', expand=True, pady=(12, 0))
        self.note('等待文件。仅删除精确匹配的水印；未匹配则跳过，不生成副本。')
        threading.Thread(target=self.worker, daemon=True).start()
        self.root.after(100, self.poll)
        self.root.after(200, lambda: self.add(initial_files or []))

    def note(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def choose(self):
        self.add(filedialog.askopenfilenames(filetypes=[('PDF 文件', '*.pdf')]))

    def set_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output = folder
            self.location.configure(text='输出到：' + folder)

    def open_output(self):
        if self.last_folder:
            os.startfile(self.last_folder)

    def add(self, paths):
        files = []
        for path in paths:
            p = Path(path)
            if p.is_dir():
                files.extend(sorted(x for x in p.iterdir() if x.suffix.lower() == '.pdf'))
            elif p.suffix.lower() == '.pdf':
                files.append(p)
        for file in dict.fromkeys(files):
            self.pending.put((file, self.output))
            self.note('已加入：' + file.name)

    def worker(self):
        while True:
            file, output = self.pending.get()
            self.events.put(('log', '处理中：' + file.name))
            try:
                result, count, pages = clean_pdf(file, output or None)
                if result:
                    self.events.put(('folder', str(result.parent)))
                    self.events.put(('log', f'完成：{result.name}（{pages} 页，移除 {count} 处）'))
                else:
                    self.events.put(('log', f'跳过：{file.name}，未找到匹配的独立水印。'))
            except Exception as error:
                self.events.put(('log', f'失败：{file.name}：{error}'))
            finally:
                self.pending.task_done()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'folder':
                    self.last_folder = value
                else:
                    self.note(value)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--self-test':
        import json
        import time
        app = App()
        app.root.withdraw()
        app.output = sys.argv[3]
        app.add([sys.argv[2]])
        deadline = time.monotonic() + 60
        while app.pending.unfinished_tasks and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.02)
        app.poll()
        report = {'tkdnd': app.root.tk.call('package', 'require', 'tkdnd'),
                  'log': app.log.get('1.0', 'end'),
                  'completed': app.pending.unfinished_tasks == 0,
                  'output': app.last_folder}
        Path(sys.argv[3]).mkdir(parents=True, exist_ok=True)
        Path(sys.argv[3], 'self-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        app.root.destroy()
    else:
        App(sys.argv[1:]).root.mainloop()
