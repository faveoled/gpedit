# -*- encoding: utf-8 -*-
'''
  Script used for setup and installation purpose. 
  
  The script can create exe stand alone programs under windows, but py2app doesn't word until now.
'''

import sys, os
from glob import glob
import matplotlib
from subprocess import call
from distutils.core import setup
try:
  # Use easy setup to ensure dependencies
  import ez_setup
  ez_setup.use_setuptools()
except ImportError:
  pass


__package_name__='gpedit'
__author__="Artur Glavic"
__copyright__="Copyright 2013"
__license__="GPL v3"
__email__="artur.glavic@gmail.com"
__author_email__=__email__
__url__="http://sourceforge.net/projects/gpedit"
__description__='''Interactive gnuplot script editor'''
__version__='1.5.1'

__scripts__=['gped']
__py_modules__=[]
__package_dir__={}
__packages__=['gpedit']
__package_data__={'gpedit': ['htmldocs/*.html']}

__data_files__=[
                ('/usr/share/applications', ['dist_data/GnuplotEditor.desktop']),
                ('/usr/share/icons/gnome/128x128/apps/', ['dist_data/GnuplotEditor_128x128.png']),
                ('/usr/share/mime/packages', ['dist_data/x-gnuplot.xml']),
                ]

if 'cx_Freeze' in sys.argv:
  FREEZE=True
  sys.argv.remove('cx_Freeze')
  sys.argv.append('build')
  from cx_Freeze import setup, Executable #@Reimport
  base=None
  if sys.platform=='win32':
      base='Win32GUI'
  __options__=dict(
                   executables=[Executable('gped', base=base,
                                           icon="dist_data/GnuplotEditor.ico")],
                   options={
                     'build_exe': {'includes':  []}
                     },
                   optimize=2
                  )
else:
  FREEZE=False
  __options__={}

__requires__=[]

# extensions modules written in C
__extensions_modules__=[]

if 'install' not in sys.argv:
  # Remove MANIFEST before distributing to be sure no file is missed
  if os.path.exists('MANIFEST'):
    os.remove('MANIFEST')

#### Run the setup command with the selected parameters ####
setup(name=__package_name__,
      version=__version__,
      description=__description__,
      author=__author__,
      author_email=__email__,
      url=__url__,
      scripts=__scripts__,
      py_modules=__py_modules__,
      ext_modules=__extensions_modules__,
      packages=__packages__,
      package_dir=__package_dir__,
      package_data=__package_data__,
      data_files=__data_files__,
      requires=__requires__, #does not do anything
      **__options__
     )

if 'bdist' in sys.argv:
  # build debian package from rpm
  print('Building .deb ...')
  os.chdir('dist')
  call(['fakeroot', 'alien', '-k', '-g', __package_name__+'-'+__version__+'-1.noarch.rpm'])
  os.chdir(__package_name__+'-'+__version__)
  open('debian/control', 'w').write(open('../../dist_data/deb_control', 'r').read())
  call(['dpkg-buildpackage', '-i.*', '-I', '-rfakeroot', '-us', '-uc'])
  os.chdir('..')
  call(['rm', '-r', __package_name__+'-'+__version__])
  call(['rm', __package_name__+'_'+__version__+'.orig.tar.gz'])
  call(['rm', __package_name__+'_'+__version__+'-1_amd64.changes'])
  call(['rm', __package_name__+'_'+__version__+'-1.dsc'])
  call(['rm', __package_name__+'_'+__version__+'-1.diff.gz'])

if 'py2app' in sys.argv:
  # add qt.conf which fixes issues with the app and a currently installed qt4 library
  open('dist/quickplot.app/Contents/Resources/qt.conf', 'w').write(open('dist_data/qt.conf', 'r').read())
elif FREEZE:
  # copy gnuplot into build folder to prepare packaging
  call(r'xcopy /Y /S /I ..\gnuplot\bin build\exe.win-amd64-3.6\gnuplot')
