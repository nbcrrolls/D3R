#!/Users/robswift/.virtualenvs/d3r2.7_12.4.15/bin/python

__author__ = 'robswift'

import argparse
import os
import sys
import xlsxwriter
from rdkit import Chem
from rdkit.Chem import Draw
from io import BytesIO


class MakeSheet(object):

    inchi_dict = {}
    inchi_file = None
    @staticmethod
    def set_inchi_dict(compinchi):
        MakeSheet.inchi_file = compinchi
        handle = open(MakeSheet.inchi_file, 'r')
        for line in handle.readlines():
            try:
                words = line.split()
                if words:
                    inchi = words[0]
                    resname = words[1]
                MakeSheet.inchi_dict[format(resname)] = format(inchi)
            except:
                continue
        handle.close()

    def __init__(self):
        self.out_dir = None
        self.image_file = None
        self.content_dict = None
        self.work_book = None
        self.header = ['Resname', 'Molecule']
        self.header_format = None
        self.body_format = None
        self.size = (25, 39.2)

    def make_sheet(self, out_file):
        bk_file = os.path.join(self.out_dir, 'dockable.xlsx')
        self.work_book = xlsxwriter.Workbook(bk_file)
        work_sheet = self.work_book.add_worksheet()
        work_sheet.set_column('A:A', self.size[0])
        work_sheet.set_column('B:B', self.size[1])
        self.set_header_format()
        self.set_body_format()
        self.write_header(work_sheet)
        self.write_data(work_sheet)

    def set_header_format(self):
        self.header_format = self.work_book.add_format()
        self.header_format.set_align('center')
        self.header_format.set_font_size(16)
        self.header_format.set_bold(True)

    def set_body_format(self):
        self.body_format = self.work_book.add_format()
        self.body_format.set_align('center')
        self.body_format.set_align('vcenter')
        self.body_format.set_font_size(14)

    def write_header(self, work_sheet):
        c = 0
        for col in self.header:
            work_sheet.write_string(0, c, col, self.header_format)
            c += 1

    def write_data(self, work_sheet):
        r = 1
        for resname in self.content_dict.keys():
            work_sheet.set_row(r, 215)
            c = 0
            work_sheet.write_string(r, c, resname, self.body_format)
            c += 1
            if self.make_image(resname):
                image_handle = open(self.image_file, 'rb')
                image_data = BytesIO(image_handle.read())
                image_handle.close()
                self.rm_image()
                work_sheet.insert_image(r, c, "f", {'image_data' : image_data, 'x_offset' : 4 ,'y_offset': 8,
                                            'positioning' : 1})

            else:
                work_sheet.write_string(r, c, 'N/A', self.body_format)
            r += 1
        self.work_book.close()

    def make_image(self, resname):
        if not self.image_file:
            self.set_image_file()
        if not MakeSheet.inchi_dict:
            MakeSheet.set_inchi_dict()
        try:
            inchi = MakeSheet.inchi_dict[resname]
            rd_mol = Chem.MolFromInchi(format(inchi), sanitize=True, treatWarningAsError=True)
            Draw.MolToFile(rd_mol, self.image_file, size=(275,275))
            return True
        except:
            return False

    def set_image_file(self):
        self.image_file = os.path.join(self.out_dir, 'tmp_img.png')

    def rm_image(self):
        os.remove(self.image_file)

def read_log(path, compinchi):
    """
    read log file and add resname and inchi to d = dict {'resname': inchi}
    :param path:
    :return: d
    """
    if not MakeSheet.inchi_dict:
        MakeSheet.set_inchi_dict(compinchi)
    f = os.path.join(path, 'blastnfilter.log')
    content_dict = {}
    handle = open(f, 'r')
    for line in handle.readlines():
        if 'Ligand:' in line:
            resname = line.split()[1].split('|')[0]
            if resname not in content_dict.keys():
                try:
                    inchi = MakeSheet.inchi_dict[resname]
                    content_dict[resname] = inchi
                except KeyError:
                    print resname
                    continue
    return content_dict

def cmd_line():
    parser = argparse.ArgumentParser()

    parser.add_argument("dir", help='stage.2.blastnfilter directory')
    parser.add_argument('--compinchi', help='Path to Components-inchi.ich file',
                        required=True)
    return parser.parse_args()

def run():
    parsed_args = cmd_line()
    out_dir = os.path.abspath(parsed_args.dir)
    content_dict = read_log(out_dir, parsed_args.compinchi)
    make_sheet = MakeSheet()
    make_sheet.out_dir = out_dir
    make_sheet.content_dict = content_dict
    make_sheet.make_sheet(out_dir)

if __name__ == "__main__":
    sys.exit(run())