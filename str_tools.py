#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import codecs
import os
import sys
import re
import sqlite3

import logging
import datetime
import write_utf
import datetime
import types
import ConfigParser

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", filename="students.log", filemode="w", level=logging.INFO)

now = datetime.datetime.now()

Writer = write_utf.write_gen()

class Conduit:
    '''Create base, tables, insert-delete students etc'''

    def __init__(self, b_name=None):

        self.config = ConfigParser.ConfigParser()
        self.config.read(os.path.join(os.path.expanduser('~'), '.config', 'str', 'strrc'))

        if not b_name:
            self.b_name = self.config.get('Paths', 'stud_path1')
        else:
            self.b_name = b_name
        print 'b_name', self.b_name

        # get time
        self.date = now.strftime("%d_%m_%Y")
#        print self.date

    def create_base(self):

        conn = sqlite3.connect(self.b_name)
        cur = conn.cursor()

        command = "CREATE TABLE students (s_num INTEGER PRIMARY KEY, s_name TEXT, email TEXT, phone TEXT, photo TEXT, active TEXT, comment TEXT)"
        command2 = "CREATE TABLE attendance (a_num TEXT, s_num INTEGER, date TEXT, absence TEXT, comment TEXT)"
        command3 = "CREATE TABLE grades (g_num TEXT, s_num INTEGER, e_name TEXT, e_num INT, date TEXT, mark REAL, comment TEXT)"
        command4 = "CREATE TABLE lectures (e_id INTEGER PRIMARY KEY, date TEXT, topic TEXT, comment TEXT)"
        command5 = "CREATE TABLE seminars (e_id INTEGER PRIMARY KEY, date TEXT, topic TEXT, comment TEXT)"
        command6 = "CREATE TABLE tests (e_id INTEGER PRIMARY KEY, date TEXT, topic TEXT, comment TEXT)"
        command7 = "CREATE TABLE essays (e_id INTEGER PRIMARY KEY, date TEXT, enddate TEXT, topic TEXT, comment TEXT)"
        command8 = 'CREATE TABLE notes (c_num TEXT, s_num INTEGER, date TEXT, comment TEXT)' # TODO: make "fulfilled" or "acted_on" column
        command9 = 'CREATE TABLE assignments (a_num TEXT, s_num INTEGER, e_id INTEGER, delivered TEXT, date TEXT, mark REAL, comment TEXT)'
        for com in [command, command2, command3, command4, command5, command6, command7, command8, command9]:
            cur.execute(com) # TODO: executescript()

        cur.close()

    def open_base(self):
        # should check if the base is already opened

        if self.b_name:
            base_p = self.b_name
        else:
            home = os.path.expanduser('~')
            base_p = os.path.join(home, '/home/frpaul/svncod/trunk/studentus/stud_base_05_15_16.db')

        conn = sqlite3.connect(base_p)
        
#        cur = self.conn.cursor()

        return conn

    def ins_stud(self, data, tab_name):
        # data = (word_greek, word_slav, description)
        
        conn = self.open_base()
        cur = conn.cursor()
            
#        cur.execute("INSERT INTO " + tab_name + " (s_num, s_name, email, phone, photo, class) VALUES (?,?,?,?,?,?);", data)
#        cur.execute("INSERT INTO " + tab_name + " (s_name, email, phone, photo, class, comment) VALUES (?,?,?,?,?,?);", data)
        cur.execute("INSERT INTO " + tab_name + " (s_name, email, phone, photo, active, comment) VALUES (?,?,?,?,?,?);", data)
        conn.commit()
        cur.close()

        print 'Inserted: ' + ', '.join(data) + ' into base'

#    def exec_sql(self, b_name=None, command=None):
    def exec_sql(self, **kw):
        
        if not kw['b_name']:
            b_name = self.b_name
        else:
            b_name = kw['b_name']
        command = kw['command']

        if not command:
            command = 'select b_greek, c_slav, d_rus, e_desc from dictionary order by a_num'

        con = sqlite3.connect(b_name)
        cur = con.cursor()

        cur.execute(command)
        if command.startswith('insert') or command.startswith('update') or command.startswith('delete') or command.startswith('drop'):
            if debug:
                print command
            else:
                con.commit()
        else:
            res = cur.fetchall()

            for i in res:
                print '---------------------'
                for x in i:
#            if x and not type(x) == types.IntType and not type(x):
                    if x and type(x) == types.StringType:
                        x = x.encode('utf-8')
                    print x
        con.close()


    def parse_event(self, f_lines):

        conn = self.open_base()
        cur = conn.cursor()

        for n in range(len(f_lines)):
#            data = self.reg.findall(line)[0]
            line = f_lines[n]
            line = line.strip()
            # commentaries (e.g. text already inserted into base)
            if line.startswith('#'):
                continue
            if '||' in line:
#                line = self.get_uuid() + '||' + line
                data = line.split('||')
            elif '//' in line:
#                line = self.get_uuid() + '//' + line
                data = line.split('//')
            else:
                print 'no delimiter in line', n
                logging.info('no delimiter in line %s', n)
                continue
            data.append('') # for comment
            e_type = data.pop(0) # letter goes first in event_list: l//date//topic
            d_sp = data[0].split('-')
            data[0] = datetime.date(int(d_sp[0]), int(d_sp[1]), int(d_sp[2])).strftime('%Y-%m-%d') # нужны даты с ноликами Ж)

            for s in ['lectures', 'seminars', 'essays', 'tests']: 
                if s.startswith(e_type):
                    print 'found type'

                    cur.execute("INSERT INTO " + s + " (date, topic, comment) VALUES (?,?,?);", data)
                
                    print 'Inserted: ' + ', '.join(data) + ' into base'
#        cur.execute("INSERT INTO " + tab_name + " (s_num, s_name, email, phone, photo, class) VALUES (?,?,?,?,?,?);", data)
            conn.commit()
        cur.close()


    def parse_stud(self, f_lines):
        """Parse students data from file"""

        for n in range(len(f_lines)):
#            data = self.reg.findall(line)[0]
            line = f_lines[n]
            line = line.strip()
            # commentaries (e.g. text already inserted into base)
            if line.startswith('#'):
                continue

            if '||' in line:
#                line = self.get_uuid() + '||' + line
                data = line.split('||')
            elif '//' in line:
#                line = self.get_uuid() + '//' + line
                data = line.split('//')
            else:
                print 'no delimiter in line', n
                logging.info('no delimiter in line %s', n)
                continue
            data.append('')
            if len(data) > 6:
                print 'too many chunks in', n
                logging.info('too many chunks in %s', n)
            if len(data) < 6:
                print 'too few chunks in', n
                logging.info('too few chunks in %s', n)
#            for i in data:
#                print i.strip()
            else:
                self.ins_stud(data, 'students')
#                print 'OK in', n
#

    def pr_base(self, pr_b, tab=None):
        """print base to file (dump text)"""
        print 'printing from base'
        conn = self.open_base()
        cur = conn.cursor()
        if tab == 'grades':
            cur.execute('select s_name, event, date, mark from grades join students on grades.s_num = students.s_num')
            res = cur.fetchall()
            pr = []
#            print 'date', self.date
            pr.append(self.date + '\n')
            for n, e, d, m in res:
                ln = ' '.join([n, e, d, str(m)]) +'\n'
                pr.append(ln)
            if pr_b:
                Writer.write_file('grades_dump', pr, 'a')
            else:
                for i in pr:
                    print i.strip()

        elif tab == 'attendance':
            cur.execute('select s_name, date, absence, comment from attendance join students on attendance.s_num = students.s_num')
            res = cur.fetchall()
            pr = []
            pr.append(self.date + '\n')
            for s, d, a, c in res:
                ln =  ' '.join([s, d, a, c]) + '\n'
                pr.append(ln)
            if pr_b:
                Writer.write_file('attend_dump', pr, 'a')
            else:
                for i in pr:
                    print i.strip()

        elif tab == 'students':
            cur.execute('select * from students')
            res = cur.fetchall()
            pr = []
            for a,b,c,d,e,f,j in res:
                ln = ' '.join([str(a),b,c,d,e,f,j]) + '\n'
                pr.append(ln)
            if pr_b:
                Writer.write_file('students_dump', pr, 'a')
            else:
                for i in pr:
                    print i.strip()




        cur.close()
#        command = "SELECT * FROM " + tab_name + " ORDER BY b_greek"
#        rows = self.get_f_base(command)
#
#        out_l = []
#
#        for row in rows:
#            itms = []
#
#            for itm in [row[1], '||', row[2], '||', row[3], '||', row[4]]:
#                n_itm = itm.replace('\n', '; ')
#                n_itm = n_itm.strip()
#                itms.append(n_itm)
#
#            out_l.append(''.join(itms))
#            out_l.append('\n')
#
#
#    def update_txt(self, row, col, text, tab_name='dictionary'):
#        '''Update entry in the table'''
#
#        command = "SELECT * FROM " + tab_name + " WHERE a_num=\"" + str(row) + "\""
#        res = self.get_f_base(command)
#        old_text = res[0][int(col)]
#        new_text = ''.join([old_text, '; ', text])
#
#        print new_text
#
#        command = "UPDATE " + tab_name + " SET " + self.cols[int(col) - 1] + "=\"" + new_text + "\" WHERE a_num=\"" + str(row) + "\""
#

if __name__ == '__main__':

#    cond = Conduit()
    global debug
    debug = False

    from optparse import OptionParser
    usage = "usage: %prog [options] filename"
    parser = OptionParser(usage=usage)

    parser.add_option("-c", "--create", dest="create", action="store_true", help="Create new base")
    parser.add_option("-p", "--print_b", dest="print_b", action="store_true", help="Output from base - look up some tables")
    parser.add_option("-w", "--write", dest="write", action="store_true", help="Print base entries as formatted text into file")
    parser.add_option("-r", "--read", dest="read", action="store_true", help="Read text from \"student_list\" file, parse and insert into base")
    parser.add_option("-i", "--insert", dest="insert", action="store_true", help="Read text from \"event_list\" file, parse and insert into base")
    parser.add_option("-d", "--dryrun", dest="dryrun", action="store_true", help="Test stuff")
    parser.add_option("-l", "--line", dest="line", action="store_true", help="Read text from string, parse and insert into base")
    parser.add_option("-t", "--testsql", dest="testsql", action="store_true", help="Test SQL command")

    (options, args) = parser.parse_args()
    if args:
        if options.create:
            main_f = Conduit(args[0])
            # needs NO table name as an argument
            main_f.create_base()

        elif options.print_b:
            # print base entries into text file
            main_f = Conduit(args[0])
            main_f.pr_base(False, args[1])

        elif options.write:
            # outbut from base
            main_f = Conduit(args[0])
            main_f.pr_base(True, args[1])

        elif options.insert:
            # stud_tools -i base_name events_list.txt
            main_f = Conduit(args[0])
            fp = codecs.open(args[1], "rb", "utf-8")
            f_lines = fp.readlines()
            fp.close()

            main_f.parse_event(f_lines)

        elif options.read:
            # read students data file,
            # insert formatted lines into base 
            # (separator: // or ||)
            # args: 0=base, 1=tab, 2=file_name

            main_f = Conduit(args[0])
#            fp = codecs.open("student_list.txt", "rb", "utf-8")
            fp = codecs.open(args[1], "rb", "utf-8")
            f_lines = fp.readlines()
            fp.close()

            # strings and table name to parse 
            main_f.parse_stud(f_lines)

        elif options.dryrun:
            debug = True

        elif options.testsql:
            main_f = Conduit()
#            main_f.exec_sql(args[0])
#            main_f.exec_sql(*args)
            if len(args) > 1:
                bb = args[0]
                cc = args[1]
            else:
                bb = None
                cc = args[0]
            main_f.exec_sql(b_name=bb, command=cc)

        elif options.line:
            # isert formatted line into base (separator: // or ||)
            # args: 0=base, 1=tab, 2=string
            main_f = Conduit(args[0])
            string1 = args[2].decode('utf8')
            # str and table name to parse 
            main_f.parse_txt([string1,], args[1])

# TODO: -s for different bases
# TODO: 
# TODO: 
