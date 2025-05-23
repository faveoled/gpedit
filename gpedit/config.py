#-*- coding: utf-8 -*-
'''
User configuration file handling.
'''

import configparser
import os

CFG_DEFAULTS={
              'user macros': {},
              'gui': {
                      'data file filters': ';'.join(['*.dat', '*.txt', '*.out']),
                      },
              }

# User config settings
CFG_PATH=os.path.join(os.path.expanduser('~'), '.gpedit')
CFG_FILE=os.path.join(CFG_PATH, 'config.ini')


cfg=configparser.ConfigParser()
cfg.optionxform=str # allow upper case option names

def write_config():
  cfg.write(open(CFG_FILE, 'w'))

if not os.path.exists(CFG_PATH):
  os.mkdir(CFG_PATH)
if os.path.exists(CFG_FILE):
  cfg.read_file(open(CFG_FILE, 'r'))
else:
  for key, settings in list(CFG_DEFAULTS.items()):
    cfg.add_section(key)
    for subkey, item in list(settings.items()):
      cfg.set(key, subkey, item)
  write_config()

def add_user_macro(name, text):
  cfg.set('user macros', name, text)
  write_config()

def del_user_macro(name):
  cfg.remove_option('user macros', name)
  write_config()
