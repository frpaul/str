#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""модуль для записи информации в файл. Два первых аргумента - обязательны.
Аргументы: 1 имя файла (куда писать), 2 список со строками, 3 параметр записи
4 кодировка """

class write_gen:
    def write_file(self, f_name, data, mode='w', enc='utf8'):
        utf = open(f_name, mode)
        for x in data:
        # TODO: add x = x.decode('utf8') and fix all programms, using this module
            utf.write(x.encode(enc))
        print 'writing ', f_name
        utf.close() 
    def write_line(self, f_name, data, mode='w', enc='utf8'):
        utf = open(f_name, mode)
        # TODO: add x = x.decode('utf8')
        utf.write(data[0].encode(enc))
        print 'writing ', f_name
        utf.close() 



