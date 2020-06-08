#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 22 14:03:13 2018

@author: Joker
"""

import glob
import os
import pprint
from collections import Counter
from send2trash import send2trash

animes = {
    "dota 2 (game)": "defense of the ancients",
    "emiya-san chi no kyou no gohan": "fate",
    "fate": "fate",
    "ghost blade":"ghostblade",
    "idolm@ster": "idolmaster",
    "monogatari": "monogatari",
    "nier automata": "nier automata",
    "nier": "nier automata",
    "white album 2": "white album",
    "white album": "white album",
    "yahari ore no seishun lovecome wa machigatteiru": "yahari ore no seishun love comedy wa machigatteiru",
}

pic_dir = r'D:\SynologyDrive\Pictures\Eye Candy' if os.name == 'nt' else '/Users/Joker/SynologyDrive/Pictures/Eye Candy'


def cleanup(*args):
    pwd = os.getcwd()
    os.chdir(pic_dir)

    # clean up suffix
    suffix = '_waifu2x'
    allf = glob.glob('./*/*')
    allfmap = {os.path.splitext(os.path.basename(f))[0]: f for f in allf}
    for fn in glob.glob('./*/*') + glob.glob('./*.*'):
        if suffix in fn:
            print(f'cleaning up {fn}')
            bn, ext = os.path.splitext(os.path.basename(fn))
            bn = bn[:bn.index('_waifu2x')]
            orig = allfmap.get(bn)
            if orig:
                print(f'deleting: {orig}')
                send2trash(orig)
                to = os.path.splitext(orig)[0] + ext
            else:
                to = fn[fn.index('_waifu2x')] + ext
            os.rename(fn, to)

    # put pics into folders
    idle = glob.glob('./*.*')
    for fn in idle:
        bn = os.path.basename(fn)
        anime = bn.split(' - ')
        if len(anime) >= 3:
            anime = anime[2].strip()
        else:
            continue
        to = './{}/{}'.format(anime, bn)
        print(f'moving: {bn} to {to}')
        if os.path.exists(to):
            os.remove(fn)
        else:
            try:
                os.rename(fn, to)
            except FileNotFoundError:
                os.makedirs(f'./{anime}')
                os.rename(fn, to)


    # clean up folders
    folders = glob.glob("./*/")
    for f in folders:
        for badname, goodname in animes.items():
            if badname in f and f[2:-1] != goodname:
                print(f'moving: {f} to {goodname}')
                pics = glob.glob(f'./{f}/*')
                for p in pics:
                    to = './{}/{}'.format(goodname, os.path.basename(p))
                    if os.path.exists(to):
                        os.remove(p)
                    else:
                        os.rename(p, to)
    for f in folders:
        if not os.listdir(f):
            print(f'deleting: {f}')
            try:
                os.rmdir(f)
            except:
                print(f'FAILED: {f}')

    folders = glob.glob("./*/")
    pics = glob.glob('./*.jpg') + glob.glob('./*.png') + glob.glob('./*/*.jpg') + glob.glob('./*/*.png')
    print('Pics: {},  Folders: {}'.format(len(pics), len(folders)))

    os.chdir(pwd)

if __name__ == "__main__":
    cleanup()
