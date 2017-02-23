#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import pygtk
pygtk.require('2.0')
import gtk
import pango

import codecs
import os
import sys
import re
import sqlite3
import uuid
import tarfile

import ConfigParser
import types
import logging
import datetime

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", filename="students.log", filemode="w", level=logging.INFO)

now = datetime.datetime.now()

#global self.c_group
# temporary list of grades. After 'Save' is pressed list is written into base
global temp_grades # temp_ grades: [g_num, s_num, e_name, e_num, date, float(mark), comment]
temp_grades = []
# temp list of attendance
global temp_attend # temp_ attend: [a_num, s_num, date, absence, comment] # a_num - hash
temp_attend = []

global debug

class Conduit:
    '''Callbacks and other functions.'''

    def __init__(self, b_name=None, cm=None):

        self.cur_model = config.get('Settings', 'default_view') # current model used (0 = long sheet, 1 = short)
        if b_name:
            self.b_name = b_name
        else:
            self.b_name = None

        self.c_group = config.get('Settings', 'default_c_group')

        self.start_dialog_on = bool(int(config.get('Settings', 'start_dialog_on')))

        self.due = config.get('Settings', 'essays_due_time')  # Time for delivering essays 2 weeks.

        if debug:
#           self.date = now.strftime("%Y-%m-%d")
#           self.date = '2015-09-01'
#           self.date = '2015-09-08'
#           self.date = '2015-12-29'
#           self.date = '2016-01-26'
            self.date = '2016-02-02'
#           self.date = '2016-02-09'
#           self.date = '2016-02-16'
        else:
            self.date = now.strftime("%Y-%m-%d")

        self.ev_names = ['lectures', 'essays', 'seminars', 'tests']

        self.new_gr = False # There is a new grade in Details (not in temp_grades yet)
        self.new_ev = False # There is a new event in Events (not in the base yet)

        # get years and current semester LATER
#        self.year_ls = []
        self.semester = 0
    
#        self.year_ls = self.get_years() # (year1, year2, semester)
#        self.semester = self.year_ls[2]

    def rem_confirm(self, txt):
        ''' Confirmation dialog for removing stuff '''

        dialog = gtk.Dialog(txt, None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        response = dialog.run()
        if response == -3: # resp accepted
            dialog.destroy()
            return True
        else:
            dialog.destroy()
            return False

    def delete_cb(self, widget, event):
        if temp_grades or temp_attend:
            dialog = gtk.Dialog('Save into base?', None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_UNDO, gtk.RESPONSE_NONE, gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
            response = dialog.run()
#        print response
            if response == -3: # resp accepted
                self.save_into_b()
                dialog.destroy()
                return False
            elif response == -2: # resp rejected
                dialog.destroy()
                return True
        else:
            return False

    def destroy_cb(self, widget):
        gtk.main_quit()
               
    def redraw_cb(self, widget, event, c_id=None):
        ''' callback for main window. A key was pressed '''

        keyname = gtk.gdk.keyval_name(event.keyval)

        # get events menu
        if (keyname == "e" or keyname == "Cyrillic_u") and event.state & gtk.gdk.CONTROL_MASK:
            self.event_win = Events()

        # switch between long and short views
        elif (keyname == "w" or keyname == "Cyrillic_tse") and event.state & gtk.gdk.CONTROL_MASK:
            self.change_wk_model() # doesn't do anyth. yet
        
        # grab focus for some combobox
        elif (keyname == "c" or keyname == "Cyrillic_es") and event.state & gtk.gdk.CONTROL_MASK: #details of a student's grades and attend
            self.combo_b.grab_focus() # strange thing to do

#        elif (keyname == "r" or keyname == "Cyrillic_k") and event.state & gtk.gdk.CONTROL_MASK:
#            self.reload_ln()

        # Get students info menu
        elif (keyname == "i" or keyname == "Cyrillic_sha") and event.state & gtk.gdk.CONTROL_MASK:
            Stud_info()

        # save stuff
        elif (keyname == "s" or keyname == "Cyrillic_yeru") and event.state & gtk.gdk.CONTROL_MASK:
            self.save_into_b()

        #purgatory
        elif (keyname == "p" or keyname == "Cyrillic_ef") and event.state & gtk.gdk.CONTROL_MASK:
            Assign()

        # details (attendance):
        elif (keyname == "d" or keyname == "Cyrillic_ef") and event.state & gtk.gdk.CONTROL_MASK: #details of a student's grades and attend
            sel = gstud.selection
            model, path = sel.get_selected_rows()
            iter_v = model.get_iter(path[0])
            s_num = model.get_value(iter_v, 0) # s_num instead of s_name
            s_name = model.get_value(iter_v, 1) # s_name
            print 's_num', s_num, s_name
            self.attend_one_cb(s_num)
            gstud.status_bar.push(c_id, 'Getting attendance for ' + s_name)

        # get information menu
        elif (keyname == "u" or keyname == "Cyrillic_ghe") and event.state & gtk.gdk.CONTROL_MASK:
            Information()

        # dump base(s), archivate, move
        elif (keyname == "q" or keyname == "Cyrillic_shorti") and event.state & gtk.gdk.CONTROL_MASK:
            self.arch(b_name)

    def reload_sh(self):
        '''reload short view'''
        for cc in gstud.tv.get_columns():
            gstud.tv.remove_column(cc)
        gstud.w_model.clear() 

        res_cols = gstud.make_wk_columns() # get columns
        for cc in res_cols:
            gstud.tv.append_column(cc)
        self.ins_wk_main(gstud.w_model)

    def reload_ln(self):
        '''reload long view'''
#        self.tv.set_model(None)
        # FIX it like reload_sh ^^^
        for cc in self.tv.get_columns():
            self.tv.remove_column(cc)
        self.model.clear() 

        date_ls = self.get_dates() # gets tuple: (date list, length)

        self.insert_columns(date_ls) # Doesn't return anything!!!
#        self.tv.set_model(self.model)
        self.ins_main()

    def arch(self, b_path):
        ''' Dump base to file, archivate, move? '''

        names = []
        pf = ''
        f_name = ''

        name = os.path.basename(b_path)
        print 'name', name

        f_name = os.path.splitext(name)[0] + "_dump_(" + self.date + ').sql'
        print f_name

        conn = sqlite3.connect(b_path)

        print 'writing dump', f_name
        with open(f_name, 'w') as f:
            for line in conn.iterdump():
                f.write('%s\n' % line.encode('utf8'))

        archname = 'str_dump_' + self.date + '.tgz'

        print 'writing archive', archname

        with tarfile.open(archname, "w:gz") as tar:
            tar.add(f_name)
            os.remove(f_name)

# TODO: Стоит ли сделать сразу перемещение в папку архивов?
# Возможно стоит ввести в конфиг строчку "arch_path" - путь, куда копировать архивы 
#
#        print 'moving archive', archname, 'to yadisk'
#        os.rename(os.path.join(os.getcwd(), archname), os.path.join(os.path.expanduser('~'), 'yadisk', 'backups', archname))

    def get_years(self):
        dts = self.get_dates()[0]
        year1 = dts.pop(0)[:4]
        year2 = ''
        for dd in dts:
            if dd[:4] != year1:
                year2 = dd[:4]
                break

        # get current semester
        sem = 0
        if self.date[:4] < year2:
            sem = 1
        else:
            sem = 2

        return [year1, year2, sem]

    def get_dates(self):
        # get from base all unic dates of events AND grades

        conn = self.open_base()
        cur = conn.cursor()
#        cur.execute('select date from lectures join seminars on lectures.date!=seminars.date')
        cur.execute('select date from lectures')
        res = cur.fetchall()
        cur.execute('select date from seminars')
        res.extend(cur.fetchall())
        cur.execute('select enddate from essays')
        res.extend(cur.fetchall())
        cur.execute('select date from tests')
        res.extend(cur.fetchall())
        cur.execute('select date from grades') # not sure this is nesessary
        res.extend(cur.fetchall())
        
        cur.close()

        out = []
        for i in res:
            z = i[0]
            out.append(z)
        out.sort()

        # kill duplicates
        fin = []
        for x in out:
            if not x in fin:
                fin.append(x)
        fin.sort()

        fin.append(self.date)

        d_plain = [] # даты в "русском формате" %d-%m-%Y
        for dd in fin:
            j = dd.split('-')
            p = '-'.join([j[2], j[1], j[0]])
            d_plain.append(p)

        return (fin, len(fin), d_plain)

    def get_s_name(self, num):
        
        cm = 'select s_name from students where s_num="' + str(num) + '"'
        sn = self.exec_sql(cm)[0][0]
        return sn

    def col_counter(self, len_d, d):
        '''gets lenght of dates list and current date num'''
        cnt2 = 0
        # cycle through column numbers (for color)
        # start from 4 = s_num -0, s_name -1, empty col for s_name color -2, date#1 -3.
        for x in range(4, (len_d * 2) + 3, 2):
            if cnt2 == d:
                return x
            cnt2 += 1

    def attend_one_cb(self, s_num):
        ''' callback for Viewer, get attendance for given student '''

        command = 'select * from attendance where s_num=' + str(s_num)
        data_a = self.exec_sql(command) 
        # base: a_num, s_num, date, absence, comment)
        out = []
        for i in data_a:
        # -> Attendance: a_num, s_num, date, absence, comment, saved)
            out.append([i[0], i[1], i[2], i[3], i[4], True])

        # temp_attend: a_num, s_num, date, absence, comment)
        for j in range(len(temp_attend)):
            if temp_attend[j][1] == s_num: # only for given student
                out.append([temp_attend[j][0], temp_attend[j][1], temp_attend[j][2], temp_attend[j][3], None, False])

        Attendance(s_num, self.get_s_name(s_num), out)

    def get_attend(self):
        '''get info from base, prepair for filling cells'''

        command = 'select * from attendance'
        ab = self.exec_sql(command)

        dt = self.get_dates()
        date_pl = dt[2]
        len_d = dt[1]
         
        # TODO: student info <= переменная в __init__ читается в начале работы программы из текстового файла
#        cur.execute('select s_num, s_name from students') 
        cm = 'select s_num, s_name from students'
        # list of all student names (s_num, s_name)
        full_st_l = self.exec_sql(cm)

#        cur.close()
       
        res = [] # (s_num, [col, True/False], L/N, comment)

        def serv(st, dp):
            ''' check if student missed class on day dp 
            '''

            x = self.col_counter(len_d, dp) # day number (date_ls) => column number

            for a in ab: # marks from attendance table
                if a[0] == st and a[1] == date_pl[dp]: # this student was absent on day dp
                    # only paints first column for some comment
                    return [x, True]
            return [x, False]

        for stud in full_st_l:
            res_line = [stud[0],]
            day = []
            for dp in range(len(date_pl)): # chek all dates
                lst = serv(stud[0], dp)
                day.extend(lst)

            res_line.append(day)
            res.append(res_line)

        return res

    def ins_debt(self):
        ''' Insert info into Information (debtors) '''

                                #  debtors:
                                #  status, a_num (hide), s_name, e_word (essays), topic 
                                #  notifications:
                                #  status (напр.: "не забудь!", c_num, s_name, e_word (notification), comment

        tail = self.get_tail('essays')

                               #  str, str, str, str, str)
        # должники
        cm = "select a_num, s_num, essays.topic from assignments join essays on assignments.e_id=essays.e_id where delivered is NULL" + tail
#        cm = "select a_num, s_num, essays.topic from assignments join essays on assignments.e_id=essays.e_id where delivered is ''"

        debtors = self.exec_sql(cm)

        # не проставлена оценка (уже сдали работу)
        cm = "select a_num, s_num, essays.topic from assignments join essays on assignments.e_id=essays.e_id where delivered<='" + self.date + "' and assignments.mark is NULL" + tail # TODO: delete mark is NULL condition after making completed assignments move from this table into grades

        wait = self.exec_sql(cm)
#        print 'wait', wait

        # assignments: a_num TEXT, s_num INTEGER, e_id INTEGER, delivered TEXT, date TEXT, mark REAL, comment TEXT)
        if debtors:
            for dd in range(len(debtors)):
                itr = self.mod_d.append()
                self.mod_d.set(itr, 0, u'Должник!', 1, self.get_s_name(debtors[dd][1]), 2, u'Эссе', 3, debtors[dd][2], 4, debtors[dd][0]) # a_num hidden (for future, if user wishes to check out particular assignments)
        if wait:
            for ww in range(len(wait)):
                itr = self.mod_d.append()
                self.mod_d.set(itr, 0, u'Ждет оценки', 1, self.get_s_name(wait[ww][1]), 2, u'Эссе', 3, wait[ww][2], 4, wait[ww][0]) # a_num hidden (for future, if user wishes to check out particular assignments)


    def ins_info(self):
        ''' Insert info into Information (events) '''

        tail = self.get_tail()

        cm = "select e_id, min(date), topic from lectures where date>='" + self.date + "'" + tail
        l_dates = self.exec_sql(cm)
        cm = "select e_id, min(date), topic from seminars where date>='" + self.date + "'" + tail # prepair for seminar
        s_dates = self.exec_sql(cm)
        cm = "select e_id, min(date), topic from tests where date>='" + self.date + "'" + tail 
        t_dates = self.exec_sql(cm)
        cm = "select e_id, min(date), topic from essays where date>'" + self.date + "'" + tail 
        e_dates = self.exec_sql(cm)
        cm = "select e_id, min(enddate), topic from essays where enddate>='" + self.date + "'" + tail  # hay day
        d_dates = self.exec_sql(cm)

        out = []
        dates = [l_dates[0], s_dates[0], t_dates[0], e_dates[0], d_dates[0]]

        for dd in range(len(dates)):
#            print dd, dates[dd][1]
#            print 'sem', self.semester

            if dates[dd][0]:
                itr = self.mod_i.append()
            else:
                continue

            if dd == 0:
                e_word = u'Лекция'
            elif dd == 1:
                e_word = u'Семинар'
            elif dd == 2:
                e_word = u'Тест'
            elif dd > 2:
                e_word = u'Эссе'

            if dd == 4: # TODO: надо это вывести из списка и проверять отдельно
                stat = u'Долги!'
            elif dates[dd][1] > self.date:
                stat = u'Ожидается'
            elif dates[dd][1] == self.date:
                stat = u'Сегодня'
#            elif dates[dd][1] < self.date:
#                stat = u'Долги!'

            # model: status, date, e_id, e_word (Лекция...), topic
            self.mod_i.set(itr, 0, stat, 1, dates[dd][1], 2, dates[dd][0], 3, e_word, 4, dates[dd][2])

    def ins_wk_main(self, w_mod):
        '''isert info into columnts in Viewer'''
        #(int, str, 'gboolean', str, str, str, 'gboolean', 'gboolean', float) 
        # s_num, s_name, Absent(st), Late(st), Avg(st), Absent, Late, Grade

        cm = 'select s_num, s_name, active from students'
        full_st_l = self.exec_sql(cm)

        res = []

        # Define tail for SQL command 
        tail = self.get_tail()

        for s_n, s_name, act in full_st_l:
            c_res = []
            s_num = str(s_n)
            if act == '0':
                stud_color = True
            else:
                stud_color = False

            iter = w_mod.append()

            c_res = [iter, 0, s_n, 1, s_name, 2, stud_color]
            #### stats: Absent
            cm = 'select count(absence) from attendance where s_num="' + s_num + '" and absence="N"' + tail
            N = self.exec_sql(cm)[0][0]
            c_res.extend([3, str(N)])
            # stats: Late
            cm = 'select count(absence) from attendance where s_num="' + s_num + '" and absence="L"' + tail
            L = self.exec_sql(cm)[0][0]
            c_res.extend([4, str(L)])

            A = self.get_avg(s_num)
            c_res.extend([5, A])
            # hash для записи о сегодняшней посещаемости
            cm = 'select * from attendance where s_num=' + s_num + ' and date="' + self.date + '"'
            att = self.exec_sql(cm)
            if att: # there is an absence remark for this student and date
#                print 'att', att[0]
                c_res.extend([9, att[0][0]])
                if att[0][3] == 'N':
                    c_res.extend([6, True])
                    c_res.extend([7, False])
                elif att[0][3] == 'L':
                    c_res.extend([6, False])
                    c_res.extend([7, True])
            else:
                c_res.extend([9, None])
                c_res.extend([6, False])
                c_res.extend([7, False])

            c_res.extend([10, int(act)])

            cm = 'select mark from grades where s_num=' + s_num + ' and date="' + self.date + '"'
            grade_c_ls = self.exec_sql(cm)
            grade_c = []
            if len(grade_c_ls) > 1:
                for i in grade_c_ls:
                    print 'grades', i
                    grade_c.append(str(i[0]))
                
                grc = '/'.join(grade_c)
            elif len(grade_c_ls) == 1:
                grc = grade_c_ls[0][0]
            else:
                grc = ''
            c_res.extend([8, grc]) # grade

            cm = 'select comment from notes where s_num="' + s_num + '"'
            nt_ls = self.exec_sql(cm)
            if nt_ls:
                nt = nt_ls.pop()[0] # latest note
                c_res.extend([11, nt])

#            print 'c_res', c_res
            w_mod.set(*c_res)

    def ins_main(self):
        ''' populate main window with entries for all students
        read from base, find all dates in the columns' titles,  - bad crutch, but I dont think I can store dates in the model
        But in other insert (for short view, i think), I got dates from model... Fix it here also!
        put grades in the corresponding columns.
        '''

        attend = self.get_attend()

        conn = self.open_base()
        cur = conn.cursor()

        cur.execute('select s_num, s_name from students')
        # list of all student names (s_num, s_name)
        full_st_l = cur.fetchall()

        # list of graded students with their info (including grades)
        # dates - из grades (т.е. дата оценки, а не события!)
#        cur.execute('select grades.s_num, s_name, mark, date, event from grades join students on grades.s_num=students.s_num')
        cur.execute('select grades.s_num, s_name, mark, date, e_name, e_num from grades join students on grades.s_num=students.s_num')

        # graded - list of all grades (separately)
        graded = cur.fetchall()

#        cols = self.get_dates()[2] # "russian" - 02-02-2016. Why?
        cols = self.get_dates()[0] # Y-m-d format 
#        print 'cols', cols

        # std_l - list of data (including all grades) for each student: 
        # (s_num, s_name, [(column, grade) # - list of tuples with student's grades,...])
        std_l = []
        cc = 0

        ### get date-columns, get all marks and corresponding columns for every student
        for i in graded:
            sw = 0 # switch...
            cnt = 1 # count of grades

            for t in range(len(cols)):
                cnt += 2 # column number for grade
                # check date of grading 
                if i[3] == cols[t]:
                    cc = cnt

            for s in std_l:
                # if there is already a student with one or more grades (std_l)
                if i[0] == s[0]:
                    sw = 1
                    s[2].append((cc, i[2])) # i[2] - mark

            # the student has no grades, make a new entry with tuple
            if not sw:
                std_l.append([i[0], i[1], [(cc, i[2])]])

        ### get all prepaired info into model
        for stud in full_st_l: # all students [(s_num, s_name),...

            iter = self.model.append()

            # first, only set s_num and s_name for all students
            res_ls = [iter, 0, stud[0], 1, stud[1], 2, '']

            # Expand with absence - в хвосте дописываем пропущенные занятия
            for a in attend:
                if a[0] == stud[0]:
                    res_ls.extend(a[1])

            for st in std_l:
                # intersect lists (get res_ls - all students with and without grades)
                if st[0] == stud[0]: # s_num in condensed list is equal to s_num in full stud list
                    tmp = {} # blessed dictionaries! Half a day thrown away with lists, before you remember this kinda thing
                    for i, j in st[2]:
                        if tmp.has_key(i):
                            tmp[i] += '/' + str(j)
                        else:
                            tmp[i] = str(j)
#                    print st, tmp
                    logging.info('student %s, tail %s', st, tmp)
                    # вставляем отсутствующих (True/False)
                    while tmp:
                        res_ls.extend(tmp.popitem()) # be careful! get keyerror if tmp is empty
#            for rr in res_ls:
#                print 'new row', rr
            self.model.set(*res_ls)
        cur.close()

    def change_wk_model(self):
        ''' change working model for main window '''
        # remove columns, insert, set other model
        for x in self.tv.get_columns():
            self.tv.remove_column(x)

        # 2. get new columns
        if self.cur_model == '1':
            print 'current model is short'
            columns = self.insert_columns(self.get_dates())
            for col in columns:
                # get cell_renderer
                self.tv.append_column(col)
#            self.ins_main() # this doubles rows
            self.tv.set_model(self.model)
            self.cur_model = '0'

        # set different model for clean TV
        elif self.cur_model == '0':
            print 'current model is long'
            columns = self.make_wk_columns()
            for col in columns:
                # get cell_renderer
                self.tv.append_column(col)
#            self.ins_wk_main(self.w_model) # this doubles rows
        # set different model for clean TV
            self.tv.set_model(self.w_model)
            self.cur_model = '1'

# TODO: filter doesnt work after switching. 
# Have to refresh model before setting to TV

    def vis(self, model, itr):
        """Callback for the model-filter in Viewer.
        Show/hide rows that contain info for students 
        not present in this (or any) class

        """
        av_l = model.get_value(itr, 5)
        act = model.get_value(itr, 2)
#        print 'act', act
        if type(av_l) == types.NoneType:
#            print 'av_l', av_l
            return False

        if av_l != '0':
            av_ls = av_l.split('/')
            av = float(av_ls[0])
        else: 
            av = 0
#        av =  self.w_model.get(itr, 0,1,2,3,4,5,6,7,8,9)

        if self.c_group == 0: # weak
#            print 'group - weak'
            if not act:
                if av:
                    if av < 3.5:
                        return True
                    else:
                        return False
                else:
                    return True
            else:
                return False
        elif self.c_group == 1: # strong
#            print 'group - strong'
            if not act:
                if av:
                    if av >= 3.5:
                        return True
                    else:
                        return False
                else:
                    return False
            else:
                return False
        elif self.c_group == 2: # active
#            print 'group - active'
            if not act:
                return True
            else:
                return False
        elif self.c_group == 3: # all
            return True

    def toggler(self, cell, path, model, ab, col):
        '''callback for short view - checkboxes'''

        o_path = self.modelfilter.convert_path_to_child_path(path)[0]
        model[o_path][col] = not model[o_path][col] # переключаем кликнутый чекбокс
        s_num = int(o_path) + 1
        iter1 = self.modelfilter.get_iter(path)
        iter2 = self.modelfilter.convert_iter_to_child_iter(iter1)

        a_num = model.get_value(iter2, 9) # value written in Viewer 9th column (today's attendance)
#        print 'a_num', a_num
        if ab == 'N':
            model.set_value(iter2, 7, False) # переключаем параллельные чекбоксы (активен либо L, либо N)
        elif ab == 'L':
            model.set_value(iter2, 6, False)

        if temp_attend and a_num:
            for t in range(len(temp_attend)):
                if temp_attend[t][0] == a_num: # if there is absence today already, change value L/M
#                    print 'found a_num'
                    if ab == "L":
                        ab == "N"
                    elif ab == "N":
                        ab == "L"
                    temp_attend[t][3] = ab # меняем L на M или наоборот
                    return
        elif a_num: # ничего в temp_att, но есть запись с прошлого запуска в базе (сегодняшняя)
#            print 'ab', ab
            # удалить из базы, ввести в temp_att
            cm = 'delete from attendance where a_num="' + str(a_num) + '"'
            self.exec_sql(cm)
            temp_attend.append([a_num, s_num, self.date, ab, None, False]) # идентификатор - хэш
#            temp_attend[t][3] = ab # меняем L на M или наоборот
        else:
            temp_attend.append([str(uuid.uuid4())[:8], s_num, self.date, ab, None, False]) # идентификатор - хэш
            model.set_value(iter2, 9, str(uuid.uuid4())[:8]) # временно! Если удаляем из temp_attend, это тоже стереть!
#            print 'toggler', temp_attend

        return

    def on_click(self, widget, path, col):
        ''' callback for mainview (Viewer, longview)'''

        res = []
#        print path

        tit = col.get_title() # this is date, actually

        model, path = self.selection.get_selected_rows()
        iter_v = self.model.get_iter(path[0])
        s_num = self.model.get_value(iter_v, 0) # s_num instead of s_name
#        print  value, tit
       
        if tit == 'student':
            # if we choose student's name, get GUI for grading
            self.grad = Grader(self, s_num, b_name, path[0])
            #TODO: if not - get menu for changing current grade?
        elif "-" in tit: 

            # there is similar call in self.details() - only there is a full grades list for a student
            #TODO: Сделай фильтр, показывай оценки на выбранную дату, по событию (лекция, эссе...)

#            mk = self.model.get_value(iter_v, cc) 
            conn = self.open_base()
            cur = conn.cursor()
            
            # make startdate -> date in essays or else this call doenst work on essays
#            command1 = 'select s_name, event, mark from grades join students on students.s_num="' + s_num + '"where grades.s_num="' + s_num + '" and date="' + tit + '"'
            command1 = 'select s_name, event, mark from grades join students on students.s_num="' + str(s_num) + '" where grades.s_num="' + str(s_num) + '" and date="' + tit + '"'
            cur.execute(command1)
            s_grades = cur.fetchall()

            if s_grades:

                res = []
                event = ''
                for line in s_grades:
#                    print line
                    e_id = line[1] # "s3",  e_id[0] = s
                    for ev in self.ev_names:
                        if ev[:1] == e_id[0]: # s - letter part
                            event = ev
                    e_num = e_id[1] # 3 - numeric part

                    # if event == "essay": # make different call to SQL

                    command2 = 'select date, topic from ' + event + ' where e_id="' + e_num + '"' 
                    cur.execute(command2)
                    event_l = cur.fetchall()[0]
#                    print line[0], event_l[0], event_l[1], line[2]

                    res.append([line[0], line[1], event_l[0], event_l[1], line[2]]) # s_name, e_id, date, topic, mark
#                    print res
                self.grada = Details(res)
            else:
                self.grada = Grader(self, s_num, b_name, path[0], tit)

            cur.close()

    def get_all_events(self):
        # get all events on Events() initialization
        # TODO: could use it for intersection - get_dates()

        conn = self.open_base()
        cur = conn.cursor()

        cur.execute('select * from lectures')
        lec = cur.fetchall()

        cur.execute('select * from essays')
        ess = cur.fetchall()

        cur.execute('select * from seminars')
        sem = cur.fetchall()
    
        cur.execute('select * from tests')
        tes = cur.fetchall()

        cur.close()

        return (lec, ess, sem, tes)

    def choose_gr(self, widget):
        ''' callback for combobox in Viewer() window. Choose group (weak, strong) to show.'''

        ac = widget.get_active_text() 
#        print 'ac', ac
        if ac == 'Weak':
            self.c_group = 0
        elif ac == 'Strong':
            self.c_group = 1
        elif ac == 'Active':
            self.c_group = 2
        elif ac == 'All':
            self.c_group = 3

#        print self.c_group

        self.modelfilter.refilter()

    def choose_cl(self, widget):
        ''' callback for combobox in Viewer() window. Choose class to show.'''

        ac = widget.get_active_text() 
#        print ac
        if ac == 'All time':
            self.semester = 0
            if debug:
                self.date = '2016-02-02'
            else:
                self.date = now.strftime("%Y-%m-%d") # TODO: show stuff for today time
        elif ac == 'Today':
            if debug:
                self.date = '2016-02-02'
            else:
                self.date = now.strftime("%Y-%m-%d") # TODO: show stuff for today time
            self.semester = self.get_years()[2]
        else:
            self.date = ac # set new current date for get_years() to work correctly
            self.semester = self.get_years()[2]
        self.reload_sh()

    def choose(self, widget):
        ''' callback for combobox in Events() window. Choose event type.'''

        # get event type from combo
        e_name = widget.get_active_text() 

        for i in range(len(self.ev_names)):
            # get event number 0-3
            if self.ev_names[i] == e_name:
                # save current events group
                gstud.cur_e_name = e_name
#                print self.cur_e_name

                # Clean up the TreeView. 
                # 1. remove old columns from TV
                for x in self.e_tv.get_columns():
                    self.e_tv.remove_column(x)

                # 2. get new columns
                columns = self.make_columns(i)
                for col in columns:
                    # get cell_renderer
                    self.e_tv.append_column(col)

                # set different model for clean TV
                self.e_tv.set_model(self.e_models[i])

    def ins_assign(self):
        ''' insert info into Assignments '''

        cm = 'select * from assignments where mark is NULL' # иначе кажет старые записи и они опять лезут в grades
        res = self.exec_sql(cm)
        if res:
            for aa in res:
                itr = self.aa_model.append()
                snm = 'select s_name from students where s_num="' + str(aa[1]) + '"'
                res2 = self.exec_sql(snm)
                s_name = res2[0][0]
                topic = self.get_topic(('essays', aa[2]))[1]
                self.aa_model.set(itr, 0, aa[0], 1, s_name, 2, topic, 3, aa[3], 4, aa[4], 5, aa[5], 6, aa[6])
#            print res2
#        else:
#            itr = self.aa_model.append()
#            self.aa_model.set(itr, 0, '', 1, '', 2, '', 3, '', 4, '', 5, '', 6, '')

    def ins_events(self, mod, evt):
        if mod.get_n_columns() > 4:
            for ev in evt:
                iter = mod.append()
                mod.set(iter, 0, ev[0], 1, ev[1], 2, ev[2], 3, ev[3], 4, ev[4])
        else:
            for ev in evt:
                iter = mod.append()
                mod.set(iter, 0, ev[0], 1, ev[1], 2, ev[2], 3, ev[3])

        return mod

    def assign_save(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        if (keyname == "s" or keyname == "Cyrillic_yeru") and event.state & gtk.gdk.CONTROL_MASK: 
            # idea1: while True; get_iter_next
            if self.rem_confirm('Save data?'):
                model = self.aa_model
                refs = []
                for i in range(len(model)):
                    x = gtk.TreeRowReference(model, i) # have to use refs, else iters mess up after rows are deleted
                    refs.append(x)

                for r in refs:
#                    p = r.get_path()
                    new_itr = model.get_iter(r.get_path())
                    if new_itr:
                        v = model.get(new_itr, 0, 1, 2, 3, 4, 5, 6) # a_num, s_name, topic, delivered(date), date, mark and comment
                        a_num = v[0]
                        s_name = v[1]
                        top = v[2]
                        dl = v[3]
                        dt = v[4]
                        mk = v[5]
                        cmt = v[6]
                        # grades: (g_num TEXT, s_num INTEGER, e_name TEXT, e_num INT, date TEXT, mark REAL, comment TEXT)"
                        if mk:
                            if dl: # there is a delivery date set
                                # bad. Should have used model to keep e_id and s_num
                                e_id = self.exec_sql("select e_id from essays where topic='" + top + "'")[0][0]
                                s_num = self.exec_sql("select s_num from students where s_name='" + s_name + "'")[0][0]
                                s_num = int(s_num)
                                e_id = int(e_id)

                                if cmt:
                                    cmt = cmt.decode('utf-8')
                                cm = "insert into grades (g_num, s_num, e_name, e_num, date, mark, comment) values (?,?,?,?,?,?,?)"
                                                # text, int, text, int, text, real, text
                                self.exec_sql(cm, [a_num, s_num, 'essays', e_id, dt, mk, cmt])

                                if cmt:
                                    cmt = "'" + cmt + "'"
                                else:
                                    cmt = 'NULL'

#                                print 'curr delivery=', dl
#                            cm = "update assignments set mark=" + mk + ", comment=" + cmt + " where a_num='" + a_num + "'"
                                cm = "update assignments set mark=" + mk + ", delivered='" + dl + "', comment=" + cmt + " where a_num='" + a_num + "'"
#                                print cm
                                self.exec_sql(cm)

                                model.remove(new_itr)
                            else:
                                Popup('Set delivery date, please')

                        else:
                            if not dl or dl == ' ':
                                dl = 'NULL'
                            else:
                                dl = "'" + dl + "'" # нужны кавыки, иначе не жрет
                            if not cmt or cmt == ' ':
                                cmt = 'NULL'
                            else:
                                cmt = "'" + cmt + "'"

                            cm = "update assignments set delivered=" + dl + ", comment=" + cmt + " where a_num='" + a_num + "'"
                            self.exec_sql(cm)

    def assign_set(self, cell, path, new_text, col):
        '''Callback for Assignments, when row is edited'''

        iter_cur = self.aa_model.get_iter(path)
        self.aa_model.set(iter_cur, col, new_text)
        # check for "delivered" being set: (else algorythm for Information.debtors gets messed up)
        if col == 5: # mark
            deliv = self.aa_model.get_value(iter_cur, 3) # delivered
            if not deliv:
                Popup('no delivery date!')

    def event_set(self, tv, path, column, g_path):
        '''Callback for Entry - when row with event is chosen'''

# TODO: а что если Entry вызван из Viewer, а не из Details?
# можно просто сделать потомка от Entry
        cur_mod = tv.get_model()

        iter_cur = cur_mod.get_iter(path)
        e_num = cur_mod.get_value(iter_cur, 0)
#        e_date = cur_mod.get_value(iter_cur, 1) # дата события
        e_top = cur_mod.get_value(iter_cur, 2)
        e_word = gstud.cur_e_name + ' ' + str(e_num) # что за ерунда? cur_e_name?

        iter_g = gstud.grada.mod_g.get_iter(g_path)
        g_date = gstud.grada.mod_g.get_value(iter_g, 2) # дата оценки
        #  mod_g: g_num, grade, date, event (full), topic, saved, index=None (its not in temp_grades)
        gstud.grada.mod_g.set(iter_g, 1, None, 2, g_date, 3, e_word, 4, e_top)

#        destroy_cb(self) # можно сделать два объекта Events() c разными коллбэками. Один - с дестроем, другой - без

    def open_ev(self, tv, g_path, column):
        ''' callback for Details() when clicked on date - open Events, choose event '''
        res = Events(g_path)

    def ins_new_event(self, e_type, date, topic, due=2): 
        # не уверен, что надо, посмотрим "на поле боя"
#    def ins_new_event(self, *args): 
        # lecture, seminar, essay (date = (start, end)), test
        conn = self.open_base()
        cur = conn.cursor()

        topic = topic.decode('utf-8')
        due = int(due) # TODO: standart delta ^^^ =2. Read from config.

        if e_type == "e":
            date_t = date.split('-')
            startdate_o = datetime.date(int(date_t[2]), int(date_t[1]), int(date_t[0]))
            delta = datetime.timedelta(due)
            enddate_o = startdate_o + delta
            enddate = enddate_o.strftime("%d-%m-%Y")

            command = 'insert into essays (date, enddate, topic) values (?,?,?);'
            cur.execute(command, (date, enddate, topic))

        elif e_type == 'l':
            command = 'insert into lectures (date, topic) values (?,?);'
            cur.execute(command, (date, topic))
        elif e_type == 's':
            command = 'insert into seminars (date, topic) values (?,?);'
            cur.execute(command, (date, topic))
        elif e_type == 't':
            command = 'insert into tests (date, topic) values (?,?);'
            cur.execute(command, (date, topic))

        conn.commit()
        cur.close()

    def get_enddate(self):

        due = int(self.due) # TODO: standart delta. Read from config.
        date_t = self.date.split('-')
        startdate_o = datetime.date(int(date_t[0]), int(date_t[1]), int(date_t[2]))
        delta = datetime.timedelta(due)
        enddate_o = startdate_o + delta

        return enddate_o.strftime("%Y-%m-%d")

    def make_new_ev(self, model):            
        ''' Make new default event for Events() '''
#       model: (int, str, str, str, [str])
        mc = model.get_n_columns()
        # get date.
        if mc > 4: # essays
            enddate = self.get_enddate()
            new_iter = model.append([0, self.date, enddate, '', ''])
            c_col = 3

        elif mc == 4: # everything else
            new_iter = model.append([0, self.date, '', ''])
            c_col = 2
        self.new_ev = True
        new_path = model.get_path(new_iter)[0]

        # move selection to the new entry
        c_col = self.e_tv.get_column(0)
        self.e_tv.set_cursor(new_path, c_col, False)
        self.e_tv.grab_focus()

    def make_new_en_att(self, model, s_num):            
        ''' Make new entry for Attendance() '''
        # Attendance: a_num, s_num, date, absence, comment, saved
        new_iter = model.append(['', s_num, self.date, 'Late', '', False])
        new_path = model.get_path(new_iter)[0]

        # move selection to the new entry
        c_col = self.a_tv.get_column(1)
        self.a_tv.set_cursor(new_path, c_col, False)

    def make_new_en(self, model):            
        ''' Make new entry for Details() '''

        self.new_gr = True # entry was just created (but not saved even to temp_grades)

        for tab in ['lectures', 'seminars']:
            # ищем актуальную лекцию, или семинар (на сегодняшний день) 
            # lectures, seminars: e_id, date, topic , comment)"
#TODO: а надо на прошлый раз!
# select ... max(date) from tab where date < self.date # надо подзапросом
            command = 'select * from ' + tab + ' where date="' + self.date + '"'
            lecs = self.exec_sql(command)
#            print 'lecs', lecs
            if lecs:
                ev = tab + ' ' + str(lecs[0][0]) # берем первую найденную лекцию
                top = lecs[0][2]
                break
            else:
                ev = ''
                top = ''

            # grades (base):  g_num, s_num, e_name, e_num, date, mark, comment 
                    #  model: g_num, grade, date, event (full), topic, saved

#                
        new_iter = model.append([str(uuid.uuid4())[:8], '', self.date, ev, top, None, False])
        new_path = model.get_path(new_iter)[0]

        # move selection to the new entry
        c_col = self.g_tv.get_column(0)
        self.g_tv.set_cursor(new_path, c_col, False)
#        self.tv.grab_focus()

    def get_topic(self, e_ls):
        ''' костылище! TODO: сделать get_f_base, как в beta'''
# TODO: разобраться как делать подзапрос в SQL

        cm = 'select date, topic from ' + e_ls[0] + ' where e_id="' + str(e_ls[1]) + '"' 
        event_l = self.exec_sql(cm)[0]

        # ('2015-03-15', 'какая-то тема')
        return (event_l[0], event_l[1])
 
    def edited_cb(self, widget, path, col):
        '''callback for short view - when clicked on a row 
        get all marks of a student, Output to Details()
        ''' 

        model = widget.get_model()
        iter_v = self.modelfilter.get_iter(path)
        s_num = self.modelfilter.get_value(iter_v, 0) # возможно, что-то не так: итер нужно конвертнуть?
        s_name = self.modelfilter.get_value(iter_v, 1)

        g_temp_ls = [] # list of temporary marks (not in the base) => feed to Details()

#        temp_ grades: [g_num, s_num, e_name, e_num, date, float(mark), comment]
        # Отберем "временные" оценки данного студента:
        for i in range(len(temp_grades)):
            cur_gr = temp_grades[i]
            if cur_gr[1] == s_num:
                e_word = cur_gr[2] + ' ' + cur_gr[3]
 
                # g_num, grade, date, event (full), topic, comment, saved (True if grade still not saved)
                # это формат списка для Details, который отличается от temp_grades
                g_temp_ls.append([cur_gr[0], cur_gr[5], cur_gr[4], e_word, self.get_topic([cur_gr[2], cur_gr[3]])[1], cur_gr[6], False])

        cm = 'select g_num, s_name, date, e_name, e_num, mark, grades.comment from grades join students on students.s_num=grades.s_num where grades.s_num=' + str(s_num)
        
        # получаем оценки данного студента из базы
        s_grades = self.exec_sql(cm)

        if s_grades:
            res = []
            event = ''
            for line in s_grades:
                e_name = line[3]
                e_num = line[4]

                e_word = e_name + " " + str(e_num)
                comment = line[6]

                cm = 'select topic from ' + e_name + ' where e_id="' + str(e_num) + '"' 
                print 'cm', cm
                event_l = self.exec_sql(cm)[0]
                res.append([line[0], line[5], line[2], e_word, event_l[0], comment, True]) # g_num, mark, date, event (full), topic, saved, index
            res.extend(g_temp_ls) # добавим временные оценки к взятым из базы

            self.grada = Details(s_num, s_name, res)
        elif g_temp_ls:
            # There are marks not saved into base
            self.grada = Details(s_num, s_name, g_temp_ls)
        else:
            # no marks at all - make new entry
            self.grada = Details(s_num, s_name, [])
#            Popup('This guy has no grades!')

    def ch_menu_cb(self, widget, event, e_id):
        ''' Callback for Choose student menu '''
        keyname = gtk.gdk.keyval_name(event.keyval)
        if keyname == "Return" and event.state & gtk.gdk.CONTROL_MASK: 
            # make a new entry 
#            model = self.c_model()
            out = []
            model, paths = self.selection.get_selected_rows()  # 0 - filter (model) object, 1 - list of tuples [(2,), (3,)...]
            for pp in paths:
                itr = model.get_iter(pp)
                s_num = model.get_value(itr, 0) # s_num
        # assignments (a_num TEXT, s_num INTEGER, e_id INTEGER, delivered TEXT, date TEXT, mark REAL, comment TEXT)'
                out.append([str(uuid.uuid4())[:8], s_num, e_id, self.date])
            cm = 'insert into assignments (a_num, s_num, e_id, date) values (?,?,?,?)'
            for oo in out:
                self.exec_sql(cm, oo)

            Assign()

    def fix_grades_cb(self, widget, event, s_num):
        '''callback for Details correcting list of grades, 
           making new entries, etc.
        '''

        keyname = gtk.gdk.keyval_name(event.keyval)
        if (keyname == "n" or keyname == "Cyrillic_te") and event.state & gtk.gdk.CONTROL_MASK: 
            # make a new entry 
            model = self.g_tv.get_model()

            # make a new entry (mark is empty)
            self.make_new_en(model)

        elif (keyname == "r" or keyname == "Cyrillic_ka") and event.state & gtk.gdk.CONTROL_MASK: 
            # remove row from base or from temp_grades
            if self.rem_confirm('Remove entry?'):
                model, path = self.selection.get_selected_rows()
                iter_v = model.get_iter(path[0])
                # vals = [mark, date, event + num, topic, saved (False = grade not saved, it's in temp_grades), index (in temp_grades)]
                g_num =  model.get_value(iter_v, 0)

                if model.get_value(iter_v, 6):
                    print 'remove from base'
                    command = 'delete from grades where g_num="' + str(g_num) + '"'
                    self.exec_sql(command)
                else:
                    print 'remove from list'
#                    temp_grades.pop(model.get_value(iter_v, 6)) # wrong!
                    for i in range(len(temp_grades)):
                        if g_num == temp_grades[i][0]:
                            temp_grades.pop(i)
                model.remove(iter_v)
# TODO: remove mark from short view also

    def fix_absence_cb(self, widget, event, s_num):
        '''callback for Details correcting list of grades, 
           making new entries, etc.
        '''

        keyname = gtk.gdk.keyval_name(event.keyval)
        
        if (keyname == "n" or keyname == "Cyrillic_te") and event.state & gtk.gdk.CONTROL_MASK: 
            # make a new entry 
            model = self.a_tv.get_model()
            # make a new entry (L is set)
            self.make_new_en_att(model, s_num)

        elif (keyname == "r" or keyname == "Cyrillic_ka") and event.state & gtk.gdk.CONTROL_MASK: 
            # remove row from base or from temp_grades
#            print temp_attend
            if self.rem_confirm('Remove entry?'):
                model, path = self.selection.get_selected_rows()
                iter_v = model.get_iter(path[0])
                # vals = [mark, date, event + num, topic, saved (False = grade not saved, it's in temp_grades), index (in temp_grades)]
                vals = []

                for i in range(6):
                    att = model.get_value(iter_v, i) # s_num instead of s_name
                    vals.append(att)
                print 'vals', vals

                if model.get_value(iter_v, 5):
                    print 'remove from base'
                    command = 'delete from attendance where a_num="' + str(vals[0]) + '"'
                    self.exec_sql(command)
                    model.remove(iter_v)

#                    o_path = gstud.modelfilter.convert_path_to_child_path(s_num - 1)[0]
                    o_path = s_num - 1
#                    iter_m = gstud.w_model.get_iter(s_num - 1)
                    iter_m = gstud.w_model.get_iter(o_path)

                    if vals[2] == self.date: #  На случай, если удаляем не в self.date, а в другой день
                        gstud.w_model.set_value(iter_m, 6, False)
                        gstud.w_model.set_value(iter_m, 7, False)

                    cm = 'select count(absence) from attendance where s_num="' + str(s_num) + '" and absence="L"' + self.get_tail()
                    gstud.w_model[o_path][4] = self.exec_sql(cm)[0][0]
                    cm = 'select count(absence) from attendance where s_num="' + str(s_num) + '" and absence="N"' + self.get_tail()
                    gstud.w_model[o_path][3] = self.exec_sql(cm)[0][0]

                else:
                    print 'remove from list'
                    for t in range(len(temp_attend)):
                        if temp_attend[t][0] == vals[0]:
                            temp_attend.pop(t)
                            model.remove(iter_v)

    def edit_attend(self, cell, path, new_text, s_num, col_num):
        '''callback for Attendance when row is clicked '''

        # Attendance: a_num, s_num, date, absence, comment, saved
        self.mod_a[path][col_num + 2] = new_text # вставили новую оценку в TV
        iter_v = self.mod_a.get_iter(path)

        vals = []
        for i in range(6):
            at = self.mod_a.get_value(iter_v, i) # s_num instead of s_name
            vals.append(at)
        print 'vals', vals

        if new_text == "Late" or new_text == "L":
            new_text = "L"
        elif new_text == "Not present" or new_text == "N":
            new_text = "N"

        if vals[5]: # saved. TODO: По идее надо в save_into_b ставить все mod_a => saved=1
            # save to base

            if col_num == 1 and new_text:
                command = 'update attendance set absence="' + new_text + '" where a_num="' + vals[0] + '"'
                self.exec_sql(command)
                o_path = s_num - 1

                if vals[2] == self.date: # Если исправляем не за другой день, а в self.date
                    if new_text == "L":
                        gstud.w_model[o_path][6] = False
                        gstud.w_model[o_path][7] = True
                    elif new_text == "N":
                        gstud.w_model[o_path][6] = True
                        gstud.w_model[o_path][7] = False

                cm = 'select count(absence) from attendance where s_num="' + str(s_num) + '" and absence="L"' + self.get_tail()
                gstud.w_model[o_path][4] = self.exec_sql(cm)[0][0]
                cm = 'select count(absence) from attendance where s_num="' + str(s_num) + '" and absence="N"' + self.get_tail()
                gstud.w_model[o_path][3] = self.exec_sql(cm)[0][0]

                # TODO: может стоит сделать переключение полей и для temp_attend? (Ниже)

            elif col_num == 2:
                command = 'update attendance set comment="' + new_text + '" where a_num="' + vals[0] + '"'
                self.exec_sql(command)
        else:
            print 'changing temp_attend'
            for i in range(len(temp_attend)):

                if temp_attend[i][0] == vals[0]:
                    if col_num == 1 and new_text:
                        temp_attend[i][3] = new_text.decode('utf-8')
                    if col_num == 2:
                        temp_attend[i][4] = new_text.decode('utf-8')

    def edit_notes(self, cell, path, new_text): 
        ''' Callback for Notes, short view '''
        print path
        o_path = self.modelfilter.convert_path_to_child_path(path)[0]
        self.w_model[o_path][11] = new_text # вставили новую оценку в TV
        s_num = str(int(o_path) + 1)
        if self.rem_confirm('Save notes?'):
            command = 'insert into notes (c_num, s_num, date, comment) values (?,?,?,?)'
            self.exec_sql(command, [str(uuid.uuid4())[:8], s_num, self.date, new_text.decode('utf-8')]) 

    def edit_stud(self, cell, path, new_text, col):
        ''' callback for Stud_info '''
        print path, col
        self.s_model[path][col] = new_text # вставили новую оценку в TV

        col_ls = ['s_num', 's_name', 'email', 'phone', 'photo', 'active', 'comment']
        s_num = str(int(path) + 1)

#        students (s_num INTEGER PRIMARY KEY, s_name TEXT, email TEXT, phone TEXT, photo TEXT, active TEXT, comment TEXT)"
        if self.rem_confirm('Save info?'):
#            iter_v = self.mod_g.get_iter(path)

            command = 'update students set ' + col_ls[col] + '="' + new_text + '" where s_num="' + s_num + '"'
            self.exec_sql(command)

        # TODO: перечитать TV в Vewer short view
            self.reload_sh()

    def edit_grade(self, cell, path, new_text, s_num, col):
        ''' callback for Details - editing grade column '''

        #  mod_g: g_num, grade, date, event (full), topic, comment, saved
        # edit only mark, if you're not happy with the rest, better remove all grade, and start over
        self.mod_g[path][col] = new_text # вставили новую оценку в TV
        iter_v = self.mod_g.get_iter(path)
        vals = []
        for i in range(7):
            gr = self.mod_g.get_value(iter_v, i) # s_num instead of s_name
            vals.append(gr)
#            print 'gr', gr
        e_ls = vals[3].split()
        g_num = vals[0]


        print vals

        if self.new_gr:  # entry was just created (but not saved even to temp_grades)
            # s_num, e_name, e_num, date, mark, comment=None

            r_mark = self.check_old_grades(s_num, e_ls[0], e_ls[1], vals[2], vals[1])

            itr = gstud.w_model.get_iter(s_num - 1)

            if r_mark:
#                temp_grades.append([str(uuid.uuid4())[:8], s_num, e_ls[0], e_ls[1], vals[2], vals[1], vals[5]]) 
                temp_grades.append([g_num, s_num, e_ls[0], e_ls[1], vals[2], vals[1], vals[5]]) 
                gstud.w_model.set_value(itr, 8, r_mark)

                self.new_gr = False
            else:
                self.mod_g[path][1] = '' # вставили новую оценку в TV

        else: # editing old entries

#            if self.mod_g.get_value(iter_v, 4):
            if vals[6]: # saved - оценка записана в базу, правим прямо там
                print 'changing the base'
                if col == 1:
                    command = 'update grades set mark=' + new_text + ' where g_num="' + str(vals[0]) + '"'
                elif col == 5:
                    command = 'update grades set comment=' + new_text + ' where g_num="' + str(vals[0]) + '"'

#                print command
                self.exec_sql(command)

            else: # оценка - в temp_grades, а не в базе
#        temp_ grades: [g_num, s_num, e_name, e_num, date, float(mark), comment]
                print 'changing temp list'
                for i in range(len(temp_grades)):
                    if temp_grades[i][0] == vals[0]:
                        if col == 1:
                            temp_grades[i][5] = new_text
                        if col == 5:
                            temp_grades[i][6] = new_text

            r_mark = self.check_old_grades(s_num, e_ls[0], e_ls[1], vals[2], vals[1])
            # show today's grades in Short view: 5.0/3.5...
            if r_mark:
                itr = gstud.w_model.get_iter(s_num - 1)
                gstud.w_model.set_value(itr, 8, r_mark)
#            else:
#                self.mod_g[path][1] = '' # вставили новую оценку в TV

    def edit_event(self, cell, path, new_text, col):
#        print path, new_text
        tab_num = self.combo.get_active()
        tab_name = self.ev_names[tab_num]
        
        mod_e = self.e_tv.get_model() # current model (there are 4)
        n = mod_e.get_n_columns()
        print 'n_colunns', n

        if tab_num == 1:
            j = 3
        else:
            j = 2
        mod_e[path][col] = new_text # вставили новую оценку в TV
        iter_v = mod_e.get_iter(path)
        vals = []
        for i in range(n):
            gr = mod_e.get_value(iter_v, i) # s_num instead of s_name
            if type(gr) == types.StringType:
                gr = gr.decode('utf-8')
            vals.append(gr)

        if vals[0] == 0:
            vals[0] = None # for e_id Int primary key - autoiteration
        
#        print tab_name
        if self.rem_confirm('Save topic?'):
            if self.new_ev:
                if tab_num == 1: # essays
                    command = 'insert into ' + tab_name + ' (e_id, date, enddate, topic, comment) values (?,?,?,?,?)'
                    print 'c2', command
                    self.exec_sql(command, vals)
                    self.new_ev = False
                else:
                    command = 'insert into ' + tab_name + ' (e_id, date, topic, comment) values (?,?,?,?)'
                    print 'c1', command
                    self.exec_sql(command, vals)
                    self.new_ev = False
            else:
                if col == 4: # comment column
                    j += 1
                    command = 'update ' + tab_name + ' set comment="' + vals[j] + '" where e_id="' + str(vals[0]) + '"'
                    print 'ess, comment:', command
                    self.exec_sql(command)
                else: # topic 
                    command = 'update ' + tab_name + ' set topic="' + vals[j] + '" where e_id="' + str(vals[0]) + '"'
                    print 'ess, topic:', command
                    self.exec_sql(command)
        # Bugs: не сохраняет comment, 

    def event_n(self, widget, event):
        ''' Callback for Events() when key is pressed '''

        keyname = gtk.gdk.keyval_name(event.keyval)
        if (keyname == "n" or keyname == "Cyrillic_te") and event.state & gtk.gdk.CONTROL_MASK: 
            model = self.e_tv.get_model()
            # make a new entry (mark is empty - default event)
            self.make_new_ev(model)
        elif (keyname == "s" or keyname == "Cyrillic_yeru") and event.state & gtk.gdk.CONTROL_MASK: 
            model = self.e_tv.get_model()
            self.save_events(model)
            self.new_ev = False

        elif (keyname == "m" or keyname == "Cyrillic_softsign") and event.state & gtk.gdk.CONTROL_MASK: 
            # pick students to write essay
#            self.combo.get_active() # essays, obviously. Then block it for other events
#            self.selection
            model, paths = self.selection.get_selected_rows()  # 0 - filter (model) object, 1 - list of tuples [(2,), (3,)...]
            if paths:
                Choose_students(paths[0][0] + 1)
            else:
                Popup('Choose some topic, please')

        elif (keyname == "d" or keyname == "Cyrillic_ve") and event.state & gtk.gdk.CONTROL_MASK: 
            self.topic_down()

        elif (keyname == "u" or keyname == "Cyrillic_ghe") and event.state & gtk.gdk.CONTROL_MASK: 
            self.topic_up()

    def topic_down(self):
        '''Move topics, starting with the current, one position (date) down'''
        
        model, paths = self.selection.get_selected_rows()  # 0 - filter (model) object, 1 - list of tuples [(2,), (3,)...]
#        rows = model.get_n_columns()
        new_top = ''

        # move topics down 1 step in a model:
        while True:
            if new_top:
                new_itr = model.iter_next(itr)
                if new_itr: # есть еще строчка в TV
                    old_top = model.get_value(new_itr, 2) # сохраняем тему, стоявшую на следующей дате
                    print old_top.encode('utf-8')
                    model.set(new_itr, 2, new_top) # ставим предыдущую тему на следующую дату
                    new_top = old_top
                    itr = new_itr
                else:
                    break
            else:
                # 0 cycle. Topic is left empty, for I missed that day.
                itr = model.get_iter(paths[0][0])
#                print 'path, itr', paths[0][0], itr
                new_top = model.get_value(itr, 2)
#                print '0 cycle, top', new_top.encode('utf-8')
                if new_top:
                    model.set(itr, 2, '')
                else:
                    print 'No topic in one of the later events, breaking up "while"'
                    break
        # TODO: возможно следует сделать в начале new_top='empty' вместо пустого литерала. Хотя какой в этом смысл?

        print 'while cycle ended'
        # save to base
        if self.rem_confirm('Save new event list?'): # TODO: confirmation after _all_ changes done! Save => separate callback
            e_name = self.combo.get_active_text() 
            for n in range(len(model)):
                vals = model.get(model.get_iter(n), 0, 1, 2, 3) # make separate for essays
                if e_name == 'essays':
                    # TODO: возможно стоит сделать тоже
                    print 'make new essay, delete old, don\'t be lazy'
#                    enddate = self.get_enddate(vals[1])
#                    comm = "update lectures set topic='" + vals[2] + "', comment='" + vals[3] + "' where e_id='" + str(vals[0]) + "'"
                else:
#                    comm = "update lectures set topic='" + vals[2] + "', comment='" + vals[3] + "' where e_id='" + str(vals[0]) + "'"
                    comm = "update " + e_name + " set topic='" + vals[2] + "', comment='" + vals[3] + "' where e_id='" + str(vals[0]) + "'"
                    print comm
                    self.exec_sql(comm)
        # TODO: Складывать "лишние темы", получившиеся в результате пропусков, в отдельный файл (или таблицу), чтобы можно было вклеить их обратно (напр. в уже существующий лекционный день, или ctrl + up)

    def topic_up(self):
        '''Move topics, starting with the current, one position (date) up'''
        
        model, paths = self.selection.get_selected_rows()  # 0 - filter (model) object, 1 - list of tuples [(2,), (3,)...]
#        rows = model.get_n_columns()
        new_top = ''

        cur_path = paths[0][0]

        # 0 цикл. Текущую тему приклеиваем к предыдущей # TODO: меню: concatenate or drop first line?
        if cur_path: # not 0 - else cannot move up
            new_itr = model.get_iter(cur_path)
            old_itr = model.get_iter(cur_path - 1)
#                print 'path, itr', paths[0][0], itr
            new_top = model.get_value(new_itr, 2)
            old_top = model.get_value(old_itr, 2)
            conc = ' '.join([old_top, new_top])
#                print '0 cycle, top', new_top.encode('utf-8')
            # TODO: постоянная ширина колонки 'topic'
        else:
            print '0 row, nothing to do'
            return
        #if new_top
        model.set(old_itr, 2, conc)

        # move topics up 1 step in a model:
        while True:
            old_itr = new_itr
            new_itr = model.iter_next(old_itr)
            if new_itr: # есть еще строчка в TV
                new_top = model.get_value(new_itr, 2)
                print new_top.encode('utf-8')
                model.set(old_itr, 2, new_top) # ставим предыдущую тему на следующую дату
            else:
                break

        print 'while cycle ended'

    def save_events(self, model):
        '''Save changes in Events() to base'''
# найти список моделей для events, цикл по ev_names[i]
        
        if self.rem_confirm('Save changes in Events?'):
#            for e_name in self.ev_names:
            for i in range(len(self.ev_names)):
                model = self.e_models[i]
                e_name = self.ev_names[i]
                for n in range(len(model)):
                    if e_name == 'essays':
                        vals = model.get(model.get_iter(n), 0, 1, 2, 3, 4)
                        comm = "update essays set enddate ='" + vals[2] + "', topic='" + vals[3] + "', comment='" + vals[4] + "' where e_id='" + str(vals[0]) + "'"
                    else:
                        vals = model.get(model.get_iter(n), 0, 1, 2, 3)
                        comm = "update " + e_name + " set topic='" + vals[2] + "', comment='" + vals[3] + "' where e_id='" + str(vals[0]) + "'"
                    print comm
                    self.exec_sql(comm)

    def save_into_b(self):
        '''save info in temporary lists to base'''
        if self.rem_confirm('Save?'):
            print 'Saving info into base' #TODO: message - to statusbar

            conn = self.open_base()
            cur = conn.cursor()

            if temp_grades:
                while temp_grades:
                    ln = temp_grades.pop(0)
                    command3 = 'insert into grades (g_num, s_num, e_name, e_num, date, mark, comment) values (?,?,?,?,?,?,?);'
                    cur.execute(command3, ln)
                    conn.commit()
                    # s_num, e_name, e_num, date, mark, comment=None
                    r_mark = self.check_old_grades(ln[1], ln[2], ln[3], ln[4], ln[5])
            # show today's grades in Short view: 5.0/3.5...
                    itr = gstud.w_model.get_iter(ln[1] - 1) # (s_num - 1)
                    if r_mark:
                        gstud.w_model.set_value(itr, 8, r_mark)
                    avg = self.get_avg(str(ln[1])) # s_num
                    if avg:
                        gstud.w_model.set_value(itr, 5, avg)

            if temp_attend:
                while temp_attend:
                    ln = temp_attend.pop(0)
                    ln.pop() # 'saved' popped
                    command1 = 'insert into attendance (a_num, s_num, date, absence, comment) values (?,?,?,?,?);' # проверь, сколько знаков "?"
                    cur.execute(command1, ln)
                    conn.commit()

            cur.close()

    def get_tail(self, prefix=None):
        ''' Define tail for SQL command '''

        year_ls = self.get_years() # (year1, year2, semester)
        self.semester = year_ls[2]

        # for ambiguous col names like essays.date
        if prefix:
            date_str = ' and ' + prefix + '.date like "'
        else:
            date_str = ' and date like "'

        if self.semester == 2:
            tail = date_str + year_ls[1] + '%"'
#            print 'tail', tail
        elif self.semester == 1:
            tail = date_str + year_ls[0] + '%"'
#            print 'tail', tail
        else:
            tail = ''

        return tail

    def get_avg(self, s_num):
        ''' get average mark/mark count '''

        tail = self.get_tail()

        # stats: Average grade
        cm = 'select avg(mark) from grades where s_num="' + s_num + '"' + tail
        G = self.exec_sql(cm)[0][0]
        cm = 'select count(mark) from grades where s_num="' + s_num + '"' + tail
        C = str(self.exec_sql(cm)[0][0])
#            print s_name, G, type(G)
        if G:
            G = str(round(G, 1))
            A = G + '/' + C
        else: 
            G = str(0)
            A = G
#            print s_name, G, type(G)

        return A

    def check_old_grades(self, s_num, e_name, e_num, date, mark):
        ''' Check if there are alternative marks for the event, get string like 4.0/3.0 for short view
            Add grade to temp_grades!
        '''
        # s_num, e_name, e_num, date, mark

        mark_ls = [] # list of alternative marks at date, already existing in the base 

        cm = 'select g_num, mark, e_name, e_num, date from grades where s_num=' + str(s_num)
        alt_g = self.exec_sql(cm)

        # check if there are alternative marks in the base
        # and fill mark_ls with alternative marks
        if alt_g:
            for line in alt_g:
                if line[2] == e_name and str(line[3]) == e_num: # следи за типами! e_num - str, line[3] - int
#                    print 'this student has been graded already for this event!'
                    if self.new_gr: # the mark is set, not edited
                        Popup('this student has been graded already for this event!')
                    return False
#                mark_ls.append(str(line[0]))
                if line[4] == date:
                    mark_ls.append(str(line[1]))
        # check if there are alternative marks in temp_grades
#        temp_ grades: [g_num, s_num, e_name, e_num, date, float(mark), comment]
        if temp_grades:
            for gr in temp_grades:
#                print gr
                if gr[2] == e_name and gr[3] == e_num:
                    if self.new_gr:
                        Popup('this student has been graded already for this event!')
                    return False
                if gr[3] == date:
                    mark_ls.append(str(gr[4]))

        mark_ls.append(mark)
        r_mark = '/'.join(mark_ls) # needed for TV only

        return r_mark

    def open_base(self):
        # should check if the base is already opened
        
        if self.b_name:
            print 'b_name:', self.b_name
            conn = sqlite3.connect(self.b_name)
        else:
            print 'no b_name'
#        if b_name:
#            base_p = b_name
#        else:
#            print 'no b_name, using old b_name'
#            home = os.path.expanduser('~')
#            base_p = os.path.join(home, 'svncod/trunk/student_base_01.db')
#        if debug:
#            print 'base_p', base_p
#        conn = sqlite3.connect(self.b_name)
        
        return conn

    def exec_sql(self, command, ex=None):
        
        con = self.open_base()
        cur = con.cursor()
        res = []
#        try:
#            cur.execute(command)
#        except sqlite3.Error, e:
#            print "An error occurred:", e.args[0]
#            Popup('SQL Error, look up logs')
##            logging.error('SQL Error %s',  e.args[0]) # TODO: put error into statusbar
        if command.startswith('select'):
            cur.execute(command)
            res = cur.fetchall()
        elif command.startswith('insert'):
            print ex
            cur.execute(command, ex)
            con.commit()
        else:
            cur.execute(command)
            con.commit()

        con.close()

        return res

#################################### GUI classes ########################
class Information(Conduit):
    ''' GUI for showing grades of a student at a given date (small grades menu) '''

#    def __init__(self, par):
    def __init__(self):
        Conduit.__init__(self)

        self.window_i = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window_i.set_resizable(True)
        self.window_i.set_border_width(2)
        self.window_i.set_size_request(950, 350)

        self.window_i.set_title("Information")

        i_box1 = gtk.VBox(False, 0)
        self.window_i.add(i_box1)
        i_box1.show()

        i_label1 = gtk.Label() 
        i_label2 = gtk.Label() 

        i_sw = gtk.ScrolledWindow()
        d_sw = gtk.ScrolledWindow()
        i_sw.set_border_width(2)
        d_sw.set_border_width(2)
        i_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        d_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        i_sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        d_sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        i_box1.pack_start(i_label1, False, False, 0)
        i_box1.pack_start(i_sw, True, True, 0)
        i_box1.pack_start(i_label2, False, False, 0)
        i_box1.pack_start(d_sw, True, True, 0)

        i_label1.set_text("Events:")
        i_label2.set_text("Students:")
                                                            # TV: grade, date, event, topic, comment
        self.mod_i = gtk.ListStore(str, str, int, str, str)
                                #  current events:
                                #  status, e_id, e_word (lection, essay), topic, (status: current, incoming, set task, get res)
        self.mod_d = gtk.ListStore(str, str, str, str, str)
                                #  debtors:
                                #  status, a_num (hide), s_name, e_word (essays), topic 
                                #  notifications:
                                #  status (напр.: "не забудь!", c_num, s_name, e_word (notification), comment

        # isert information into model
        ins_info = self.ins_info()
        ins_debt = self.ins_debt()

        self.i_tv = gtk.TreeView(self.mod_i)
        self.d_tv = gtk.TreeView(self.mod_d)

        self.i_tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)
        self.d_tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

        self.i_selection = self.i_tv.get_selection()
        self.d_selection = self.d_tv.get_selection()

        i_sw.add(self.i_tv)
        d_sw.add(self.d_tv)

        for i in self.make_cols_info():
            self.i_tv.append_column(i)

        for i in self.make_cols_debt():
            self.d_tv.append_column(i)

        i_sw.show_all()
        d_sw.show_all()
        self.i_tv.show()
        self.d_tv.show()
        i_label1.show()
        i_label2.show()
        self.window_i.show()

#        self.window_i.set_transient_for(par)


    def make_cols_info(self):
        ''' Make cols for Information menu, a part for events '''
#        (int, str, str, str)
        #  e_id, e_word (lection, essay), topic, status (current, incoming, set task, get res)
 
        res = []

        cell3 = gtk.CellRendererText()
        cell3.set_property('font', 'FreeSans 12')
        column3 = gtk.TreeViewColumn('Status', cell3, text=0) 
        res.append(column3)

        cell4 = gtk.CellRendererText()
        cell4.set_property('font', 'FreeSans 12')
        column4 = gtk.TreeViewColumn('Date', cell4, text=1) 
        res.append(column4)

        cell0 = gtk.CellRendererText()
        cell0.set_property('font', 'FreeSans 12')
        column0 = gtk.TreeViewColumn('Event', cell0, text=3) 
        res.append(column0)

        cell1 = gtk.CellRendererText()
        cell1.set_property('font', 'FreeSans 12')
        column1 = gtk.TreeViewColumn('Topic', cell1, text=4) 
        res.append(column1)

        return res

    def make_cols_debt(self):
        ''' Make them when reloading Events TV, after event in Combo is choosen '''
        #  debtors: s_num, s_name, e_id, e_word (essays), topic, status (pending assignment (how long), 

        res = []

        cell4 = gtk.CellRendererText()
        cell4.set_property('font', 'FreeSans 12')
        column4 = gtk.TreeViewColumn('Status', cell4, text=0) 
        res.append(column4)

        cell0 = gtk.CellRendererText()
        cell0.set_property('font', 'FreeSans 12')
        column0 = gtk.TreeViewColumn('Name', cell0, text=1)
        res.append(column0)

        cell1 = gtk.CellRendererText()
        cell1.set_property('font', 'FreeSans 12')
        column1 = gtk.TreeViewColumn('Type', cell1, text=2) 
        res.append(column1)

        cell3 = gtk.CellRendererText()
        cell3.set_property('font', 'FreeSans 12')
        column3 = gtk.TreeViewColumn('Topic', cell3, text=3) 
        res.append(column3)

        return res

class Details(Conduit):
    ''' GUI for showing grades of a student at a given date (small grades menu) '''

    def __init__(self, s_num, s_name, data_g): # mark, date, event (full), topic, saved, index
        Conduit.__init__(self)

        window_g = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window_g.set_resizable(True)
        window_g.set_border_width(2)
        window_g.set_size_request(950, 350)

        window_g.set_title("Grades at date")

        g_box1 = gtk.VBox(False, 0)
        window_g.add(g_box1)
        g_box1.show()

        g_label = gtk.Label() 

        g_sw = gtk.ScrolledWindow()
        g_sw.set_border_width(2)
        g_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        g_sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        g_box1.pack_start(g_label, False, False, 0)
        g_box1.pack_start(g_sw, True, True, 0)

        g_label.set_text(s_name)
                                                            # TV: grade, date, event, topic, comment
        self.mod_g = gtk.ListStore(str, str, str, str, str, str, 'gboolean')
                                    #  g_num, grade, date, event (full), topic, comment, saved 
        self.g_tv = gtk.TreeView(self.mod_g)

        ev_word = ''

#        print 'data_g', data_g
        if data_g:
            for ln in data_g:
                iter = self.mod_g.append()

                                    #  g_num, grade, date, event (full), topic, comment, saved 
                self.mod_g.set(iter, 0, ln[0], 1, ln[1], 2, ln[2], 3, ln[3], 4, ln[4], 5, ln[5], 6, ln[6])
        else:
            # make a new entry (mark is empty)
            self.make_new_en(self.mod_g)

        self.g_tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

        self.selection = self.g_tv.get_selection()

        g_sw.add(self.g_tv)

        cell1 = gtk.CellRendererText()
        cell2 = gtk.CellRendererText()
        cell3 = gtk.CellRendererText()
        cell4 = gtk.CellRendererText()
        cell5 = gtk.CellRendererText()

#        c1 = gtk.gdk.Color('#6ef36e')#67cef9
        c1 = gtk.gdk.Color('#67cef9')#
        cell1.set_property('font', 'FreeSans 12')
        cell1.set_property('cell-background', c1)  # blue for saved entries
        cell1.set_property('editable', True)       
        cell1.connect('edited', self.edit_grade, s_num, 1) 
        cell2.set_property('font', 'FreeSans 12')
        cell3.set_property('font', 'FreeSans 12')
        cell4.set_property('font', 'FreeSans 12')
        cell5.set_property('font', 'FreeSans 12')
        cell5.set_property('editable', True)       
        cell5.connect('edited', self.edit_grade, s_num, 5) 

        self.column1 = gtk.TreeViewColumn("grade", cell1)
        self.column1.set_attributes(cell1, text=1, cell_background_set=6) # blue for saved entries
        self.column2 = gtk.TreeViewColumn("date", cell2, text=2)
        self.column3 = gtk.TreeViewColumn("event", cell3, text=3)
        self.column4 = gtk.TreeViewColumn("topic", cell4, text=4)
        self.column5 = gtk.TreeViewColumn("comment", cell5, text=5)

        self.g_tv.append_column(self.column1)
        self.g_tv.append_column(self.column2)
        self.g_tv.append_column(self.column3)
        self.g_tv.append_column(self.column4)
        self.g_tv.append_column(self.column5)
#
        g_sw.show_all()
        self.g_tv.show()
        g_label.show()
        window_g.show()

#        self.g_tv.connect('row-activated', self.edit_grade)
        window_g.connect('key_press_event', self.fix_grades_cb, s_num) # all other callbacks
        self.g_tv.connect('row-activated', self.open_ev) # when clicked on date - open Events, choose event '''

        # TODO: make "if" for essays (start and enddates wont show yet)

class Attendance(Conduit):
    ''' GUI for showing attendance of a student at a given date (small grades menu) '''

    def __init__(self, s_num, s_name, data_a): # mark, date, event (full), topic, saved, index
        Conduit.__init__(self)

        window_g = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window_g.set_resizable(True)
        window_g.set_border_width(2)
        window_g.set_size_request(950, 350)

        window_g.set_title("Attendance")

        g_box1 = gtk.VBox(False, 0)
        window_g.add(g_box1)
        g_box1.show()

        g_label = gtk.Label() 

        g_sw = gtk.ScrolledWindow()
        g_sw.set_border_width(2)
        g_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        g_sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        g_box1.pack_start(g_label, False, False, 0)
        g_box1.pack_start(g_sw, True, True, 0)

        g_label.set_text(s_name)

        self.mod_a = gtk.ListStore(str, int, str, str, str, 'gboolean')  # attendace table: a_num INTEGER s_num INTEGER, date TEXT, absence TEXT, comment TEXT saved boolean, index int
        ev_word = ''

        a_word = ''
        if data_a:
            for ln in data_a:
                iter = self.mod_a.append()

                if ln[3] == 'N':
                    a_word = 'Not present'
                elif ln[3] == 'L':
                    a_word = 'Late'
        # data_a: a_num, s_num, date, absence, comment, saved)
        # Attendance: a_num, s_num, date, absence, comment, saved
#                self.mod_a.set(iter, 0, ln[0], 1, ln[1], 2, a_word, 3, ln[3], 4, ln[4], 5, ln[5])
                self.mod_a.set(iter, 0, ln[0], 1, ln[1], 2, ln[2], 3, a_word, 4, ln[4], 5, ln[5])
            # TODO: показывать прогулы и опоздания за текущий семестр (то же и с оценками)
        else:
            # make a new entry (mark is empty)
            print 'This student had\'nt been late or absent'
#            self.make_new_en(self.mod_g)

        self.a_tv = gtk.TreeView(self.mod_a)
        self.a_tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

        self.selection = self.a_tv.get_selection()

        g_sw.add(self.a_tv)

        cell2 = gtk.CellRendererText()
        cell3 = gtk.CellRendererText()
        cell4 = gtk.CellRendererText()

#        c1 = gtk.gdk.Color('#6ef36e')#67cef9
#        c1 = gtk.gdk.Color('#67cef9')#
        cell2.set_property('font', 'FreeSans 12')
        cell3.set_property('font', 'FreeSans 12')
        cell3.set_property('editable', True)       
        cell3.connect('edited', self.edit_attend, s_num, 1) # это номер колонки
        cell4.set_property('font', 'FreeSans 12')
        cell4.set_property('editable', True)       
        cell4.connect('edited', self.edit_attend, s_num, 2)

        self.column2 = gtk.TreeViewColumn("date", cell2, text=2)
        self.column3 = gtk.TreeViewColumn("absence", cell3, text=3)
        self.column4 = gtk.TreeViewColumn("comment", cell4, text=4)

        self.a_tv.append_column(self.column2)
        self.a_tv.append_column(self.column3)
        self.a_tv.append_column(self.column4)
#
        g_sw.show_all()
        self.a_tv.show()
        g_label.show()
        window_g.show()

        window_g.connect('key_press_event', self.fix_absence_cb, s_num)
#        self.a_tv.connect('row-activated', self.open_ev)

# TODO: сделать удаление пропусков и опозданий. 
#       Добавление нового прогула (ctr+n). 
#       Редактирование поля L/N. Дату лучше не трогать

class Bases(Conduit):
    '''GUI for assignments: essays. and personal quests '''

    def __init__(self, b_names):
        # g_path - for key_press() to change row in g_tv (Details)
        Conduit.__init__(self)

        self.window_b = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window_b.set_resizable(True)
        self.window_b.set_border_width(2)
        self.window_b.set_size_request(250, 350)

        self.window_b.set_title("Choose students")

        c_box1 = gtk.VBox(False, 0)
        self.window_b.add(c_box1)
        c_box1.show()

        c_sw = gtk.ScrolledWindow()
        c_sw.set_border_width(2)
        c_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
 
        self.b_model = gtk.ListStore(str, str) # s_num, s_name

        self.b_tv = gtk.TreeView()
        self.b_tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

        self.selection = self.b_tv.get_selection()
        self.selection.set_mode(gtk.SELECTION_MULTIPLE)

        self.b_tv.set_model(self.b_model)
        c_sw.add(self.b_tv)

        cols = self.make_b_cols()
        for i in cols:
            self.b_tv.append_column(i)

        for b in b_names:
            print b
            itr = self.b_model.append()
            out = [itr, 0, b[0], 1, b[1]]
#            for i in range(len(r)):
#                out.extend([i, r[i]])
            self.b_model.set(*out)

        c_box1.pack_start(c_sw, True, True, 0)

        self.window_b.set_type_hint (gtk.gdk.WINDOW_TYPE_HINT_DIALOG) 

        c_sw.show_all()
        self.window_b.show()

#        self.window_b.set_modal(True)

#        window_b.connect('key_press_event', self.ch_menu_cb, e_id)
        self.window_b.connect("destroy", self.destroy_cb) 

#        main()

#        print 'level', gtk.main_level()

        cb = self.b_tv.connect('row-activated', self.base_start) # when clicked on base name - start main programm
#        if cb:
#            self.window_b.hide()
#    def hide_widget(self, *args):
        
    def base_start(self, tv, path, column):
#        Conduit.__init__(self)
        # возможно придется прибить main() и начать другой луп
        itr = self.b_model.get_iter(path[0])
        fpath = self.b_model.get_value(itr, 0)
#        print fpath
        grst = Viewer(fpath, None)
        self.window_b.hide()

        return True

    def make_b_cols(self):
        ''' cols for Students menu '''
        res = []
#        cell1 = gtk.CellRendererText()
#        cell1.set_property('font', 'FreeSans 12')
#        column1 = gtk.TreeViewColumn('Num', cell1, text=0) 
#        res.append(column1)

        cell2 = gtk.CellRendererText()
        cell2.set_property('font', 'FreeSans 12')
        column2 = gtk.TreeViewColumn('Base Name', cell2, text=1) 
        res.append(column2)

        return res

class Choose_students(Conduit):
    '''GUI for assignments: essays. and personal quests '''

    def __init__(self, e_id):
        # g_path - for key_press() to change row in g_tv (Details)
        Conduit.__init__(self)

        window_c = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window_c.set_resizable(True)
        window_c.set_border_width(2)
        window_c.set_size_request(250, 350)

        window_c.set_title("Choose students")

        c_box1 = gtk.VBox(False, 0)
        window_c.add(c_box1)
        c_box1.show()

        c_sw = gtk.ScrolledWindow()
        c_sw.set_border_width(2)
        c_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
 
        self.c_model = gtk.ListStore(int, str) # s_num, s_name

        self.c_tv = gtk.TreeView()
        self.c_tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

        self.selection = self.c_tv.get_selection()
        self.selection.set_mode(gtk.SELECTION_MULTIPLE)

        self.c_tv.set_model(self.c_model)
        c_sw.add(self.c_tv)

        cols = self.make_c_cols()
        for i in cols:
            self.c_tv.append_column(i)

        cm = 'select s_num, s_name from students where active=1'
        s_ls = self.exec_sql(cm)
        out = []
        for r in s_ls:
            itr = self.c_model.append()
            out = [itr,]
            for i in range(len(r)):
                out.extend([i, r[i]])
            self.c_model.set(*out)

        c_box1.pack_start(c_sw, True, True, 0)
        c_sw.show_all()
        window_c.show()

        window_c.connect('key_press_event', self.ch_menu_cb, e_id)

    def make_c_cols(self):
        ''' cols for Students menu '''
        res = []
        cell1 = gtk.CellRendererText()
        cell1.set_property('font', 'FreeSans 12')
        column1 = gtk.TreeViewColumn('Num', cell1, text=0) 
        res.append(column1)

        cell2 = gtk.CellRendererText()
        cell2.set_property('font', 'FreeSans 12')
        column2 = gtk.TreeViewColumn('Name', cell2, text=1) 
        res.append(column2)

# TODO: column for avg(mark)?

        return res

class Assign(Conduit):
    '''GUI for assignments: essays. and personal quests '''

    def __init__(self, stud_ls=None):
        Conduit.__init__(self)

        window_a = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window_a.set_resizable(True)
        window_a.set_border_width(2)
        window_a.set_size_request(950, 450)

        window_a.set_title("Assignments")

        a_box1 = gtk.VBox(False, 0)
        window_a.add(a_box1)
        a_box1.show()
        a_box2 = gtk.VBox(False, 10)
        a_box2.set_border_width(2)

        a_box1.pack_start(a_box2, True, True, 0)
        a_box2.show()

        aa_sw = gtk.ScrolledWindow()
        aa_sw.set_border_width(2)
        aa_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
 
#        assignments: (a_num, s_name, topic, delivered, date, mark, comment)'
        self.aa_model = gtk.ListStore(str, str, str, str, str, str, str) 
        self.modelfilter = self.aa_model.filter_new()

        self.ins_assign() # insert info into model

        self.aa_tv = gtk.TreeView()
        self.aa_tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)
        self.selection = self.aa_tv.get_selection()

#        self.a_tv.set_model(self.a_model)
        self.aa_tv.set_model(self.modelfilter)
        aa_sw.add(self.aa_tv)

        cols = self.make_asn_cols()
        for i in cols:
            self.aa_tv.append_column(i)

        self.label = gtk.Label() 
        a_box2.pack_start(self.label, False, False, 0)
        a_box2.pack_start(aa_sw, True, True, 0)

        self.label.show()
        self.aa_tv.show()
        aa_sw.show_all()
        window_a.show()

        window_a.connect('key_press_event', self.assign_save) # Ctrl+n, s
#
#        self.aa_tv.connect('row-activated', self.assign_set) # выбираем ряд для вставки в Details

#        self.combo.connect("changed", self.choose) # комбо с названиями таблиц: lectures, etc.
#        self.combo.set_active(0)

    def make_asn_cols(self):
        ''' Make them when reloading Events TV, after event in Combo is choosen '''
#        assignments: (a_num TEXT, s_num INTEGER, e_id INTEGER, delivered TEXT, date TEXT, mark REAL, comment TEXT)'
        res = []

        cell0 = gtk.CellRendererText()
        cell0.set_property('font', 'FreeSans 12')
        column0 = gtk.TreeViewColumn('Name', cell0, text=1) 
        res.append(column0)

        cell1 = gtk.CellRendererText()
        cell1.set_property('font', 'FreeSans 12')
        column1 = gtk.TreeViewColumn('e_id', cell1, text=2) 
        res.append(column1)

#        cell2 = gtk.CellRendererText()
#        cell2.set_property('font', 'FreeSans 12')
##        cm = 'select topic from essays where e_id="' + e_id + '"' # TODO: get e_id
#        column2 = gtk.TreeViewColumn('topic', cell2) #, text=top) 
#        res.append(column1)

        cell3 = gtk.CellRendererText()
        cell3.set_property('font', 'FreeSans 12')
        cell3.set_property('editable', True)
        cell3.connect('edited', self.assign_set, 3)
        column3 = gtk.TreeViewColumn('delivered', cell3, text=3) 
        res.append(column3)

        cell4 = gtk.CellRendererText()
        cell4.set_property('font', 'FreeSans 12')
        column4 = gtk.TreeViewColumn('date', cell4, text=4) 
        res.append(column4)

        cell5 = gtk.CellRendererText()
        cell5.set_property('font', 'FreeSans 12')
        cell5.set_property('editable', True)
        cell5.connect('edited', self.assign_set, 5)
        column5 = gtk.TreeViewColumn('mark', cell5, text=5) 
        res.append(column5)

        cell6 = gtk.CellRendererText()
        cell6.set_property('font', 'FreeSans 12')
        cell6.set_property('editable', True)
        cell6.connect('edited', self.assign_set, 6)
        column6 = gtk.TreeViewColumn('commment', cell6, text=6) 
        res.append(column6)

        return res

class Events(Conduit):

    '''GUI for events: lectures, seminars, tests, essays. '''
#TODO:    Should add talks, or is it essay with talking part? Or is it a personal assignment?

    def __init__(self, g_path=None):
        # g_path - for key_press() to change row in g_tv (Details)
        Conduit.__init__(self)

        self.tv = gstud.tv
        self.insert_columns = gstud.insert_columns

        window_e = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window_e.set_resizable(True)
        window_e.set_border_width(2)
        window_e.set_size_request(950, 450)

        window_e.set_title("Events")

        e_box1 = gtk.VBox(False, 0)
        window_e.add(e_box1)
        e_box1.show()
        e_box2 = gtk.VBox(False, 10)
        e_box2.set_border_width(2)

        # combo box initiated 
        self.combo = gtk.combo_box_new_text()
        e_box1.pack_start(self.combo, False, False, 0)
        self.combo.show()
        
        self.combo_lst = self.ev_names
        for i in self.combo_lst: 
            self.combo.append_text(i)
        # tuple of 4 lists (lectures, seminars...), each list contains events (tuple: e_num, date, topic, comment)
        self.all_evts = self.get_all_events()

        e_box1.pack_start(e_box2, True, True, 0)
        e_box2.show()

        e_sw = gtk.ScrolledWindow()
        e_sw.set_border_width(2)
        e_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        e_sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        
        self.e_models = []
        for i in range(4):
            if i == 1:
                mod = gtk.ListStore(int, str, str, str, str) # 1 = essays
            else:
                mod = gtk.ListStore(int, str, str, str)

        # for every model of 4 (lectures, seminars...)
        # insert events
            self.ins_events(mod, self.all_evts[i]) # i helps to find out, which one is essay
            self.e_models.append(mod)

        self.e_tv = gtk.TreeView(self.e_models[0])
        gstud.cur_e_name = self.combo_lst[0]

        self.e_tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

        self.selection = self.e_tv.get_selection()

        e_sw.add(self.e_tv)

        self.label = gtk.Label() 
        self.entry = gtk.Entry()

        # append 4 columns to TView (needed later, after removing cols from model)

        # columns are made in combo 
       
        e_sw.show_all()
        self.e_tv.show()
        e_box2.pack_start(self.label, False, False, 0)
        e_box2.pack_start(e_sw, True, True, 0)
        e_box2.pack_start(self.entry, False, False, 0)

        self.entry.show()
        self.label.show()
        window_e.show()

        window_e.connect('key_press_event', self.event_n) # Ctrl+n, s

        self.e_tv.connect('row-activated', self.event_set, g_path) # выбираем ряд для вставки в Details

        self.combo.connect("changed", self.choose) # комбо с названиями таблиц: lectures, etc.
        self.combo.set_active(0)

        # entry to add new event (date/topic)
#        self.entry.connect('activate', self.ins_ev_cb) # старый вызов (для Entry)

    def make_columns(self, ev_n):
        ''' Make them when reloading Events TV, after event in Combo is choosen '''
        res = []
        cell1 = gtk.CellRendererText()
        cell1.set_property('font', 'FreeSans 12')
        column1 = gtk.TreeViewColumn('e_id', cell1, text=0) 
        res.append(column1)

        cell2 = gtk.CellRendererText()
        cell2.set_property('font', 'FreeSans 12')
        column2 = gtk.TreeViewColumn('date', cell2, text=1) 
        res.append(column2)

        # вставка доп. столбца для essays
        if ev_n == 1:
            cell5 = gtk.CellRendererText()
            cell5.set_property('font', 'FreeSans 12')
            cell5.set_property('editable', True)       
            cell5.connect('edited', self.edit_event, 2)
            column5 = gtk.TreeViewColumn('deadline', cell5, text=2) # enddate in the model
            res.append(column5)
            tx1 = 3
            tx2 = 4
        # сдвигаем оставшиеся столбцы
        else:
            tx1 = 2
            tx2 = 3

        cell3 = gtk.CellRendererText()
        cell3.set_property('font', 'FreeSans 12')
        cell3.set_property('editable', True)       
        cell3.connect('edited', self.edit_event, tx1)
#        cell3.connect('edited', self.edit_ev)
        column3 = gtk.TreeViewColumn('topic', cell3, text=tx1) 
        res.append(column3)

        cell4 = gtk.CellRendererText()
        cell4.set_property('font', 'FreeSans 12')
        cell4.set_property('editable', True)       
        cell4.connect('edited', self.edit_event, tx2)
#        cell4.connect('edited', self.edit_ev)
        column4 = gtk.TreeViewColumn('comment', cell4, text=tx2) 
        res.append(column4)

        return res
 
class Viewer(Conduit):
    ''' Main window '''

    def __init__(self, b_p, cm):
        Conduit.__init__(self, b_p, cm)


#        self.b_sw = b_sw # switch between bases from args: 1, 2

        # name of current events group (lectures, essays...)
        self.cur_e_name = ''
        self.cur_e_num = 0

        window2 = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window2.set_resizable(True)
        window2.set_border_width(2)
        window2.set_size_request(950, 450)

        window2.set_title("Slacker tracker")

        box1 = gtk.VBox(False, 0)
        window2.add(box1)
        box1.show()
        box2 = gtk.VBox(False, 10)
        box2.set_border_width(2)
        box1.pack_start(box2, True, True, 0)
        box2.show()

        sw = gtk.ScrolledWindow()
        sw.set_border_width(2)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        dates = self.get_dates()
        self.date_ls = dates[0]
        self.len_d = dates[1] # number of data entries
        
#        logging.info('dates %s', dates)

        # model for 'short view'
        # s_num, s_name, colored (s_num), av(abs), av(late), av(grade), checkbox(N), checkbox(L), grade, hash for absence
        self.w_model = gtk.ListStore(int, str, 'gboolean', str, str, str, 'gboolean', 'gboolean', str, str, int, str) 
        self.ins_wk_main(self.w_model)

        self.modelfilter = self.w_model.filter_new()
        self.modelfilter.set_visible_func(self.vis) # visible function call
        # make cols in model
######### model for 'long view' ##########
        strs = [int, str, 'gboolean']
        for i in range(0, (self.len_d * 2), 2): # 3 for s_num, s_name and current date on end
            strs.append(str) # set types for text column
            strs.append('gboolean') # set types for color column
#
##        logging.info('strs %s', len(strs)) # количество столбцов в модели
#        # model for 'regular view'
        self.model = gtk.ListStore(*strs) # method to create dynamic model
#        self.tv = gtk.TreeView(self.model)
##########################################
        self.tv = gtk.TreeView(self.w_model)
        self.tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

        self.tv.set_model(self.modelfilter)
        sw.add(self.tv)
        self.selection = self.tv.get_selection()
#        self.selection.set_mode(gtk.SELECTION_MULTIPLE)

        self.combo_b = gtk.combo_box_new_text() # classes
        self.combo_g = gtk.combo_box_new_text() # groups: weak, strong
        self.label = gtk.Label() 
#        self.entry = gtk.Entry()
#        self.insert_columns(dates) # inserting columns
        res_cols = self.make_wk_columns() # inserting columns
        for cc in res_cols:
            self.tv.append_column(cc)

#        self.tv.set_search_column(1)
        
        sw.show_all()
#        self.tv.show() # необязательно (sw.show_all показывает)

        box2.pack_start(self.label, False, False, 0)
        box3 = gtk.HBox(False, 0)
        box3.show()
        box2.pack_start(box3, False, False, 0)
        box3.pack_start(self.combo_b, False, False, 0)
        box3.pack_start(self.combo_g, False, False, 0)
        self.combo_b.show()
        self.combo_g.show()
        
#        self.combo_b_lst = ['seniors', 'minors', 'All']
        self.combo_b.set_active(0) # default
        gtd = self.get_dates()[0]
        gtd.pop()

        self.combo_b.append_text('All time')
        for i in range(1, len(gtd)):
            self.combo_b.append_text(gtd[i])
            if gtd[i] == self.date: # if today is in CPlan
                self.combo_b.set_active(i)
        self.combo_b.append_text('Today')
                
#        print 'len', len(self.combo_b.get_model())
        if self.combo_b.get_active() == -1:
            self.combo_b.set_active(len(self.combo_b.get_model()) - 1) # last item - Today

        self.combo_g_lst = ['Weak', 'Strong', 'Active', 'All']
        for j in self.combo_g_lst: 
            self.combo_g.append_text(j)

        self.combo_b.connect('changed', self.choose_cl)

        self.combo_g.connect('changed', self.choose_gr)
        self.combo_g.set_active(int(self.c_group))
        self.modelfilter.refilter()

        box2.pack_start(sw)
#        box2.pack_start(self.entry, False, False, 0)

        self.status_bar = gtk.Statusbar()
#        box2.pack_start(self.status_bar, True, True, 0)
        box2.pack_start(self.status_bar, False, False, 2)

#        self.entry.connect('activate', self.entry_cb)
#        self.entry.connect('key_press_event', self.on_key_press_event)
        f_d = pango.FontDescription("sans normal 12")
#        c_d = pango.Color("red")
        l_text = (os.path.basename(self.b_name).split('_')[0] + ' year').upper() + '    Today is: ' + self.date
        self.label.set_text(l_text) # senior-minor year 
        self.label.modify_font(f_d)
#        self.label.modify_style(c_d) # look up pango context

#        self.entry.show()
        self.label.show()
        self.status_bar.show()
        c_id = self.status_bar.get_context_id('Смотрим оценки')


        window2.show()
        window2.connect("delete-event", self.delete_cb) 
        window2.connect("destroy", self.destroy_cb) 
        # try delete-event or destroy-event
        
        window2.connect('key_press_event', self.redraw_cb, c_id)
        self.tv.connect('row-activated', self.edited_cb)
#        window2.connect('key_press_event', self.redraw_cb)

        self.ins_main()

#        for i in range(len(self.w_model)):
#            itr = self.w_model.get_iter(i) 
#            print self.w_model.get(itr,0,1,2,3,4,5,6,7,8,9,10)

        # move cursor and selection
        c_col = self.tv.get_column(7)
        self.tv.set_cursor(0, c_col, False)
        self.tv.grab_focus()

        if self.start_dialog_on:
#            inf = Information(window2)
            inf = Information()
#            inf.window_i.grab_focus()
#            inf.window_i.activate_focus()


    def make_wk_columns(self):

        #(int, str, 'gboolean', str, str, str, 'gboolean', 'gboolean', float) 

        res_cols = []

#        c1 = gtk.gdk.Color('#ea7e58')
#        c1 = gtk.gdk.Color('#6ef36e')
        c1 = gtk.gdk.Color('gray')
        cell1 = gtk.CellRendererText()
        cell1.set_property('font', 'FreeSans 12')
        self.column1 = gtk.TreeViewColumn('s_num', cell1)
        cell1.set_property('cell-background', c1) 
        self.column1.set_attributes(cell1, text=0, cell_background_set=2)
#        self.tv.append_column(self.column1)
        res_cols.append(self.column1)

        cell3 = gtk.CellRendererText()
        cell3.set_property('font', 'FreeSans 12')
        cell3.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
        self.column3 = gtk.TreeViewColumn('student', cell3, text=1)
        self.column3.set_sort_column_id(1)
#        self.tv.append_column(self.column3)
        res_cols.append(self.column3)
        
        lst_stat = ['absent', 'late', 'avg grade']
        for cn in range(len(lst_stat)):
            cell = gtk.CellRendererText()
            cell.set_property('font', 'FreeSans 12')
            cell.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
            self.column = gtk.TreeViewColumn(lst_stat[cn], cell, text= cn + 3)
            self.column.set_sort_column_id(1)

#            self.tv.append_column(self.column)
            res_cols.append(self.column)

#        ls_abs = ['N', 'L']
#        for ss in range(len(ls_abs)):
        cell4 = gtk.CellRendererToggle()
        cell4.set_property('activatable', True)
        cell4.connect('toggled', self.toggler, self.w_model, 'N', 6)
        self.column4 = gtk.TreeViewColumn('N', cell4)
        self.column4.add_attribute(cell4, 'active', 6)
#        self.tv.append_column(self.column4)
        res_cols.append(self.column4)

        cell5 = gtk.CellRendererToggle()
        cell5.set_property('activatable', True)
        cell5.connect('toggled', self.toggler, self.w_model, 'L', 7)
        self.column5 = gtk.TreeViewColumn('L', cell5)
        self.column5.add_attribute(cell5, 'active', 7)
#        self.tv.append_column(self.column5)
        res_cols.append(self.column5)

        # Grade
        cell6 = gtk.CellRendererText()
        cell6.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)

        self.column6 = gtk.TreeViewColumn('G', cell6, text=8) 
#        self.column6.set_sort_column_id(1)
        res_cols.append(self.column6)

        cell7 = gtk.CellRendererText()
        cell7.set_property('font', 'FreeSans 12')
#        cell7.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
        cell7.set_property('editable', True)       
        cell7.connect('edited', self.edit_notes)   #, s_num) 

        self.column7 = gtk.TreeViewColumn('Notes', cell7, text=11) 


        res_cols.append(self.column7)

        return res_cols

#        self.tv.append_column(self.column6)
#        self.tv.connect('row-activated', self.edited_cb)

    def insert_columns(self, date):
        
        date_ls = date[0]
        len_d = date[1]
        res_cols = []

        cell1 = gtk.CellRendererText()
        cell1.set_property('font', 'FreeSans 12')
        self.column1 = gtk.TreeViewColumn('s_num', cell1, text=0) 
        res_cols.append(self.column1)
#        self.tv.append_column(self.column1)


        cell2 = gtk.CellRendererText()
        cell2.set_property('font', 'FreeSans 12')
        cell2.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
        self.column2 = gtk.TreeViewColumn('student', cell2, text=1) 
        self.column2.set_sort_column_id(1)
        res_cols.append(self.column2)

        a1 = gtk.gdk.Color('#ea7e58')
        # начинаем с 3й колонки, длина = количество дат + 2
        cnt = 0 # counter for dates list date_ls
        for i in range(3, (len_d*2) + 3, 2):
#            print 'col', date_ls[cnt], i
#            logging.info('column %s, text from model row %s', date_ls[cnt], i)
            cell = gtk.CellRendererText()
            cell.set_property('font', 'FreeSans 12')
            cell.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
            cell.set_property('cell-background', a1) # COLOR for Absent students (light red?). False/True - in Liststore col
            
#            self.column = gtk.TreeViewColumn(date_ls[cnt].strftime("%d-%m-%Y"), cell)
            self.column = gtk.TreeViewColumn(date_ls[cnt], cell)
            self.column.set_attributes(cell, text=i, cell_background_set=(i+1))

            res_cols.append(self.column)

            cnt += 1 

        return res_cols

#        self.tv.connect('row-activated', self.on_click)

class Stud_info(Conduit):
    ''' Main window '''

    def __init__(self):
        Conduit.__init__(self)

        window2 = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window2.set_resizable(True)
        window2.set_border_width(10)
        window2.set_size_request(950, 450)

        window2.set_title("Studentus")

        box1 = gtk.VBox(False, 0)
        window2.add(box1)
        box1.show()
        box2 = gtk.VBox(False, 10)
        box2.set_border_width(10)
        box1.pack_start(box2, True, True, 0)
        box2.show()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.s_model = gtk.ListStore(int, str, str, str, str, str, str)
        self.tv = gtk.TreeView(self.s_model)
        self.selection = self.tv.get_selection()

        self.modelfilter = self.s_model.filter_new()
        self.tv.set_model(self.modelfilter)

        sw.add(self.tv)

        self.label = gtk.Label() 
        self.entry = gtk.Entry()
        
        cell0 = gtk.CellRendererText()
        cell1 = gtk.CellRendererText()
        cell2 = gtk.CellRendererText()
        cell3 = gtk.CellRendererText()
        cell4 = gtk.CellRendererText()
        cell5 = gtk.CellRendererText()
        cell6 = gtk.CellRendererText()
        cell7 = gtk.CellRendererText()

        cell0.set_property('font', 'FreeSans 12')
#        cell0.set_property('editable', True)       
#        cell0.connect('edited', self.edit_stud, 0) 
        cell1.set_property('font', 'FreeSans 12')
        cell1.set_property('editable', True)       
        cell1.connect('edited', self.edit_stud, 1) 
        cell2.set_property('font', 'FreeSans 12')
        cell2.set_property('editable', True)       
        cell2.connect('edited', self.edit_stud, 2) 
        cell3.set_property('font', 'FreeSans 12')
        cell3.set_property('editable', True)       
        cell3.connect('edited', self.edit_stud, 3) 
        cell4.set_property('font', 'FreeSans 12')
        cell4.set_property('editable', True)       
        cell4.connect('edited', self.edit_stud, 4) 
        cell5.set_property('font', 'FreeSans 12')
        cell5.set_property('editable', True)       
        cell5.connect('edited', self.edit_stud, 5) 
        cell6.set_property('font', 'FreeSans 12')
        cell6.set_property('editable', True)       
        cell6.connect('edited', self.edit_stud, 6) 
        cell7.set_property('font', 'FreeSans 12')
        cell7.set_property('editable', True)       
        cell7.connect('edited', self.edit_stud, 7) 

# students (s_num INTEGER PRIMARY KEY, s_name TEXT, email TEXT, phone TEXT, photo TEXT, active TEXT, comment TEXT)"
        self.column0 = gtk.TreeViewColumn("s_num", cell0, text=0)
        self.column1 = gtk.TreeViewColumn("Name", cell1, text=1)
        self.column2 = gtk.TreeViewColumn("e-mail", cell2, text=2)
        self.column3 = gtk.TreeViewColumn("phone", cell3, text=3)
        self.column4 = gtk.TreeViewColumn("photo", cell4, text=4)
        self.column5 = gtk.TreeViewColumn("active", cell5, text=5)
        self.column6 = gtk.TreeViewColumn("average", cell6) #, text=6) # not in the base table, get avg(mark)
        self.column7 = gtk.TreeViewColumn("comment", cell7, text=6)

        self.tv.append_column(self.column0)
        self.tv.append_column(self.column1)
        self.tv.append_column(self.column2)
        self.tv.append_column(self.column3)
        self.tv.append_column(self.column4)
        self.tv.append_column(self.column5)
        self.tv.append_column(self.column6)
        self.tv.append_column(self.column7)
        
        sw.show_all()
        self.tv.show()
        box2.pack_start(self.label, False, False, 0)
        box2.pack_start(sw)
        box2.pack_start(self.entry, False, False, 0)

        self.entry.show()
        self.label.show()

        window2.show()
        self.get_stud_info()

    def get_stud_info(self):

        conn = self.open_base()
        cur = conn.cursor()

        cur.execute('select * from students')

        res = cur.fetchall()

        for r in res:
            iter = self.s_model.append()
            out = [iter,]
            for i in range(len(r)):
                out.extend([i, r[i]])
            self.s_model.set(*out)

class Popup:
    def __init__(self, text=None):
        self.text = text
        dialog = gtk.Dialog(title='warning')
        label = gtk.Label(self.text)
        dialog.vbox.pack_start(label, True, True, 10)
        label.show()
        dialog.show()

#class Wiz(Conduit):
class Wiz():
    ''' A wizard to fill in all info,
     needed for the application to start. Main window

    '''
    def __init__(self):
#        Conduit.__init__(self)
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_resizable(True)
        window.set_border_width(10)
        window.set_size_request(250, 200)

        window.set_title("Studentus")

        box1 = gtk.VBox(False, 0)
        window.add(box1)
        box1.show()

        self.label = gtk.Label('Welcome to the STR.\nThere is no database available.\nDo you whant to create it?')
        self.button1 = gtk.Button(None, gtk.STOCK_CANCEL)
        self.button2 = gtk.Button(None, gtk.STOCK_OK)

        box1.pack_start(self.label, True, True, 0)
        box2 = gtk.HBox(False, 0)
        box2.show()
        box1.pack_start(box2, False, False, 0)
        box2.pack_start(self.button1, True, False, 0)
        box2.pack_start(self.button2, True, False, 0)
        self.label.show()
        self.button1.show()
        self.button2.show()
        window.show()
        window.connect("destroy", self.destroy_cb) 
        self.button1.connect('clicked', self.destroy_cb)
        self.button2.connect('clicked', self.get_bn)

    def destroy_cb(self, widget):
        gtk.main_quit()

    def get_bn(self, button):
        '''Make a new base - dialog'''

        res = self.insert_bn()  # returns base name
        print 'New base name is:', res

        if res:
            # TODO: User needs an option for a path.
            # TODO: Write to config
            b_path = os.path.join(os.path.expanduser('~'), res + '.db')
#            print b_path
            self.create_base(b_path)

        else:
            print 'no result'

    def insert_bn(self):
        ''' A Dialog for Wizard - choose base name '''

        z_dialog = gtk.Dialog("Base name", None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

        self.z_entry = gtk.Entry()
        z_dialog.vbox.pack_start(self.z_entry, True, True, 0)
        self.z_entry.show()
        z_dialog.show()

        response = z_dialog.run()
        if response == -3: # resp accepted
#            get data from Entry
            res = self.z_entry.get_text()
#            print res
            z_dialog.destroy()
            return res

#            self.destroy_cb
#            gtk.main_quit()
#            return True
#            return None
        else:
            z_dialog.destroy()
            return

    def create_base(self, b_path):
        '''Create a new base'''

        conn = sqlite3.connect(b_path)
        cur = conn.cursor()
        cur.executescript("""
                CREATE TABLE students (s_num INTEGER PRIMARY KEY, s_name TEXT, email TEXT, phone TEXT, photo TEXT, active TEXT, comment TEXT);
                CREATE TABLE attendance (a_num TEXT, s_num INTEGER, date TEXT, absence TEXT, comment TEXT);
                CREATE TABLE grades (g_num TEXT, s_num INTEGER, e_name TEXT, e_num INT, date TEXT, mark REAL, comment TEXT);
                CREATE TABLE lectures (e_id INTEGER PRIMARY KEY, date TEXT, topic TEXT, comment TEXT);
                CREATE TABLE seminars (e_id INTEGER PRIMARY KEY, date TEXT, topic TEXT, comment TEXT);
                CREATE TABLE tests (e_id INTEGER PRIMARY KEY, date TEXT, topic TEXT, comment TEXT);
                CREATE TABLE essays (e_id INTEGER PRIMARY KEY, date TEXT, enddate TEXT, topic TEXT, comment TEXT);
                CREATE TABLE notes (c_num TEXT, s_num INTEGER, date TEXT, comment TEXT);
                CREATE TABLE assignments (a_num TEXT, s_num INTEGER, e_id INTEGER, delivered TEXT, date TEXT, mark REAL, comment TEXT);
        """)
        conn.commit()
        cur.close()

def main():
    gtk.main()
    return 0

if __name__ == '__main__':

################# Options ###########


#    global b_name

    from optparse import OptionParser
    usage = "usage: %prog [-d] [-c config] -s base_name"
    parser = OptionParser(usage=usage)

    parser.add_option("-s", "--switch", dest="switch", action="store", help="Switch between bases 1 and 2")
    parser.add_option("-c", "--config", dest="config", action="store", help="Get config from path")
    parser.add_option("-d", "--debug", dest="debug", action="store_true", help="Debug this thing. self.date is set to specific date")
    (options, args) = parser.parse_args()

    if options.config: # for debugging (alternative paths and stuff)
        c_path = options.config
    else:
        c_path = os.path.join(os.path.expanduser('~'), '.config', 'str', 'strrc')

    config = ConfigParser.ConfigParser()
    config.read(c_path)

#    global cur_model
#    cur_model = config.get('Settings', 'default_view') # current model used (0 = long sheet, 1 = short)

    if options.debug:
        debug = True
    else:
        debug = False
# TODO: Здесь нужно проверить валидность путей к базам (сколько их д.б.?,  как нумеровать

    b_path = config.get('Paths', 'base_path')
    print 'path', b_path

    b_names = os.listdir(b_path) # base names to show in menu
    bp = []
    for b in b_names:
        n = os.path.join(b_path, b)
        bp.append((n, b)) # full paths to bases

    if b_names:
        # show menu with available bases
        print "yes"
        bss = Bases(bp)
#        if bss:
#            bss.destroy()
    else:
        # show menu create new base? Or point to base_dir (write to config)
        print "No"

    main()

#    if not b_path:
#        print 'no base available, starting a wizard'
#        # start a wizard
#        wz = Wiz()
#
#    else:
#        # check for validity
#        gstud = Viewer(cur_model)

# Switch overrides base_path, no menues to choose - just given base.
#    if options.switch:
#        if options.switch == '1':
#            b_name = config.get('Paths', 'stud_path1')
#        elif options.switch == '2':
#            b_name = config.get('Paths', 'stud_path2')
#            print b_name
#        gstud = Viewer(cur_model)
#    else:
#        print "no options given, exiting"
#        sys.exit(0)


# TODO: В Events ставим курсор на текущую дату (если есть) или в начало списка, если нету
# TODO: make checkbox delete absence record (+popup)
# TODO: Details: общий GUI: switch between Grades, Attendance, Assignments, Notes(?)
# TODO: Details: Сделать комментарии к оценкам: в Details - колонку, в edited_g... - добавить опцию
# TODO: Details: Надо ставить по умолчанию не текущее событие, а предыдущее (за которое обычно и ставится оценка)
# TODO: Редактирование поля L/N в Attendance.
# TODO: show student's picture, so you know, to whom you gave F-
# TODO: Глюк: при исправлении старой оценки вылазит Popup "this student already had a grade..."
# Не очень актуально: SQL Errors go to status bar (others too), (gtk.Statusbar), log
# CLI: Двоеточие или / - команды-фильтры (today, last - in grades), поиск
# Сделать окошко для всех temp_grades ? В принципе, может пригодиться
# TODO: 
# TODO: Перенести часть опций из str_tools (-c, -i, -r...)
# TODO: нужна возможность отдельно импортировать lections, seminars
# TODO: Удаление тем из Events (если еще нет в Grades)
# TODO: Постоянная длина колонки topic в Events (а то комментариев не видать)
# TODO: При move up событий - всплывающее меню "concatenate/drop"
# TODO: line 659 - what the??? Разберись, нужно ли сохранять attendace в модели. Странно это.
# TODO: Разберись, нужен ли temp_grades (temp_attend можно оставить)
# TODO: Нужен ли бэкап отдельно, если есть dump?
# TODO: 
# TODO: В Assignments: когда ставится оценка, всплывает напоминание, если delivered не проставлено.
# TODO: Сделай сохранение в Details. Неудобно для этого лазить в Viewer.
# TODO: В stud_info сделать Ctrl+n - добавление студента. (s_num, и active - обязательно)
# TODO: Перевести все диалоги и надписи на русский.
# TODO: Перенести списки студентов, событий... в .config/str
# TODO: 
# TODO: README <= формат файла Events: l//2014-03-30//Тема занятия
# Первый маркер может иметь значения: l(ecture), s(eminar), e(ssay), t(est)


'''# TODO: Отключен --switch. Откуда брать пути к базам? Их должно быть неограниченное количество. 
С+o (open base) - диалог open file - для добавления (новых) и просмотра старых баз. При сохранении, имя базы пишется в конфиг. Это можно сделать для текущей базы (отдельное меню base-info, где сказано - сохранена ли она в конфиге, кнопка сохранения).

Переключаемся с помощью drop-down (combo) + С-b
Читаем все имена баз из конфига, добавляем в combo.
При переключении придется вытирать главное окно и загружать всю инфу из другой базы.

Мораль - для возни с базами нужна отдельная ветка. Надо довести до ума Визард и включить обратно --switch, чтобы замержить в master. Уже накопилось коммитов.

-----------------
 get_bn() - создаем новую базу
 insert_bn()  # returns base name - gui выбор имени базы - переделать.

 TODO: Пишем в конфиге дефолтную директорию для баз (по умолчанию - в .config/str/bases) +
 В меню этого не нужно - хотят, пусть в конфиге меняют.
 При запуске проверяем эту директорию. Если ничего нету,

 Пока ничего не перерисовываем (reload), выбрать базу можно только при старте.

 Если баз нет физически, сначала выводим (пустое) меню выбора "доступных баз", с чекбоксами. 
 Кнопка "создать новую базу". Создаем новую базу с именем, данным юзером и помещаем ее в диру для баз, сразу помечаяем как рабочую в конфиге? - Спросить надо!
 Если в конфиге нет списка рабочих баз - то же самое меню
 Если есть рабочие базы и они есть физически (проверяем), то открываем меню "рабочих баз".

 Если базы есть, но в конфиге нет списка "рабочих баз" (которые отображаются в меню выбора базы) - 
 Выводим меню выбора из "доступных баз". Здесь можно в чекбоксах отметить базы,
 которые будут загружаться в меню выбора по умолчанию - "рабочие базы".
 то же меню, только без чекбоксов. Чтобы изменить набор - спец кнопка,
 при нажатии должны появляться чекбоксы и "доступные базы".
 Пишем отмеченные базы в список дефолтных (конфиг).

 Выбрали "рабочие базы" среди доступных. Пишем в конфиг. 
 Появляется меню "рабочие базы" (без чекбоксов)
 Выбираем базу для загрузки, появляется главное окно. Ффу!

 Заполнение базы данными: 
 Меню для студентов: Хотите ввести данные студентов в ручную?
 Хотите ввести данные из файла? => открываем меню студентов. С+n - новая строка.
 Читать vcf или свой формат (имя, e-mail, телефон, путь к фотографии, активный =0/1).
 разделенные двойным слэшем, дефис для незаполненных полей
            write the path to str directory to config! Check str directory for existing bases
 idea is simple - no more separate addresses for bases in the config. 
 Main programm checks out the STR dir, shows the _default base_ (if set in config)
 Or suggests a choise of the base to show through the menu (if number of bases > 1)
'''
