# based on http://dzone.com/snippets/set-windows-desktop-wallpaper
import ctypes
import glob
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter
from functools import partial

import pandas as pd
import wx
from apscheduler.schedulers.background import BackgroundScheduler
from PIL import ExifTags, Image
from PIL.ExifTags import TAGS
from send2trash import send2trash

from category import cleanup

if os.name == 'nt':
    import win32api
    import win32con
    import win32gui

syndrive = r'D:\SynologyDrive' if os.name == 'nt' else '/Users/Joker/SynologyDrive'
GLOBAL_config = {
    'interval': 10,
    'folder': os.path.join(syndrive, 'Pictures/Eye Candy'),
    'safewp': r'D:\Photo\Gallery\_T1A5048-2-编辑.jpg' if os.name == 'nt'
    else '/Users/Joker/Pictures/Photo/Gallery/_T1A5048-2-编辑.jpg',
}
current_fn = None
n_last = 1000

try:
    with open(os.path.join(os.path.dirname(__file__), 'last.txt')) as f:
        last = json.load(f)
except Exception:
    last = []

config_fn = os.path.join(os.path.dirname(__file__), 'config.txt')


def read_config():
    with open(config_fn) as f:
        GLOBAL_config.update(json.load(f))


def save_config():
    with open(config_fn, 'w') as f:
        json.dump(GLOBAL_config, f, indent=2)


def _setWallpaperWin(path, style='10'):
    key = win32api.RegOpenKeyEx(
        win32con.HKEY_CURRENT_USER, "Control Panel\\Desktop", 0, win32con.KEY_SET_VALUE)
    # 最后的参数:2拉伸,0居中,6适应,10填充
    win32api.RegSetValueEx(key, "WallpaperStyle", 0, win32con.REG_SZ, style)
    win32api.RegSetValueEx(key, "TileWallpaper", 0, win32con.REG_SZ, "0")
    win32gui.SystemParametersInfo(
        win32con.SPI_SETDESKWALLPAPER, path, win32con.SPIF_SENDWININICHANGE)


def _setWallpaperMac(path):
    path = path.replace("'", """'"'"'""")
    cmd = f"""osascript -e 'tell application "System Events" to set picture of every desktop to "{path}"' """
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    proc.communicate()


_setWallpaper = _setWallpaperMac if os.name == 'posix' else _setWallpaperWin


def add_margin(pil_img, top, bottom, left, right, color):
    width, height = pil_img.size
    new_width = width + right + left
    new_height = height + top + bottom
    result = Image.new(pil_img.mode, (new_width, new_height), color)
    result.paste(pil_img, (left, top))
    return result


def set_wallpaper(fn):
    global last
    img = Image.open(fn)
    width, height = img.size
    exif = img.getexif()
    flip = False
    if exif.get(274, 1) != 1:   # check for rotation
        width, height = height, width
        flip = True
    ratio = width / height / (16/9)
    print(os.path.basename(fn))
    if not last or fn != last[-1]:
        last.append(fn)
        if len(last) > n_last:
            last = last[-n_last:]
        with open(os.path.join(os.path.dirname(__file__), 'last.txt'), 'w+') as f:
            json.dump(last, f, indent=2)
    print('    - {} x {}'.format(width, height))
    if .8 < ratio < 1.25:
        img.close()
        _setWallpaper(fn)
    else:
        if ratio <= .8:
            borders = [img.getpixel((i, j)) for i in (0, 1, 2, width-3, width-2, width-1)
                    for j in range(height)]
            counts = Counter(borders)
            color, cts = counts.most_common(1)[0]
            sim_ratio = cts / len(borders)
            if sim_ratio > .01:
                print('    - Edge Similarity: {}'.format(round(sim_ratio, 2)))
            if sim_ratio <= .05:
                color = (0, 0, 0)
            if height > 2000:
                img = img.resize((int(width / height * 2000 + .5), 2000))
                width, height = img.size
            need_w = height / 9 * 16
            margin = int((need_w - width) / 2 + .5)
            img = add_margin(img, 0, 0, margin, margin, color)
        else:  # wide
            need_h = width / 16 * 9
            margin = int((need_h - height) / 2 + .5)
            img = add_margin(img, margin, margin, 0, 0, (0, 0, 0))
        with tempfile.TemporaryDirectory() as tmpdir:
            fn = os.path.join(tmpdir, 'tmp{}'.format(os.path.splitext(fn)[1]))
            img.save(fn)
            img.close()
            _setWallpaper(fn)
            if os.name == 'nt':
                time.sleep(1)


def change_wallpaper(*args):
    global current_fn, n_last
    folder = GLOBAL_config['folder']
    allpics = glob.glob(os.path.join(folder, '*.jpg')) + \
        glob.glob(os.path.join(folder, '*.png')) + \
        glob.glob(os.path.join(folder, '*/*.jpg')) + \
        glob.glob(os.path.join(folder, '*/*.png'))
    n_last = min(n_last, int(len(allpics) * .8))
    allpics = list(set(allpics) - set(last))
    if not allpics:
        return
    fn = random.choice(allpics)
    current_fn = fn
    set_wallpaper(fn)


def prev_wallpaper(*args):
    global current_fn, last
    if len(last) < 2:
        return
    fn = last[-2]
    last = last[:-1]
    current_fn = fn
    set_wallpaper(fn)


class RedirectText(object):
    def __init__(self, aWxTextCtrl):
        self.out = aWxTextCtrl

    def write(self, string):
        wx.CallAfter(self.out.WriteText, string)

    def flush(self, *args):
        return


class TabSetting(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        st1 = wx.StaticText(self, label='Interval')
        hbox1.Add(st1, flag=wx.RIGHT, border=8)
        self.interval_ctrl = wx.TextCtrl(self)
        self.interval_ctrl.write(str(GLOBAL_config['interval']))
        hbox1.Add(self.interval_ctrl, proportion=1)
        vbox.Add(hbox1, flag=wx.EXPAND | wx.LEFT |
                 wx.RIGHT | wx.TOP, border=10)

        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        st1 = wx.StaticText(self, label='Folder')
        hbox2.Add(st1, flag=wx.RIGHT, border=8)
        self.folder_ctrl = wx.DirPickerCtrl(self)
        self.folder_ctrl.SetPath(GLOBAL_config['folder'])
        hbox2.Add(self.folder_ctrl, proportion=1)
        vbox.Add(hbox2, flag=wx.EXPAND | wx.LEFT |
                 wx.RIGHT | wx.TOP, border=10)

        vbox.Add((-1, 25))
        hbox5 = wx.BoxSizer(wx.HORIZONTAL)
        btn1 = wx.Button(self, label='Apply', size=(70, 30))
        hbox5.Add(btn1)
        vbox.Add(hbox5, flag=wx.ALIGN_RIGHT | wx.RIGHT, border=10)

        self.SetSizer(vbox)

        self.Bind(wx.EVT_BUTTON, self._update_setting, btn1)

    def _update_setting(self, *args):
        self._update_path()
        self._update_interval()
        save_config()

    def _update_path(self, *args):
        GLOBAL_config['folder'] = self.folder_ctrl.GetPath()
        change_wallpaper()

    def _update_interval(self, *args):
        try:
            interval = int(self.interval_ctrl.GetLineText(0))
            if interval < 1:
                raise ValueError
        except ValueError:
            return
        GLOBAL_config['interval'] = interval
        scheduler.pause()
        scheduler.reschedule_job(
            'change', trigger='interval', minutes=GLOBAL_config['interval'])
        scheduler.resume()


class TabLog(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        vbox = wx.FlexGridSizer(1, 1, 0, 0)

        log = wx.TextCtrl(self, wx.ID_ANY, style=wx.TE_MULTILINE |
                          wx.TE_READONLY | wx.HSCROLL)
        vbox.Add(log, flag=wx.EXPAND | wx.LEFT |
                 wx.RIGHT | wx.TOP, border=2)
        vbox.AddGrowableRow(0, 0)
        vbox.AddGrowableCol(0, 0)
        # redirect text here
        redir = RedirectText(log)
        sys.stdout = redir

        self.SetSizer(vbox)


class Example(wx.Frame):

    def __init__(self, *args, **kwargs):
        super(Example, self).__init__(*args, **kwargs)
        self._icon_folder = os.path.join(os.path.dirname(__file__), 'assets')

        self.InitUI()

    def InitUI(self):
        self._init_toolbar()

        panel = wx.Panel(self)
        nb = wx.Notebook(panel)
        tab_setting = TabSetting(nb)
        tab_log = TabLog(nb)
        nb.AddPage(tab_log, 'Log')
        nb.AddPage(tab_setting, 'Setting')

        # Set noteboook in a sizer to create the layout
        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        panel.SetSizer(sizer)

        self.SetIcon(wx.Icon(os.path.join(self._icon_folder, "wall.png")))
        self.SetSize((600, 300))
        self.SetTitle('Wallpaper Changer')
        # self.Centre()

    def OnQuit(self, e):
        self.Close()

    def _init_toolbar(self):
        toolbar = self.CreateToolBar()
        tool_start = toolbar.AddTool(wx.ID_ANY, 'Start', wx.Bitmap(
            os.path.join(self._icon_folder, 'Start-icon.png')))
        tool_prev = toolbar.AddTool(wx.ID_ANY, 'Previous', wx.Bitmap(
            os.path.join(self._icon_folder, 'back-icon.png')))
        tool_next = toolbar.AddTool(wx.ID_ANY, 'Next', wx.Bitmap(
            os.path.join(self._icon_folder, 'forward-icon.png')))
        tool_stop = toolbar.AddTool(wx.ID_ANY, 'Stop', wx.Bitmap(
            os.path.join(self._icon_folder, 'Stop-red-icon.png')))
        tool_left = toolbar.AddTool(wx.ID_ANY, 'Left', wx.Bitmap(
            os.path.join(self._icon_folder, 'Arrow-turn-left-icon.png')))
        tool_right = toolbar.AddTool(wx.ID_ANY, 'Right', wx.Bitmap(
            os.path.join(self._icon_folder, 'Arrow-turn-right-icon.png')))
        tool_edit = toolbar.AddTool(wx.ID_ANY, 'Edit', wx.Bitmap(
            os.path.join(self._icon_folder, 'edit-icon.png')))
        tool_clip = toolbar.AddTool(wx.ID_ANY, 'clipboard', wx.Bitmap(
            os.path.join(self._icon_folder, 'copy-icon.png')))
        tool_clean = toolbar.AddTool(wx.ID_ANY, 'cleanup', wx.Bitmap(
            os.path.join(self._icon_folder, 'data-add-icon.png')))
        tool_refresh = toolbar.AddTool(wx.ID_ANY, 'Refresh', wx.Bitmap(
            os.path.join(self._icon_folder, 'Rules-icon.png')))
        tool_del = toolbar.AddTool(wx.ID_ANY, 'Delete', wx.Bitmap(
            os.path.join(self._icon_folder, 'Trash-icon.png')))
        tool_safe = toolbar.AddTool(wx.ID_ANY, 'Safe', wx.Bitmap(
            os.path.join(self._icon_folder, 'Accept-icon.png')))
        toolbar.Realize()

        # set buttons callback
        def resume(evt):
            scheduler.resume()

        def pause(evt):
            scheduler.pause()

        def rotate_left(evt):
            rotate_wallpaper(90)

        def rotate_right(evt):
            rotate_wallpaper(270)

        def refresh(evt):
            global current_fn
            cleanup()
            try:
                set_wallpaper(current_fn)
            except FileNotFoundError:
                bn, ext = os.path.splitext(current_fn)
                fn = bn + '.png'
                current_fn = fn
                set_wallpaper(current_fn)
            else:
                return

        def rotate_wallpaper(degree):
            scheduler.pause()
            img = Image.open(current_fn)
            img = img.rotate(degree, expand=True)
            img.save(current_fn)
            img.close()
            set_wallpaper(current_fn)

        def clipboard(*args):
            scheduler.pause()
            pd.DataFrame([current_fn]).to_clipboard(index=False, header=False)
            mod_fn = current_fn.replace(syndrive, r'D:\SynologyDrive') \
                .replace('/', '\\')
            with open(os.path.join(os.path.dirname(__file__), 'mark.txt'), 'a+') as f:
                f.write(f'{mod_fn}\n')

        def delete(evt):
            need_to_resume = False
            if scheduler.state == 1:
                scheduler.pause()
                need_to_resume = True
            print('    - Deleted')
            send2trash(current_fn)
            change_wallpaper()
            if need_to_resume:
                scheduler.resume()

        def edit(evt):
            os.startfile(current_fn)

        def safe(evt):
            scheduler.pause()
            set_wallpaper(GLOBAL_config['safewp'])

        self.Bind(wx.EVT_TOOL, resume, tool_start)
        self.Bind(wx.EVT_TOOL, prev_wallpaper, tool_prev)
        self.Bind(wx.EVT_TOOL, change_wallpaper, tool_next)
        self.Bind(wx.EVT_TOOL, pause, tool_stop)
        self.Bind(wx.EVT_TOOL, rotate_left, tool_left)
        self.Bind(wx.EVT_TOOL, rotate_right, tool_right)
        self.Bind(wx.EVT_TOOL, clipboard, tool_clip)
        self.Bind(wx.EVT_TOOL, edit, tool_edit)
        self.Bind(wx.EVT_TOOL, refresh, tool_refresh)
        self.Bind(wx.EVT_TOOL, cleanup, tool_clean)
        self.Bind(wx.EVT_TOOL, delete, tool_del)
        self.Bind(wx.EVT_TOOL, safe, tool_safe)

        # Create an accelerator table
        self.accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), tool_start.GetId()),
            (wx.ACCEL_CTRL, ord('P'), tool_stop.GetId()),
            (wx.ACCEL_CTRL, ord('B'), tool_prev.GetId()),
            (wx.ACCEL_CTRL, ord('F'), tool_next.GetId()),
            (wx.ACCEL_CTRL, ord('D'), tool_del.GetId()),
            (wx.ACCEL_CTRL, ord('L'), tool_left.GetId()),
            (wx.ACCEL_CTRL, ord('R'), tool_right.GetId()),
        ])
        self.SetAcceleratorTable(self.accel_tbl)


def main_gui():
    app = wx.App()
    ex = Example(None)
    ex.Show()
    change_wallpaper()
    app.MainLoop()


if __name__ == '__main__':
    current_fn = None
    read_config()
    scheduler = BackgroundScheduler()
    scheduler.add_job(change_wallpaper, 'interval',
                      minutes=GLOBAL_config['interval'], id='change')
    scheduler.start()
    main_gui()

# change_wallpaper()
