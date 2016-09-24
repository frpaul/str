# str

Slacker Tracker
----------------

STR is a personal teacher's tool for keeping track of students' grades and attendance.
There are lots of programms like Moodle, big and powerfull. STR is just a simple offline programm
to handle sqlite base with several tables. A future integration with Moodle is a possibility.

Features:

Main window:
-------------

* Names of the students
* Various statistics (attendance, avg grade, current grade)
* Fields N (not present) and L (late) to easily check slackers

Events window (Ctrl + e)
------------------------

4 views: lections, essays, seminars, tests.

User may create (ctrl-n), change (Return), delete (ctrl + r) or move (ctrl-d - down) topics.
This window also used to choose event to grade for.

Information (Ctrl + u)
-----------------------

Look up coming events (i.e. lectures)

Check for lazy students (or assignments not yet checked)

Details (Return)
-----------------

Check grades of the student.

Grade student for some event.

Correct grade (or add a comment)

Attendance (Ctrl + d)
---------------------

Manage attendance (not fully functional)

Assignments - purgatory (Ctrl + p)
-----------------------------------

* Assigning jobs:

1. choose Events -> essays -> some topic, 

2. pick up students to do an essay (Ctrl + m - this pops up short students' menu)

3. Ctrl + Return - Selected students get to the Assignments menu with new jobs-

4. Students who didn't finish work (or weren't graded yet) will show up in Information menu

* Grading:

1. set date when student brought in his/her paper.

2. grade the paper 

3. graded assignments do not show in the Assignments menu anymore (though they are not deleted from the corresponding base table), but show up in Details menu as ordinary grades

Create and fill the base
-------------------------

* User has to create a set of text files: student_list.txt, event_list.txt accoring to the default ones.

* Execute ./str_tools.py -c base_name.db

* ./str_tools.py -i student_list.txt

* ./str_tools.py -r event_list.txt
