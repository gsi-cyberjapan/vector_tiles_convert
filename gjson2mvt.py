import os
from os import makedirs,listdir
from os.path import join,exists
from sys import exit


def mbtile(inpath,outpath,z):
    _in = join(inpath,z,'*','*.geojson')
    cmd = 'tippecanoe -o '+outpath+' -z '+z+' -Z '+z+' -ac -ar -ao -pp '+_in
    print cmd
    #os.system(cmd)

def pbf(inpath,outpath,z):
    _in = join(inpath,z)
    for yd in listdir(_in):
        for xf in listdir(join(_in,yd)):
            if not exists(join(outpath,z,yd)):
                makedirs(join(outpath,z,yd))
            nxf = xf.split('.')[0]+'.pbf'
            cmd = 'json2geobuf '+join(_in,yd,xf)+' > '+join(outpath,z,yd,nxf)
            print cmd
            os.system(cmd)

def help():
    print '''
    python gjson2mvt.py mbtile|pbf in_base out_base z

    in_base: path of base directory of input data
    out_base: (mbtile) path of base directory of output data
              (pbf)    path of output file
    z      : zoom level
    '''

if __name__ == '__main__':
    from sys import argv

    if not len(argv) == 5:
        help()
        exit()

    assert(argv[1] == 'mbtile' or argv[1] == 'pbf')

    if argv[1] == 'mbtile':
        mbtile(argv[2],argv[3],argv[4])
    elif argv[1] == 'pbf':
        pbf(argv[2],argv[3],argv[4])
