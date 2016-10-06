#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import codecs
import os
import sys
import re

def parse_ls(f_lines, ctg):
    '''parse stud_list, export to vCard'''

    for ln in f_lines:
        if ln != '\n':
            ln = ln.strip()
            ln_ls = ln.split('//')
            name = ln_ls[0]
            name_ls = name.split()

            fam = name_ls[0].encode('utf-8')
            sur = name_ls[1].encode('utf-8')
            orn = ''
            if len(name_ls) > 2:
                orn = name_ls[2].encode('utf-8') # сан
                n_full = fam + ';' + sur + ';;' + orn + '\n'
            else:
                n_full = fam + ';' + sur + ';;\n'

            email = ln_ls[1].encode('utf-8')
#        teleph = ln_ls[2]
#CATEGORIES:seniors_16_17
#        print name, email, teleph
            v_ln = 'BEGIN:VCARD\nVERSION:3.0\nCATEGORIES:' + ctg + '\nN:' + n_full + 'FN:' + ' '.join([sur, fam]) + '\nEMAIL:' + email + '\nEND:VCARD'
            print v_ln

if __name__ == '__main__':

    from optparse import OptionParser
    usage = "usage: %prog [options] filename"
    parser = OptionParser(usage=usage)

#    parser.add_option("-c", "--create", dest="create", action="store_true", help="Create new base")

    (options, args) = parser.parse_args()
    if args:
        if len(args) == 2:
            fp = codecs.open(args[0], "rb", "utf-8")
            f_lines = fp.readlines()
            fp.close()

            parse_ls(f_lines, args[1]) # (student-list, category:senior/minor
        else: 
            print 'not enough args, exiting'
            sys.exit(0)

# must export to .vcf
