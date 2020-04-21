# based on http://dzone.com/snippets/set-windows-desktop-wallpaper
from apscheduler.schedulers.background import BackgroundScheduler
from collections import Counter
from functools import partial
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS
from send2trash import send2trash
import ctypes
import glob
import json
import os
import random
import sys
import time
import win32api
import win32con
import win32gui
import wx

GLOBAL_config = {
    'interval': 10
}

last = []

config_fn = r'D:\dev\wallpaper_changer\config.txt'

def read_config():
    with open(config_fn) as f:
        GLOBAL_config.update(json.load(f))

def save_config():
    with open(config_fn, 'w') as f:
        json.dump(GLOBAL_config, f, indent=2)

def _setWallpaper(path, style='0'):
    key = win32api.RegOpenKeyEx(
        win32con.HKEY_CURRENT_USER, "Control Panel\\Desktop", 0, win32con.KEY_SET_VALUE)
    # 最后的参数:2拉伸,0居中,6适应,10填充
    win32api.RegSetValueEx(key, "WallpaperStyle", 0, win32con.REG_SZ, style)
    win32api.RegSetValueEx(key, "TileWallpaper", 0, win32con.REG_SZ, "0")
    win32gui.SystemParametersInfo(
        win32con.SPI_SETDESKWALLPAPER, path, win32con.SPIF_SENDWININICHANGE)


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
    style = '10' if .7 < ratio < 1.25 else '6'
    print(os.path.basename(fn))
    if not last or fn != last[-1]:
        last.append(fn)
        if len(last) > 10:
            last = last[-10:]
    if height < 1000:
        print('    - Small ({}x{})'.format(width, height))
    if ratio < .7:
        borders = [img.getpixel((i, j)) for i in (0, width-1)
                   for j in range(height)]
        counts = Counter(borders)
        color, cts = counts.most_common(1)[0]
        sim_ratio = cts / len(borders)
        if sim_ratio > .01:
            print('    - Edge Similarity: {}'.format(round(sim_ratio, 2)))
        if sim_ratio > .01:
            if height > 3000:
                print('    - Large ({}x{})'.format(width, height))
                img = img.resize((int(width / height * 3000 + .5), 3000))
                width, height = img.size
            need_w = height / 9 * 16
            margin = int((need_w - width) / 2 + .5)
            img = add_margin(img, 0, 0, margin, margin, color)
            fn = r'd:\dev\wallpaper_changer\tmp{}'.format(
                os.path.splitext(fn)[1])
            # print('\tPadding to 16:9')
            style = '10'
            img.save(fn)

    img.close()
    _setWallpaper(fn, style)


def change_wallpaper(*args):
    global current_fn
    folder = r'D:\Pictures\Eye Candy'
    allpics = glob.glob(os.path.join(folder, '*/*.jpg')) + \
        glob.glob(os.path.join(folder, '*/*.png'))
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
        vbox.Add(hbox1, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # vbox.Add((-1, 10))


        vbox.Add((-1, 25))

        hbox5 = wx.BoxSizer(wx.HORIZONTAL)
        btn1 = wx.Button(self, label='Apply', size=(70, 30))
        hbox5.Add(btn1)
        # btn2 = wx.Button(panel, label='Close', size=(70, 30))
        # hbox5.Add(btn2, flag=wx.LEFT | wx.BOTTOM, border=5)
        vbox.Add(hbox5, flag=wx.ALIGN_RIGHT | wx.RIGHT, border=10)

        self.SetSizer(vbox)

        self.Bind(wx.EVT_BUTTON, self._update_interval, btn1)
    
    def _update_interval(self, *args):
        try:
            interval = int(self.interval_ctrl.GetLineText(0))
            if interval < 1:
                raise ValueError
        except ValueError:
            return
        GLOBAL_config['interval'] = interval
        scheduler.pause()
        scheduler.reschedule_job('change', trigger='interval', minutes=GLOBAL_config['interval'])
        scheduler.resume()
        save_config()


class TabLog(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        log = wx.TextCtrl(self, wx.ID_ANY, size=(480, 133),
                          style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        # redirect text here
        redir = RedirectText(log)
        sys.stdout = redir


class Example(wx.Frame):

    def __init__(self, *args, **kwargs):
        super(Example, self).__init__(*args, **kwargs)
        self._icon_folder = r'D:/dev/wallpaper_changer/assets/'

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

        self.SetIcon(wx.Icon("D:/dev/wallpaper_changer/assets/wall.png"))
        self.SetSize((500, 250))
        self.SetTitle('Wallpaper Changer')
        self.Centre()

    def OnQuit(self, e):
        self.Close()

    def _init_toolbar(self):
        toolbar = self.CreateToolBar()
        tool_start = toolbar.AddTool(wx.ID_ANY, 'Start', wx.Bitmap(
            self._icon_folder + 'Start-icon.png'))
        tool_prev = toolbar.AddTool(wx.ID_ANY, 'Previous', wx.Bitmap(
            self._icon_folder + 'back-icon.png'))
        tool_next = toolbar.AddTool(wx.ID_ANY, 'Next', wx.Bitmap(
            self._icon_folder + 'forward-icon.png'))
        tool_stop = toolbar.AddTool(wx.ID_ANY, 'Stop', wx.Bitmap(
            self._icon_folder + 'Stop-red-icon.png'))
        tool_left = toolbar.AddTool(wx.ID_ANY, 'Left', wx.Bitmap(
            self._icon_folder + 'Arrow-turn-left-icon.png'))
        tool_right = toolbar.AddTool(wx.ID_ANY, 'Right', wx.Bitmap(
            self._icon_folder + 'Arrow-turn-right-icon.png'))
        tool_del = toolbar.AddTool(wx.ID_ANY, 'Delete', wx.Bitmap(
            self._icon_folder + 'Trash-icon.png'))
        # toolbar.SetToolBitmapSize((32, 32))
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

        def delete(evt):
            send2trash(current_fn)
            change_wallpaper()

        self.Bind(wx.EVT_TOOL, resume, tool_start)
        self.Bind(wx.EVT_TOOL, prev_wallpaper, tool_prev)
        self.Bind(wx.EVT_TOOL, change_wallpaper, tool_next)
        self.Bind(wx.EVT_TOOL, pause, tool_stop)
        self.Bind(wx.EVT_TOOL, rotate_left,  tool_left)
        self.Bind(wx.EVT_TOOL, rotate_right, tool_right)
        self.Bind(wx.EVT_TOOL, delete, tool_del)

        # Create an accelerator table
        self.accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), tool_start.GetId()),
            (wx.ACCEL_CTRL, ord('P'), tool_stop.GetId()),
            (wx.ACCEL_CTRL, ord('B'), tool_prev.GetId()),
            (wx.ACCEL_CTRL, ord('N'), tool_next.GetId()),
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


def rotate_wallpaper(degree):
    scheduler.pause()
    img = Image.open(current_fn)
    img = img.rotate(degree, expand=True)
    img.save(current_fn)
    img.close()
    set_wallpaper(current_fn)


if __name__ == '__main__':
    current_fn = None
    read_config()
    scheduler = BackgroundScheduler()
    scheduler.add_job(change_wallpaper, 'interval', minutes=GLOBAL_config['interval'], id='change')
    scheduler.start()
    main_gui()

# change_wallpaper()

# set_wallpaper(r'D:\Pictures\Eye Candy\Hyouka\anime-pictures.net - 611370 - hyouka+kyoto animation - chitanda eru.png')
