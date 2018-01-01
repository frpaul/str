#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import codecs
import os
import sys
import re
import unidecode as uni

def parse_ya(f_lines, ctg):
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

def parse_mo(f_lines):
    '''parse stud_list, export to vCard'''

    #print 'username,password,firstname,lastname,email,lang,cohort'
    print 'username,password,firstname,lastname,email,lang'
#    cohort = raw_input('Введите название курса (когорты)')

    for ln in f_lines:
        if ln != '\n':
            ln = ln.strip()
            ln_ls = ln.split('//')
            name = ln_ls[0]
            name_ls = name.split()

            # generate username
            user1 = uni.unidecode(name_ls[0]).replace("\'", '') # don't need quot marks in u-names
            user2 = uni.unidecode(name_ls[1]).replace("\'", '')
#            user_name = user1 + '_' + user2
            user_name = user1 + '.' + user2

            fam = name_ls[0].encode('utf-8')
            sur = name_ls[1].encode('utf-8')
            lang = 'RU'

            email = ln_ls[1].encode('utf-8')

#            users.append(user_name + ',' + ',' + sur + ',' + fam + ',' + email + '\n')
#            print user_name + ',' + ',' + sur + ',' + fam + ',' + email + ',' + lang, ',' + cohort
            print user_name + ',' + ',' + sur + ',' + fam + ',' + email + ',' + lang


if __name__ == '__main__':

    from optparse import OptionParser
    usage = "usage: %prog filename category"
    parser = OptionParser(usage=usage)
    parser.add_option("-y", "--yandex", dest="yandex", action="store_true", help="Create vcf file for yandex")
    parser.add_option("-m", "--moodle", dest="moodle", action="store_true", help="Create csv file for moodle")

#    parser.add_option("-c", "--create", dest="create", action="store_true", help="Create new base")

    (options, args) = parser.parse_args()
    if args:
        if options.yandex:
            if len(args) == 2:
                fp = codecs.open(args[0], "rb", "utf-8")
                f_lines = fp.readlines()
                fp.close()

                parse_ya(f_lines, args[1]) # 0: student-list, 1: категория: "senior" или "minor"
                
            else: 
                print 'not enough args, exiting'
                sys.exit(0)
        elif options.moodle:
            if len(args) == 1:
                fp = codecs.open(args[0], "rb", "utf-8")  # 0: student-list
                f_lines = fp.readlines()
                fp.close()

                parse_mo(f_lines)

            else: 
                print 'not enough args, exiting'
                sys.exit(0)
    else:
        print 'no args. Need --o[ption], file_name and [category]'
        sys.exit(0)

###### export to .vcf or .csv
# usage: ./parse_stud_ls.py -y stud_list.txt senior_17_18
# or:    ./parse_stud_ls.py -m stud_list.txt 
######
