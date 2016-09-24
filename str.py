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

import ConfigParser
import types
import logging
import datetime
#import uuid
#import gobject

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", filename="students.log", filemode="w", level=logging.INFO)

now = datetime.datetime.now()

global cur_model
#global self.c_group
# temporary list of grades. After 'Save' is pressed list is written into base
global temp_grades # temp_ grades: [g_num, s_num, e_name, e_num, date, float(mark)]
temp_grades = []
# temp list of attendance
global temp_attend # temp_ attend: [a_num, s_num, date, absence, comment] # a_num - hash
temp_attend = []

class Conduit:
    '''Inspect students' attendance and grades, personal info'''

    def __init__(self):

        cur_model = config.get('Settings', 'default_view') # current model used (0 = long sheet, 1 = short)

        self.c_group = config.get('Settings', 'default_c_group')

        self.start_dialog_on = bool(int(config.get('Settings', 'start_dialog_on')))

        self.due = config.get('Settings', 'essays_due_time')  # Time for delivering essays 2 weeks.

        # get time
#        self.date = now.strftime("%Y-%m-%d")
#        self.date = '2015-09-01'
#        self.date = '2015-09-08'
#        self.date = '2015-12-29'
#        self.date = '2016-01-26'
        self.date = '2016-02-02'
#        self.date = '2016-02-09'
#        self.date = '2016-02-16'

        self.ev_names = ['lectures', 'essays', 'seminars', 'tests']

#        self.find_number = re.compile(u'^\d.*', re.U) # find if new_text is mark

        self.new_gr = False # There is a new grade in Details (not in temp_grades yet)
        self.new_ev = False # There is a new event in Events (not in the base yet)

        # get years and current semester
        self.year_ls = self.get_years() # (year1, year2, semester)
        self.semester = self.year_ls[2]

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

    def reload_sh(self):
        '''reload short view'''
        for cc in gstud.tv.get_columns():
            gstud.tv.remove_column(cc)
        gstud.w_model.clear() 

        res_cols = gstud.make_wk_columns() # get columns
        for cc in res_cols:
            gstud.tv.append_column(cc)
        self.ins_wk_main()

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

    def get_years(self):
        dts = self.get_dates()[0]
        year1 = dts.pop(0)[:4]
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

        return (year1, year2, sem)

    def get_dates(self):
        # get from base all unic dates of events AND grades

        # TODO: add all other events (tests, essays)

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
        cur.execute('select date from grades')
        res.extend(cur.fetchall())
        
        cur.close()

#        out = res[0].sort()
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

        cur.close()
       
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
        tail = ''
        if self.semester == 1:
            tail = " and essays.date < '2016'"
        elif self.semester == 2:
            tail = " and essays.date > '2015'"

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
        tail = ''
        if self.semester == 1:
            tail = " and date < '2016'"
        elif self.semester == 2:
            tail = " and date > '2015'"

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
            print dd, dates[dd][1]
            print 'sem', self.semester

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

    def ins_wk_main(self):
        '''isert info into columnts in Viewer'''
        #(int, str, 'gboolean', str, str, str, 'gboolean', 'gboolean', float) 
        # s_num, s_name, Absent(st), Late(st), Avg(st), Absent, Late, Grade

        cm = 'select s_num, s_name, active from students'
        full_st_l = self.exec_sql(cm)

        res = []

######## Define tail for SQL command #########
        if self.semester == 2:
            tail = ' and date like "' + self.year_ls[1] + '%"'
#            print 'tail', tail
        elif self.semester == 1:
            tail = ' and date like "' + self.year_ls[0] + '%"'
#            print 'tail', tail
        else:
            tail = ''
#            print 'tail', tail

        for s_n, s_name, act in full_st_l:
            c_res = []
            s_num = str(s_n)
            if act == '0':
                stud_color = True
            else:
                stud_color = False

            iter = self.w_model.append()

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
            self.w_model.set(*c_res)

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
        cur.execute('select grades.s_num, s_name, mark, date, event from grades join students on grades.s_num=students.s_num')

        # graded - list of all grades (separately)
        graded = cur.fetchall()

        cols = self.get_dates()[2]
#        print 'cols', cols

        # std_l - list of data (including all grades) for each student: 
        # (s_num, s_name, [(column, grade) # - list of tuples with student's grades,...])
        std_l = []
        cc = 0

        ### get date-columns, get all marks and corresponding columns for every student
        for i in graded:
            sw = 0
            cnt = 1                

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
#                    logging.info('student %s, tail %s', st, tmp)
                    # вставляем отсутствующих (True/False)
                    while tmp:
                        res_ls.extend(tmp.popitem()) # be careful! get keyerror if tmp is empty
            self.model.set(*res_ls)
        cur.close()

    def change_wk_model(self):
        ''' change working model for main window '''
        pass
        # remove columns, insert, set other model

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
            self.date = '2016-01-26'
#            self.date = now.strftime("%Y-%m-%d") # TODO: show stuff for today time
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

            model = self.aa_model
            vals = []
            for i in range(len(model)):
                itr = model.get_iter(i)
#                v = model.get(itr, 0, 3, 5, 6) # a_num, delivered(date), mark and comment
                v = model.get(itr, 0, 1, 2, 3, 4, 5, 6) # a_num, s_name, topic, delivered(date), date, mark and comment
                vals.append(v)
#            print vals
            if self.rem_confirm('Save data?'):
#                for v in vals:
                for vv in range(len(vals)):
                    v = vals[vv]

                    a_num = v[0]
                    s_name = v[1]
                    top = v[2]
                    dl = v[3]
                    dt = v[4]
                    mk = v[5]
                    cmt = v[6]
                    # grades: (g_num TEXT, s_num INTEGER, e_name TEXT, e_num INT, date TEXT, mark REAL, comment TEXT)"
                    if mk:
                        e_id = self.exec_sql("select e_id from essays where topic='" + top + "'")[0][0]
                        s_num = self.exec_sql("select s_num from students where s_name='" + s_name + "'")[0][0]
                        s_num = int(s_num)
                        e_id = int(e_id)

#                        print a_num, s_num, e_id, dt, mk, cmt
#                        print type(a_num), type(s_num), type(e_id), type(dt), type(mk), type(cmt)
                        if cmt:
                            cmt = cmt.decode('utf-8')
                        cm = "insert into grades (g_num, s_num, e_name, e_num, date, mark, comment) values (?,?,?,?,?,?,?)"
                                        # text, int, text, int, text, real, text
                        self.exec_sql(cm, [a_num, s_num, 'essays', e_id, dt, mk, cmt])

#                        cm = "delete from assignments where a_num='" + a_num + "'" # let it be there, just in case...
                        if cmt:
                            cmt = "'" + cmt + "'"
                        else:
                            cmt = 'NULL'
                        cm = "update assignments set mark=" + mk + ", comment=" + cmt + " where a_num='" + a_num + "'"
                        self.exec_sql(cm)

                        model.remove(model.get_iter(vv))
# в update странность: надо ставить кавычки у литералов, а NULL - без кавычек (просто '' не прокатывает)
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
        self.aa_model.set(iter_cur, col, new_text) # нужны кавыки, иначе не жрет

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
        ''' callback for Grader() button 'Event' - choose event '''
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

    def make_new_en(self, model):            
        ''' Make new entry for Details() '''

        self.new_gr = True # entry was just created (but not saved even to temp_grades)

        for tab in ['lectures', 'seminars']:
            # ищем актуальную лекцию, или семинар (на сегодняшний день) #TODO: а надо на прошлый раз!
            # lectures, seminars: e_id, date, topic , comment)"
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
        new_iter = model.append(['', '', self.date, ev, top, None, False])
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

        g_temp_ls = [] # list of temporary marks (not in the base)

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

                cm = 'select topic from ' + e_name + ' where e_id="' + str(e_num) + '"' 
                event_l = self.exec_sql(cm)[0]
                res.append([line[0], line[5], line[2], e_word, event_l[0], True, 0]) # g_num, mark, date, event (full), topic, saved, index
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
#                val = model.get_value(itr, 0) # s_num
                s_num = model.get_value(itr, 0) # s_num
        # assignments (a_num TEXT, s_num INTEGER, e_id INTEGER, delivered TEXT, date TEXT, mark REAL, comment TEXT)'
#                out.append([str(uuid.uuid4())[:8], s_num, e_id, None, self.date, None, None])
                out.append([str(uuid.uuid4())[:8], s_num, e_id, self.date])
#            print out
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

                if model.get_value(iter_v, 5):
                    print 'remove from base'
                    command = 'delete from grades where g_num="' + str(g_num) + '"'
                    self.exec_sql(command)
                    model.remove(iter_v)
                else:
                    print 'remove from list'
                    temp_grades.pop(model.get_value(iter_v, 6))
                    model.remove(iter_v)
# TODO: remove mark from short view also

    def fix_absence_cb(self, widget, event, s_num):
        '''callback for Details correcting list of grades, 
           making new entries, etc.
        '''

        keyname = gtk.gdk.keyval_name(event.keyval)
        
        if (keyname == "n" or keyname == "Cyrillic_te") and event.state & gtk.gdk.CONTROL_MASK: 
            # make a new entry 
            model = self.g_tv.get_model()
            print 'you hadn\'t done this one yet'

            # make a new entry (mark is empty)
#            self.make_new_en(model)

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

            if model.get_value(iter_v, 5):
                print 'remove from base'
                command = 'delete from attendance where a_num="' + str(vals[0]) + '"'
                self.exec_sql(command)
                model.remove(iter_v)
                iter_m = gstud.w_model.get_iter(s_num - 1)
                gstud.w_model.set_value(iter_m, 6, False)
                gstud.w_model.set_value(iter_m, 7, False)
            else:
                print 'remove from list'
                for t in range(len(temp_attend)):
                    if temp_attend[t][0] == vals[0]:
                        temp_attend.pop(t)
                        model.remove(iter_v)

    def edit_attend(self, cell, path, new_text, s_num):
        self.mod_a[path][4] = new_text # вставили новую оценку в TV
        iter_v = self.mod_a.get_iter(path)

        vals = []
        for i in range(6):
            at = self.mod_a.get_value(iter_v, i) # s_num instead of s_name
            vals.append(at)
 
        if vals[5]: # saved
            # save to base
            command = 'update attendance set comment="' + new_text + '" where a_num="' + vals[0] + '"'
            self.exec_sql(command)
        else:
            print 'gonna change temp_attend'
            for i in range(len(temp_attend)):

                if temp_attend[i][0] == vals[0]:
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

    def edit_grade(self, cell, path, new_text, s_num):
        ''' callback for Details - editing grade column '''

        #  mod_g: g_num, grade, date, event (full), topic, comment, saved
        # edit only mark, if you're not happy with the rest, better remove all grade, and start over
        self.mod_g[path][1] = new_text # вставили новую оценку в TV
        iter_v = self.mod_g.get_iter(path)
        vals = []
        for i in range(6):
            gr = self.mod_g.get_value(iter_v, i) # s_num instead of s_name
            vals.append(gr)
#            print 'gr', gr
        e_ls = vals[3].split()

        if self.new_gr:  # entry was just created (but not saved even to temp_grades)
            # s_num, e_name, e_num, date, mark, comment=None

            r_mark = self.check_old_grades(s_num, e_ls[0], e_ls[1], vals[2], vals[1])

            itr = gstud.w_model.get_iter(s_num - 1)

            if r_mark:
                temp_grades.append([str(uuid.uuid4())[:8], s_num, e_ls[0], e_ls[1], vals[2], vals[1], vals[5]]) 
                gstud.w_model.set_value(itr, 8, r_mark)

                self.new_gr = False
            else:
                self.mod_g[path][1] = '' # вставили новую оценку в TV

        else: # editing old entries

#            if self.mod_g.get_value(iter_v, 4):
            if vals[5]: # saved - оценка записана в базу, правим прямо там
                print 'changing the base'
                command = 'update grades set mark=' + new_text + ' where g_num="' + str(vals[0]) + '"'
#                print command
                self.exec_sql(command)

            else: # оценка - в temp_grades, а не в базе
                print 'changing temp list'
                for i in range(len(temp_grades)):
                    if temp_grades[i][0] == vals[0]:
                        temp_grades[i][5] = new_text # глюк здесь?

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
            self.save_event()
        # TODO: влазит что-то и "n" при правке текста выдает новую запись c+n
        # Почему не работает ctrl_mask? OR неправильный, олух.

        elif (keyname == "m" or keyname == "Cyrillic_softsign") and event.state & gtk.gdk.CONTROL_MASK: 
#            self.combo.get_active() # essays, obviously. Then block it for other events
#            self.selection
            model, paths = self.selection.get_selected_rows()  # 0 - filter (model) object, 1 - list of tuples [(2,), (3,)...]
            if paths:
                Choose_students(paths[0][0] + 1)
            else:
                Popup('Choose some topic, please')

        elif (keyname == "d" or keyname == "Cyrillic_ve") and event.state & gtk.gdk.CONTROL_MASK: 
            self.topic_down()

    def topic_down(self):
        '''Move topics below the current, one position (date) down'''
        
        model, paths = self.selection.get_selected_rows()  # 0 - filter (model) object, 1 - list of tuples [(2,), (3,)...]
#        rows = model.get_n_columns()
        new_top = ''

        # move topics down 1 step in a model:
        while True:
            if new_top:
                new_itr = model.iter_next(itr)
                if new_itr:
                    old_top = model.get_value(new_itr, 2)
                    print old_top.encode('utf-8')
                    model.set(new_itr, 2, new_top)
                    new_top = old_top
                    itr = new_itr
                else:
                    break
            else:
                # 0 cycle. Topic is left empty, for I missed that day.
                itr = model.get_iter(paths[0][0])
                print 'path, itr', paths[0][0], itr
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
        if self.rem_confirm('Save new event list?'):
            e_name = self.combo.get_active_text() 
            for n in range(len(model)):
                vals = model.get(model.get_iter(n), 0, 1, 2, 3) # make separate for essays
                if e_name == 'essays':
                    print 'make new essay, delete old, don\'t be lazy'
#                    enddate = self.get_enddate(vals[1])
#                    comm = "update lectures set topic='" + vals[2] + "', comment='" + vals[3] + "' where e_id='" + str(vals[0]) + "'"
                else:
                    comm = "update lectures set topic='" + vals[2] + "', comment='" + vals[3] + "' where e_id='" + str(vals[0]) + "'"
                    print comm
                    self.exec_sql(comm)
        # TODO: Складывать "лишние темы", получившиеся в результате пропусков, в отдельный файл (или таблицу), чтобы можно было вклеить их обратно (напр. в уже существующий лекционный день)

    def save_event(self):
        '''save new entry in Events() to base'''
        # get new info:
        model = self.e_tv.get_model()
        n = model.get_n_columns()
        itr = model.get_iter(n - 1)
        cc = []
        for i in range(n):
            cc.append[i]
        print model.get(itr, *cc)

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

    def get_avg(self, s_num):
        ''' get average mark/mark cout '''

######## Define tail for SQL command #########
        if self.semester == 2:
            tail = ' and date like "' + self.year_ls[1] + '%"'
#            print 'tail', tail
        elif self.semester == 1:
            tail = ' and date like "' + self.year_ls[0] + '%"'
#            print 'tail', tail
        else:
            tail = ''

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

        if b_name:
            base_p = b_name
        else:
            print 'no b_name, using old b_name'
            home = os.path.expanduser('~')
            base_p = os.path.join(home, 'svncod/trunk/student_base_01.db')
        conn = sqlite3.connect(base_p)
        
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
                self.mod_g.set(iter, 0, ln[0], 1, ln[1], 2, ln[2], 3, ln[3], 4, ln[4], 5, ln[5], 6, ln[5])
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

#        c1 = gtk.gdk.Color('#6ef36e')#67cef9
        c1 = gtk.gdk.Color('#67cef9')#
        cell1.set_property('font', 'FreeSans 12')
        cell1.set_property('cell-background', c1)  # blue for saved entries
        cell1.set_property('editable', True)       
        cell1.connect('edited', self.edit_grade, s_num) 
        cell2.set_property('font', 'FreeSans 12')
        cell3.set_property('font', 'FreeSans 12')
        cell4.set_property('font', 'FreeSans 12')

        self.column1 = gtk.TreeViewColumn("grade", cell1)
        self.column1.set_attributes(cell1, text=1, cell_background_set=6) # blue for saved entries
        self.column2 = gtk.TreeViewColumn("date", cell2, text=2)
        self.column3 = gtk.TreeViewColumn("event", cell3, text=3)
        self.column4 = gtk.TreeViewColumn("topic", cell4, text=4)

        self.g_tv.append_column(self.column1)
        self.g_tv.append_column(self.column2)
        self.g_tv.append_column(self.column3)
        self.g_tv.append_column(self.column4)
#
        g_sw.show_all()
        self.g_tv.show()
        g_label.show()
        window_g.show()

#        self.g_tv.connect('row-activated', self.edit_grade)
        window_g.connect('key_press_event', self.fix_grades_cb, s_num)
        self.g_tv.connect('row-activated', self.open_ev)

        # TODO: make "if" for essays (start and enddates wont show yet)

class Attendance(Conduit):
    ''' GUI for showing grades of a student at a given date (small grades menu) '''

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
        cell4.set_property('font', 'FreeSans 12')
        cell4.set_property('editable', True)       
        cell4.connect('edited', self.edit_attend, s_num)  # , 4) # это номер колонки

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
            column5 = gtk.TreeViewColumn('deadline', cell5, text=2) 
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

    def __init__(self):
        Conduit.__init__(self)


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
        self.ins_wk_main()

        self.modelfilter = self.w_model.filter_new()
        self.modelfilter.set_visible_func(self.vis) # visible function call
        # make cols in model
######### model for 'long view' ##########
#        strs = [int, str, 'gboolean']
#        for i in range(0, (self.len_d * 2), 2): # 3 for s_num, s_name and current date on end
#            strs.append(str) # set types for text column
#            strs.append('gboolean') # set types for color column
#
##        logging.info('strs %s', len(strs)) # количество столбцов в модели
#        # model for 'regular view'
#        self.model = gtk.ListStore(*strs) # method to create dynamic model
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
        l_text = (os.path.basename(b_name).split('_')[0] + ' year').upper() + '    Date: ' + self.date
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

#        self.ins_main()

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

        cell1 = gtk.CellRendererText()
        cell1.set_property('font', 'FreeSans 12')
        self.column1 = gtk.TreeViewColumn('s_num', cell1, text=0) 
        self.tv.append_column(self.column1)


        cell2 = gtk.CellRendererText()
        cell2.set_property('font', 'FreeSans 12')
        cell2.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
        self.column2 = gtk.TreeViewColumn('student', cell2, text=1) 
        self.column2.set_sort_column_id(1)
        self.tv.append_column(self.column2)

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
            
            self.column = gtk.TreeViewColumn(date_ls[cnt].strftime("%d-%m-%Y"), cell)
            self.column.set_attributes(cell, text=i, cell_background_set=(i+1))

            self.tv.append_column(self.column)

            cnt += 1 

        self.tv.connect('row-activated', self.on_click)

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
#        self.title = ""
        self.text = text
        dialog = gtk.Dialog(title='warning')
        label = gtk.Label(self.text)
        dialog.vbox.pack_start(label, True, True, 10)
        label.show()
        dialog.show()


def main():
    gtk.main()
    return 0

if __name__ == '__main__':

################# Options ###########


    global b_name

    from optparse import OptionParser
    usage = "usage: %prog [options] filename"
    parser = OptionParser(usage=usage)

    parser.add_option("-s", "--switch", dest="switch", action="store", help="Switch between bases 1 and 2")
    parser.add_option("-c", "--config", dest="config", action="store", help="Get config from path")
    (options, args) = parser.parse_args()

    if options.config: # for debugging (alternative paths and stuff)
        c_path = options.config
    else:
        c_path = os.path.join(os.path.expanduser('~'), '.config', 'studentus', 'studrc')

    config = ConfigParser.ConfigParser()
    config.read(c_path)

    if options.switch:
        if options.switch == '1':
            b_name = config.get('Paths', 'stud_path1')
        elif options.switch == '2':
            b_name = config.get('Paths', 'stud_path2')
        gstud = Viewer()
    else:
        print "no options given, exiting"
        sys.exit(0)
    main()

# TODO: В Events ставим курсор на текущую дату (если есть) или в начало списка, если нету
# TODO: В Events приделать нормальное ctrl+n - добавление события (напр. тесты, эссе!) - тестить!
# TODO: make checkbox delete absence record (+popup)
# TODO: Details: общий GUI switch between Grades, Attendance, Assignments, Notes(?)
# TODO: Details: Сделать комментарии к оценкам: в Details - колонку, в edited_g... - добавить опцию
# TODO: Details: Надо ставить по умолчанию не текущее событие, а предыдущее (за которое обычно и ставится оценка)
# TODO: Редактирование поля L/N в Attendance.
# TODO: show student's picture, so you know, to whom you gave F-
# TODO: Глюк: при исправлении старой оценки вылазит Popup "this student already had a grade..."
# Не очень актуально: SQL Errors go to status bar (others too), (gtk.Statusbar), log
# Сделать окошко для всех temp_grades ? В принципе, может пригодиться
# TODO: Information(): Тестить: сдача эссе подоспела
# TODO: Выводить в Info все актуальные Notes.
# TODO: Перенести часть опций из str_tools (-c, -i, -r...)
# TODO:
# TODO: 
# TODO:
# TODO:
# TODO:
# TODO: 
# TODO: 