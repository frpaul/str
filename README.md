# str

Slacker Tracker
----------------

STR is a personal teacher's tool for keeping track of students' grades and attendance.
There are lots of programms like Moodle, big and powerfull. STR is just a simple offline programm
to handle sqlite base with several tables. A future integration with Moodle is a possibility.

First steps:
------------

    Create and fill the base
    -------------------------

    * User has to create a set of text files: student_list.txt, event_list.txt accoring to the default ones.

    * Execute ./str_tools.py -c base_name.db

    * ./str_tools.py -r base_name.db student_list.txt

    * ./str_tools.py -i base_name.db event_list.txt

    * Edit configuration file strrc: insert correct paths to the base(s).


GUI description:
----------------

    Main window:
    -------------

    * Names of the students
    * Various statistics (attendance, avg grade, current grade)
    * Switches N (not present) and L (late) to easily check slackers

    Events window (Ctrl + e)
    ------------------------

    4 views: lections, essays, seminars, tests.

    User may create (ctrl-n), change (Return), delete (ctrl + r) or move (ctrl-d - down) topics.
    This window also used to choose event to grade for (Details).

    Information (Ctrl + u)
    -----------------------

    Browse upcoming events (i.e. lectures)

    Check for lazy students (or assignments not yet checked)

    Details (Return)
    -----------------

    Check grades of the student.

    Grade student for some event.

    Correct grade (or add a comment)

    Attendance (Ctrl + d)
    ---------------------

    Manage attendance (not fully functional)

    Assignments (Ctrl + p)
    -----------------------------------

    * Assigning jobs (tested only for essays):

        1. Call Events dialog (Ctrl-e) -> choose essays in a drop-down menu -> choose some topic, 

        2. pick up students (mulit-selection) to do an essay (Ctrl + m - this pops up short menu, containing students' names)

        3. Ctrl + Return - Selected students' names get to the Assignments menu with their jobs.

        4. Students who didn't hand over their paper (or weren't graded yet) will show up in the Information menu

    * Grading:

        1. set date when student brought in his/her paper.

        2. grade the paper 

        3. graded assignments do not show in the Assignments menu anymore (though they are not deleted from the corresponding base table), but are transfered to the Details menu as ordinary grades


