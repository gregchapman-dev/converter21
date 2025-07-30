import sys
import argparse
import glob
import os

'''
    main entry point (parse arguments and do conversion)
'''
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='python findmultiscorekern.py',
        description='Search a folder recursively for .krn/.kern files'
            ' that contain multiple scores'
    )
    parser.add_argument('search_folder',
                        help='folder to search')
    args = parser.parse_args()

    folder: str = args.search_folder
    folder = os.path.expanduser(folder)
    folder = glob.escape(folder)
    pathList = list(glob.iglob(folder + '/**/*.kern', recursive=True))
    pathList += list(glob.iglob(folder + '/**/*.krn', recursive=True))
    contents = ''
    for pathstr in pathList:
        try:
            with open(pathstr, 'rt', encoding='utf-8') as f:
                contents = f.read()
        except UnicodeDecodeError:
            try:
                with open(pathstr, 'rt', encoding='latin-1') as f:
                    contents = f.read()
            except UnicodeError:
                with open(pathstr, 'rt', encoding='utf-16') as f:
                    contents = f.read()
        contents = contents.split('\n')
        num_end_interps = 0
        num_segments = 0
        for line in contents:
            if line.startswith('*-'):
                num_end_interps += 1
            if line.startswith('!!!!SEGMENT'):
                num_segments += 1
        if num_end_interps > 1:
            print(f'{pathstr}: {num_end_interps} scores')
        if num_segments > 1:
            print(f'{pathstr}: {num_segments} SEGMENTS')
    print('done.')

