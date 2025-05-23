set term pngcairo size 16,16
set output "palette_bwr.png"

unset xtics
unset ytics
set pm3d map

set bmargin at screen 0
set tmargin at screen 1
set lmargin at screen 0
set rmargin at screen 1

unset tics
unset grid
unset border

unset colorbox

set palette defined (0 0 0 0.5, 1 0 0 1, 5 1 1 1, 9 1 0 0, 10 0.5 0 0) model RGB

splot x w pm3d
