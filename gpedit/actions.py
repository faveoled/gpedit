#-*- coding: utf-8 -*-
'''
Gnuplot action macros for the menus.
'''

SET_ACTIONS=[
   ['terminal', [
                 ['png', 'set term png #enhanced size w,h font "Arial,20" lw 2'],
                 ['pngcairo', 'set term pngcairo #enhanced size w,h font "Arial,20" lw 2'],
                 ['pdf', 'set term pdf #enhanced color solid size w,h font "Arial,20" lw 2'],
                 ['pdfcairo', 'set term pdfcairo #enhanced size w,h font "Arial,20" lw 2'],
                 ['postscript', 'set term postscript #landscape enhanced color solid size w,h "Arial,20"'],
                 ]
    ],
   ['output', 'set output "/tmp/test.png"'],
   ['margins', 'set bmargin at screen 0.15\nset tmargin at screen 0.95\nset lmargin at screen 0.1\nset rmargin at screen 0.95'],
   None,
   ['range', [
             ['x', 'set xrange [:]'],
             ['y', 'set yrange [:]'],
             ['z', 'set zrange [:]'],
             ['cb', 'set cbrange [:]'],
             ['auto x', 'set autoscale x'],
             ['auto y', 'set autoscale y'],
             ['auto z', 'set autoscale z'],
             ['auto cb', 'set autoscale cb'],
            ]
    ],
   ['log', [
             ['x', 'set log x'],
             ['y', 'set log y'],
             ['z', 'set log z'],
             ['cb', 'set log cb'],
            ]
    ],
   ['format', [
               ['10^x', [
                         ['x', 'set format x "10^{%L}"'],
                         ['y', 'set format y "10^{%L}"'],
                         ['z', 'set format z "10^{%L}"'],
                         ['cb', 'set format cb "10^{%L}"'],
                        ]],
               ['y·10^x', [
                         ['x', 'set format x "%.1l·10^{%L}"'],
                         ['y', 'set format y "%.1l·10^{%L}"'],
                         ['z', 'set format z "%.1l·10^{%L}"'],
                         ['cb', 'set format cb "%.1l·10^{%L}"'],
                        ]],
               ['default', [
                         ['x', 'set format x "% g"'],
                         ['y', 'set format y "% g"'],
                         ['z', 'set format z "% g"'],
                         ['cb', 'set format cb "% g"'],
                        ]],
               ['float', [
                         ['x', 'set format x "% f"'],
                         ['y', 'set format y "% f"'],
                         ['z', 'set format z "% f"'],
                         ['cb', 'set format cb "% f"'],
                        ]],
            ]
    ],
    None,
   ['labels', [
             ['title', 'set title ""'],
             ['x', 'set xlabel ""'],
             ['y', 'set ylabel ""'],
             ['z', 'set zlabel ""'],
             ['cb', 'set cblabel ""'],
             ['text', 'set label "" at 0,0 #front center point'],
            ]
    ],
   ['draw', [
               ['arrow', 'set arrow from 0,0 to 0,0 #nohead front'],
               ['rect', 'set object rect from 0,0 to 0,0 #front'],
               ['circ', 'set object circ at 0,0 size 0,0 #front arc [from:to]'],
    ],
    ],
    None,
   ['tics', [
             ['x', 'set xtics'],
             ['y', 'set ytics'],
             ['z', 'set ztics'],
             ['cb', 'set cbtics'],
            ]
    ],
   ['grid', 'set grid #front lw 2'],
   ['border', 'set border #front lw 2'],
   None,
   ['colorbox', 'set colorbox #horizontal origin x,y size x,y'],
   ['pm3d', 'set pm3d map #interpolate 3,3 clip4in cornors2color mean|geomean|median|min|max|c1|c2|c3|c4'],
             ]

PALETTS=[
               ['default', ':/misc/palette_default.png',
                'set palette defined (0 "blue", 1 "green", 2 "yellow", 3 "red", 4 "purple", 5 "black") model RGB'],
               ['default WB', ':/misc/palette_default_wb.png',
                'set palette defined (0 "white", 0.001  "blue", 1 "green", 2 "yellow", 3 "red", 4 "purple", 5 "black") model RGB'],
               ['GLI', ':/misc/palette_gli.png',
                'set palette functions (gray*5./6.<0.75)?0.75-gray*5./6.:1.75-gray*5./6., 0.857, 0.875 model HSV'],
               ['Black to Red', ':/misc/palette_black_red.png',
                'set palette defined (0 "black", 1 "purple", 2 "blue", 3 "green", 4 "yellow",  5 "red") model RGB'],
               ['Grey Scale', ':/misc/palette_gray.png',
                'set palette gray model RGB'],
               ['Blue,Green,Yellow,Red', ':/misc/palette_bgyr.png',
                'set palette defined (0 "blue",1 "green", 2 "yellow",3 "red") model RGB'],
               ['Black to Yellow', ':/misc/palette_bty.png',
                'set palette defined (0 "black",1 "blue", 2 "red",3 "yellow") model RGB'],
               ['Gnuplot', ':/misc/palette_gp.png',
                'set palette rgbformulae 7,5,15 model RGB'],
               ['MARIA log', ':/misc/palette_mlog.png',
                'set palette defined (0 0 0 0 , 1 0 1 0, 2 0 0 1, 3 1 0 0, 4 0 1 1 , 5 1 0 1, 6 1 1 0, 7 1 1 1) model RGB'],
               ['MARIA lin', ':/misc/palette_mlin.png',
                'set palette defined (0 1 1 1 , 1 0 1 0, 2 0 0 1, 3 1 0 0, 4 0 1 1 , 5 1 0 1, 6 1 1 0, 7 1 1 1) model RGB'],
               ['fit2d', ':/misc/palette_f2d.png',
                'set palette defined (0 "#000000", 1 "#0000d1", 2 "#c3c3ff", 3 "#9ee246", 4 "#fdfe78", 5.5 "#cc8800", 6.5 "#dc3ef7", 7.5 "#ffffff") model RGB'],
               ['rainbow', ':/misc/palette_rainbow.png',
                'set palette rgbformulae 22,13,-31 model RGB'],
               ['hot', ':/misc/palette_hot.png',
                'set palette rgbformulae 21,22,23 model RGB'],
               ['color gray printable', ':/misc/palette_cgp.png',
                'set palette rgbformulae 31,32,33 model RGB'],
               ['Blue/White/Red', ':/misc/palette_bwr.png',
                'set palette defined (0 0 0 0.5, 1 0 0 1, 5 1 1 1, 9 1 0 0, 10 0.5 0 0) model RGB'],
         ]

TEMPLATE='''set term pngcairo enhanced size 1600,1200 font "Arial,28" lw 2
set encoding utf8

set title "Plot Title"
set xlabel "x"
set ylabel "y"

set output "%s/test.png"
plot sin(x) w lines
'''

